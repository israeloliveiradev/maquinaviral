import asyncio
import json
import logging
from pathlib import Path
from typing import Callable, Awaitable, Optional, Dict, Any

from src.core.config import settings
from src.core.exceptions import FFprobeError, FFmpegExecutionError
from src.domain.models import CropCoordinates, OverlayLayout

logger = logging.getLogger(__name__)


class FFmpegRenderer:
    def __init__(
        self,
        ffmpeg_path: str = settings.FFMPEG_PATH,
        ffprobe_path: str = settings.FFPROBE_PATH,
    ):
        self.ffmpeg_path = ffmpeg_path
        self.ffprobe_path = ffprobe_path
        self._cached_codec: Optional[str] = None

    async def detect_best_codec(self) -> str:
        """
        Detects the best available video encoder on the system.
        Performs a short test encode to verify if hardware acceleration (NVENC)
        is actually functional and can initialize, falling back to libx264.
        """
        if self._cached_codec is not None:
            return self._cached_codec

        if settings.VIDEO_CODEC != "auto":
            self._cached_codec = settings.VIDEO_CODEC
            return self._cached_codec

        logger.info("Probing GPU hardware acceleration capability...")
        
        # Test NVENC functionality by encoding a 0.1s dummy canvas
        test_cmd = [
            self.ffmpeg_path,
            "-y",
            "-f", "lavfi",
            "-i", "color=c=black:s=64x64:d=0.1",
            "-c:v", "h264_nvenc",
            "-f", "null",
            "-"
        ]
        
        try:
            process = await asyncio.create_subprocess_exec(
                *test_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await process.communicate()
            
            if process.returncode == 0:
                logger.info("NVIDIA NVENC hardware acceleration is verified and active.")
                self._cached_codec = "h264_nvenc"
            else:
                logger.info("NVIDIA NVENC test failed (driver or hardware missing). Using libx264 (CPU).")
                self._cached_codec = "libx264"
        except Exception as e:
            logger.warning(f"Error testing NVENC encoder: {e}. Falling back to libx264 (CPU).")
            self._cached_codec = "libx264"

        return self._cached_codec

    async def get_media_metadata(self, file_path: str) -> Dict[str, Any]:
        """
        Queries file dimensions, duration, FPS and audio details using ffprobe.
        """
        cmd = [
            self.ffprobe_path,
            "-v", "error",
            "-show_entries", "format=duration:stream=width,height,r_frame_rate,codec_type",
            "-of", "json",
            file_path
        ]
        
        logger.debug(f"Probing file: {file_path}")
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                raise FFprobeError(f"Failed to probe {file_path}: {stderr.decode().strip()}")
            
            data = json.loads(stdout.decode("utf-8"))
            
            # Format info
            duration = float(data.get("format", {}).get("duration", 0.0))
            
            width = 0
            height = 0
            fps = 30.0
            has_audio = False
            has_video = False
            
            for stream in data.get("streams", []):
                codec_type = stream.get("codec_type")
                if codec_type == "video":
                    has_video = True
                    width = int(stream.get("width", 0))
                    height = int(stream.get("height", 0))
                    r_frame_rate = stream.get("r_frame_rate", "30/1")
                    try:
                        if "/" in r_frame_rate:
                            num, den = map(int, r_frame_rate.split("/"))
                            if den > 0:
                                fps = num / den
                        else:
                            fps = float(r_frame_rate)
                    except Exception:
                        pass
                elif codec_type == "audio":
                    has_audio = True
                    
            return {
                "duration": duration,
                "width": width,
                "height": height,
                "fps": fps,
                "has_audio": has_audio,
                "has_video": has_video
            }
        except Exception as e:
            if not isinstance(e, FFprobeError):
                raise FFprobeError(f"Unexpected error probing {file_path}: {str(e)}") from e
            raise

    async def render_video(
        self,
        video_path: str,
        template_path: str,
        coords: CropCoordinates,
        layout: OverlayLayout,
        output_path: str,
        progress_callback: Callable[[float], Awaitable[None]],
        output_width: Optional[int] = None,
        output_height: Optional[int] = None,
        source_crop: Optional[CropCoordinates] = None,
    ) -> None:
        """
        Executes the video rendering pipeline. Scaled and cropped video combined with
        the template in a single FFmpeg call, reporting progress in real-time.
        Supports custom output dimensions (rescaling background and overlay grids).
        """
        # 1. Fetch metadata for both files
        video_meta = await self.get_media_metadata(video_path)
        template_meta = await self.get_media_metadata(template_path)
        
        duration = video_meta["duration"]
        fps = video_meta["fps"]
        has_audio = video_meta["has_audio"]
        
        # Override template dimensions if custom output size is specified
        w_t = output_width if output_width is not None else template_meta["width"]
        h_t = output_height if output_height is not None else template_meta["height"]
        
        if duration <= 0:
            raise FFmpegExecutionError("Source video duration is zero or invalid.")
        if w_t <= 0 or h_t <= 0:
            raise FFmpegExecutionError("Target canvas dimensions are zero or invalid.")
 
        # 2. Detect best codec
        codec = await self.detect_best_codec()
        
        # 3. Assemble FFmpeg Command
        cmd = [
            self.ffmpeg_path,
            "-y",                   # Overwrite output
            "-progress", "pipe:1",  # Send progress information to stdout
            "-i", video_path,
            "-loop", "1", "-i", template_path  # Loop template image indefinitely
        ]
        
        # Build filter complex
        # A. Scale source video to cover W_v x H_v, crop
        if source_crop:
            scale_video_filter = (
                f"[0:v]crop={source_crop.width}:{source_crop.height}:{source_crop.x}:{source_crop.y}[cropped_v]; "
                f"[cropped_v]scale=w='trunc(max(iw*{coords.height}/ih,{coords.width})/2)*2':"
                f"h='trunc(max(ih*{coords.width}/iw,{coords.height})/2)*2',crop={coords.width}:{coords.height}[vid];"
            )
        else:
            scale_video_filter = (
                f"[0:v]scale=w='trunc(max(iw*{coords.height}/ih,{coords.width})/2)*2':"
                f"h='trunc(max(ih*{coords.width}/iw,{coords.height})/2)*2',crop={coords.width}:{coords.height}[vid];"
            )
        
        # B. Rescale the template to fit the desired output canvas size
        scale_tmpl_filter = f"[1:v]scale={w_t}:{h_t}[scaled_tmpl];"
        
        if layout == OverlayLayout.VIDEO_ON_TOP:
            # Video sits on top of the scaled template background
            filter_complex = (
                scale_video_filter + " " +
                scale_tmpl_filter + " " +
                f"[scaled_tmpl][vid]overlay=x={coords.x}:y={coords.y}:shortest=1[out_v]"
            )
        else:
            # Video sits on a solid color canvas, template frames it on top
            filter_complex = (
                scale_video_filter + " " +
                scale_tmpl_filter + " " +
                f"color=s={w_t}x{h_t}:c=black:r={fps}[bg]; "
                f"[bg][vid]overlay=x={coords.x}:y={coords.y}:shortest=1[bg_vid]; "
                f"[bg_vid][scaled_tmpl]overlay=x=0:y=0:shortest=1[out_v]"
            )
            
        cmd.extend(["-filter_complex", filter_complex])
        
        # Streams mapping
        cmd.extend(["-map", "[out_v]"])
        if has_audio:
            cmd.extend([
                "-map", "0:a",
                "-c:a", "aac",
                "-ar", "48000",
                "-b:a", "192k",
            ])
            
        # Codec-specific settings
        if codec == "h264_nvenc":
            cmd.extend([
                "-c:v", "h264_nvenc",
                "-preset", "p1",
                "-pix_fmt", "yuv420p"
            ])
        elif codec == "h264_vaapi":
            cmd.extend([
                "-c:v", "h264_vaapi",
                "-pix_fmt", "vaapi"
            ])
        else:
            cmd.extend([
                "-c:v", "libx264",
                "-preset", settings.CPU_PRESET,
                "-crf", str(settings.VIDEO_CRF),
                "-pix_fmt", "yuv420p"
            ])
            
        # Target Output File
        cmd.append(output_path)
        
        logger.info(f"Starting FFmpeg process with codec={codec} for output={output_path}")
        logger.debug(f"FFmpeg Command: {' '.join(cmd)}")
        
        # 4. Spawn Asynchronous Subprocess
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        # 5. Read stdout in real-time to track progress
        async def parse_progress():
            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                line_str = line.decode("utf-8").strip()
                if "=" in line_str:
                    key, val = line_str.split("=", 1)
                    key = key.strip()
                    val = val.strip()
                    if key == "out_time_us":
                        try:
                            time_us = int(val)
                            pct = (time_us / 1_000_000) / duration * 100
                            pct = min(max(pct, 0.0), 99.9)
                            await progress_callback(pct)
                        except Exception:
                            pass
                    elif key == "progress" and val == "end":
                        await progress_callback(100.0)

        # 6. Read stderr to capture failure details
        async def capture_stderr():
            stderr_lines = []
            while True:
                line = await process.stderr.readline()
                if not line:
                    break
                line_str = line.decode("utf-8", errors="ignore").strip()
                if line_str:
                    stderr_lines.append(line_str)
                    if len(stderr_lines) > 100:
                        stderr_lines.pop(0)
            return stderr_lines

        progress_task = asyncio.create_task(parse_progress())
        stderr_task = asyncio.create_task(capture_stderr())
        
        # Wait for the subprocess to complete
        return_code = await process.wait()
        
        # Ensure parsing completes
        await progress_task
        stderr_logs = await stderr_task
        
        if return_code != 0:
            error_details = "\n".join(stderr_logs[-10:])
            logger.error(f"FFmpeg failed with exit code {return_code}. Details:\n{error_details}")
            raise FFmpegExecutionError(
                f"FFmpeg execution failed (code {return_code}). Details: {error_details}"
            )
            
        logger.info(f"Render completed successfully: {output_path}")
        await progress_callback(100.0)

    def detect_subject_crop(
        self,
        video_path: str,
        target_width: int,
        target_height: int
    ) -> Optional[CropCoordinates]:
        """
        Analyzes the source video using OpenCV to detect faces and calculate optimal
        crop coordinates to keep the subject centered at the target aspect ratio.
        """
        logger.info(f"Running smart auto-center subject detection on: {video_path}")
        try:
            import cv2
            import numpy as np
        except ImportError:
            logger.warning("OpenCV is not installed. Falling back to default center crop.")
            return None

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            logger.warning(f"Could not open video {video_path} for smart crop probing.")
            return None

        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        if width <= 0 or height <= 0 or frame_count <= 0:
            cap.release()
            return None

        # Load OpenCV Haar cascade for face detection
        # Use cv2.data.haarcascades to locate the file path on the system automatically
        cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        face_cascade = cv2.CascadeClassifier(cascade_path)
        if face_cascade.empty():
            logger.warning("Haar cascade classifier file not found or empty.")
            cap.release()
            return None

        # Sample up to 5 frames throughout the first half of the video (5%, 10%, 20%, 30%, 40%)
        sample_percentages = [0.05, 0.1, 0.2, 0.3, 0.4]
        sample_indices = [int(frame_count * p) for p in sample_percentages]
        sample_indices = [idx for idx in sample_indices if 0 <= idx < frame_count]
        if not sample_indices:
            sample_indices = [0]

        detected_x_centers = []

        for idx in sample_indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ret, frame = cap.read()
            if not ret or frame is None:
                continue

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            # Detect faces with standard parameters
            faces = face_cascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=(60, 60)
            )

            if len(faces) > 0:
                # Select the largest face (assumed to be the main subject)
                largest_face = max(faces, key=lambda rect: rect[2] * rect[3])
                fx, fy, fw, fh = largest_face
                face_x_center = fx + (fw / 2)
                detected_x_centers.append(face_x_center)

        cap.release()

        # Target Aspect Ratio: target_width / target_height
        target_ar = target_width / target_height
        source_ar = width / height

        # Compute crop width and height matching target aspect ratio
        if source_ar > target_ar:
            # Source is wider than target. Crop the width.
            crop_h = height
            crop_w = int(height * target_ar)
        else:
            # Source is taller than target. Crop the height.
            crop_w = width
            crop_h = int(width / target_ar)

        # Force dimensions to be even numbers for FFmpeg compatibility
        crop_w = (crop_w // 2) * 2
        crop_h = (crop_h // 2) * 2

        # Determine optimal X center
        if detected_x_centers:
            # Median center coordinates of detected faces
            optimal_x_center = int(np.median(detected_x_centers))
            logger.info(f"Smart crop: Face detected at center X={optimal_x_center}")
        else:
            # Fallback to physical center
            optimal_x_center = width // 2
            logger.info("Smart crop: No faces detected. Falling back to video center X.")

        # Compute crop_x based on optimal_x_center
        crop_x = optimal_x_center - (crop_w // 2)
        crop_x = max(0, min(width - crop_w, crop_x))

        # Center vertically (default fallback since face y-center can be jittery or cut heads)
        crop_y = (height - crop_h) // 2
        crop_y = max(0, min(height - crop_h, crop_y))

        # Force crop_x and crop_y to even for FFmpeg
        crop_x = (crop_x // 2) * 2
        crop_y = (crop_y // 2) * 2

        logger.info(f"Computed auto-center crop: x={crop_x}, y={crop_y}, w={crop_w}, h={crop_h}")
        return CropCoordinates(x=crop_x, y=crop_y, width=crop_w, height=crop_h)


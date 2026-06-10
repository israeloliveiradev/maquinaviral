import asyncio
import os
from pathlib import Path
import subprocess

from src.services.ffmpeg_renderer import FFmpegRenderer
from src.domain.models import CropCoordinates, OverlayLayout


def generate_test_assets():
    """Generates a sample video and template image using FFmpeg to test offline."""
    print("Generating test assets via FFmpeg...")
    
    # 1. Generate a 5-second test video (640x360, 30fps) with a 1kHz audio beep
    video_cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "testsrc=size=640x360:rate=30",
        "-f", "lavfi", "-i", "sine=frequency=1000:sample_rate=48000",
        "-t", "5",
        "-c:v", "libx264",
        "-c:a", "aac",
        "-pix_fmt", "yuv420p",
        "sample_video.mp4"
    ]
    
    # 2. Generate a template image (1280x720 blue canvas with a transparent/translucent border)
    # We can create a simple solid color PNG image using ffmpeg
    template_cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "color=c=blue:s=1280x720:d=1,format=rgba",
        "-vf", "drawbox=x=100:y=100:w=400:h=400:color=black@0:t=fill,drawbox=x=166:y=172:w=948:h=375:color=black@0:t=fill",
        "-vframes", "1",
        "sample_template.png"
    ]
    
    print(f"Running video generator: {' '.join(video_cmd)}")
    subprocess.run(video_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    print(f"Running template generator: {' '.join(template_cmd)}")
    subprocess.run(template_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    print("Assets generated successfully: sample_video.mp4, sample_template.png\n")


async def progress_tracker(pct: float):
    print(f"[Render Progress] {pct:.2f}%")


async def main():
    # 1. Generate assets if they don't exist
    if not os.path.exists("sample_video.mp4") or not os.path.exists("sample_template.png"):
        generate_test_assets()
        
    # 2. Setup paths
    video_path = "sample_video.mp4"
    template_path = "sample_template.png"
    output_path = "test_output.mp4"
    
    # Coordinates: position scaled video at X=100, Y=100 with Width=400, Height=400
    coords = CropCoordinates(x=100, y=100, width=400, height=400)
    layout = OverlayLayout.TEMPLATE_ON_TOP
    
    # 3. Instantiate Renderer
    renderer = FFmpegRenderer()
    
    # 4. Probe input details
    print("--- Probing video metadata ---")
    video_meta = await renderer.get_media_metadata(video_path)
    print(f"Video format metadata: {video_meta}")
    
    print("\n--- Probing template metadata ---")
    template_meta = await renderer.get_media_metadata(template_path)
    print(f"Template format metadata: {template_meta}")
    
    # 5. Run Render (Horizontal 16:9)
    print("\n--- Starting Rendering Process (Horizontal 1280x720) ---")
    try:
        await renderer.render_video(
            video_path=video_path,
            template_path=template_path,
            coords=coords,
            layout=layout,
            output_path=output_path,
            progress_callback=progress_tracker
        )
        print("\n--- Horizontal rendering finished successfully! ---")
        
        # Probe output to check results
        output_meta = await renderer.get_media_metadata(output_path)
        print(f"Rendered Horizontal Output Metadata: {output_meta}")
        print(f"Horizontal Output saved to: {Path(output_path).resolve()}")
        
        # 6. Run Render (Vertical 9:16 - 1080x1920)
        print("\n--- Starting Rendering Process 2 (Vertical 1080x1920) ---")
        output_path_vertical = "test_output_vertical.mp4"
        coords_vertical = CropCoordinates(x=140, y=460, width=800, height=1000)
        await renderer.render_video(
            video_path=video_path,
            template_path=template_path,
            coords=coords_vertical,
            layout=layout,
            output_path=output_path_vertical,
            progress_callback=progress_tracker,
            output_width=1080,
            output_height=1920
        )
        print("\n--- Vertical rendering finished successfully! ---")
        
        # Probe output to check results
        output_meta_vertical = await renderer.get_media_metadata(output_path_vertical)
        print(f"Rendered Vertical Output Metadata: {output_meta_vertical}")
        print(f"Vertical Output saved to: {Path(output_path_vertical).resolve()}")
        
    except Exception as e:
        print(f"\n[Error] Rendering failed: {e}")


if __name__ == "__main__":
    # Add project root to path just in case
    import sys
    sys.path.append(os.path.abspath(os.path.dirname(__file__)))
    
    asyncio.run(main())

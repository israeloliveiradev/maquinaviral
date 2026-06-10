import asyncio
import datetime
import logging
from pathlib import Path
from typing import Optional
import httpx

from src.core.config import settings
from src.core.exceptions import DownloadError
from src.domain.models import CropCoordinates, OverlayLayout, TaskStatus
from src.infrastructure.queue.celery_app import celery_app
from src.infrastructure.storage.redis_client import RedisClient
from src.services.ffmpeg_renderer import FFmpegRenderer

logger = logging.getLogger(__name__)


async def download_file(url: str, dest_path: Path) -> None:
    """Downloads a file asynchronously using streaming HTTPX."""
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    logger.info(f"Downloading file from {url} to {dest_path}")
    
    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            async with client.stream("GET", url, follow_redirects=True) as response:
                if response.status_code != 200:
                    raise DownloadError(f"HTTP error {response.status_code} requesting resource.")
                
                # Write file block by block to prevent memory spikes
                with open(dest_path, "wb") as f:
                    async for chunk in response.aiter_bytes(chunk_size=65536):
                        f.write(chunk)
        logger.info(f"Finished downloading {url}")
    except Exception as e:
        if dest_path.exists():
            try:
                dest_path.unlink()
            except OSError:
                pass
        if isinstance(e, DownloadError):
            raise
        raise DownloadError(f"Failed to download media file from {url}: {e}") from e


async def execute_task_pipeline(
    batch_id: str,
    task_id: str,
    template_id: str,
    coords_dict: dict,
    source_crop_dict: Optional[dict],
    layout_val: str,
    video_source: str,
    output_width: Optional[int] = None,
    output_height: Optional[int] = None,
    smart_crop: bool = False,
) -> str:
    """
    Executes the task processing pipeline:
    1. Downloads video from URL (if applicable).
    2. Probes video duration.
    3. Runs FFmpeg renderer.
    4. Automatically cleans up temp files.
    """
    redis_client = RedisClient()
    renderer = FFmpegRenderer()
    
    now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
    await redis_client.update_task_progress(
        batch_id=batch_id,
        task_id=task_id,
        status=TaskStatus.DOWNLOADING,
        progress=0.0,
        started_at=now_str
    )
    
    local_video_path: Optional[Path] = None
    temp_template_path: Optional[Path] = None
    
    try:
        # Parse inputs
        coords = CropCoordinates(**coords_dict)
        source_crop = CropCoordinates(**source_crop_dict) if source_crop_dict else None
        layout = OverlayLayout(layout_val)
        
        # 1. Resolve source video path (local or download from URL)
        if video_source.startswith(("http://", "https://")):
            # Create a unique temp file name
            file_ext = Path(video_source.split("?")[0]).suffix or ".mp4"
            local_video_path = settings.TEMP_DIR / f"vid_{task_id}{file_ext}"
            await download_file(video_source, local_video_path)
        else:
            local_video_path = Path(video_source)
            if not local_video_path.exists():
                raise FileNotFoundError(f"Local video file not found: {video_source}")

        # 2. Resolve Template path
        local_template_path = Path(template_id)
        if not local_template_path.exists():
            # Try searching in templates directory
            local_template_path = settings.TEMPLATES_DIR / template_id
            if not local_template_path.exists():
                # If template is a URL, download it!
                if template_id.startswith(("http://", "https://")):
                    file_ext = Path(template_id.split("?")[0]).suffix or ".png"
                    temp_template_path = settings.TEMP_DIR / f"tmpl_{task_id}{file_ext}"
                    await download_file(template_id, temp_template_path)
                    local_template_path = temp_template_path
                else:
                    raise FileNotFoundError(f"Template path '{template_id}' could not be resolved.")

        # 3. Create output path
        output_dir = settings.STORAGE_DIR / batch_id
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{task_id}.mp4"

        # 4. Probe the video properties
        await redis_client.update_task_progress(
            batch_id=batch_id,
            task_id=task_id,
            status=TaskStatus.PROBING,
            progress=0.0
        )
        
        # This will fail fast if the file is corrupted or not a valid video
        await renderer.get_media_metadata(str(local_video_path))

        # 4B. Run smart auto-center subject detection if enabled and no manual crop is set
        if not source_crop and smart_crop:
            await redis_client.update_task_progress(
                batch_id=batch_id,
                task_id=task_id,
                status=TaskStatus.PROBING,
                progress=50.0
            )
            detected_crop = await asyncio.to_thread(
                renderer.detect_subject_crop,
                str(local_video_path),
                coords.width,
                coords.height
            )
            if detected_crop:
                source_crop = detected_crop

        # 5. Define progress callback
        async def progress_callback(pct: float):
            await redis_client.update_task_progress(
                batch_id=batch_id,
                task_id=task_id,
                status=TaskStatus.RENDERING,
                progress=pct
            )

        # 6. Execute FFmpeg Rendering
        await renderer.render_video(
            video_path=str(local_video_path),
            template_path=str(local_template_path),
            coords=coords,
            source_crop=source_crop,
            layout=layout,
            output_path=str(output_path),
            progress_callback=progress_callback,
            output_width=output_width,
            output_height=output_height
        )
        
        # 7. Complete Task
        complete_time_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
        await redis_client.update_task_progress(
            batch_id=batch_id,
            task_id=task_id,
            status=TaskStatus.COMPLETED,
            progress=100.0,
            output_path=str(output_path),
            completed_at=complete_time_str
        )
        
        return str(output_path)
        
    except Exception as e:
        logger.exception(f"Error executing task pipeline for Task={task_id}")
        fail_time_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
        await redis_client.update_task_progress(
            batch_id=batch_id,
            task_id=task_id,
            status=TaskStatus.FAILED,
            progress=0.0,
            error=str(e),
            completed_at=fail_time_str
        )
        raise
        
    finally:
        # Clean up temporary downloads
        # Note: we use redis client closure in task scope to ensure clean socket closures
        await redis_client.close()
        
        if local_video_path and video_source.startswith(("http://", "https://")):
            try:
                if local_video_path.exists():
                    local_video_path.unlink()
                    logger.info(f"Cleaned up temp video download: {local_video_path}")
            except OSError as ex:
                logger.error(f"Error cleaning up temporary file {local_video_path}: {ex}")
                
        if temp_template_path:
            try:
                if temp_template_path.exists():
                    temp_template_path.unlink()
                    logger.info(f"Cleaned up temp template download: {temp_template_path}")
            except OSError as ex:
                logger.error(f"Error cleaning up temporary file {temp_template_path}: {ex}")


@celery_app.task(name="src.infrastructure.queue.tasks.process_video_task", bind=True)
def process_video_task(
    self,
    batch_id: str,
    task_id: str,
    template_id: str,
    coords_dict: dict,
    source_crop_dict: Optional[dict],
    layout_val: str,
    video_source: str,
    output_width: Optional[int] = None,
    output_height: Optional[int] = None,
    smart_crop: bool = False,
) -> str:
    """Celery task entry point wrapper executing the async pipeline."""
    return asyncio.run(
        execute_task_pipeline(
            batch_id=batch_id,
            task_id=task_id,
            template_id=template_id,
            coords_dict=coords_dict,
            source_crop_dict=source_crop_dict,
            layout_val=layout_val,
            video_source=video_source,
            output_width=output_width,
            output_height=output_height,
            smart_crop=smart_crop,
        )
    )

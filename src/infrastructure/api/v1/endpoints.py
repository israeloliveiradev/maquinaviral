from fastapi import APIRouter, HTTPException, status, UploadFile, File

from src.core.exceptions import BatchNotFoundError
from src.infrastructure.api.v1.schemas import (
    BatchCreateRequest,
    BatchCreateResponse,
    BatchStatusResponse,
)
from src.services.batch_orchestrator import BatchOrchestrator

router = APIRouter(prefix="/render", tags=["Render Orchestrator"])


@router.post(
    "/batch",
    response_model=BatchCreateResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Enqueue a batch of videos to render",
    description="Validates dimensions, registers a batch, and starts parallel rendering in background worker threads."
)
async def create_batch(payload: BatchCreateRequest):
    orchestrator = BatchOrchestrator()
    try:
        batch_id = await orchestrator.create_batch(
            template_id=payload.template_id,
            coords=payload.crop_coordinates,
            source_crop=payload.source_crop_coordinates,
            layout=payload.layout,
            video_sources=payload.video_sources,
            output_width=payload.output_width,
            output_height=payload.output_height,
            smart_crop=payload.smart_crop
        )
        return BatchCreateResponse(
            batch_id=batch_id,
            message="Batch processing started. Check status using the status endpoint."
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create batch: {str(e)}"
        )
    finally:
        await orchestrator.close()


@router.get(
    "/status/{batch_id}",
    response_model=BatchStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve progress status of a batch",
    description="Gets general batch stats (total, success, failed, progress) and state for each individual video."
)
async def get_batch_status(batch_id: str):
    orchestrator = BatchOrchestrator()
    try:
        status_data = await orchestrator.get_batch_status(batch_id)
        return status_data
    except BatchNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.message
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to query batch status: {str(e)}"
        )
    finally:
        await orchestrator.close()


@router.post(
    "/upload",
    status_code=status.HTTP_201_CREATED,
    summary="Upload a local video file",
    description="Uploads a video file to the server's temporary storage, returning its local path for batch processing."
)
async def upload_video(file: UploadFile = File(...)):
    import uuid
    import shutil
    import asyncio
    from pathlib import Path
    from src.core.config import settings

    try:
        ext = Path(file.filename).suffix.lower()
        if ext not in [".mp4", ".mov", ".avi", ".mkv", ".png", ".jpg", ".jpeg"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported file extension. Please upload standard video or image formats."
            )
        
        unique_filename = f"upload_{uuid.uuid4()}{ext}"
        file_path = settings.TEMP_DIR / unique_filename
        
        def save_file():
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
                
        await asyncio.to_thread(save_file)
        
        return {
            "filename": file.filename,
            "temp_path": str(file_path),
            "url": f"/storage/temp/{unique_filename}"
        }
    except Exception as e:
        if not isinstance(e, HTTPException):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Upload failed: {str(e)}"
            )
        raise


@router.get(
    "/download/batch/{batch_id}",
    summary="Download all completed videos in a batch as a ZIP",
    description="Gathers all rendered videos for the batch, packages them into a ZIP archive, and streams it for download."
)
async def download_batch_zip(batch_id: str):
    import zipfile
    import asyncio
    from fastapi.responses import FileResponse
    from src.core.config import settings

    batch_dir = settings.STORAGE_DIR / batch_id
    if not batch_dir.exists() or not batch_dir.is_dir():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch folder not found or no files rendered yet."
        )
        
    video_files = list(batch_dir.glob("*.mp4"))
    video_files = [f for f in video_files if f.name != f"batch_{batch_id}.zip"]
    
    if not video_files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No rendered videos found in this batch yet."
        )
        
    zip_path = batch_dir / f"batch_{batch_id}.zip"
    
    def create_zip():
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for video in video_files:
                zipf.write(video, arcname=video.name)
                
    await asyncio.to_thread(create_zip)
    
    return FileResponse(
        path=str(zip_path),
        media_type="application/zip",
        filename=f"batch_{batch_id}.zip"
    )

from typing import List, Optional
from pydantic import BaseModel, Field

from src.domain.models import CropCoordinates, OverlayLayout


class BatchCreateRequest(BaseModel):
    template_id: str = Field(
        ...,
        description="Path or ID of the template image file."
    )
    crop_coordinates: CropCoordinates = Field(
        ...,
        description="Target dimensions and overlay coordinates."
    )
    source_crop_coordinates: Optional[CropCoordinates] = Field(
        None,
        description="Optional coordinates for cropping the input source videos."
    )
    layout: OverlayLayout = Field(
        OverlayLayout.TEMPLATE_ON_TOP,
        description="Overlay strategy: TEMPLATE_ON_TOP (frame) or VIDEO_ON_TOP (background)."
    )
    output_width: Optional[int] = Field(
        None,
        description="Optional target width of the output video canvas.",
        gt=0
    )
    output_height: Optional[int] = Field(
        None,
        description="Optional target height of the output video canvas.",
        gt=0
    )
    video_sources: List[str] = Field(
        ...,
        description="List of paths or URLs of videos to process.",
        min_items=1
    )


class BatchCreateResponse(BaseModel):
    batch_id: str = Field(..., description="Unique UUID generated for the batch.")
    message: str = Field(..., description="Status message.")


class TaskStatusResponse(BaseModel):
    task_id: str
    source: str
    status: str
    progress: float
    error: Optional[str] = None
    output_path: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class BatchStatusResponse(BaseModel):
    batch_id: str
    template_id: str
    status: str
    total_tasks: int
    completed_tasks: int
    failed_tasks: int
    progress: float
    output_width: Optional[int] = None
    output_height: Optional[int] = None
    created_at: str
    updated_at: str
    tasks: List[TaskStatusResponse]

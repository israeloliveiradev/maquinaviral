from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    DOWNLOADING = "DOWNLOADING"
    PROBING = "PROBING"
    RENDERING = "RENDERING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class BatchStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class OverlayLayout(str, Enum):
    VIDEO_ON_TOP = "VIDEO_ON_TOP"        # Overlay scaled video over the template background
    TEMPLATE_ON_TOP = "TEMPLATE_ON_TOP"  # Overlay transparent template over the scaled video


class CropCoordinates(BaseModel):
    x: int = Field(..., description="X coordinate for the overlay position", ge=0)
    y: int = Field(..., description="Y coordinate for the overlay position", ge=0)
    width: int = Field(..., description="Target width of the scaled video", gt=0)
    height: int = Field(..., description="Target height of the scaled video", gt=0)


class VideoTaskState(BaseModel):
    task_id: str
    source: str
    status: TaskStatus = TaskStatus.PENDING
    progress: float = 0.0
    error: Optional[str] = None
    output_path: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class BatchState(BaseModel):
    batch_id: str
    template_id: str
    crop_coordinates: CropCoordinates
    source_crop_coordinates: Optional[CropCoordinates] = None
    layout: OverlayLayout = OverlayLayout.TEMPLATE_ON_TOP
    output_width: Optional[int] = None
    output_height: Optional[int] = None
    status: BatchStatus = BatchStatus.PENDING
    total_tasks: int
    completed_tasks: int = 0
    failed_tasks: int = 0
    task_ids: List[str] = Field(default_factory=list)
    created_at: str
    updated_at: str

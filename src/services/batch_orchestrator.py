import datetime
import uuid
import logging
from typing import List, Dict, Any, Optional

from src.domain.models import (
    BatchState,
    VideoTaskState,
    CropCoordinates,
    OverlayLayout,
    TaskStatus,
    BatchStatus,
)
from src.infrastructure.storage.redis_client import RedisClient
from src.infrastructure.queue.tasks import process_video_task

logger = logging.getLogger(__name__)


class BatchOrchestrator:
    def __init__(self, redis_client: Optional[RedisClient] = None):
        self.redis_client = redis_client or RedisClient()

    async def create_batch(
        self,
        template_id: str,
        coords: CropCoordinates,
        layout: OverlayLayout,
        video_sources: List[str],
        source_crop: Optional[CropCoordinates] = None,
        output_width: Optional[int] = None,
        output_height: Optional[int] = None,
    ) -> str:
        """
        Registers a rendering batch in Redis, schedules independent Celery tasks
        for each source, and returns the generated batch ID.
        """
        batch_id = str(uuid.uuid4())
        created_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        
        task_ids = []
        for source in video_sources:
            task_id = str(uuid.uuid4())
            task_ids.append(task_id)
            
            # 1. Create and persist initial task state
            task_state = VideoTaskState(
                task_id=task_id,
                source=source,
                status=TaskStatus.PENDING,
                progress=0.0
            )
            await self.redis_client.save_task_state(task_state)
            
            # 2. Enqueue asynchronous worker execution
            process_video_task.delay(
                batch_id=batch_id,
                task_id=task_id,
                template_id=template_id,
                coords_dict=coords.model_dump(),
                source_crop_dict=source_crop.model_dump() if source_crop else None,
                layout_val=layout.value,
                video_source=source,
                output_width=output_width,
                output_height=output_height
            )
            
        # 3. Create and persist Batch metadata
        batch_state = BatchState(
            batch_id=batch_id,
            template_id=template_id,
            crop_coordinates=coords,
            source_crop_coordinates=source_crop,
            layout=layout,
            output_width=output_width,
            output_height=output_height,
            status=BatchStatus.PENDING,
            total_tasks=len(video_sources),
            completed_tasks=0,
            failed_tasks=0,
            task_ids=task_ids,
            created_at=created_at,
            updated_at=created_at
        )
        await self.redis_client.save_batch_state(batch_state)
        
        logger.info(f"Successfully orchestrating Batch={batch_id} containing {len(video_sources)} task(s).")
        return batch_id

    async def get_batch_status(self, batch_id: str) -> Dict[str, Any]:
        """
        Fetches the batch state and aggregates stats from all child tasks.
        """
        batch = await self.redis_client.get_batch_state(batch_id)
        
        tasks_info = []
        total_progress_sum = 0.0
        
        for task_id in batch.task_ids:
            try:
                task = await self.redis_client.get_task_state(task_id)
                tasks_info.append(task)
                total_progress_sum += task.progress
            except Exception as e:
                logger.error(f"Task={task_id} state missing from storage: {e}")
                # Fallback task mock to maintain data consistency
                fallback_task = VideoTaskState(
                    task_id=task_id,
                    source="unknown",
                    status=TaskStatus.FAILED,
                    error="State records missing in cache database."
                )
                tasks_info.append(fallback_task)
        
        # Calculate dynamic batch percentage progress
        avg_progress = 0.0
        if batch.total_tasks > 0:
            avg_progress = total_progress_sum / batch.total_tasks
            
        return {
            "batch_id": batch.batch_id,
            "template_id": batch.template_id,
            "status": batch.status.value,
            "total_tasks": batch.total_tasks,
            "completed_tasks": batch.completed_tasks,
            "failed_tasks": batch.failed_tasks,
            "progress": round(avg_progress, 2),
            "output_width": batch.output_width,
            "output_height": batch.output_height,
            "created_at": batch.created_at,
            "updated_at": batch.updated_at,
            "tasks": [t.model_dump() for t in tasks_info]
        }
        
    async def close(self) -> None:
        """Closes internal Redis connections."""
        await self.redis_client.close()

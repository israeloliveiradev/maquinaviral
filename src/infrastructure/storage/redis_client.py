import datetime
import json
import logging
from typing import Optional, List, Dict, Any
import redis.asyncio as aioredis

from src.core.config import settings
from src.core.exceptions import BatchNotFoundError, TaskNotFoundError
from src.domain.models import BatchState, VideoTaskState, TaskStatus, BatchStatus

logger = logging.getLogger(__name__)


class RedisClient:
    def __init__(self, redis_url: str = settings.REDIS_URL):
        self.redis_url = redis_url
        self._redis: Optional[aioredis.Redis] = None

    async def get_client(self) -> aioredis.Redis:
        """Get or initialize the async Redis client."""
        if self._redis is None:
            self._redis = aioredis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
        return self._redis

    async def close(self) -> None:
        """Close the Redis connection pool."""
        if self._redis is not None:
            await self._redis.close()
            self._redis = None

    async def save_batch_state(self, batch: BatchState) -> None:
        """Persist the batch state metadata."""
        client = await self.get_client()
        key = f"batch:{batch.batch_id}"
        await client.set(key, batch.model_dump_json())
        logger.debug(f"Saved batch state for {batch.batch_id}")

    async def get_batch_state(self, batch_id: str) -> BatchState:
        """Retrieve the batch state. Raises BatchNotFoundError if not found."""
        client = await self.get_client()
        key = f"batch:{batch_id}"
        data = await client.get(key)
        if not data:
            raise BatchNotFoundError(batch_id)
        return BatchState.model_validate_json(data)

    async def save_task_state(self, task: VideoTaskState) -> None:
        """Persist individual video task state."""
        client = await self.get_client()
        key = f"task:{task.task_id}"
        await client.set(key, task.model_dump_json())
        logger.debug(f"Saved task state for {task.task_id}")

    async def get_task_state(self, task_id: str) -> VideoTaskState:
        """Retrieve individual task state. Raises TaskNotFoundError if not found."""
        client = await self.get_client()
        key = f"task:{task_id}"
        data = await client.get(key)
        if not data:
            raise TaskNotFoundError(task_id)
        return VideoTaskState.model_validate_json(data)

    async def update_task_progress(
        self,
        batch_id: str,
        task_id: str,
        status: TaskStatus,
        progress: float,
        error: Optional[str] = None,
        output_path: Optional[str] = None,
        started_at: Optional[str] = None,
        completed_at: Optional[str] = None,
    ) -> None:
        """
        Updates task progress and, if transitioning to a terminal state (COMPLETED/FAILED),
        atomically updates the batch status using Redis transaction watches.
        """
        client = await self.get_client()
        task_key = f"task:{task_id}"
        batch_key = f"batch:{batch_id}"

        # 1. Update the task state
        task_data = await client.get(task_key)
        if not task_data:
            logger.warning(f"Task {task_id} not found in Redis, skipping progress update.")
            return

        task = VideoTaskState.model_validate_json(task_data)
        old_status = task.status

        # Apply updates
        task.status = status
        task.progress = progress
        if error is not None:
            task.error = error
        if output_path is not None:
            task.output_path = output_path
        if started_at is not None:
            task.started_at = started_at
        if completed_at is not None:
            task.completed_at = completed_at

        await client.set(task_key, task.model_dump_json())
        logger.debug(f"Task {task_id} progress updated to {progress}% ({status})")

        # 2. Update Batch counters if task transitioned to a terminal status
        is_terminal = status in (TaskStatus.COMPLETED, TaskStatus.FAILED)
        was_terminal = old_status in (TaskStatus.COMPLETED, TaskStatus.FAILED)

        if is_terminal and not was_terminal:
            # We must atomically increment counters on the batch using WATCH/MULTI/EXEC
            async with client.pipeline(transaction=True) as pipe:
                while True:
                    try:
                        await pipe.watch(batch_key)
                        batch_data = await pipe.get(batch_key)
                        if not batch_data:
                            logger.error(f"Batch {batch_id} not found while updating terminal task state.")
                            break

                        batch = BatchState.model_validate_json(batch_data)
                        
                        if status == TaskStatus.COMPLETED:
                            batch.completed_tasks += 1
                        elif status == TaskStatus.FAILED:
                            batch.failed_tasks += 1

                        total_processed = batch.completed_tasks + batch.failed_tasks
                        if total_processed >= batch.total_tasks:
                            batch.status = BatchStatus.COMPLETED
                        else:
                            batch.status = BatchStatus.PROCESSING

                        batch.updated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()

                        pipe.multi()
                        pipe.set(batch_key, batch.model_dump_json())
                        await pipe.execute()
                        logger.info(
                            f"Batch {batch_id} counters updated: "
                            f"{batch.completed_tasks}/{batch.total_tasks} completed, "
                            f"{batch.failed_tasks} failed (Status: {batch.status})"
                        )
                        break
                    except aioredis.WatchError:
                        # Transaction conflict occurred, retry execution loop
                        logger.debug("Redis WATCH collision on batch update, retrying...")
                        continue

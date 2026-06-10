class AppException(Exception):
    """Base application exception."""
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class FFmpegError(AppException):
    """Base exception for all FFmpeg / FFprobe related errors."""
    pass


class FFprobeError(FFmpegError):
    """Raised when probing a media file fails."""
    pass


class FFmpegExecutionError(FFmpegError):
    """Raised when FFmpeg execution fails or returns non-zero status."""
    pass


class DownloadError(AppException):
    """Raised when downloading a media file from a URL fails."""
    pass


class BatchError(AppException):
    """Base exception for batch related operations."""
    pass


class BatchNotFoundError(BatchError):
    """Raised when a batch ID is not found in the storage."""
    def __init__(self, batch_id: str):
        super().__init__(f"Batch with ID '{batch_id}' was not found.")
        self.batch_id = batch_id


class TaskNotFoundError(BatchError):
    """Raised when a task ID is not found in the storage."""
    def __init__(self, task_id: str):
        super().__init__(f"Task with ID '{task_id}' was not found.")
        self.task_id = task_id

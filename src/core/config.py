import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )

    # Project Paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    STORAGE_DIR: Path = BASE_DIR / "storage"
    TEMPLATES_DIR: Path = BASE_DIR / "templates"
    TEMP_DIR: Path = STORAGE_DIR / "temp"

    # Redis / Celery
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"

    # FFmpeg Configuration
    FFMPEG_PATH: str = "ffmpeg"
    FFPROBE_PATH: str = "ffprobe"
    
    # Render Options
    # "auto" detects NVIDIA h264_nvenc, VAAPI, or falls back to libx264
    VIDEO_CODEC: str = "auto"
    CPU_PRESET: str = "fast"  # fast, faster, veryfast, superfast, ultrafast
    VIDEO_CRF: int = 23       # Constant Rate Factor for CPU encoding

    # API Configuration
    API_TITLE: str = "SaaS Mass Video Rendering API"
    API_VERSION: str = "1.0.0"
    API_PORT: int = 8000
    API_HOST: str = "0.0.0.0"

    def create_directories(self) -> None:
        """Create necessary project directories on start."""
        for directory in [self.STORAGE_DIR, self.TEMPLATES_DIR, self.TEMP_DIR]:
            directory.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.create_directories()

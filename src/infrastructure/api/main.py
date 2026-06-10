import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.core.config import settings
from src.infrastructure.api.v1.endpoints import router as v1_router

# Configure detailed logging format
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup actions
    logger.info("Initializing SaaS Mass Video Editing Backend...")
    settings.create_directories()
    # Create static directory if it doesn't exist to prevent mounting errors
    static_dir = Path(__file__).resolve().parent / "static"
    static_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Storage and temporary directories verified.")
    yield
    # Shutdown actions
    logger.info("Shutting down SaaS Mass Video Editing Backend...")


app = FastAPI(
    title=settings.API_TITLE,
    version=settings.API_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static folders before routes so assets load correctly
# Create paths as string absolute paths to prevent any mounting errors
static_path = str(Path(__file__).resolve().parent / "static")
app.mount("/static", StaticFiles(directory=static_path), name="static")
app.mount("/storage", StaticFiles(directory=str(settings.STORAGE_DIR)), name="storage")
app.mount("/templates", StaticFiles(directory=str(settings.TEMPLATES_DIR)), name="templates")

# Register routers
app.include_router(v1_router, prefix="/api/v1")


@app.get("/", include_in_schema=False)
async def serve_frontend():
    """Serves the premium frontend dashboard on root."""
    frontend_index = Path(__file__).resolve().parent / "static" / "index.html"
    if not frontend_index.exists():
        # Fallback to redirecting to /docs if index.html is still being created
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/docs")
    return FileResponse(str(frontend_index))


@app.get("/health", tags=["System Health"])
async def health_check():
    """Simple API live health check."""
    return {"status": "healthy", "service": settings.API_TITLE}

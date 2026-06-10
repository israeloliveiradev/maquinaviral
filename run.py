import sys
import os
import argparse
import platform
import subprocess
import uvicorn

def start_api():
    """Starts the FastAPI app with Uvicorn."""
    print("Starting FastAPI Rendering API...")
    uvicorn.run(
        "src.infrastructure.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )

def start_worker():
    """Starts the Celery worker with proper OS-specific pool settings."""
    print("Starting Celery Rendering Worker...")
    
    # Base command
    cmd = [
        "celery",
        "-A", "src.infrastructure.queue.celery_app",
        "worker",
        "--loglevel=info"
    ]
    
    # Windows doesn't support Celery's default prefork pool, so we override it
    if platform.system() == "Windows":
        print("[System Info] Windows OS detected. Forcing '--pool=solo' for Celery worker stability.")
        cmd.extend(["--pool", "solo"])
    else:
        # On Linux/Docker we can run standard or eventlet/gevent pools.
        # Let's specify threads for thread safety with FFmpeg subprocesses
        cmd.extend(["--pool", "threads", "-c", "4"])
        
    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print("\nStopping Celery Worker...")
    except Exception as e:
        print(f"Error starting Celery: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SaaS Mass Video Rendering Platform CLI")
    parser.add_argument(
        "mode",
        choices=["api", "worker"],
        help="Whether to run the FastAPI server ('api') or Celery background worker ('worker')"
    )
    
    args = parser.parse_args()
    
    if args.mode == "api":
        start_api()
    elif args.mode == "worker":
        start_worker()

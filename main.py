"""
GPR VR Processor - Main Application
Refactored modular structure with clean separation of concerns.
"""
import os
import multiprocessing
from concurrent.futures import ProcessPoolExecutor
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from fastapi.middleware.cors import CORSMiddleware
from gtts import gTTS
import io
from fastapi.responses import StreamingResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Import configuration
from app.config import (
    config,
    UPLOAD_FOLDER,
    PROCESSED_FOLDER,
    STATIC_FOLDER,
    TEMPLATES_FOLDER,
    TILES_FOLDER,
    MAX_WORKERS
)
from app.database import init_db
from app.limiter import limiter

# Import service containers
from app.services.gpr_processor import ExecutorContainer

# Import all routers
from app.routes import auth_routes, upload_routes, job_routes, tool_routes, session_routes, annotation_routes


# ============ LIFESPAN CONTEXT MANAGER ============

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup and shutdown"""
    # Startup logic: Initialize executor for both reload and normal modes
    print("Application started")
    print(f"Initializing ProcessPoolExecutor with {MAX_WORKERS} workers")
    ExecutorContainer.executor = ProcessPoolExecutor(max_workers=MAX_WORKERS)
    init_db()  # Ensure database tables exist
    yield
    # Shutdown logic: Cleanup executor
    if ExecutorContainer.executor:
        print("Shutting down process pool executor via lifespan...")
        ExecutorContainer.executor.shutdown(wait=True)
        print("Process pool executor shutdown complete")


from fastapi.middleware.gzip import GZipMiddleware
from starlette.responses import Response, FileResponse
from starlette.types import Scope
import mimetypes

# ============ CUSTOM STATIC FILES HANDLER ============
class CacheControlStaticFiles(StaticFiles):
    """Custom StaticFiles handler that sets aggressive caching headers"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def get_response(self, path: str, scope: Scope) -> Response:
        response = await super().get_response(path, scope)
        # Set Cache-Control header for 1 year (31536000 seconds)
        # BUT: exclude binary potree files from immutable flag to allow range requests
        if not path.endswith(('.bin', '.octree')):
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        else:
            response.headers["Cache-Control"] = "public, max-age=31536000"
        return response

# ============ APP INITIALIZATION ============

# Hide auto-generated API docs for security/obscurity
app = FastAPI(
    title="GPR VR Processor", 
    lifespan=lifespan,
    docs_url=None,      # Disable Swagger UI at /docs
    redoc_url=None,     # Disable ReDoc at /redoc
    openapi_url=None    # Disable OpenAPI JSON schema at /openapi.json
)

# ============ RATE LIMITING ============
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Add GZip Middleware (Professional standard for text compression)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Add session middleware
app.add_middleware(SessionMiddleware, secret_key=config.SECRET_KEY)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create necessary folders
for folder in [UPLOAD_FOLDER, PROCESSED_FOLDER, TEMPLATES_FOLDER, STATIC_FOLDER]:
    if not os.path.exists(folder):
        os.makedirs(folder)

# Mount static file directories with Caching
app.mount("/static", CacheControlStaticFiles(directory=STATIC_FOLDER), name="static")
app.mount("/processed", CacheControlStaticFiles(directory=PROCESSED_FOLDER), name="processed")
app.mount("/tiles", CacheControlStaticFiles(directory=TILES_FOLDER), name="tiles")

# ============ POTREE STREAMING ENDPOINT ============
from fastapi import Request
from starlette.responses import StreamingResponse
import aiofiles

def get_optimal_chunk_size(file_size: int) -> int:
    """
    Calculate optimal chunk size based on file size.
    Automatically scales chunk size to maintain ~200 requests maximum,
    while keeping memory usage reasonable.
    
    Args:
        file_size: Size of file in bytes
    
    Returns:
        Optimal chunk size in bytes
    
    Examples:
        616MB file → 1MB chunks (631 requests)
        1GB file → 10MB chunks (102 requests)
        10GB file → 50MB chunks (204 requests)
        100GB file → 256MB chunks (400 requests)
    """
    # Strategy: chunk_size ≈ file_size / 200, but within sensible bounds
    MB = 1024 * 1024
    
    if file_size < 100 * MB:                      # < 100MB
        return 1 * MB                             # 1MB chunks
    elif file_size < 1024 * MB:                   # < 1GB
        return 10 * MB                            # 10MB chunks
    elif file_size < 10 * 1024 * MB:              # < 10GB
        return 50 * MB                            # 50MB chunks
    elif file_size < 100 * 1024 * MB:             # < 100GB
        return 100 * MB                           # 100MB chunks
    else:                                         # >= 100GB
        return 256 * MB                           # 256MB chunks

@app.get("/api/potree/{file_path:path}")
async def stream_potree_file(file_path: str, request: Request):
    """
    Stream Potree files with proper range request support.
    Handles large binary files (octree.bin, hierarchy.bin) efficiently.
    Supports both static /static/potree_lidar and dynamic uploads in /processed/potree_dynamic.
    """
    # Security: prevent path traversal
    if ".." in file_path or file_path.startswith("/"):
        return {"error": "Invalid file path"}
    
    # Check if it starts with 'potree_dynamic'
    if file_path.startswith("potree_dynamic/"):
        inner_path = file_path.replace("potree_dynamic/", "")
        full_path = os.path.join(PROCESSED_FOLDER, "potree_dynamic", inner_path)
    else:
        full_path = os.path.join(STATIC_FOLDER, "potree_lidar", file_path)
    
    # Normalize path and verify it exists
    full_path = os.path.normpath(full_path)
    if not os.path.isfile(full_path):
        # Fallback: check if it's in processed/potree_dynamic without the prefix (for backward compat if needed)
        dynamic_fallback = os.path.normpath(os.path.join(PROCESSED_FOLDER, "potree_dynamic", file_path))
        if os.path.isfile(dynamic_fallback):
            full_path = dynamic_fallback
        else:
            return {"error": "File not found"}
    
    file_size = os.path.getsize(full_path)
    optimal_chunk_size = get_optimal_chunk_size(file_size)
    
    # Handle Range requests for efficient streaming of large files
    if "range" in request.headers:
        range_header = request.headers.get("range")
        if range_header.startswith("bytes="):
            ranges = range_header[6:].split(",")
            start, end = ranges[0].split("-")
            start = int(start) if start else 0
            end = int(end) if end else file_size - 1
            
            async def range_file_iterator():
                async with aiofiles.open(full_path, mode='rb') as f:
                    await f.seek(start)
                    remaining = end - start + 1
                    while remaining > 0:
                        chunk_size = min(optimal_chunk_size, remaining)  # Adaptive chunks
                        chunk = await f.read(chunk_size)
                        if not chunk:
                            break
                        remaining -= len(chunk)
                        yield chunk
            
            return StreamingResponse(
                range_file_iterator(),
                status_code=206,
                headers={
                    "Content-Range": f"bytes {start}-{end}/{file_size}",
                    "Content-Length": str(end - start + 1),
                    "Content-Type": "application/octet-stream",
                    "Cache-Control": "public, max-age=31536000, must-revalidate",
                    "Accept-Ranges": "bytes"
                }
            )
    
    # Regular full-file download
    async def full_file_iterator():
        async with aiofiles.open(full_path, mode='rb') as f:
            while True:
                chunk = await f.read(optimal_chunk_size)  # Adaptive chunks
                if not chunk:
                    break
                yield chunk
    
    return StreamingResponse(
        full_file_iterator(),
        media_type="application/octet-stream",
        headers={
            "Content-Length": str(file_size),
            "Cache-Control": "public, max-age=31536000, must-revalidate",
            "Accept-Ranges": "bytes"
        }
    )

# ============ REGISTER ROUTERS ============

# Authentication routes (/, /register, /login, /verify, /dashboard, /logout)
app.include_router(auth_routes.router)

# Upload routes (/upload, /files/{job_id}/{filename})
app.include_router(upload_routes.router)

# Job management routes (/status, /view, /list-jobs, /view_multi, /download, /cleanup)
app.include_router(job_routes.router)

# Tool routes (/converter, /tools/survey_boundary)
app.include_router(tool_routes.router)

# Session collaboration routes (/session, /ws)
app.include_router(session_routes.router, prefix="/session", tags=["session"])

# Annotation routes (/api/annotations/{job_id})
app.include_router(annotation_routes.router)


# ============ HEALTH CHECK ============

@app.get("/health")
async def health_check():
    """
    Health check endpoint
    
    Returns:
        Status and timestamp
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/api/tts")
async def get_tts(text: str):
    """
    Generate TTS audio on the server to bypass browser restrictions
    """
    try:
        tts = gTTS(text=text, lang='en')
        mp3_fp = io.BytesIO()
        tts.write_to_fp(mp3_fp)
        mp3_fp.seek(0)
        return StreamingResponse(mp3_fp, media_type="audio/mpeg")
    except Exception as e:
        print(f"TTS generation error: {e}")
        return {"error": "TTS failed"}

# ============ MAIN ENTRY POINT ============

if __name__ == "__main__":
    # Required for Windows multiprocessing
    multiprocessing.freeze_support()
    
    # Executor initialization moved to lifespan to support reload=True
    
    import uvicorn
    import socket
    from gen_cert import generate_self_signed_cert
    
    # Generate SSL certificates if they don't exist
    if not os.path.exists("cert.pem") or not os.path.exists("key.pem"):
        print("🔐 Generating self-signed SSL certificates for HTTPS...")
        generate_self_signed_cert()
    
    # Get local IP for display
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)
    
    print("\n" + "="*70)
    print("🚀 STARTING STRATUM XR (EXTENDED REALITY) - SECURE SERVER")
    print("="*70)
    print(f"📊 Parallel workers for GPR processing: {MAX_WORKERS}")
    print(f"🔒 Local Access:   https://127.0.0.1:5007")
    print(f"🌐 Network Access: https://{local_ip}:5007")
    print("="*70)
    print("\n⚠️  SECURITY NOTE:")
    print("    You will see a browser security warning (self-signed certificate).")
    print("    Click 'Advanced' → 'Proceed to...' to access the application.")
    print("    This is normal for local development.\n")
    
    try:
        # Run with reload=True for development
        # When reload=True, we must pass the app as an import string "main:app"
        uvicorn.run(
            "main:app",
            host="0.0.0.0",
            port=5009,
            ssl_keyfile="key.pem",
            ssl_certfile="cert.pem",
            reload=True
        )
    finally:
        # Cleanup on exit
        if ExecutorContainer.executor:
            print("\nShutting down process pool executor...")
            ExecutorContainer.executor.shutdown(wait=True)
            print("Process pool executor shutdown complete")

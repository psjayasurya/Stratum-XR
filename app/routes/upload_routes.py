"""
Upload Routes
Handles file upload and file serving endpoints.
"""
from fastapi import APIRouter, File, Form, UploadFile, HTTPException, Request
from fastapi.responses import FileResponse
from typing import Optional, Any, Dict
import os
import re
from datetime import datetime
import shutil

from app.config import UPLOAD_FOLDER, PROCESSED_FOLDER
from app.utils.auth_security import validate_csrf
from app.utils.file_utils import secure_filename
from app.services.gpr_processor import processing_jobs
from app.services.job_queue import enqueue_gpr_job

# Create router
router = APIRouter(tags=["Upload"])

# Import limiter from shared module
from app.limiter import limiter

UPLOAD_CHUNK_SIZE = 1024 * 1024


async def _save_upload_file(upload_file: UploadFile, destination_path: str) -> None:
    """Write an uploaded file to disk in chunks so we never buffer the whole file in memory."""
    with open(destination_path, "wb") as buffer:
        while True:
            chunk = await upload_file.read(UPLOAD_CHUNK_SIZE)
            if not chunk:
                break
            buffer.write(chunk)
    await upload_file.close()


def _extract_user_email(job_id: str) -> Optional[str]:
    email_pattern = r'-([^_]+@[^_]+)(?:_|$)'
    match = re.search(email_pattern, job_id)
    return match.group(1) if match else None


def _register_processed_job(job_id: str, user_email: Optional[str], job_name: str, status: str, storage_path: str) -> None:
    if not user_email:
        return

    try:
        from app.database import get_db

        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO processed_jobs (job_id, user_email, job_name, processing_date, status, storage_path)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (job_id) DO UPDATE SET
                processing_date = EXCLUDED.processing_date,
                status = EXCLUDED.status,
                storage_path = EXCLUDED.storage_path,
                job_name = EXCLUDED.job_name
            """,
            (job_id, user_email, job_name, datetime.now(), status, storage_path),
        )
        conn.commit()
        conn.close()
    except Exception as exc:
        print(f"Error registering job in DB: {exc}")


def _build_base_settings(**kwargs) -> Dict[str, Any]:
    settings = {
        "job_name": kwargs["job_name"],
        "file_format": kwargs["file_format"],
        "col_idx_x": kwargs["col_idx_x"],
        "col_idx_y": kwargs["col_idx_y"],
        "col_idx_z": kwargs["col_idx_z"],
        "col_idx_amplitude": kwargs["col_idx_amplitude"],
        "threshold_percentile": kwargs["threshold_percentile"],
        "iso_bins": kwargs["iso_bins"],
        "depth_offset_per_level": kwargs["depth_offset_per_level"],
        "vr_point_size": kwargs["vr_point_size"],
        "font_size_multiplier": kwargs["font_size_multiplier"],
        "font_family": kwargs["font_family"],
        "invert_depth": kwargs["invert_depth"],
        "center_coordinates": kwargs["center_coordinates"],
        "generate_surface": kwargs["generate_surface"],
        "surface_resolution": kwargs["surface_resolution"],
        "surface_depth_slices": kwargs["surface_depth_slices"],
        "surface_opacity": kwargs["surface_opacity"],
        "generate_amplitude_surface": kwargs["generate_amplitude_surface"],
        "max_points_per_layer": kwargs["max_points_per_layer"],
        "color_palette": kwargs["color_palette"],
    }

    pipe_filename = kwargs.get("pipe_filename")
    if pipe_filename:
        settings["pipe_filename"] = pipe_filename

    return settings


@router.post("/upload")
@limiter.limit("10/minute")
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    job_name: str = Form(...),
    file_format: str = Form("csv"),
    pipe_file: Optional[UploadFile] = File(None),
    kml_file: Optional[UploadFile] = File(None),
    col_idx_x: int = Form(0),
    col_idx_y: int = Form(1),
    col_idx_z: int = Form(7),
    col_idx_amplitude: int = Form(8),
    threshold_percentile: float = Form(0.63),
    iso_bins: int = Form(5),
    depth_offset_per_level: float = Form(0.05),
    vr_point_size: float = Form(0.015),
    font_size_multiplier: float = Form(1.0),
    font_family: str = Form('Arial'),
    invert_depth: bool = Form(True),
    center_coordinates: bool = Form(True),
    generate_surface: bool = Form(False),
    surface_resolution: int = Form(100),
    surface_depth_slices: int = Form(0),
    surface_opacity: float = Form(0.6),
    generate_amplitude_surface: bool = Form(False),
    max_points_per_layer: int = Form(500000),
    color_palette: str = Form('Standard'),
):
    """
    Upload and process GPR data file
    
    Args:
        file: Main GPR data file (CSV or HDF)
        job_name: Unique job identifier name
        file_format: File format ('csv' or 'hdf')
        pipe_file: Optional pipe model PLY file
        kml_file: Optional KML geolocation file OR Zipped Shapefile
        col_idx_x: Column index for X coordinate
        col_idx_y: Column index for Y coordinate
        col_idx_z: Column index for Z/depth coordinate
        col_idx_amplitude: Column index for amplitude values
        threshold_percentile: Amplitude threshold percentile (0-1)
        iso_bins: Number of amplitude layers to generate
        depth_offset_per_level: Depth offset between layers
        vr_point_size: Point size in VR viewer
        font_size_multiplier: UI font size multiplier
        font_family: UI font family
        invert_depth: Whether to invert depth values
        center_coordinates: Whether to center coordinates
        generate_surface: Whether to generate surface mesh
        surface_resolution: Surface mesh resolution
        surface_depth_slices: Number of depth slices
        surface_opacity: Surface opacity (0-1)
        generate_amplitude_surface: Whether to generate amplitude surface
        max_points_per_layer: Maximum points per layer
        color_palette: Color palette name
        
    Returns:
        Dictionary with job_id, filename, and queue status
    """
    validate_csrf(request, request.headers.get("x-csrf-token"))

    if not file.filename:
        raise HTTPException(status_code=400, detail="No file selected")

    if not job_name.strip():
        raise HTTPException(status_code=400, detail="Job Name is required")

    job_id = secure_filename(job_name.strip())
    if not job_id:
        raise HTTPException(status_code=400, detail="Invalid Job Name")

    job_dir = os.path.join(PROCESSED_FOLDER, job_id)
    if os.path.exists(job_dir):
        raise HTTPException(status_code=400, detail=f"Job name '{job_name}' already exists")

    filename = secure_filename(file.filename)
    filepath = os.path.join(UPLOAD_FOLDER, f"{job_id}_{filename}")
    await _save_upload_file(file, filepath)

    pipe_filename = None
    if pipe_file and pipe_file.filename:
        pipe_filename = secure_filename(pipe_file.filename)
        pipe_path = os.path.join(UPLOAD_FOLDER, f"{job_id}_{pipe_filename}")
        await _save_upload_file(pipe_file, pipe_path)

    geo_path = None
    if kml_file and kml_file.filename:
        geo_filename = secure_filename(kml_file.filename)
        geo_path = os.path.join(UPLOAD_FOLDER, f"{job_id}_{geo_filename}")
        await _save_upload_file(kml_file, geo_path)

    settings = _build_base_settings(
        job_name=job_name,
        file_format=file_format,
        col_idx_x=col_idx_x,
        col_idx_y=col_idx_y,
        col_idx_z=col_idx_z,
        col_idx_amplitude=col_idx_amplitude,
        threshold_percentile=threshold_percentile,
        iso_bins=iso_bins,
        depth_offset_per_level=depth_offset_per_level,
        vr_point_size=vr_point_size,
        font_size_multiplier=font_size_multiplier,
        font_family=font_family,
        invert_depth=invert_depth,
        center_coordinates=center_coordinates,
        generate_surface=generate_surface,
        surface_resolution=surface_resolution,
        surface_depth_slices=surface_depth_slices,
        surface_opacity=surface_opacity,
        generate_amplitude_surface=generate_amplitude_surface,
        max_points_per_layer=max_points_per_layer,
        color_palette=color_palette,
        pipe_filename=pipe_filename,
    )

    processing_jobs[job_id] = {
        'status': 'queued',
        'message': 'Upload received, waiting for a worker...',
        'filename': filename,
        'settings': settings,
    }

    user_email = _extract_user_email(job_id)
    _register_processed_job(job_id, user_email, job_name, 'queued', 'pending')

    enqueue_gpr_job(
        job_id=job_id,
        filepath=filepath,
        filename=filename,
        settings=settings,
        user_email=user_email,
        job_name=job_name,
        geo_path=geo_path,
    )

    return {"job_id": job_id, "filename": filename, "status": "queued"}


@router.get("/files/{job_id}/{filename:path}")
async def serve_file(job_id: str, filename: str):
    """
    Serve processed files for a specific job
    
    Args:
        job_id: Job identifier
        filename: Filename to serve (can include subdirectories)
        
    Returns:
        File response
    """
    output_dir = os.path.join(PROCESSED_FOLDER, job_id)
    if not os.path.exists(output_dir):
        raise HTTPException(status_code=404, detail="Job not found")
    
    file_path = os.path.join(output_dir, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(file_path)


@router.post("/upload_potree")
async def upload_potree_files(
    request: Request,
    metadata_file: UploadFile = File(...),
    hierarchy_file: UploadFile = File(...),
    octree_file: UploadFile = File(...),
    log_file: Optional[UploadFile] = File(None)
):
    """
    Upload and replace Potree LiDAR files dynamically.
    Saves to a special 'dynamic' folder for the session.
    """
    validate_csrf(request, request.headers.get("x-csrf-token"))

    try:
        potree_dir = os.path.join(PROCESSED_FOLDER, "potree_dynamic")
        if os.path.exists(potree_dir):
            shutil.rmtree(potree_dir)
        os.makedirs(potree_dir, exist_ok=True)

        files = [
            (metadata_file, "metadata.json"),
            (hierarchy_file, "hierarchy.bin"),
            (octree_file, "octree.bin")
        ]
        if log_file:
            files.append((log_file, "log.txt"))

        for file_obj, target_name in files:
            target_path = os.path.join(potree_dir, target_name)
            await _save_upload_file(file_obj, target_path)

        return {"success": True, "potree_id": "potree_dynamic"}
    except Exception as e:
        print(f"Potree upload error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


__all__ = ['router']

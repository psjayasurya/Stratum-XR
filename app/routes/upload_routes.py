"""
Upload Routes
Handles file upload and file serving endpoints.
"""
from fastapi import APIRouter, File, Form, UploadFile, HTTPException, Request
from fastapi.responses import FileResponse
from typing import Optional
import os
import asyncio

from app.config import UPLOAD_FOLDER, PROCESSED_FOLDER
from app.utils.file_utils import secure_filename
from app.services.kml_parser import extract_kml_data
from app.services.gpr_processor import process_gpr_data, processing_jobs, ExecutorContainer


from app.services.shapefile_parser import extract_shapefile_data
from datetime import datetime
import shutil

# Create router
router = APIRouter(tags=["Upload"])

# Import limiter from shared module
from app.limiter import limiter


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
        Dictionary with job_id and filename
    """
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
    
    # Save main file
    filename = secure_filename(file.filename)
    filepath = os.path.join(UPLOAD_FOLDER, f"{job_id}_{filename}")
    
    with open(filepath, "wb") as buffer:
        content = await file.read()
        buffer.write(content)
    
    # Save pipe file if present
    pipe_filename = None
    if pipe_file and pipe_file.filename:
        pipe_filename = secure_filename(pipe_file.filename)
        pipe_path = os.path.join(UPLOAD_FOLDER, f"{job_id}_{pipe_filename}")
        with open(pipe_path, "wb") as buffer:
            content = await pipe_file.read()
            buffer.write(content)
    
    # Process KML or Shapefile if present
    kml_anchor = None
    kml_polygon = None
    if kml_file and kml_file.filename:
        geo_filename = secure_filename(kml_file.filename)
        geo_path = os.path.join(UPLOAD_FOLDER, f"{job_id}_{geo_filename}")
        with open(geo_path, "wb") as buffer:
            content = await kml_file.read()
            buffer.write(content)
        
        geo_ext = os.path.splitext(geo_filename)[1].lower()
        
        if geo_ext == '.kml':
            kml_data = extract_kml_data(geo_path)
            if kml_data:
                kml_anchor = kml_data['center']
                kml_polygon = kml_data['points']
        elif geo_ext == '.zip':
            shape_data = extract_shapefile_data(geo_path)
            if shape_data:
                kml_anchor = shape_data['center']
                kml_polygon = shape_data['points']
    
    # Create settings dict
    settings = {
        'job_name': job_name,
        'file_format': file_format,
        'col_idx_x': col_idx_x,
        'col_idx_y': col_idx_y,
        'col_idx_z': col_idx_z,
        'col_idx_amplitude': col_idx_amplitude,
        'threshold_percentile': threshold_percentile,
        'iso_bins': iso_bins,
        'depth_offset_per_level': depth_offset_per_level,
        'vr_point_size': vr_point_size,
        'font_size_multiplier': font_size_multiplier,
        'font_family': font_family,
        'invert_depth': invert_depth,
        'center_coordinates': center_coordinates,
        'generate_surface': generate_surface,
        'surface_resolution': surface_resolution,
        'surface_depth_slices': surface_depth_slices,
        'surface_opacity': surface_opacity,
        'generate_amplitude_surface': generate_amplitude_surface,
        'max_points_per_layer': max_points_per_layer,
        'max_points_per_layer': max_points_per_layer,
        'color_palette': color_palette
    }
    
    if pipe_filename:
        settings['pipe_filename'] = pipe_filename
    if kml_anchor:
        settings['kml_anchor'] = kml_anchor
    if kml_polygon:
        settings['kml_polygon'] = kml_polygon
    
    # Initialize job tracking
    processing_jobs[job_id] = {
        'status': 'pending',
        'message': 'Waiting to start...',
        'filename': filename,
        'settings': settings
    }
    
    # Submit to process pool for true parallel execution
    # This bypasses Python's GIL and allows multiple files to process simultaneously
    loop = asyncio.get_running_loop()
    loop.run_in_executor(ExecutorContainer.executor, process_gpr_data, job_id, filepath, settings, filename)
    
    # Record in Database as 'processing'
    try:
        from app.database import get_db
        from datetime import datetime
        import re
        
        # Extract email from job_id: ProjectName-email_id
        email_pattern = r'-([^_]+@[^_]+)(?:_|$)'
        match = re.search(email_pattern, job_id)
        if match:
            user_email = match.group(1)
            conn = get_db()
            cur = conn.cursor()
            
            cur.execute("""
                INSERT INTO processed_jobs (job_id, user_email, job_name, processing_date, status, storage_path)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (job_id) DO UPDATE SET
                    processing_date = EXCLUDED.processing_date,
                    status = 'processing'
            """, (job_id, user_email, job_name, datetime.now(), 'processing', 'pending'))
            
            conn.commit()
            conn.close()
    except Exception as e:
        print(f"Error registering job in DB: {e}")

    return {"job_id": job_id, "filename": filename}


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
    metadata_file: UploadFile = File(...),
    hierarchy_file: UploadFile = File(...),
    octree_file: UploadFile = File(...),
    log_file: Optional[UploadFile] = File(None)
):
    """
    Upload and replace Potree LiDAR files dynamically.
    Saves to a special 'dynamic' folder for the session.
    """
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
            with open(target_path, "wb") as buffer:
                content = await file_obj.read()
                buffer.write(content)

        return {"success": True, "potree_id": "potree_dynamic"}
    except Exception as e:
        print(f"Potree upload error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


__all__ = ['router']

"""
Job Management Routes
Handles job status, viewing, listing, downloading, and cleanup.
"""
from fastapi import APIRouter, Request, HTTPException, Cookie
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse
from typing import Optional
import os
import json
import glob
import zipfile
import shutil
import re

from app.config import PROCESSED_FOLDER, UPLOAD_FOLDER, TEMPLATES_FOLDER
from app.storage import supabase, SUPABASE_BUCKET, get_base_url
from app.services.gpr_processor import processing_jobs
from app.services.viewer_generator import create_vr_viewer
from app.routes.auth_routes import get_current_user
from app.database import get_db
from app.models import SavedViewRequest
from datetime import datetime


# Create router
router = APIRouter(tags=["Jobs"])


@router.get("/status/{job_id}")
async def get_status(job_id: str):
    """
    Get processing status for a job
    
    Args:
        job_id: Job identifier
        
    Returns:
        Status dictionary with processing information
    """
    # Base status from memory (might be just 'pending')
    status = {}
    if job_id in processing_jobs:
        status = processing_jobs[job_id].copy()
    
    # Try to read updated status from disk (written by worker process)
    status_file = os.path.join(PROCESSED_FOLDER, job_id, "status.json")
    if os.path.exists(status_file):
        try:
            with open(status_file, 'r') as f:
                disk_status = json.load(f)
                status.update(disk_status)
        except:
            pass
    
    if not status and not os.path.exists(status_file):
        raise HTTPException(status_code=404, detail="Job not found")
        
    return status


@router.get("/view/{job_id}", response_class=HTMLResponse)
async def view_result(job_id: str):
    """
    View processed result for a single job
    
    Args:
        job_id: Job identifier
        
    Returns:
        HTML response with VR viewer or redirect to Supabase
    """
    output_dir = os.path.join(PROCESSED_FOLDER, job_id)
    if os.path.exists(output_dir) and os.path.exists(os.path.join(output_dir, 'index.html')):
        return FileResponse(os.path.join(output_dir, 'index.html'))
    
    if supabase and SUPABASE_BUCKET:
        public_url = get_base_url(job_id) + "/index.html"
        return RedirectResponse(url=public_url)
    
    raise HTTPException(status_code=404, detail="Job not found")


@router.get("/api/jobs")
async def list_jobs(access_token: Optional[str] = Cookie(None), refresh: bool = False):
    """
    List all jobs for the current user
    
    Args:
        access_token: JWT access token from cookie
        refresh: Force refresh from storage (slow)
        
    Returns:
        List of job dictionaries with id, name, and date
    """
    user = get_current_user(access_token)
    if not user:
        return []

    try:
        conn = get_db()
        cur = conn.cursor()

        # Check if we have cached jobs
        cur.execute("SELECT COUNT(*) FROM processed_jobs WHERE user_email = %s", (user,))
        count_res = cur.fetchone()
        count = count_res[0] if count_res else 0

        # If no jobs found or refresh forced, sync from storage
        if count == 0 or refresh:
            await sync_jobs(user, conn, cur)

        # Fetch from DB
        cur.execute(
            "SELECT job_id, job_name, processing_date FROM processed_jobs WHERE user_email = %s ORDER BY processing_date DESC",
            (user,)
        )
        rows = cur.fetchall()
        
        cur.close()
        conn.close()

        jobs = []
        for row in rows:
            proc_date = row[2]
            date_str = ""
            if isinstance(proc_date, str):
                date_str = proc_date
            elif hasattr(proc_date, 'strftime'):
                date_str = proc_date.strftime("%Y-%m-%d %H:%M:%S")
                
            jobs.append({
                'id': row[0],
                'name': row[1],
                'date': date_str
            })
        
        return jobs
    except Exception as e:
        print(f"Error listing jobs: {e}")
        return []


async def sync_jobs(user: str, conn, cur):
    """Sync jobs from storage to database for a user"""
    print(f"Syncing jobs for user {user}...")
    
    # Pattern to detect email in job ID: anything@anything
    email_pattern = r'-([^_]+@[^_]+)(?:_|$)'
    
    found_jobs = []

    # 1. Sync from Supabase
    if supabase and SUPABASE_BUCKET:
        try:
            res = supabase.storage.from_(SUPABASE_BUCKET).list()
            for item in res:
                name = item.get('name')
                if not name:
                    continue
                
                # Check if job belongs to user
                match = re.search(email_pattern, name)
                if match:
                    job_email = match.group(1)
                    if job_email == user:
                        job_name = name
                        proc_date = datetime.now()
                        
                        try:
                            # Try to get info.json for metadata
                            info_bytes = supabase.storage.from_(SUPABASE_BUCKET).download(f"{name}/info.json")
                            info = json.loads(info_bytes)
                            job_name = info.get('original_filename', name)
                            # Try to parse date if available
                            if info.get('processing_date'):
                                try:
                                    proc_date = datetime.strptime(info.get('processing_date'), "%Y-%m-%d %H:%M:%S")
                                except:
                                    pass
                        except:
                            pass
                            
                        found_jobs.append({
                            'job_id': name,
                            'job_name': job_name,
                            'processing_date': proc_date,
                            'storage_path': 'supabase'
                        })
        except Exception as e:
            print(f"Error syncing Supabase jobs: {e}")

    # 2. Sync from Local Disk
    if os.path.exists(PROCESSED_FOLDER):
        try:
            for dirname in os.listdir(PROCESSED_FOLDER):
                dirpath = os.path.join(PROCESSED_FOLDER, dirname)
                if os.path.isdir(dirpath):
                    match = re.search(email_pattern, dirname)
                    if match:
                        job_email = match.group(1)
                        if job_email == user:
                            info_path = os.path.join(dirpath, 'info.json')
                            job_name = dirname
                            proc_date = datetime.now()
                            
                            if os.path.exists(info_path):
                                try:
                                    with open(info_path, 'r') as f:
                                        info = json.load(f)
                                    job_name = info.get('original_filename', dirname)
                                    if info.get('processing_date'):
                                        try:
                                            proc_date = datetime.strptime(info.get('processing_date'), "%Y-%m-%d %H:%M:%S")
                                        except:
                                            pass
                                except:
                                    pass
                            
                            found_jobs.append({
                                'job_id': dirname,
                                'job_name': job_name,
                                'processing_date': proc_date,
                                'storage_path': 'local'
                            })
        except Exception as e:
            print(f"Error syncing local jobs: {e}")

    # Update DB
    for job in found_jobs:
        try:
            # Upsert
            cur.execute("""
                INSERT INTO processed_jobs (job_id, user_email, job_name, processing_date, storage_path)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (job_id) DO UPDATE SET
                    job_name = EXCLUDED.job_name,
                    processing_date = EXCLUDED.processing_date
            """, (job['job_id'], user, job['job_name'], job['processing_date'], job['storage_path']))
        except Exception as e:
            print(f"Error inserting job {job['job_id']}: {e}")
    
    conn.commit()


@router.get("/view_multi", response_class=HTMLResponse)
async def view_multi(request: Request, jobs: str = "", access_token: Optional[str] = Cookie(None)):
    """
    View multiple jobs together as multi-grid
    
    Args:
        request: FastAPI request
        jobs: Comma-separated list of job IDs
        access_token: JWT access token from cookie
        
    Returns:
        HTML response with multi-grid VR viewer
    """
    user = get_current_user(access_token)
    if not user:
        return RedirectResponse(url="/", status_code=303)
    
    job_ids = [j.strip() for j in jobs.split(',') if j.strip()]
    if not job_ids:
        raise HTTPException(status_code=400, detail="No job IDs provided")
    
    # STRICT filtering - only include jobs belonging to the current user
    # Job naming convention: projectName-userEmail_id
    user_job_ids = []
    
    # Pattern to detect email in job ID: anything@anything before _id
    email_pattern = r'-([^_]+@[^_]+)_'
    
    for jid in job_ids:
        # Check if this job ID contains an email
        match = re.search(email_pattern, jid)
        
        if match:
            # Format with email - check if it matches current user
            job_email = match.group(1)
            if job_email == user:
                user_job_ids.append(jid)
                print(f"✓ Including job {jid} - belongs to user {user}")
            else:
                print(f"✗ Rejecting job {jid} - belongs to different user {job_email}, current user is {user}")
        else:
            # No email in name - REJECT (strict mode)
            print(f"✗ Rejecting job {jid} - no user email found, current user is {user}")
    
    if not user_job_ids:
        raise HTTPException(
            status_code=403, 
            detail=f"No authorized jobs found for user {user}. Only projects with format 'ProjectName-{user}_id' are allowed."
        )
    
    multi_grids = []
    
    for jid in user_job_ids:
        info = None
        ply_files = []
        
        if supabase and SUPABASE_BUCKET:
            try:
                info_bytes = supabase.storage.from_(SUPABASE_BUCKET).download(f"{jid}/info.json")
                info = json.loads(info_bytes)
                files_res = supabase.storage.from_(SUPABASE_BUCKET).list(jid)
                ply_files = [f['name'] for f in files_res if f['name'].startswith('layer_')]
            except:
                pass
        
        if info is None:
            output_dir = os.path.join(PROCESSED_FOLDER, jid)
            info_path = os.path.join(output_dir, 'info.json')
            if os.path.exists(info_path):
                try:
                    with open(info_path, 'r') as f:
                        info = json.load(f)
                    ply_files = [os.path.basename(f) for f in glob.glob(os.path.join(output_dir, "layer_*.ply"))]
                except:
                    pass
        
        if info:
            try:
                def _sort_layers(x):
                    return int(x.split('_')[1].split('.')[0])
                ply_files.sort(key=_sort_layers)
            except:
                ply_files.sort()
            
            bounds = info.get('data_bounds', {'x_min': 0, 'x_max': 10, 'y_min': 0, 'y_max': 10, 'z_min': -5, 'z_max': 0})
            
            grid_entry = {
                'job_id': jid,
                'name': info.get('original_filename', jid),
                'settings': info.get('settings', {}),
                'data_info': {
                    'original_filename': info.get('original_filename', jid),
                    'total_points': info.get('total_points', 0),
                    'x_min': bounds.get('x_min', 0),
                    'x_max': bounds.get('x_max', 10),
                    'y_min': bounds.get('y_min', 0),
                    'y_max': bounds.get('y_max', 10),
                    'z_min': bounds.get('z_min', -5),
                    'z_max': bounds.get('z_max', 0),
                    'amp_min': 0,
                    'amp_max': 1000,
                    'offset_x': info.get('settings', {}).get('offset_x', 0),
                    'offset_y': info.get('settings', {}).get('offset_y', 0),
                    'scale_factor': info.get('settings', {}).get('scale_factor', 1.0),
                    'processing_date': info.get('processing_date', '')
                },
                'ply_files': ply_files,
                'has_surface': info.get('has_surface', False),
                'num_slices': info.get('num_slices', 0),
                'base_url': get_base_url(jid)
            }
            multi_grids.append(grid_entry)
    
    if not multi_grids:
        raise HTTPException(status_code=404, detail="No valid jobs found")
    
    html = create_vr_viewer(
        ply_files=[], layer_info="", legend_info="",
        output_dir="", settings=multi_grids[0]['settings'],
        data_info=multi_grids[0]['data_info'], job_id="",
        multi_grids=multi_grids
    )
    
    return HTMLResponse(content=html)


@router.get("/download/{job_id}")
async def download_result(job_id: str):
    """
    Download all processed files as ZIP
    
    Args:
        job_id: Job identifier
        
    Returns:
        ZIP file response
    """
    output_dir = os.path.join(PROCESSED_FOLDER, job_id)
    if not os.path.exists(output_dir):
        raise HTTPException(status_code=404, detail="Job not found")
    
    zip_path = os.path.join(PROCESSED_FOLDER, f'{job_id}.zip')
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(output_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, output_dir)
                zipf.write(file_path, arcname)
    
    return FileResponse(zip_path, filename=f'gpr_vr_{job_id}.zip', media_type='application/zip')


@router.get("/cleanup/{job_id}")
async def cleanup_job(job_id: str, access_token: Optional[str] = Cookie(None)):
    """
    Cleanup all files for a job (Local and Supabase)
    """
    return await _perform_cleanup(job_id, access_token)


@router.post("/api/cleanup-batch")
async def batch_cleanup_jobs(request: dict, access_token: Optional[str] = Cookie(None)):
    """
    Cleanup multiple jobs at once
    """
    job_ids = request.get("job_ids", [])
    if not job_ids:
        return {"success": False, "message": "No job IDs provided"}
    
    results = []
    for jid in job_ids:
        try:
            await _perform_cleanup(jid, access_token)
            results.append({"job_id": jid, "success": True})
        except Exception as e:
            results.append({"job_id": jid, "success": False, "error": str(e)})
            
    return {"success": True, "results": results}


async def _perform_cleanup(job_id: str, access_token: Optional[str] = Cookie(None)):
    """Internal helper to cleanup a single job"""
    user = get_current_user(access_token)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # STRICT security check - only allow user to delete their own jobs
    if f"-{user}_" not in job_id and not job_id.endswith(f"-{user}"):
        raise HTTPException(status_code=403, detail="Forbidden: You can only delete your own projects")

    # 1. Cleanup Supabase
    if supabase and SUPABASE_BUCKET:
        try:
            file_paths = _list_supabase_files_recursive(job_id)
            if file_paths:
                _remove_supabase_files(file_paths)
        except Exception as e:
            print(f"Error deleting from Supabase: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to delete Supabase files for {job_id}")

    # 2. Cleanup Local Uploads
    upload_pattern = os.path.join(UPLOAD_FOLDER, f"{job_id}_*")
    for f in glob.glob(upload_pattern):
        try: os.remove(f)
        except: pass
    
    # 3. Cleanup Local Processed
    output_dir = os.path.join(PROCESSED_FOLDER, job_id)
    if os.path.exists(output_dir):
        try: shutil.rmtree(output_dir)
        except: pass
    
    # 4. Cleanup Local ZIP
    zip_file = os.path.join(PROCESSED_FOLDER, f'{job_id}.zip')
    if os.path.exists(zip_file):
        try: os.remove(zip_file)
        except: pass
    
    # 5. Remove from in-memory
    if job_id in processing_jobs:
        del processing_jobs[job_id]
        
    # 6. Remove from Database
    try:
        db = get_db()
        cur = db.cursor()
        cur.execute("DELETE FROM processed_jobs WHERE job_id = %s", (job_id,))
        db.commit()
        db.close()
    except Exception as e:
        print(f"Error removing job from DB: {e}")
    
    return {"success": True}


def _list_supabase_files_recursive(prefix: str):
    """Return all file paths under a Supabase storage prefix (recursive)."""
    files = []
    visited_dirs = set()

    def walk(path: str):
        if path in visited_dirs:
            return
        visited_dirs.add(path)

        items = supabase.storage.from_(SUPABASE_BUCKET).list(path) or []
        for item in items:
            name = item.get('name')
            if not name:
                continue

            # Supabase folder entries typically have no id/metadata.
            is_folder = item.get('id') is None and item.get('metadata') is None
            full_path = f"{path}/{name}" if path else name

            if is_folder:
                walk(full_path)
            else:
                files.append(full_path)

    walk(prefix)
    return files


def _remove_supabase_files(file_paths):
    """Delete files from Supabase in safe batches."""
    batch_size = 100
    for i in range(0, len(file_paths), batch_size):
        batch = file_paths[i:i + batch_size]
        supabase.storage.from_(SUPABASE_BUCKET).remove(batch)


# ============ SAVED VIEWS API ============

@router.post("/api/saved-views")
async def save_view(request: SavedViewRequest, access_token: Optional[str] = Cookie(None)):
    """
    Save a new named multi-grid view
    """
    user = get_current_user(access_token)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    job_ids_str = ",".join(request.job_ids)
    
    try:
        db = get_db()
        cur = db.cursor()
        cur.execute(
            "INSERT INTO saved_views (user_email, view_name, job_ids) VALUES (%s, %s, %s)",
            (user, request.name, job_ids_str)
        )
        db.commit()
        db.close()
        return {"success": True}
    except Exception as e:
        print(f"Error saving view: {e}")
        raise HTTPException(status_code=500, detail="Database error")


@router.get("/api/saved-views")
async def list_saved_views(access_token: Optional[str] = Cookie(None)):
    """
    List all saved views for the current user
    """
    user = get_current_user(access_token)
    if not user:
        return []

    try:
        db = get_db()
        cur = db.cursor()
        cur.execute(
            "SELECT id, view_name, job_ids, created_at FROM saved_views WHERE user_email = %s ORDER BY created_at DESC",
            (user,)
        )
        rows = cur.fetchall()
        db.close()
        
        views = []
        for row in rows:
            views.append({
                "id": row[0],
                "name": row[1],
                "job_ids": row[2].split(",") if row[2] else [],
                "job_ids_str": row[2],
                "date": row[3].strftime("%Y-%m-%d %H:%M") if row[3] else ""
            })
        return views
    except Exception as e:
        print(f"Error listing views: {e}")
        return []


@router.delete("/api/saved-views/{view_id}")
async def delete_saved_view(view_id: int, access_token: Optional[str] = Cookie(None)):
    """
    Delete a saved view
    """
    user = get_current_user(access_token)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        db = get_db()
        cur = db.cursor()
        # Ensure user owns the view before deleting
        cur.execute(
            "DELETE FROM saved_views WHERE id = %s AND user_email = %s",
            (view_id, user)
        )
        db.commit()
        db.close()
        return {"success": True}
    except Exception as e:
        print(f"Error deleting view: {e}")
        raise HTTPException(status_code=500, detail="Database error")


@router.get("/api/supabase/meshes")
async def list_supabase_meshes():
    """
    List all .glb files in the Supabase bucket
    """
    if not supabase or not SUPABASE_BUCKET:
        return []
    
    try:
        res = supabase.storage.from_(SUPABASE_BUCKET).list()
        meshes = []
        for item in res:
            name = item.get('name')
            if name and name.lower().endswith('.glb'):
                # Return local proxy URL instead of direct Supabase URL to avoid CORS issues
                proxy_url = f"/api/supabase/mesh/{name}"
                meshes.append({
                    "name": name,
                    "url": proxy_url
                })
        return meshes
    except Exception as e:
        print(f"Error listing Supabase meshes: {e}")
        return []


@router.get("/api/supabase/mesh/{filename}")
async def get_supabase_mesh_proxy(filename: str):
    """
    Proxy glb files from Supabase to avoid CORS issues in Three.js
    """
    if not supabase or not SUPABASE_BUCKET:
        raise HTTPException(status_code=500, detail="Supabase not configured")
    
    try:
        from fastapi import Response
        res = supabase.storage.from_(SUPABASE_BUCKET).download(filename)
        return Response(content=res, media_type="model/gltf-binary")
    except Exception as e:
        print(f"Proxy error for {filename}: {e}")
        raise HTTPException(status_code=404, detail="Mesh file not found in cloud storage")



@router.get("/vr-tutorial", response_class=HTMLResponse)
async def vr_tutorial():
    """
    Serve the VR Controller Tutorial page.
    Standalone page — no auth required (loaded in new tab from VR viewer).
    """
    tutorial_path = os.path.join(TEMPLATES_FOLDER, "vr_tutorial.html")
    if not os.path.exists(tutorial_path):
        raise HTTPException(status_code=404, detail="Tutorial page not found")
    with open(tutorial_path, "r", encoding="utf-8") as f:
        content = f.read()
    return HTMLResponse(content=content)


__all__ = ['router']


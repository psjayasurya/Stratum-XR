"""
Storage Service
Functions for cloud storage operations (Supabase).
"""
import os
import time
import mimetypes
from supabase import create_client, Client
from typing import Optional
from app.config import SUPABASE_URL, SUPABASE_KEY, SUPABASE_BUCKET

EXCLUDED_EXTENSIONS = ('.csv', '.h5', '.hdf', '.hdf5', '.he5')


# Initialize Supabase client
supabase: Optional[Client] = None

if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        print(f"Supabase client initialized with URL: {SUPABASE_URL}")
    except Exception as e:
        print(f"Failed to initialize Supabase client: {e}")
else:
    print("Warning: SUPABASE_URL and SUPABASE_KEY not found in environment variables.")


def get_base_url(job_id: str) -> str:
    """
    Get the base URL for file loading (Supabase or Local)
    
    Args:
        job_id: Job identifier
        
    Returns:
        Base URL string for file access
    """
    if supabase and SUPABASE_BUCKET:
        # URL encode the job_id to handle spaces and special characters
        import urllib.parse
        encoded_job_id = urllib.parse.quote(job_id, safe='')
        # Construct the URL manually to avoid Supabase client adding '?' character
        base_url = f"{SUPABASE_URL}/storage/v1/object/public/{SUPABASE_BUCKET}/{encoded_job_id}"
        return base_url
    else:
        return f'/files/{job_id}'


def upload_files_to_supabase(job_id: str, local_dir: str) -> bool:
    """
    Upload all files in the local directory to Supabase
    
    Args:
        job_id: Job identifier
        local_dir: Local directory path containing files to upload
        
    Returns:
        True if all files uploaded successfully, False otherwise
    """
    if not supabase:
        return False
        
    print(f"Uploading files for job {job_id} to Supabase bucket '{SUPABASE_BUCKET}'...")
    success_count = 0
    fail_count = 0
    
    try:
        from concurrent.futures import ThreadPoolExecutor, as_completed

        files_to_upload = []
        for root, dirs, files in os.walk(local_dir):
            for filename in files:
                if filename.lower().endswith(EXCLUDED_EXTENSIONS):
                    print(f"Skipping upload of {filename}")
                    continue

                file_path = os.path.join(root, filename)
                rel_path = os.path.relpath(file_path, local_dir)
                storage_path = f"{job_id}/{rel_path}".replace("\\", "/")
                
                mime_type, _ = mimetypes.guess_type(file_path)
                if not mime_type:
                    mime_type = 'application/octet-stream'
                
                files_to_upload.append((file_path, storage_path, mime_type, rel_path))

        def upload_single_file(args):
            f_path, s_path, m_type, r_path = args
            max_retries = 5
            for attempt in range(max_retries):
                try:
                    with open(f_path, 'rb') as f:
                        # print(f"  -> Uploading {r_path}...")
                        supabase.storage.from_(SUPABASE_BUCKET).upload(
                            path=s_path,
                            file=f,
                            file_options={"content-type": m_type, "upsert": "true"}
                        )
                    return True
                except Exception as e:
                    # print(f"  !! Failed {r_path}: {e}")
                    if attempt < max_retries - 1:
                        time.sleep(1 + attempt)
                        # Try update on retry
                        try:
                            with open(f_path, 'rb') as f:
                                supabase.storage.from_(SUPABASE_BUCKET).update(
                                    path=s_path,
                                    file=f,
                                    file_options={"content-type": m_type, "upsert": "true"}
                                )
                            return True
                        except:
                            continue
            print(f"Failed to upload {r_path} after retries")
            return False

        print(f"Uploading {len(files_to_upload)} files with parallel threads...")
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_file = {executor.submit(upload_single_file, f): f for f in files_to_upload}
            for future in as_completed(future_to_file):
                if future.result():
                    success_count += 1
                else:
                    fail_count += 1
                        
        print(f"Supabase sync complete: {success_count} succeeded, {fail_count} failed.")
        return success_count > 0 and fail_count == 0
    except Exception as e:
        print(f"Error during Supabase sync loop: {e}")
        return False


__all__ = ['supabase', 'get_base_url', 'upload_files_to_supabase']

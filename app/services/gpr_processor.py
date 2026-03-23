"""
GPR Data Processor Service
Core GPR data processing logic,  PLY generation, and viewer creation.
"""
import os
import json
import time
import shutil
import threading
import pandas as pd
import numpy as np
from typing import Dict, Any
from datetime import datetime

from app.config import UPLOAD_FOLDER, PROCESSED_FOLDER, COLOR_PALETTES
from app.utils.colors import get_color_from_palette
from app.services.ply_generator import write_ply_fast
from app.services.viewer_generator import create_vr_viewer
from app.storage import supabase, upload_files_to_supabase, get_base_url
from app.services.iso_mesher import generate_isosurface
from app.services.slice_generator import generate_depth_slices


# Use a container class to avoid global declaration issues
class ExecutorContainer:
    """Container for process pool executor"""
    executor = None


# Job status tracking with thread-safe access
processing_jobs: Dict[str, Dict[str, Any]] = {}
jobs_lock = threading.Lock()


def update_job_status(job_id, status, message=None, **kwargs):
    """
    Update job status by writing to a JSON file (safe for multiprocessing)
    
    Args:
        job_id: Job identifier
        status: Job status string (processing, completed, error)
        message: Optional status message
        **kwargs: Additional data to store in status
    """
    output_dir = os.path.join(PROCESSED_FOLDER, job_id)
    if not os.path.exists(output_dir):
        try:
            os.makedirs(output_dir)
        except OSError:
            pass  # Already exists

    status_file = os.path.join(output_dir, "status.json")
    
    # Read existing status if possible to preserve data
    current_status = {}
    if os.path.exists(status_file):
        try:
            with open(status_file, 'r') as f:
                current_status = json.load(f)
        except Exception:
            pass
    
    # Update fields
    current_status['status'] = status
    if message:
        current_status['message'] = message
    
    # Update any other kwargs
    for k, v in kwargs.items():
        if k == 'settings':  # Don't overwrite settings if already there unless needed
            current_status[k] = v
        else:
            current_status[k] = v
        
    current_status['updated_at'] = time.time()
    
    # Write back
    try:
        with open(status_file, 'w') as f:
            json.dump(current_status, f)
    except Exception as e:
        print(f"Error writing status file for {job_id}: {e}")


def process_gpr_data(job_id, filepath, settings, original_filename):
    """
    Process GPR data (runs in background process)
    
    Args:
        job_id: Unique job identifier
        filepath: Path to input data file
        settings: Processing settings dictionary
        original_filename: Original name of the uploaded file
    """
    try:
        file_format = settings.get('file_format', 'csv')
        # Initialize status file
        update_job_status(job_id, 'processing', f'Loading {file_format.upper()} file...', settings=settings, filename=original_filename)
        
        print(f"Processing job {job_id}: {original_filename}")
        print(f"Using color palette: {settings['color_palette']}")
        
        output_dir = os.path.join(PROCESSED_FOLDER, job_id)
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        if settings.get('pipe_filename'):
            src = os.path.join(UPLOAD_FOLDER, f"{job_id}_{settings['pipe_filename']}")
            dst = os.path.join(output_dir, settings['pipe_filename'])
            if os.path.exists(src):
                shutil.copy(src, dst)
        
        # Original file explicitly NOT copied to output directory to save space/bandwidth
        # and to prevent it from being uploaded to Supabase or kept in processed folder.
        # if os.path.exists(filepath):
        #     shutil.copy(filepath, os.path.join(output_dir, original_filename))

        update_job_status(job_id, 'processing', 'Detecting file encoding...')
        df = None
        
        if file_format == 'hdf':
            try:
                # Verify file signature
                with open(filepath, 'rb') as f_bin:
                    signature = f_bin.read(4)
                
                if signature == b'\x0e\x03\x13\x01':
                    print("HDF4 detected, using GDAL fallback")
                    import subprocess
                    import tempfile
                    
                    # 1. Get band count using gdalinfo
                    info_res = subprocess.run(['gdalinfo', filepath], capture_output=True, text=True)
                    if info_res.returncode != 0:
                        raise Exception(f"gdalinfo failed: {info_res.stderr}")
                    
                    band_count = 0
                    for line in info_res.stdout.splitlines():
                        if line.strip().startswith('Band '):
                            try:
                                b_num = int(line.split()[1])
                                band_count = max(band_count, b_num)
                            except: pass
                    
                    if band_count == 0:
                        raise Exception("HDF4 file detected but no bands found via GDAL.")
                    
                    update_job_status(job_id, 'processing', f'Extracting {band_count} bands from HDF4...')
                    
                    all_dfs = []
                    # 2. Iterate through bands and extract to XYZ format
                    for i in range(1, band_count + 1):
                        with tempfile.NamedTemporaryFile(suffix='.xyz', delete=False) as tmp:
                            tmp_name = tmp.name
                        
                        try:
                            # Extract band to XYZ (X Y Val)
                            sub_res = subprocess.run(['gdal_translate', '-b', str(i), '-of', 'XYZ', filepath, tmp_name], capture_output=True)
                            if sub_res.returncode != 0:
                                print(f"Warning: Failed to extract band {i}: {sub_res.stderr}")
                                continue
                            
                            # Read XYZ format (space separated)
                            df_b = pd.read_csv(tmp_name, sep=' ', header=None, names=['x', 'y', 'amp'])
                            df_b['y'] = -df_b['y']  # Invert Y to fix "reverse position" (Image Y vs Spatial Y)
                            df_b['z'] = (band_count - i + 1)  # Use reversed band index as depth axis
                            all_dfs.append(df_b)
                        finally:
                            if os.path.exists(tmp_name):
                                try: os.remove(tmp_name)
                                except: pass
                    
                    if not all_dfs:
                        raise Exception("HDF4 extraction failed: No data could be retrieved.")
                    
                    # Combine all bands into one DataFrame
                    df = pd.concat(all_dfs, ignore_index=True)
                    
                    # Automatically map columns to what we just generated
                    # Produced columns are: x (0), y (1), amp (2), z (3)
                    settings['col_idx_x'] = 0
                    settings['col_idx_y'] = 1
                    settings['col_idx_z'] = 3
                    settings['col_idx_amplitude'] = 2
                    
                    print(f"Successfully loaded HDF4 data: {len(df)} points")
                
                # 3. If not HDF4 or signature check didn't catch it, try HDF5 (pandas/h5py)
                else:
                    # Try pandas first (works for files created with pd.to_hdf)
                    try:
                        df = pd.read_hdf(filepath)
                        print("Read HDF using pandas")
                    except Exception as pd_err:
                        print(f"Pandas HDF read failed, trying h5py: {pd_err}")
                        # Try raw HDF5 via h5py
                        import h5py
                        with h5py.File(filepath, 'r') as h5f:
                            # Helper to find datasets recursively
                            def get_datasets(group):
                                ds_list = []
                                for name, item in group.items():
                                    if isinstance(item, h5py.Dataset):
                                        ds_list.append(item)
                                    elif isinstance(item, h5py.Group):
                                        ds_list.extend(get_datasets(item))
                                return ds_list
                            
                            all_datasets = get_datasets(h5f)
                            if not all_datasets:
                                raise Exception("No datasets found in HDF5 file")
                            
                            # Pick the largest dataset
                            target_ds = sorted(all_datasets, key=lambda x: x.size, reverse=True)[0]
                            raw_data = target_ds[:]
                            
                            if raw_data.ndim == 2:
                                df = pd.DataFrame(raw_data)
                            elif raw_data.ndim == 1:
                                # Might be a structured array
                                df = pd.DataFrame(raw_data)
                            else:
                                # Flatten higher dimensions to 2D
                                df = pd.DataFrame(raw_data.reshape(-1, raw_data.shape[-1]))
                            print(f"Read HDF using h5py, dataset: {target_ds.name}")
                
                if df is None or len(df) == 0:
                    raise Exception("No data could be extracted from the HDF file")
                
                print(f"Successfully loaded HDF data: {len(df)} rows")
            except Exception as e:
                print(f"Failed to read HDF: {e}")
                update_job_status(job_id, 'error', f'HDF loading failed: {str(e)}')
                return
        else:
            # Optimized CSV reading: try pyarrow first (fastest), then fallback to encoding detection
            df = None
            try:
                # Try pyarrow engine first (significantly faster)
                df = pd.read_csv(filepath, engine='pyarrow')
                print("Successfully read CSV with pyarrow engine")
            except:
                # If pyarrow not available, try encodings with encoding_errors='ignore' (single read)
                try:
                    df = pd.read_csv(filepath, encoding='utf-8', encoding_errors='ignore')
                    print("Successfully read CSV with utf-8 (ignoring errors)")
                except Exception as e:
                    print(f"UTF-8 failed, trying latin1: {e}")
                    try:
                        df = pd.read_csv(filepath, encoding='latin1')
                        print("Successfully read with latin1 encoding")
                    except Exception as e2:
                        print(f"Latin1 failed, trying with all encoding errors ignored")
                        try:
                            df = pd.read_csv(filepath, encoding_errors='ignore')
                            print("Read with all encoding errors ignored")
                        except Exception as e3:
                            update_job_status(job_id, 'error', f'Failed to read CSV file: {str(e3)}')
                            return
        
        update_job_status(job_id, 'processing', f'Found {len(df):,} rows, processing...')
        
        if len(df.columns) <= max(settings['col_idx_x'], settings['col_idx_y'], 
                                 settings['col_idx_z'], settings['col_idx_amplitude']):
            update_job_status(job_id, 'error', f'CSV file has only {len(df.columns)} columns')
            return
        
        # OPTIMIZATION: Convert all numeric columns in a single operation (5-10x faster)
        col_indices = [settings['col_idx_x'], settings['col_idx_y'], 
                       settings['col_idx_z'], settings['col_idx_amplitude']]
        cols_data = df.iloc[:, col_indices].apply(pd.to_numeric, errors='coerce')
        
        data = pd.DataFrame({
            'x': cols_data.iloc[:, 0],
            'y': cols_data.iloc[:, 1],
            'z': cols_data.iloc[:, 2],
            'amp': cols_data.iloc[:, 3]
        }).dropna()
        
        if len(data) == 0:
            update_job_status(job_id, 'error', 'No valid numeric data found in specified columns')
            return
        
        if settings['invert_depth']:
            data['z'] = -data['z'].abs()
        
        x_c, y_c = 0.0, 0.0
        if settings['center_coordinates']:
            x_c, y_c = data['x'].mean(), data['y'].mean()
            data['x'] -= x_c
            data['y'] -= y_c
        
        max_range = max(data['x'].max()-data['x'].min(), data['y'].max()-data['y'].min())
        sf = 1.0
        if max_range > 50:
            sf = 10 / max_range
            data['x'] *= sf
            data['y'] *= sf
            data['z'] *= sf
        
        data['abs_amp'] = data['amp'].abs()
        threshold = data['abs_amp'].quantile(settings['threshold_percentile'])
        df_filtered = data[data['abs_amp'] > threshold].copy()
        
        if len(df_filtered) == 0:
            update_job_status(job_id, 'error', 'No points after filtering!')
            return
        
        # OPTIMIZATION: Apply early point sampling for large datasets (before layer/surface generation)
        # This significantly speeds up processing without affecting visual quality
        MAX_POINTS_FOR_PROCESSING = 500000
        if len(df_filtered) > MAX_POINTS_FOR_PROCESSING:
            sample_rate = MAX_POINTS_FOR_PROCESSING / len(df_filtered)
            df_filtered = df_filtered.sample(frac=sample_rate, random_state=42).reset_index(drop=True)
            print(f"Sampled data to {len(df_filtered)} points for faster processing")
        
        amp_min = df_filtered['abs_amp'].min()
        amp_max = df_filtered['abs_amp'].max()
        
        data_bounds = {
            'x_min': float(df_filtered['x'].min()),
            'x_max': float(df_filtered['x'].max()),
            'y_min': float(df_filtered['y'].min()),
            'y_max': float(df_filtered['y'].max()),
            'z_min': float(df_filtered['z'].min()),
            'z_max': float(df_filtered['z'].max())
        }
        
        surface_info = None
        num_slices = 0
        
        update_job_status(job_id, 'processing', 'Generating automatic 2D Depth Slices...')
        try:
            num_slices = generate_depth_slices(df_filtered, output_dir, max_slices=20)
            print(f"Generated {num_slices} completely automatic 2D depth slices!")
        except Exception as e:
            print(f"Warning: automatic slice generation failed: {e}")
        
        update_job_status(job_id, 'processing', 'Creating amplitude layers...')
        try:
            df_filtered['iso_range'] = pd.qcut(df_filtered['abs_amp'], settings['iso_bins'], labels=False, duplicates='drop')
        except:
            df_filtered['iso_range'] = pd.cut(df_filtered['abs_amp'], bins=settings['iso_bins'], labels=False)
        
        actual_bins = df_filtered['iso_range'].nunique()
        
        ply_files = []
        layer_info_html = ""
        legend_html = ""
        amplitude_ranges = []
        total_output_points = 0
        cesium_layers = []
        
        palette_name = settings.get('color_palette', 'Viridis')
        palette_colors = COLOR_PALETTES.get(palette_name, COLOR_PALETTES['Viridis'])
        
        gradient_colors = [f"rgb({col[0]},{col[1]},{col[2]})" for col in palette_colors]
        gradient_str = f"linear-gradient(to right, {', '.join(gradient_colors)})"
        
        legend_html = f'''
        <div style="margin-bottom:10px;">
            <div style="height:15px; width:100%; background:{gradient_str}; border-radius:3px; border:1px solid #555;"></div>
            <div style="display:flex; justify-content:space-between; font-size:10px; color:#ccc; margin-top:2px;">
                <span>{amp_min:.0f}</span>
                <span>{amp_max:.0f}</span>
            </div>
        </div>
        '''
        
        # Layer offset for standard layers
        layer_idx_offset = 0
        
        # Parallel PLY Generation
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        def process_layer(iso_level, offset_idx):
            iso_data = df_filtered[df_filtered['iso_range'] == iso_level]
            if len(iso_data) == 0:
                return None
            
            if len(iso_data) > settings['max_points_per_layer']:
                iso_data = iso_data.sample(n=settings['max_points_per_layer'], random_state=42)
            
            x = iso_data['x'].values
            y = iso_data['y'].values
            z = iso_data['z'].values
            
            color = get_color_from_palette(iso_level, palette_name)
            colors = np.full((len(iso_data), 3), color)
            points = np.column_stack((x, y, z))
            
            iso_min, iso_max = iso_data['abs_amp'].min(), iso_data['abs_amp'].max()
            filename = f"layer_{iso_level+1}.ply"
            current_layer_idx = iso_level + offset_idx
            
            filepath_ply = os.path.join(output_dir, filename)
            write_ply_fast(filepath_ply, points, colors)
            
            color_hex = '#{:02x}{:02x}{:02x}'.format(*color)
            
            return {
                'filepath': filepath_ply,
                'min': float(iso_min), 
                'max': float(iso_max),
                'count': len(iso_data),
                'filename': filename,
                'color_hex': color_hex,
                'level': iso_level,
                'idx': current_layer_idx
            }

        update_job_status(job_id, 'processing', f'Generating {actual_bins} layers in parallel...')
        
        # Run parallel generation
        with ThreadPoolExecutor(max_workers=min(actual_bins, 8)) as executor:
            future_to_layer = {
                executor.submit(process_layer, iso, layer_idx_offset): iso 
                for iso in range(actual_bins)
            }
            
            results = []
            for future in as_completed(future_to_layer):
                try:
                    res = future.result()
                    if res:
                        results.append(res)
                except Exception as e:
                    print(f"Layer generation failed: {e}")

        # Sort results by level to maintain order in UI
        results.sort(key=lambda x: x['level'])
        
        for res in results:
            ply_files.append(res['filepath'])
            amplitude_ranges.append((res['min'], res['max']))
            total_output_points += res['count']
            
            cesium_layers.append({'filename': res['filename'], 'color': res['color_hex']})
            
            layer_info_html += f'''
            <div class="layer-item">
                <input type="checkbox" id="layer_cb_{res['idx']}" checked onchange="toggleLayer({res['idx']}, this.checked)">
                <label for="layer_cb_{res['idx']}" class="layer-label">
                    <span class="color-swatch" style="background:{res['color_hex']}"></span>
                    L{res['level']+1}: {res['min']:.0f}-{res['max']:.0f}
                </label>
            </div>'''
            
            legend_html += f'''
            <div class="legend-item">
                <span class="legend-color" style="background:{res['color_hex']}"></span>
            </div>'''
        
        # --- NEW: SURFACE GENERATION ---
        has_generated_surface = False
        surface_file = None
        
        # User wants "real surface" -> Generate isosurface for high amplitude regions
        # Use a high threshold (e.g. 70th percentile of filtered data)
        # This merges "bubbles" into a smooth mesh
        if len(df_filtered) > 100:
            update_job_status(job_id, 'processing', 'Generating smooth surface mesh...')
            # Use a slightly lower threshold to capture more volume (40th percentile of already-filtered high-amp points)
            # This ensures we get a nice merged shape instead of sparse blobs
            surface_threshold = df_filtered['abs_amp'].quantile(0.4) 
            
            surface_file = "surface.obj"
            surface_path = os.path.join(output_dir, surface_file)
            
            print(f"Generating surface at threshold {surface_threshold:.2f} (40th percentile of filtered data)...")
            if generate_isosurface(df_filtered, surface_path, surface_threshold):
                has_generated_surface = True
                print(f"Surface generated: {surface_path}")
            else:
                print("Surface generation returned False (empty or error)")
        
        update_job_status(job_id, 'processing', 'Creating VR viewer...')
        
        data_info = {
            'original_filename': original_filename,
            'total_points': total_output_points,
            'x_min': data_bounds['x_min'],
            'x_max': data_bounds['x_max'],
            'y_min': data_bounds['y_min'],
            'y_max': data_bounds['y_max'],
            'z_min': data_bounds['z_min'],
            'z_max': data_bounds['z_max'],
            'amp_min': float(amp_min),
            'amp_max': float(amp_max),
            'offset_x': float(x_c),
            'offset_y': float(y_c),
            'scale_factor': float(sf),
            'processing_date': time.strftime('%Y-%m-%d %H:%M:%S')
        }
        
        total_files = len(ply_files)
        if settings.get('generate_surface'):
            total_files += 1
        if num_slices > 0:
            total_files += num_slices
        if settings.get('pipe_filename'):
            total_files += 1
        
        cesium_data_obj = {'job_id': job_id, 'ply_files': cesium_layers}

        create_vr_viewer(
            ply_files, layer_info_html, legend_html, output_dir, settings, data_info, job_id,
            cesium_data=cesium_data_obj,
            has_surface=has_generated_surface,
            surface_info={'filename': surface_file} if has_generated_surface else None,
            num_slices=num_slices,
            total_files=total_files,
            pipe_file=settings.get('pipe_filename')
        )
        
        info_data = {
            'original_filename': original_filename,
            'total_points': total_output_points,
            'layers': actual_bins,
            'has_surface': has_generated_surface,
            'surface_file': surface_file if has_generated_surface else None,
            'num_slices': num_slices,
            'data_bounds': data_bounds,
            'settings': settings,
            'processing_date': data_info['processing_date']
        }
        with open(os.path.join(output_dir, 'info.json'), 'w', encoding='utf-8') as f:
            json.dump(info_data, f, indent=2)
        
        update_job_status(job_id, 'completed', 'Processing complete!', output_dir=job_id)
        print(f"Job {job_id} completed successfully")
        
        if supabase:
            update_job_status(job_id, 'processing', 'Uploading results to cloud storage...')
            success = upload_files_to_supabase(job_id, output_dir)
            
            if success:
                public_url = get_base_url(job_id) + "/index.html"
                data_info['public_url'] = public_url
                update_job_status(job_id, 'completed', public_url=public_url)
                
                try:
                    # Cleanup heavy files but keep status.json
                    for f in os.listdir(output_dir):
                        if f != 'status.json':
                            path = os.path.join(output_dir, f)
                            if os.path.isdir(path):
                                shutil.rmtree(path)
                            else:
                                os.remove(path)
                    print(f"Cleaned up local directory {output_dir}")
                except Exception as e:
                    print(f"Warning: Failed to cleanup local files: {e}")
            else:
                update_job_status(job_id, 'completed', 'Upload failed, keeping local files.')
        
        # Final status update with full info
        update_job_status(job_id, 'completed', 'Processing complete!', output_dir=job_id, data_info=data_info)
        print(f"Job {job_id} completed successfully")
        
        # Update Database Status
        try:
            from app.database import get_db
            import re
            
            # Extract email
            email_pattern = r'-([^_]+@[^_]+)(?:_|$)'
            match = re.search(email_pattern, job_id)
            if match:
                user_email = match.group(1)
                conn = get_db()
                cur = conn.cursor()
                
                storage_path = 'supabase' if supabase and data_info.get('public_url') else 'local'
                
                # Upsert - careful not to overwrite create date if possible, but actually we want completion date maybe?
                # The user wants listed by date. Usually create date is better. But here we have processing_date in DB.
                # Let's keep processing_date as "last updated" or completion time.
                
                # Update status and storage path, preserve job_name if possible or update from settings
                final_name = settings.get('job_name', original_filename)
                
                cur.execute("""
                    UPDATE processed_jobs 
                    SET status = 'completed', 
                        storage_path = %s,
                        job_name = %s
                    WHERE job_id = %s
                """, (storage_path, final_name, job_id))
                
                conn.commit()
                conn.close()
        except Exception as e:
            print(f"Error updating job status in DB: {e}")
        
    except Exception as e:
        print(f"Error processing job {job_id}: {e}")
        import traceback
        traceback.print_exc()
        update_job_status(job_id, 'error', f'Error: {str(e)}')

    finally:
        # Cleanup the source file from uploads directory
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
                print(f"Cleaned up source file from uploads: {filepath}")
            except Exception as e:
                print(f"Warning: Failed to cleanup source file {filepath}: {e}")


__all__ = ['ExecutorContainer', 'processing_jobs', 'jobs_lock', 'update_job_status', 'process_gpr_data']

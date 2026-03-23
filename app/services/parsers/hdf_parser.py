
import os
import pandas as pd
import numpy as np
import tempfile
import subprocess
from typing import Dict, Any
from .base import DataParser

class HDFDataParser(DataParser):
    """Parser for HDF4/HDF5 GPR data files."""

    def parse(self, filepath: str, settings: Dict[str, Any]) -> pd.DataFrame:
        """
        Parse HDF file, attempting HDF4 (GDAL) then HDF5 (pandas/h5py).
        """
        try:
            # check for HDF4 signature
            with open(filepath, 'rb') as f_bin:
                signature = f_bin.read(4)
            
            if signature == b'\x0e\x03\x13\x01':
                print("HDF4 detected, using GDAL fallback")
                return self._parse_hdf4_gdal(filepath, settings)
            else:
                return self._parse_hdf5(filepath, settings)
        except Exception as e:
            raise ValueError(f"HDF parsing failed: {str(e)}")

    def _parse_hdf4_gdal(self, filepath: str, settings: Dict[str, Any]) -> pd.DataFrame:
        import subprocess
        
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
        
        print(f"Extracting {band_count} bands from HDF4...")
        
        all_dfs = []
        # 2. Iterate through bands and extract to XYZ format
        for i in range(1, band_count + 1):
            with tempfile.NamedTemporaryFile(suffix='.xyz', delete=False) as tmp:
                tmp_name = tmp.name
            
            try:
                # Extract band to XYZ (X Y Val)
                # Use absolute path to gdal_translate if needed, assuming user has it in PATH
                sub_res = subprocess.run(['gdal_translate', '-b', str(i), '-of', 'XYZ', filepath, tmp_name], capture_output=True)
                if sub_res.returncode != 0:
                    print(f"Warning: Failed to extract band {i}: {sub_res.stderr}")
                    continue
                
                # Check if file has content
                if os.path.getsize(tmp_name) == 0:
                     continue

                # Read XYZ format (space separated)
                try:
                    df_b = pd.read_csv(tmp_name, sep=' ', header=None, names=['x', 'y', 'amp'])
                    df_b['y'] = -df_b['y']  # Invert Y to fix "reverse position" (Image Y vs Spatial Y)
                    df_b['z'] = (band_count - i + 1)  # Use reversed band index as depth axis
                    all_dfs.append(df_b)
                except pd.errors.EmptyDataError:
                    continue

            finally:
                if os.path.exists(tmp_name):
                    try: os.remove(tmp_name)
                    except: pass
        
        if not all_dfs:
            raise Exception("HDF4 extraction failed: No data could be retrieved.")
        
        # Combine all bands into one DataFrame
        df = pd.concat(all_dfs, ignore_index=True)
        
        # Update settings to map to these generated columns
        settings['col_idx_x'] = 0
        settings['col_idx_y'] = 1
        settings['col_idx_z'] = 3 # our new 'z' column
        settings['col_idx_amplitude'] = 2
        
        # We need to return a standardized dataframe with x, y, z, amp columns
        # Since we just created it with those names, we can return it directly
        return df[['x', 'y', 'z', 'amp']]

    def _parse_hdf5(self, filepath: str, settings: Dict[str, Any]) -> pd.DataFrame:
        df = None
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
                
                # Pick the largest dataset strategy
                target_ds = sorted(all_datasets, key=lambda x: x.size, reverse=True)[0]
                raw_data = target_ds[:]
                
                if raw_data.ndim == 2:
                    df = pd.DataFrame(raw_data)
                elif raw_data.ndim == 1:
                    df = pd.DataFrame(raw_data)
                else:
                    # Flatten higher dimensions to 2D
                    df = pd.DataFrame(raw_data.reshape(-1, raw_data.shape[-1]))
                print(f"Read HDF using h5py, dataset: {target_ds.name}")
        
        if df is None or len(df) == 0:
             raise Exception("No data could be extracted from the HDF file")
             
        # Map columns based on settings
        required_idx = max(
            settings.get('col_idx_x', 0),
            settings.get('col_idx_y', 1), 
            settings.get('col_idx_z', 2),
            settings.get('col_idx_amplitude', 3)
        )
        
        if len(df.columns) <= required_idx:
             raise ValueError(f"HDF5 file has only {len(df.columns)} columns, but index {required_idx} is required.")
             
        raw_x = pd.to_numeric(df.iloc[:, settings.get('col_idx_x', 0)], errors='coerce')
        raw_y = pd.to_numeric(df.iloc[:, settings.get('col_idx_y', 1)], errors='coerce')
        raw_z = pd.to_numeric(df.iloc[:, settings.get('col_idx_z', 2)], errors='coerce')
        raw_amp = pd.to_numeric(df.iloc[:, settings.get('col_idx_amplitude', 3)], errors='coerce')
        
        return pd.DataFrame({
            'x': raw_x, 'y': raw_y, 'z': raw_z, 'amp': raw_amp
        }).dropna()

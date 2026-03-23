
import numpy as np
import os
from skimage.measure import marching_cubes
from scipy.stats import binned_statistic_dd
from scipy.ndimage import gaussian_filter

def generate_isosurface(df, output_path, threshold, resolution=128):
    """
    Generate an isosurface mesh from point cloud data using Marching Cubes.
    
    Args:
        df: DataFrame with x, y, z, abs_amp columns
        output_path: Path to write the OBJ file
        threshold: Iso-surface threshold value
        resolution: Grid resolution (max dimension)
    """
    try:
        # Extract coordinates and values
        x = df['x'].values
        y = df['y'].values
        z = df['z'].values
        amp = df['abs_amp'].values
        
        if len(x) < 100:
            return False

        # Determine bounds with padding
        x_min, x_max = x.min(), x.max()
        y_min, y_max = y.min(), y.max()
        z_min, z_max = z.min(), z.max()
        
        # Calculate aspect ratio for grid resolution
        # Avoid creating huge grids for flat datasets
        dims = np.array([x_max - x_min, y_max - y_min, z_max - z_min])
        max_dim = dims.max()
        if max_dim == 0: max_dim = 1.0
        
        res_x = int(resolution * (dims[0] / max_dim))
        res_y = int(resolution * (dims[1] / max_dim))
        res_z = int(resolution * (dims[2] / max_dim))
        
        # Clamp minimum resolution
        res_x = max(10, res_x)
        res_y = max(10, res_y)
        res_z = max(10, res_z)
        
        print(f"Generating surface grid: {res_x}x{res_y}x{res_z}")
        
        # bin the data into a 3D grid
        statistic, edges, bn = binned_statistic_dd(
            [x, y, z], amp, statistic='mean', 
            bins=[res_x, res_y, res_z],
            range=[[x_min, x_max], [y_min, y_max], [z_min, z_max]]
        )
        
        # Fill empty voxels with 0
        volume = np.nan_to_num(statistic, nan=0.0)
        
        # Smooth volume to create organic, "merged" shapes
        volume = gaussian_filter(volume, sigma=1.0)
        
        # Check threshold validity
        v_min, v_max = volume.min(), volume.max()
        print(f"Volume range: {v_min:.4f} to {v_max:.4f}, Threshold: {threshold:.4f}")
        
        if threshold < v_min or threshold > v_max:
            print("Threshold outside volume range. Adjusting...")
            # Clamp to safe range (e.g. 10% to 90%)
            # If threshold is too high, lower it to 90% of max
            if threshold > v_max:
                threshold = v_max * 0.95
            
            # If threshold is too low (below noise), raise it, but usually inputs are filtered.
            if threshold < v_min:
                threshold = v_min + (v_max - v_min) * 0.1
                
            print(f"Adjusted Threshold: {threshold:.4f}")

        # Marching Cubes
        verts, faces, normals, values = marching_cubes(volume, level=threshold)
        
        # Transform transform grid coords back to world coords
        # verts are in range [0, res-1]
        
        # Get edges (step sizes)
        # binned_statistic_dd edges are len(bins)+1
        x_edges = edges[0]
        y_edges = edges[1]
        z_edges = edges[2]
        
        # We can implement simple linear scaling
        # vert[0] corresponds to index in x dimension
        # position = min + (val / (res-1)) * len?
        # Actually marching_cubes returns float coords matching the volume index directly
        
        # X mapping
        x_step = (x_max - x_min) / res_x
        verts[:, 0] = x_min + verts[:, 0] * x_step
        
        # Y mapping
        y_step = (y_max - y_min) / res_y
        verts[:, 1] = y_min + verts[:, 1] * y_step
        
        # Z mapping
        z_step = (z_max - z_min) / res_z
        verts[:, 2] = z_min + verts[:, 2] * z_step
        
        # Write OBJ File
        with open(output_path, 'w') as f:
            f.write(f"# GPR Isosurface (Threshold: {threshold})\n")
            for v in verts:
                f.write(f"v {v[0]:.4f} {v[1]:.4f} {v[2]:.4f}\n")
            for n in normals:
                f.write(f"vn {n[0]:.4f} {n[1]:.4f} {n[2]:.4f}\n")
            for face in faces:
                # OBJ is 1-indexed
                f.write(f"f {face[0]+1}//{face[0]+1} {face[1]+1}//{face[1]+1} {face[2]+1}//{face[2]+1}\n")
                
        return True
        
    except Exception as e:
        print(f"Surface generation error: {e}")
        import traceback
        traceback.print_exc()
        return False

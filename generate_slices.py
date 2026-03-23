import pandas as pd
import numpy as np
from PIL import Image
from scipy.interpolate import griddata
import os
import sys

def generate_slices(csv_path, output_dir):
    print(f"Loading {csv_path}...")
    # Load CSV, handling any weird encoding in headers
    try:
        df = pd.read_csv(csv_path, engine='pyarrow')
        print("Read CSV with pyarrow engine")
    except:
        df = pd.read_csv(csv_path, encoding='utf-8', encoding_errors='replace')
        print("Read CSV with utf-8 (errors ignored)")
    
    # The columns might have strange characters like 'X  0.0250m'. Let's clean up column names.
    df.columns = [c.encode('ascii', 'ignore').decode('ascii').strip() for c in df.columns]
    cols = df.columns.tolist()
    
    # Assume standard GPR export format: 
    # Col 0: X, Col 1: Y, Col 6: Z or Col 7: Depth, Col 8: Amplitude
    # Let's dynamically map based on keywords to be safe
    x_col = next((c for c in cols if 'X' in c.upper() or 'EAST' in c.upper()), cols[0])
    y_col = next((c for c in cols if 'Y' in c.upper() or 'NORTH' in c.upper()), cols[1])
    depth_col = next((c for c in cols if 'DEPTH' in c.upper()), cols[7] if len(cols) > 7 else cols[-2])
    amp_col = next((c for c in cols if 'AMPLITUDE' in c.upper() or 'MV' in c.upper()), cols[-1])

    print(f"Using columns: X='{x_col}', Y='{y_col}', Depth='{depth_col}', Amp='{amp_col}'")

    # Get unique depths
    depths = sorted(df[depth_col].unique())
    print(f"Found {len(depths)} unique depth levels.")

    os.makedirs(output_dir, exist_ok=True)
    
    # Save a metadata JSON for the viewer
    metadata = {
        "depths": [float(d) for d in depths],
        "x_min": float(df[x_col].min()),
        "x_max": float(df[x_col].max()),
        "y_min": float(df[y_col].min()),
        "y_max": float(df[y_col].max()),
        "slices": []
    }

    # Generate grid
    x_min, x_max = df[x_col].min(), df[x_col].max()
    y_min, y_max = df[y_col].min(), df[y_col].max()
    
    # Define grid resolution (reduced to 200 for speed)
    grid_x, grid_y = np.mgrid[x_min:x_max:200j, y_min:y_max:200j]

    for i, d in enumerate(depths):
        print(f"Processing depth {d} ({i+1}/{len(depths)})...")
        slice_df = df[df[depth_col] == d]
        
        # Interpolate onto a regular grid for nice imaging
        points = slice_df[[x_col, y_col]].values
        values = slice_df[amp_col].values
        
        # Use linear interpolation (faster than cubic)
        grid_z = griddata(points, values, (grid_x, grid_y), method='linear', fill_value=0)
        
        # Normalize to 0-1 range
        vmin, vmax = values.min() if len(values) > 0 else 0, values.max() if len(values) > 0 else 1
        if vmax > vmin:
            norm = (grid_z - vmin) / (vmax - vmin)
        else:
            norm = grid_z
        norm = np.clip(norm, 0.0, 1.0)
        
        # Save with PIL (5-10x faster than matplotlib)
        img_array = (np.flipud(norm.T) * 255).astype(np.uint8)
        img = Image.fromarray(img_array, mode='L')
        
        filename = f"slice_{i:03d}.png"
        filepath = os.path.join(output_dir, filename)
        img.save(filepath, optimize=False)
        
        metadata["slices"].append({
            "depth": float(d),
            "image": filename
        })
        
    with open(os.path.join(output_dir, "metadata.json"), "w") as f:
        json.dump(metadata, f, indent=4)
        
    print(f"Done! {len(depths)} slices saved to {output_dir}")

if __name__ == '__main__':
    csv_file = sys.argv[1]
    out_dir = sys.argv[2]
    generate_slices(csv_file, out_dir)

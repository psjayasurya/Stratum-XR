"""
Shapefile Parser Service
Functions for parsing Zipped Shapefiles and extracting geolocation data.
"""
import os
import zipfile
import tempfile
import shutil
import shapefile  # pyshp
from pyproj import CRS, Transformer
from typing import Dict, List, Optional, Any

def extract_shapefile_data(zip_filepath: str) -> Optional[Dict[str, Any]]:
    """
    Extract center and boundary polygon from a Zipped Shapefile.
    
    Args:
        zip_filepath: Path to the uploaded .zip file containing .shp, .shx, .dbf, .prj
        
    Returns:
        Dictionary with 'center' (lat/lon/alt) and 'points' list,
        or None if parsing fails
    """
    temp_dir = tempfile.mkdtemp()
    try:
        # 1. Extract Zip
        with zipfile.ZipFile(zip_filepath, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
            
        # 2. Find .shp file
        shp_file = None
        for root, dirs, files in os.walk(temp_dir):
            for f in files:
                if f.lower().endswith('.shp'):
                    shp_file = os.path.join(root, f)
                    break
            if shp_file:
                break
        
        if not shp_file:
            print("No .shp file found in zip")
            return None

        # 3. Read Shapefile
        with shapefile.Reader(shp_file) as sf:
            if not sf.shapes():
                print("Shapefile is empty")
                return None
                
            # Get the first shape (assuming it's the boundary)
            shape = sf.shape(0)
            points = shape.points
            
            # Check if shape is 3D (has Z)
            # pyshp shapeType mapping: 1=Point, 3=PolyLine, 5=Polygon, 
            # 11=PointZ, 13=PolyLineZ, 15=PolygonZ, 18=MultiPointZ, 31=MultiPatch
            has_z = shape.shapeType in [11, 13, 15, 18, 31]
            
            # It seems pyshp stores Z values in shape.z, a separate list
            z_values = []
            if has_z and hasattr(shape, 'z'):
                z_values = shape.z

        # 4. Handle Projection (read .prj) - moved out of Reader block to keep it clean, 
        # but logic for points transformation needs points first.
        
        prj_file = shp_file.replace('.shp', '.prj')
        if not os.path.exists(prj_file):
            # Try case insensitive search
            base = os.path.splitext(shp_file)[0]
            for ext in ['.prj', '.PRJ']:
                if os.path.exists(base + ext):
                    prj_file = base + ext
                    break
        
        transformer = None
        if os.path.exists(prj_file):
            try:
                with open(prj_file, 'r') as f:
                    wkt = f.read()
                crs_src = CRS.from_wkt(wkt)
                crs_dst = CRS.from_epsg(4326) # WGS84
                transformer = Transformer.from_crs(crs_src, crs_dst, always_xy=True)
            except Exception as e:
                print(f"Error reading PRJ or creating transformer: {e}")
        else:
            print("Warning: No .prj file found. Assuming WGS84.")

        # 5. Transform Points
        final_points = []
        lons = []
        lats = []
        alts = []
        
        for i, pt in enumerate(points):
            x, y = pt[0], pt[1]
            z = 0
            if has_z and i < len(z_values):
                z = z_values[i]
            
            if transformer:
                lon, lat = transformer.transform(x, y)
            else:
                lon, lat = x, y
                
            final_points.append({'lat': lat, 'lon': lon, 'alt': z})
            lons.append(lon)
            lats.append(lat)
            alts.append(z)
            
        # 6. Calculate Center
        if not lats or not lons:
            return None
            
        center_lat = sum(lats) / len(lats)
        center_lon = sum(lons) / len(lons)
        center_alt = sum(alts) / len(alts)
        
        return {
            'center': {'lat': center_lat, 'lon': center_lon, 'alt': center_alt},
            'points': final_points
        }

    except Exception as e:
        print(f"Error processing shapefile: {e}")
        import traceback
        traceback.print_exc()
        return None
        
    finally:
        # Cleanup
        shutil.rmtree(temp_dir)

__all__ = ['extract_shapefile_data']

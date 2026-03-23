"""
Tool Routes
Handles converter tools and utilities.
"""
from fastapi import APIRouter, Request, File, Form, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import pandas as pd
import os
import uuid

from app.config import HAS_GEOSPATIAL, PROCESSED_FOLDER, TEMPLATES_FOLDER
from app.utils.file_utils import secure_filename

# Import geospatial libraries if available
if HAS_GEOSPATIAL:
    from pyproj import CRS, Transformer
    from shapely.geometry import MultiPoint


# Create router
router = APIRouter(tags=["Tools"])

# Templates
templates = Jinja2Templates(directory=TEMPLATES_FOLDER)


@router.get("/converter", response_class=HTMLResponse)
async def converter_page(request: Request):
    """
    Display converter tool page
    
    Args:
        request: FastAPI request
        
    Returns:
        HTML response with converter interface
    """
    return templates.TemplateResponse("converter.html", {"request": request})


@router.post("/tools/survey_boundary")
async def tool_survey_boundary(
    file: UploadFile = File(...),
    utm_zone: int = Form(31),
    hemisphere: str = Form("north"),
    easting_col: str = Form(""),
    northing_col: str = Form("")
):
    """
    Convert survey data to KML boundary
    
    Reads a CSV file with lat/lon or UTM coordinates, creates a convex hull
    boundary, and exports as KML file.
    
    Args:
        file: CSV file with coordinates
        utm_zone: UTM zone number (if using UTM coordinates)
        hemisphere: 'north' or 'south' (if using UTM coordinates)
        easting_col: Column name for UTM easting
        northing_col: Column name for UTM northing
        
    Returns:
        Dictionary with success status and file URLs
    """
    if not HAS_GEOSPATIAL:
        return {"success": False, "error": "Geospatial libraries not installed"}
    
    job_id = str(uuid.uuid4())
    job_dir = os.path.join(PROCESSED_FOLDER, job_id)
    os.makedirs(job_dir, exist_ok=True)
    
    filename = secure_filename(file.filename)
    filepath = os.path.join(job_dir, filename)
    
    with open(filepath, "wb") as buffer:
        content = await file.read()
        buffer.write(content)
    
    try:
        df = pd.read_csv(filepath, encoding='latin-1')
        
        # Try to find latitude/longitude columns
        lat_options = ["Latitude", " Latitude", "lat", "LAT"]
        lon_options = ["Longitude", " Longitude", "lon", "LON"]
        lat_col = next((c for c in lat_options if c in df.columns), None)
        lon_col = next((c for c in lon_options if c in df.columns), None)
        
        # If lat/lon not found, try UTM conversion
        if not lat_col or not lon_col:
            if easting_col in df.columns and northing_col in df.columns:
                utm_crs = CRS.from_dict({"proj": "utm", "zone": utm_zone, "south": hemisphere == "south"})
                transformer = Transformer.from_crs(utm_crs, "EPSG:4326", always_xy=True)
                df["Longitude"], df["Latitude"] = transformer.transform(
                    df[easting_col].values,
                    df[northing_col].values
                )
                lat_col, lon_col = "Latitude", "Longitude"
            else:
                return {"success": False, "error": f"Columns not found"}
        
        # Save updated CSV with lat/lon
        updated_csv_name = "updated_data_with_latlon.csv"
        updated_csv_path = os.path.join(job_dir, updated_csv_name)
        df.to_csv(updated_csv_path, index=False)
        
        # Create convex hull boundary
        coords = list(zip(df[lon_col], df[lat_col]))
        hull = MultiPoint(coords).convex_hull
        
        if not hasattr(hull, 'exterior'):
            return {"success": False, "error": "Could not create polygon boundary"}
        
        boundary_points = list(hull.exterior.coords)
        
        # Generate KML file
        kml = '<?xml version="1.0" encoding="UTF-8"?>\n'
        kml += '<kml xmlns="http://www.opengis.net/kml/2.2">\n<Document>\n<Placemark>\n'
        kml += '<name>GPR Survey Area</name>\n<Polygon>\n<outerBoundaryIs>\n<LinearRing>\n<coordinates>\n'
        for pt in boundary_points:
            kml += f"{pt[0]},{pt[1]},0\n"
        # Close the polygon
        kml += f"{boundary_points[0][0]},{boundary_points[0][1]},0\n"
        kml += '</coordinates>\n</LinearRing>\n</outerBoundaryIs>\n</Polygon>\n</Placemark>\n</Document>\n</kml>'
        
        kml_name = "survey_area_boundary.kml"
        kml_path = os.path.join(job_dir, kml_name)
        with open(kml_path, 'w', encoding='utf-8') as f:
            f.write(kml)
        
        return {
            "success": True,
            "csv_url": f"/files/{job_id}/{updated_csv_name}",
            "kml_url": f"/files/{job_id}/{kml_name}"
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


__all__ = ['router']

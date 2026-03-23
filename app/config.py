"""
Configuration and Constants
Contains all application configuration, settings, and color palettes.
"""
import os
import multiprocessing
from datetime import timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ============ CONFIG CLASS ============
class Config:
    """Application configuration from environment variables"""
    SECRET_KEY = os.getenv("SECRET_KEY", "")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "")
    JWT_ALGORITHM = "HS256"
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=24)
    DATABASE_URL = os.getenv("DATABASE_URL", "")
    MAIL_SERVER = os.getenv("MAIL_SERVER", "")
    MAIL_PORT = int(os.getenv("MAIL_PORT", 587))
    MAIL_USERNAME = os.getenv("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", "")
    MAIL_USE_TLS = True

# Create config instance
config = Config()

# ============ SUPABASE CONFIG ============
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "")

# ============ DIRECTORY PATHS ============
UPLOAD_FOLDER = 'uploads'
PROCESSED_FOLDER = 'processed'
TEMPLATES_FOLDER = 'templates'
STATIC_FOLDER = 'static'
TILES_FOLDER = 'tiles'

# ============ PROCESSING CONFIG ============
MAX_WORKERS = min(4, multiprocessing.cpu_count())

# ============ GEOSPATIAL CONFIG ============
try:
    from pyproj import CRS, Transformer
    from shapely.geometry import MultiPoint
    HAS_GEOSPATIAL = True
except ImportError:
    HAS_GEOSPATIAL = False

# ============ DEFAULT SETTINGS ============
DEFAULT_SETTINGS = {
    'input_file': '',
    'base_output_name': 'gpr_iso',
    'use_column_indices': True,
    'col_idx_x': 0,
    'col_idx_y': 1,
    'col_idx_z': 7,
    'col_idx_amplitude': 8,
    'threshold_percentile': 0.63,
    'iso_bins': 5,
    'depth_offset_per_level': 0.05,
    'vr_point_size': 0.1,
    'font_size_multiplier': 1.0,
    'font_family': 'Arial',
    'invert_depth': True,
    'center_coordinates': True,
    'generate_surface': False,
    'surface_resolution': 100,
    'surface_depth_slices': 0,
    'surface_opacity': 0.6,
    'generate_amplitude_surface': False,
    'max_points_per_layer': 500000,
    'color_palette': 'Standard'
}

# ============ COLOR PALETTES ============
COLOR_PALETTES = {
    'Viridis': [[68, 1, 84], [72, 40, 120], [62, 74, 137], [49, 104, 142], 
                [38, 130, 142], [31, 158, 137], [53, 183, 121], [110, 206, 88], [181, 222, 43]],
    'Plasma': [[13, 8, 135], [75, 3, 161], [125, 3, 168], [168, 34, 150], 
               [203, 70, 121], [229, 107, 93], [248, 148, 65], [253, 195, 40], [240, 249, 33]],
    'Inferno': [[0, 0, 4], [25, 11, 68], [66, 10, 104], [106, 23, 110], 
                [147, 38, 103], [188, 55, 84], [221, 81, 58], [243, 119, 44], [252, 166, 50]],
    'Magma': [[0, 0, 4], [26, 16, 70], [66, 10, 104], [106, 23, 110], 
              [147, 38, 103], [188, 55, 84], [226, 83, 78], [251, 135, 97], [252, 197, 131]],
    'Cividis': [[0, 32, 76], [0, 54, 93], [0, 75, 100], [14, 94, 95], 
                [57, 112, 87], [98, 129, 81], [140, 145, 80], [182, 160, 85], [234, 176, 100]],
    'Seismic': [[0, 0, 255], [127, 127, 255], [255, 255, 255], [255, 127, 127], [255, 0, 0]],
    'Rainbow': [[148, 0, 211], [75, 0, 130], [0, 0, 255], [0, 255, 0], 
                [255, 255, 0], [255, 127, 0], [255, 0, 0]],
    'Standard': [[255, 0, 0], [255, 165, 0], [255, 255, 0], [0, 255, 0], [0, 0, 255]],
    'RdBu': [[103, 0, 31], [178, 24, 43], [214, 96, 77], [244, 165, 130], 
             [253, 219, 199], [247, 247, 247], [209, 229, 240], [146, 197, 222], 
             [67, 147, 195], [33, 102, 172], [5, 48, 97]],
    'Spectral': [[158, 1, 66], [213, 62, 79], [244, 109, 67], [253, 174, 97], 
                 [254, 224, 139], [255, 255, 191], [230, 245, 152], [171, 221, 164], 
                 [102, 194, 165], [50, 136, 189], [94, 79, 162]],
    'Blues': [[247, 251, 255], [222, 235, 247], [198, 219, 239], [158, 202, 225], 
              [107, 174, 214], [66, 146, 198], [33, 113, 181], [8, 81, 156], [8, 48, 107]],
    'Greens': [[247, 252, 245], [229, 245, 224], [199, 233, 192], [161, 217, 155], 
               [116, 196, 118], [65, 171, 93], [35, 139, 69], [0, 109, 44], [0, 68, 27]],
    'Oranges': [[255, 245, 235], [254, 230, 206], [253, 208, 162], [253, 174, 107], 
                [253, 141, 60], [241, 105, 19], [217, 72, 1], [166, 54, 3], [127, 39, 4]],
    'Turbo': [[35, 23, 27], [69, 61, 120], [97, 113, 178], [125, 170, 211], 
              [158, 222, 217], [199, 251, 194], [239, 251, 143], [255, 217, 95], 
              [255, 165, 62], [255, 109, 58], [230, 57, 43]],
    'Thermal': [[0, 0, 0], [64, 0, 0], [128, 0, 0], [192, 64, 0], 
                [255, 128, 0], [255, 192, 64], [255, 255, 128], [255, 255, 255]],
    'Ocean': [[0, 0, 128], [0, 0, 255], [0, 128, 255], [0, 255, 255], 
              [128, 255, 255], [255, 255, 255]],
    'Grayscale': [[0, 0, 0], [64, 64, 64], [128, 128, 128], [192, 192, 192], [255, 255, 255]],
    'Geology': [[139, 69, 19], [160, 82, 45], [205, 133, 63], [222, 184, 135], 
                [245, 222, 179], [210, 180, 140], [165, 42, 42], [178, 34, 34]],
    'Earth': [[0, 56, 101], [0, 92, 135], [0, 128, 149], [0, 164, 143], 
              [85, 188, 124], [170, 212, 105], [255, 235, 86], [255, 189, 46]],
    'HighContrast': [[230, 57, 70], [241, 135, 1], [255, 200, 87], 
                     [168, 218, 220], [69, 123, 157], [29, 53, 87]],
}

# Export all
__all__ = [
    'config',
    'Config',
    'SUPABASE_URL',
    'SUPABASE_KEY',
    'SUPABASE_BUCKET',
    'UPLOAD_FOLDER',
    'PROCESSED_FOLDER',
    'TEMPLATES_FOLDER',
    'STATIC_FOLDER',
    'TILES_FOLDER',
    'MAX_WORKERS',
    'HAS_GEOSPATIAL',
    'DEFAULT_SETTINGS',
    'COLOR_PALETTES',
]

"""
Pydantic Data Models
Contains all data validation and serialization models.
"""
from pydantic import BaseModel


class UserCreate(BaseModel):
    """Model for user registration"""
    email: str
    password: str


class UserLogin(BaseModel):
    """Model for user login"""
    email: str
    password: str


class OTPVerify(BaseModel):
    """Model for OTP verification"""
    email: str
    otp: str


class UploadSettings(BaseModel):
    """Model for GPR file upload and processing settings"""
    job_name: str
    file_format: str = "csv"
    col_idx_x: int = 0
    col_idx_y: int = 1
    col_idx_z: int = 7
    col_idx_amplitude: int = 8
    threshold_percentile: float = 0.63
    iso_bins: int = 5
    depth_offset_per_level: float = 0.05
    vr_point_size: float = 0.015
    font_size_multiplier: float = 1.0
    font_family: str = 'Arial'
    invert_depth: bool = True
    center_coordinates: bool = True
    generate_surface: bool = False
    surface_resolution: int = 100
    surface_depth_slices: int = 0
    surface_opacity: float = 0.6
    generate_amplitude_surface: bool = False
    max_points_per_layer: int = 500000
    color_palette: str = 'Standard'


class SavedViewRequest(BaseModel):
    """Model for saving a multi-grid view"""
    name: str
    job_ids: list[str]


class AnnotationCreate(BaseModel):
    """Model for creating a new 3D scene annotation"""
    ann_type: str                        # pin | line | polygon | label | stamp | sphere | arrow | flag | hazard | note
    label: str = ''
    color: str = '#f59e0b'
    note: str = ''
    positions: str = '[]'               # JSON string: [{x,y,z}, ...]
    metadata: str = '{}'                # JSON string: extra per-type data


class AnnotationUpdate(BaseModel):
    """Model for updating an existing annotation's editable fields"""
    label: str = ''
    color: str = '#f59e0b'
    note: str = ''


__all__ = ['UserCreate', 'UserLogin', 'OTPVerify', 'UploadSettings', 'SavedViewRequest',
           'AnnotationCreate', 'AnnotationUpdate']

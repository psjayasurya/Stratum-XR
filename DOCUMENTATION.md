# Stratum XR (Extended Reality) - Technical Documentation

**Comprehensive Technical Reference for Ground Penetrating Radar Virtual Reality Visualization Platform**

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [System Architecture](#2-system-architecture)
3. [Technology Stack](#3-technology-stack)
4. [Core Components](#4-core-components)
5. [Data Processing Pipeline](#5-data-processing-pipeline)
6. [API Reference](#6-api-reference)
7. [VR Visualization Engine](#7-vr-visualization-engine)
8. [Multi-Grid Collaboration System](#8-multi-grid-collaboration-system)
9. [Geospatial Integration](#9-geospatial-integration)
10. [Cloud Storage & Database](#10-cloud-storage--database)
11. [Authentication & Security](#11-authentication--security)
12. [Deployment Guide](#12-deployment-guide)
13. [Configuration Reference](#13-configuration-reference)
14. [Troubleshooting](#14-troubleshooting)
15. [Appendix](#15-appendix)

---

## 1. Executive Summary

### 1.1 Product Overview

**Stratum XR (Extended Reality)** is an enterprise-grade web application designed for processing, visualizing, and analyzing Ground Penetrating Radar (GPR) survey data in immersive Virtual Reality environments. The platform transforms raw GPR data (CSV/HDF5 formats) into interactive 3D point cloud visualizations with multi-user collaboration capabilities.

### 1.2 Key Capabilities

| Capability | Description |
|------------|-------------|
| **GPR Data Processing** | Amplitude-based iso-surface extraction, multi-layer point cloud generation |
| **VR Visualization** | WebXR-powered 6-DoF immersive viewing on Meta Quest and compatible devices |
| **Multi-Grid Analysis** | Simultaneous viewing of multiple survey grids with synchronized controls |
| **Geospatial Mapping** | KML/geo-reference integration with satellite/aerial tile overlays |
| **Collaboration** | Real-time WebSocket-based session sharing with annotation support |
| **Cloud Integration** | Supabase storage for processed outputs and job persistence |
| **3D Model Overlay** | GLB/GLTF mesh import for pipe network correlation |
| **Pipe Isolation Toolkit** | Lasso remove, crop/iso filtering, branch region capture (polygon + line/path) |
| **Solid Reconstruction** | PCA-guided centerline reconstruction and tube solid generation from extracted points |
| **Saved Branch Solids** | Per-user save/list/load/delete, combine-and-save, per-item visibility, scan-reveal animation |

### 1.3 Target Users

- Geotechnical Engineers
- NDT (Non-Destructive Testing) Professionals
- Structural Investigation Teams
- Utility Mapping Specialists
- Archaeological Survey Teams

### 1.4 System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| **Server** | Python 3.10+, 4GB RAM, 2 CPU cores | Python 3.11+, 16GB RAM, 8 CPU cores |
| **Client (Desktop)** | Chrome/Firefox, WebGL 2.0 | Chrome 119+, WebGL 2.0 |
| **Client (VR)** | Meta Quest 2/3, Quest Browser | Meta Quest 3/Pro |
| **Storage** | 10GB local | 100GB+ with Supabase cloud |

---

## 2. System Architecture

### 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CLIENT LAYER                                    │
├───────────────────────┬────────────────────────┬───────────────────────────┤
│   Web Browser (2D)    │   VR Headset (WebXR)   │   Mobile Browser          │
│   - File Upload UI    │   - Immersive 3D View  │   - Basic 3D Controls     │
│   - Job Management    │   - 6-DoF Navigation   │   - Touch Navigation      │
│   - Cesium Globe      │   - Controller Input   │                           │
└───────────────────────┴────────────────────────┴───────────────────────────┘
                                    │
                                    │ HTTPS/WSS
                                    ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│                           APPLICATION LAYER                                  │
│                         FastAPI Server (Python)                              │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐│
│  │ Auth Routes │  │Upload Routes│  │ Job Routes  │  │ Session/WebSocket   ││
│  │ /login      │  │ /upload     │  │ /status     │  │ /session/ws/{id}    ││
│  │ /register   │  │ /files/*    │  │ /view       │  │ /session/create     ││
│  │ /logout     │  │             │  │ /view_multi │  │ /session/finalize   ││
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────────┘│
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                        SERVICE LAYER                                   │ │
│  ├────────────────────────────────────────────────────────────────────────┤ │
│  │  GPR Processor   │  PLY Generator  │  Viewer Generator  │ TTS/AI Service │
│  │  - CSV/HDF Parse │  - Parallel PLY │  - VR HTML Builder │ - Server TTS   │
│  │  - Iso-surface   │  - Point Cloud  │  - Cesium Pages    │ - AI Insights  │
│  │  - LayerPoints   │  - RGB Vertex   │  - Multi-Grid View │ - PDF MoM      │
│  └────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    ↓                               ↓
        ┌───────────────────────┐       ┌───────────────────────┐
        │   PostgreSQL (RDS)     │       │   Supabase Storage    │
        │   - Users Table        │       │   - PLY Files         │
        │   - OTP Table          │       │   - HTML Viewers      │
        │   - Jobs Metadata      │       │   - model.glb         │
        │   - Saved Views        │       │   - Tile Cache        │
        └───────────────────────┘       └───────────────────────┘
```

### 2.2 Directory Structure

```
GPR_VR_VIEWER/
├── main.py                          # FastAPI application entry point
├── 3d.py                            # Utility: CSV to GLB pipe model converter
├── requirements.txt                 # Python dependencies
├── .env                             # Environment configuration
│
├── app/                             # Application modules
│   ├── __init__.py                  
│   ├── config.py                    # Configuration, constants, color palettes
│   ├── database.py                  # PostgreSQL connection
│   ├── models.py                    # Pydantic data models
│   ├── storage.py                   # Supabase storage operations
│   │
│   ├── routes/                      # API route handlers
│   │   ├── auth_routes.py           # Authentication (login, register, OTP)
│   │   ├── upload_routes.py         # File upload and serving
│   │   ├── job_routes.py            # Job management, view, download
│   │   ├── tool_routes.py           # Utility tools (survey converter)
│   │   └── session_routes.py        # WebSocket collaboration
│   │
│   ├── services/                    # Business logic services
│   │   ├── gpr_processor.py         # Core GPR data processing engine
│   │   ├── ply_generator.py         # Binary PLY point cloud writer
│   │   ├── viewer_generator.py      # HTML viewer template generation
│   │   ├── kml_parser.py            # KML geolocation extraction
│   │   ├── mom_service.py           # Minutes of Meeting PDF generation
│   │   └── websocket_manager.py     # WebSocket connection management
│   │
│   └── utils/                       # Utility functions
│       ├── colors.py                # Color palette interpolation
│       ├── email.py                 # SMTP email sending
│       └── file_utils.py            # Filename sanitization
│
├── templates/                       # Jinja2 HTML templates
│   ├── index.html                   # Main upload interface
│   ├── vr_viewer_template.html      # VR visualization viewer (4000+ lines)
│   ├── cesium_viewer_template.html  # Cesium globe viewer
│   ├── converter.html               # Survey area converter tool
│   ├── login.html                   # Authentication pages
│   ├── register.html
│   ├── dashboard.html
│   └── ...
│
├── static/                          # Static assets
│   ├── bg.jpg                       # Background image
│   └── logo.jpeg                    # Application logo
│
├── uploads/                         # Temporary upload storage
├── processed/                       # Processed job outputs
│   └── {job_id}/
│       ├── index.html               # Generated VR viewer
│       ├── layer_*.ply              # Point cloud layers
│       ├── model.glb                # 3D pipe model (if uploaded)
│       └── metadata.json            # Processing metadata
│
└── tiles/                           # Local tile cache (GDAL format)
```

### 2.3 Request Flow Diagram

```
┌──────────────────────────────────────────────────────────────────────────┐
│                        FILE UPLOAD & PROCESSING FLOW                      │
└──────────────────────────────────────────────────────────────────────────┘

    User                Browser              Server                  Storage
      │                    │                    │                       │
      │  1. Select Files   │                    │                       │
      ├───────────────────→│                    │                       │
      │                    │  2. POST /upload   │                       │
      │                    ├───────────────────→│                       │
      │                    │                    │  3. Save to disk      │
      │                    │                    ├───────────────────────│
      │                    │                    │                       │
      │                    │  4. Return job_id  │                       │
      │                    │←───────────────────┤                       │
      │                    │                    │                       │
      │                    │  5. Poll /status   │  ┌─────────────────┐  │
      │                    ├───────────────────→│  │  BACKGROUND     │  │
      │                    │                    │  │  ProcessPool    │  │
      │                    │                    │  │  ├─ Read CSV    │  │
      │                    │  6. "processing"   │  │  ├─ Iso-surface │  │
      │                    │←───────────────────┤  │  ├─ Gen PLY     │  │
      │                    │                    │  │  ├─ Gen HTML    │  │
      │                    │  ... polling ...   │  │  └─ Upload      │──→│
      │                    │                    │  └─────────────────┘  │
      │                    │                    │                       │
      │                    │  7. "completed"    │                       │
      │                    │←───────────────────┤                       │
      │                    │                    │                       │
      │  8. View Result    │  9. GET /view/{id} │                       │
      ├───────────────────→├───────────────────→│                       │
      │                    │                    │  10. Redirect to      │
      │                    │←────────────────────────Supabase URL       │
      │                    │                    │                       │
      │  11. VR Experience │                    │                       │
      │←───────────────────┤                    │                       │
```

---

## 3. Technology Stack

### 3.1 Backend Technologies

| Technology | Version | Purpose |
|------------|---------|---------|
| **Python** | 3.10+ | Core runtime |
| **FastAPI** | 0.104.1 | Async web framework |
| **Uvicorn** | 0.24.0 | ASGI server |
| **Pandas** | 2.1.3 | Data manipulation |
| **NumPy** | 1.26.2 | Numerical computing |
| **SciPy** | 1.11.4 | Scientific computing |
| **PyProj** | 3.6.1 | Coordinate transformations |
| **Shapely** | 2.0.2 | Geometric operations |
| **Supabase** | 2.1.0 | Cloud storage SDK |
| **psycopg2** | 2.9.9 | PostgreSQL adapter |
| **python-jose** | 3.3.0 | JWT authentication |
| **ReportLab** | 4.0.8 | PDF generation |
| **h5py** | 3.10.1 | HDF5 file support |
| **tables** | 3.9.1 | PyTables HDF support |
| **gTTS** | 2.5.1 | Google Text-to-Speech |
| **pyarrow** | 14.0.1 | High-performance CSV parsing |

### 3.2 Frontend Technologies

| Technology | Purpose |
|------------|---------|
| **Three.js** | 3D WebGL rendering engine |
| **WebXR** | Virtual reality API |
| **CesiumJS** | Geospatial globe visualization |
| **XRControllerModelFactory** | VR controller models |
| **PLYLoader** | Point cloud loading |
| **GLTFLoader** | 3D mesh loading |
| **OrbitControls** | Mouse/touch 3D navigation |
| **Jinja2** | HTML templating |

### 3.3 Infrastructure

| Component | Service |
|-----------|---------|
| **Database** | PostgreSQL (Supabase) |
| **Object Storage** | Supabase Storage |
| **Authentication** | JWT + OTP Email Verification |
| **Email** | SMTP (configurable) |

---

## 4. Core Components

### 4.1 Configuration Module (`app/config.py`)

The configuration module centralizes all application settings and constants.

#### Key Constants

```python
# Directory Paths
UPLOAD_FOLDER = 'uploads'
PROCESSED_FOLDER = 'processed'
TEMPLATES_FOLDER = 'templates'
STATIC_FOLDER = 'static'
TILES_FOLDER = 'tiles'

# Processing Configuration
MAX_WORKERS = min(4, multiprocessing.cpu_count())  # Used by ProcessPoolExecutor

# Default Processing Settings
DEFAULT_SETTINGS = {
    'threshold_percentile': 0.63,    # Amplitude threshold (0-1)
    'iso_bins': 5,                   # Number of amplitude layers
    'depth_offset_per_level': 0.05,  # Vertical separation (meters)
    'vr_point_size': 0.015,          # Point size in VR
    'max_points_per_layer': 500000,  # Point cloud density limit
    'color_palette': 'Standard'      # Default color scheme
}
```

#### Color Palettes

The system includes 20 scientific and artistic color palettes:

| Palette | Best For |
|---------|----------|
| Viridis | Perceptually uniform, colorblind-safe |
| Plasma | High contrast amplitude |
| Seismic | Bidirectional data (positive/negative) |
| Thermal | Heat-map style visualization |
| Geology | Subsurface geological data |
| HighContrast | Maximum layer differentiation |

### 4.2 Data Models (`app/models.py`)

```python
class UploadSettings(BaseModel):
    """GPR file upload and processing settings"""
    job_name: str
    file_format: str = "csv"           # 'csv' or 'hdf'
    col_idx_x: int = 0                 # X coordinate column
    col_idx_y: int = 1                 # Y coordinate column
    col_idx_z: int = 7                 # Depth column
    col_idx_amplitude: int = 8         # Amplitude column
    threshold_percentile: float = 0.63  # Filter threshold
    iso_bins: int = 5                   # Number of layers
    depth_offset_per_level: float = 0.05
    vr_point_size: float = 0.015
    invert_depth: bool = True
    center_coordinates: bool = True
    generate_surface: bool = False
    color_palette: str = 'Standard'
```

### 4.3 Storage Service (`app/storage.py`)

The storage module manages cloud file operations with Supabase.

#### Key Functions

| Function | Description |
|----------|-------------|
| `get_base_url(job_id)` | Returns Supabase public URL or local fallback |
| `upload_files_to_supabase(job_id, local_dir)` | Uploads all files with retry logic |

#### Upload Strategy

1. **Retry Logic**: 6 attempts with 3-second delays
2. **MIME Detection**: Automatic content-type inference
3. **Upsert Mode**: Updates existing files without conflict
4. **Exclusion Filter**: Skips large source files (CSV, HDF)

```python
EXCLUDED_EXTENSIONS = ('.csv', '.h5', '.hdf', '.hdf5', '.he5')
```

---

## 5. Data Processing Pipeline

### 5.1 GPR Processor Service (`app/services/gpr_processor.py`)

The GPR processor is the computational core of the application, handling data transformation from raw survey data to 3D point clouds.

#### Processing Workflow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      GPR PROCESSING PIPELINE                             │
└─────────────────────────────────────────────────────────────────────────┘

    RAW DATA              PROCESSING                    OUTPUT
    ────────              ──────────                    ──────

┌──────────────┐    ┌─────────────────────┐    ┌──────────────────────┐
│  CSV File    │───→│  1. LOAD & PARSE    │───→│ DataFrame            │
│  (80MB+)     │    │  - Encoding: latin1 │    │ [x, y, z, amplitude] │
└──────────────┘    │  - Column mapping   │    └──────────────────────┘
                    └─────────────────────┘              │
         OR                                              ↓
                                            ┌─────────────────────────┐
┌──────────────┐    ┌─────────────────────┐ │  2. COORDINATE TRANSFORM│
│  HDF5 File   │───→│  1. LOAD DATASETS   │ │  - Center to origin    │
│  (.h5, .hdf) │    │  - Recursive scan   │ │  - Invert depth (opt)  │
└──────────────┘    │  - Multi-grid merge │ │  - Scale normalization │
                    └─────────────────────┘ └─────────────────────────┘
                                                         │
                                                         ↓
                                            ┌─────────────────────────┐
                                            │  3. AMPLITUDE FILTERING │
                                            │  - Threshold percentile │
                                            │  - Remove low values    │
                                            │  - Bin into iso-levels  │
                                            └─────────────────────────┘
                                                         │
                                                         ↓
                                            ┌─────────────────────────┐
                                            │  4. LAYER GENERATION    │
                                            │  FOR each iso_level:    │
                                            │    - Extract points     │
                                            │    - Assign color       │
                                            │    - Apply depth offset │
                                            │    - Limit point count  │
                                            └─────────────────────────┘
                                                         │
                                                         ↓
                    ┌─────────────────────┐ ┌─────────────────────────┐
                    │  PLY Files          │←│  5. PLY GENERATION      │
                    │  - layer_1.ply      │ │  - Binary format        │
                    │  - layer_2.ply      │ │  - Vertex + RGB color   │
                    │  - ...              │ │  - Little-endian        │
                    └─────────────────────┘ └─────────────────────────┘
                                                         │
                                                         ↓
                    ┌─────────────────────┐ ┌─────────────────────────┐
                    │  HTML Viewer        │←│  6. VIEWER GENERATION   │
                    │  - index.html       │ │  - Template substitution│
                    │  - Layer loaders    │ │  - Multi-grid support   │
                    │  - Control panel    │ │  - VR initialization    │
                    └─────────────────────┘ └─────────────────────────┘
                                                         │
                                                         ↓
                    ┌─────────────────────┐ ┌─────────────────────────┐
                    │  Cloud Storage      │←│  7. SUPABASE UPLOAD     │
                    │  - Public URLs      │ │  - Retry with backoff   │
                    │  - CDN delivery     │ │  - Parallel upload      │
                    └─────────────────────┘ └─────────────────────────┘
```

#### Amplitude Iso-Surface Algorithm

The system extracts points by amplitude percentile ranges:

```python
# For iso_bins = 5, threshold_percentile = 0.63:
# Layer 5 (highest): 100% - 92.6% amplitude
# Layer 4: 92.6% - 85.2%
# Layer 3: 85.2% - 77.8%
# Layer 2: 77.8% - 70.4%
# Layer 1 (lowest): 70.4% - 63%
```

#### HDF5 Multi-Dataset Processing

For HDF5 files with multiple scan grids:

```python
def get_datasets(group):
    """Recursively find all datasets in HDF5 group"""
    datasets = []
    for key in group.keys():
        item = group[key]
        if isinstance(item, h5py.Dataset):
            datasets.append(item)
        elif isinstance(item, h5py.Group):
            datasets.extend(get_datasets(item))
    return datasets
```

### 5.2 PLY Generator Service (`app/services/ply_generator.py`)

Generates binary PLY (Polygon File Format) point clouds optimized for WebGL loading.

#### PLY Format Structure

```
ply
format binary_little_endian 1.0
element vertex {N}
property float x
property float y
property float z
property uchar red
property uchar green
property uchar blue
end_header
[BINARY VERTEX DATA]
```

#### Performance Considerations

| Aspect | Implementation |
|--------|---------------|
| **Parallelization** | `ProcessPoolExecutor` for concurrent layer generation |
| **Format** | Binary (not ASCII) for 3-5x smaller files |
| **Endianness** | Little-endian for JavaScript compatibility |
| **Precision** | float32 for coordinates, uint8 for colors |
| **Max Points** | Configurable limit (default 500K per layer) |

### 5.3 Viewer Generator Service (`app/services/viewer_generator.py`)

Generates customized HTML viewers with embedded Three.js visualization.

#### Template Substitution Tokens

| Token | Replacement |
|-------|-------------|
| `[[JOB_ID]]` | Unique job identifier |
| `[[ORIGINAL_FILENAME]]` | Source file name |
| `[[LAYER_LOADERS]]` | JavaScript PLY loading code |
| `[[LAYER_INFO]]` | Layer metadata HTML |
| `[[LEGEND_INFO]]` | Color legend HTML |
| `[[X_MIN]]`, `[[X_MAX]]` | Data bounds |
| `[[Y_MIN]]`, `[[Y_MAX]]` | Depth bounds |
| `[[X_LEN]]`, `[[Y_LEN]]` | Data dimensions |
| `[[GEO_ANCHOR]]` | KML anchor coordinates |
| `[[MULTI_GRIDS]]` | Multi-grid configuration JSON |

---

## 6. API Reference

### 6.1 Authentication Endpoints

#### `POST /register`
Register a new user account with email verification.

**Request Body (Form Data):**
| Field | Type | Required |
|-------|------|----------|
| email | string | Yes |
| password | string | Yes |

**Response:** Redirect to `/verify?email={email}`

---

#### `POST /verify`
Verify email with OTP code.

**Request Body (Form Data):**
| Field | Type | Required |
|-------|------|----------|
| email | string | Yes |
| otp | string | Yes |

**Response:** Redirect to `/login` on success

---

#### `POST /login`
Authenticate user and create session.

**Request Body (Form Data):**
| Field | Type | Required |
|-------|------|----------|
| email | string | Yes |
| password | string | Yes |

**Response:** 
- Set `access_token` cookie (JWT)
- Redirect to `/` (upload page)

---

#### `POST /logout`
Clear session and redirect to login.

**Response:** Redirect to `/login`

---

### 6.2 Upload Endpoints

#### `POST /upload`
Upload and process GPR data file.

**Request Body (Multipart Form):**
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| file | File | Required | GPR data (CSV/HDF) |
| job_name | string | Required | Unique job identifier |
| file_format | string | "csv" | "csv" or "hdf" |
| pipe_file | File | None | Optional 3D pipe model (PLY/GLB) |
| kml_file | File | None | Optional KML geolocation |
| col_idx_x | int | 0 | X coordinate column index |
| col_idx_y | int | 1 | Y coordinate column index |
| col_idx_z | int | 7 | Depth column index |
| col_idx_amplitude | int | 8 | Amplitude column index |
| threshold_percentile | float | 0.63 | Amplitude threshold (0-1) |
| iso_bins | int | 5 | Number of layers |
| depth_offset_per_level | float | 0.05 | Layer vertical separation |
| vr_point_size | float | 0.015 | VR point size |
| invert_depth | bool | true | Invert depth axis |
| center_coordinates | bool | true | Center data at origin |
| color_palette | string | "Standard" | Color palette name |

**Response:**
```json
{
  "job_id": "MyProject_Grid01",
  "filename": "survey_data.csv"
}
```

---

#### `GET /files/{job_id}/{filename}`
Serve processed files from job directory.

**Response:** File download

---

### 6.3 Job Management Endpoints

#### `GET /status/{job_id}`
Get processing status for a job.

**Response:**
```json
{
  "status": "processing",  // pending | processing | completed | error
  "message": "Generating PLY layers...",
  "progress": 65,
  "total_points": 1250000,
  "total_layers": 5
}
```

---

#### `GET /view/{job_id}`
View processed result for single job.

**Response:** 
- Redirect to Supabase public URL (if available)
- Or serve local `index.html`

---

#### `GET /view_multi?jobs={job_ids}`
View multiple jobs as multi-grid visualization.

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| jobs | string | Comma-separated job IDs |

**Response:** Generated multi-grid HTML viewer

---

#### `GET /list-jobs`
List all jobs for current user.

**Response:**
```json
{
  "jobs": [
    {"id": "Project_Grid01", "name": "Project_Grid01", "date": "2026-02-07"},
    {"id": "Project_Grid02", "name": "Project_Grid02", "date": "2026-02-06"}
  ]
}
```

---

#### `GET /download/{job_id}`
Download all processed files as ZIP.

**Response:** ZIP file attachment

---

#### `DELETE /cleanup/{job_id}`
Delete job files from local and cloud storage.

**Response:**
```json
{
  "status": "success",
  "message": "Job deleted successfully"
}
```

---

### 6.4 Saved Branch Solid Endpoints

The following endpoints support account-scoped branch-solid persistence from the Solid Construction workflow.

#### `POST /api/branch-solids/save`
Save a branch solid file to the current user account.

**Request Body (Multipart Form):**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| model_file | File | Yes | Solid mesh file (typically PLY) |
| name | string | No | Display name/tag |
| source_job_id | string | No | Related processing job identifier |

**Response:**
```json
{
  "success": true,
  "filename": "combined_branches_2026-04-21T11-42-18-234Z.ply"
}
```

---

#### `GET /api/branch-solids`
List saved branch solids for the authenticated user.

**Response:**
```json
[
  {
    "filename": "combined_branches_2026-04-21T11-42-18-234Z.ply",
    "download_url": "/api/branch-solids/download/combined_branches_2026-04-21T11-42-18-234Z.ply",
    "size_bytes": 1240031,
    "created_at": "2026-04-21T11:42:18Z"
  }
]
```

---

#### `GET /api/branch-solids/download/{filename}`
Download a saved branch solid file for the current user.

**Response:** File stream/download

---

#### `DELETE /api/branch-solids/{filename}`
Delete a saved branch solid for the current user.

**Response:**
```json
{
  "success": true,
  "filename": "combined_branches_2026-04-21T11-42-18-234Z.ply"
}
```

---

### 6.5 Tool Endpoints

#### `POST /tools/survey_boundary`
Convert survey coordinates to KML boundary.

**Request Body (Multipart Form):**
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| file | File | Required | CSV with coordinates |
| utm_zone | int | 31 | UTM zone number |
| hemisphere | string | "north" | "north" or "south" |
| easting_col | string | "" | UTM easting column name |
| northing_col | string | "" | UTM northing column name |

**Response:**
```json
{
  "success": true,
  "csv_url": "/files/{uuid}/updated_data_with_latlon.csv",
  "kml_url": "/files/{uuid}/survey_area_boundary.kml"
}
```

---

### 6.6 Session Collaboration Endpoints

#### `POST /session/create`
Create new collaboration session.

**Response:**
```json
{
  "session_id": "a1b2c3d4"
}
```

---

#### `WebSocket /session/ws/{session_id}`
Real-time collaboration channel.

**Message Types:**

| Type | Direction | Description |
|------|-----------|-------------|
| `join` | Client→Server | Join with email |
| `participant_update` | Server→Client | Participant count update |
| `annotation_add` | Bidirectional | Add annotation marker |
| `camera_sync` | Bidirectional | Sync camera transform |
| `transcript` | Bidirectional | Voice transcript |
| `signal` | Bidirectional | WebRTC signaling |

---

#### `GET /api/tts`
Generate TTS audio on the server to bypass browser/Quest restrictions.

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| text | string | Text to convert to speech |

**Response:** MPEG audio stream

---

#### `POST /session/{session_id}/finalize`
Generate MoM (Minutes of Meeting) and email to participants.

**Response:**
```json
{
  "message": "MoM sent successfully"
}
```

---

## 7. VR Visualization Engine

### 7.1 VR Viewer Architecture (`vr_viewer_template.html`)

The VR viewer is a 4000+ line single-page application with comprehensive 3D visualization capabilities.

#### Core Components

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        VR VIEWER COMPONENTS                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                     THREE.JS SCENE GRAPH                        │    │
│  ├─────────────────────────────────────────────────────────────────┤    │
│  │                                                                 │    │
│  │   scene                                                         │    │
│  │     ├── mainGroup (GPR point clouds)                           │    │
│  │     │     └── pointCloudGroup                                  │    │
│  │     │           ├── layer_1 (Points)                           │    │
│  │     │           ├── layer_2 (Points)                           │    │
│  │     │           └── ...                                        │    │
│  │     ├── groundGroup (map tiles)                                │    │
│  │     │     ├── tile_0_0 (Mesh)                                  │    │
│  │     │     ├── tile_0_1 (Mesh)                                  │    │
│  │     │     └── ...                                              │    │
│  │     ├── surveyMeshGroup (loaded GLB mesh)                      │    │
│  │     ├── pipeGroup (3D pipe model)                              │    │
│  │     ├── cameraRig (VR camera hierarchy)                        │    │
│  │     │     ├── camera (PerspectiveCamera)                       │    │
│  │     │     ├── controller0                                      │    │
│  │     │     └── controller1                                      │    │
│  │     └── lights                                                 │    │
│  │           ├── AmbientLight                                     │    │
│  │           └── DirectionalLight                                 │    │
│  │                                                                 │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                      CONTROL PANEL UI                           │    │
│  ├─────────────────────────────────────────────────────────────────┤    │
│  │  Layer Controls    │  View Controls     │  Geo-Reference        │    │
│  │  - Toggle layers   │  - Point size      │  - Lat/Lon input      │    │
│  │  - Show All/None   │  - Point opacity   │  - Map type select    │    │
│  │  - Sync grid       │  - Auto-rotate     │  - Zoom level         │    │
│  │                    │  - Background      │  - Set Anchor         │    │
│  ├─────────────────────────────────────────────────────────────────┤    │
│  │  Mesh Controls     │  Pipe Controls     │  Alignment Tools      │    │
│  │  - Position XYZ    │  - Scale           │  - Draw polygon       │    │
│  │  - Rotation XYZ    │  - Position XYZ    │  - Auto-fit mesh      │    │
│  │  - Opacity         │  - Rotation        │  - Clear points       │    │
│  │  - Visibility      │  - Visibility      │                       │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 7.2 VR Interaction System

#### Controller Mapping (Meta Quest)

| Controller | Action | Function |
|------------|--------|----------|
| **Right Trigger**| Select Start | Cycle Views (Sky → Aerial → Street) |
| **Right Grip**   | Squeeze | Horizontal Dragging of the survey assembly |
| **Right A (4)**  | Click | Toggle visibility (Cloud/LiDAR/PLY) based on dropdown |
| **Right B (5)**  | Click | Toggle Ground/Map visibility |
| **Left Trigger** | Select Start | Assistant Next Insight OR Cycle Layers |
| **Left Grip**    | Squeeze | Switch to a random color palette |
| **Left X (4)**   | Click | Increase Point Size (GPR & LiDAR) |
| **Left Y (5)**   | Click | Decrease Point Size (GPR & LiDAR) |
| **Thumbsticks**  | Move | Teleportation and smooth locomotion |
| **UI Control**   | Slider | Adjust VR Drag Sensitivity (1.0 = 1:1 movement) |

#### 6-DoF Manipulation

```javascript
// Grab transformation logic
function onSqueezeStart(event) {
    const controller = event.target;
    const target = getVRTarget();
    
    // Store relative transform between controller and object
    const controllerInv = controller.matrixWorld.clone().invert();
    const relativeMatrix = new THREE.Matrix4()
        .multiplyMatrices(controllerInv, target.matrixWorld);
    
    previousTransforms.set(controller, {
        relativeMatrix: relativeMatrix,
        startDist: controller0.position.distanceTo(controller1.position),
        startScale: target.scale.x
    });
}
```

### 7.3 Rendering Optimizations

| Optimization | Implementation |
|--------------|----------------|
| **Foveated Rendering** | `renderer.xr.setFoveation(1)` for Quest |
| **Point Size Attenuation** | Distance-based point scaling |
| **Level of Detail** | Layer visibility toggles |
| **Frustum Culling** | Automatic by Three.js |
| **WebGL Hints** | `powerPreference: 'high-performance'` |

### 7.4 Performance Monitoring

Built-in debug panel displays:
- FPS counter
- Draw call count
- Triangles/Points rendered
- Memory usage
- Loading progress

### 7.5 Pipe Isolation & Solid Construction

The viewer includes a dedicated extraction and reconstruction workflow for drainage/utility tracing.

#### Lasso Remove and Branch Region Selection

- **Lasso Remove Tab** separates filtering from reconstruction for cleaner workflow.
- **Selection modes**:
  - `Polygon`: closed area selection.
  - `Line/Path`: open path selection with configurable path width (pixel corridor selection).
- **Subtractive lasso mode** removes points inside selected polygon from active extraction set.
- **Branch regions persist** visually until explicit clear-all action.

#### Solid Reconstruction Algorithm

Solid generation uses a centerline-driven procedural method (not voxel marching cubes):

1. **Principal axis estimation** using covariance + power iteration (PCA-like dominant direction).
2. **Axis projection and binning** of extracted points along the dominant axis.
3. **Centerline sample extraction** via bin centroids.
4. **Robust local radius estimation** via radial-distance quantiles.
5. **Centerline smoothing** with iterative neighbor averaging.
6. **Curve fitting** using centripetal Catmull-Rom.
7. **Mesh reconstruction** with `THREE.TubeGeometry`.

This pipeline is used by both single-solid and branch-solid construction actions.

#### Solid Controls and Editing

- Radius scale supports **minimum 0.0**.
- Smoothness control tunes centerline/path quality and tube segment density.
- Generated branch solids can be:
  - selected from dropdown,
  - moved with XYZ numeric controls,
  - undone one-by-one,
  - combined and saved as one asset.

### 7.6 Saved Branch Solids & Visual Management

Saved branch solids are account-scoped and integrated into the Solid Construction tab.

#### Asset Operations

- Refresh saved list.
- Load selected saved solid into scene (PLY direct load).
- Delete saved solid.
- Combine all current branch solids and save.

#### Visibility Controls

- Global toggle: **Show Loaded Saved Solids**.
- Per-item loaded list with individual show/hide checkboxes.

#### Reveal Animation

- Loaded saved solids support animated reveal from the Solid tab.
- Current implementation uses a **scan reveal** effect:
  - clipping-plane sweep,
  - synchronized emissive glow crest,
  - auto restore of original material/clipping state at completion.


---

## 8. Multi-Grid Collaboration System

### 8.1 Multi-Grid Architecture

When viewing multiple survey grids simultaneously:

```javascript
const gridsGroup = new THREE.Group();  // Parent for all grids
const gridInstances = {};              // Grid state storage

// Each grid maintains:
gridInstances[gridId] = {
    group: new THREE.Group(),          // Grid container
    layers: [],                        // Layer references
    visible: true,                     // Master visibility
    metadata: {                        // Grid info
        bounds: { min: {...}, max: {...} },
        pointCount: 1250000,
        layerCount: 5
    }
};
```

### 8.2 Grid Management Features

| Feature | Description |
|---------|-------------|
| **Grid Selector** | Dropdown to switch active grid |
| **Sync Grid** | Link layer toggles and VR trigger cycling across all grids |
| **Focus Grid** | Camera animation to grid center |
| **Global Offset** | Adjust all grids simultaneously |
| **Individual Controls** | Per-grid layer visibility |

### 8.3 WebSocket Collaboration

Real-time session sharing enables:

1. **Participant Tracking**: See who's in the session
2. **Annotation Sharing**: Place markers visible to all
3. **Camera Sync**: Optional follow-cam mode
4. **Voice Transcript**: Speech-to-text logging
5. **Session MoM**: PDF summary emailed to participants

---

## 9. Geospatial Integration

### 9.1 Coordinate Systems

The system supports multiple coordinate reference systems:

| System | Usage |
|--------|-------|
| **WGS84 (EPSG:4326)** | GPS/KML coordinates |
| **UTM** | Survey data (zone-specific) |
| **Local Cartesian** | 3D visualization |

### 9.2 Geo-Reference Workflow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    GEO-REFERENCE WORKFLOW                                │
└─────────────────────────────────────────────────────────────────────────┘

    1. User Input               2. Globe Animation            3. Map Tiles
    ────────────               ────────────────              ──────────

┌──────────────┐           ┌──────────────────────┐       ┌──────────────┐
│ Lat:  24.5°N │  ──────→  │ 3D Earth Zoom-in     │ ───→  │ 3x3 Tile Grid│
│ Lon:  54.5°E │           │ - 6 second animation │       │ - ESRI/Google│
│ Alt:  0m     │           │ - Target highlight   │       │ - OSM        │
└──────────────┘           │ - Stats display      │       │ - Local TMS  │
                           └──────────────────────┘       └──────────────┘
         │                                                        │
         │                                                        │
         ↓                                                        ↓
┌──────────────────────────────────────────────────────────────────────┐
│                        COORDINATE CONVERSION                          │
│                                                                       │
│   Local (meters)  ←──────────────→  Geographic (degrees)             │
│                                                                       │
│   dLat = -z / METERS_PER_DEGREE_LAT                                  │
│   dLon = x / (METERS_PER_DEGREE_LAT * cos(lat))                      │
│                                                                       │
│   Where: METERS_PER_DEGREE_LAT = 111320                              │
└──────────────────────────────────────────────────────────────────────┘
```

### 9.3 Map Tile Sources

| Source | URL Pattern | Notes |
|--------|-------------|-------|
| ESRI Satellite | `server.arcgisonline.com/.../tile/{z}/{y}/{x}` | High-res imagery |
| Google Satellite | `mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}` | Global coverage |
| Google Hybrid | `mt1.google.com/vt/lyrs=y&...` | Imagery + labels |
| OpenStreetMap | `tile.openstreetmap.org/{z}/{x}/{y}.png` | Street maps |
| Local TMS | `/tiles/{z}/{x}/{yTMS}.png` | GDAL-generated tiles |

### 9.4 KML Integration

KML files provide:
- **Survey Anchor Point**: Center coordinate for geo-reference
- **Boundary Polygon**: Overlay on 3D scene
- **Placemark Data**: Reference markers

```python
def extract_kml_data(filepath):
    """Extract center and polygon from KML"""
    return {
        'center': {'lat': center_lat, 'lon': center_lon, 'alt': center_alt},
        'points': [{'lat': ..., 'lon': ..., 'alt': ...}, ...]
    }
```

---

## 10. Cloud Storage & Database

### 10.1 Supabase Storage

#### Bucket Structure

```
{SUPABASE_BUCKET}/
├── {job_id_1}/
│   ├── index.html
│   ├── layer_1.ply
│   ├── layer_2.ply
│   ├── ...
│   ├── model.glb
│   └── metadata.json
├── {job_id_2}/
│   └── ...
```

#### Public URL Format

```
https://{project}.supabase.co/storage/v1/object/public/{bucket}/{job_id}/index.html
```

### 10.2 PostgreSQL Schema

#### Users Table

```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    is_verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### OTP Table

```sql
CREATE TABLE otp_codes (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL,
    otp VARCHAR(6) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    used BOOLEAN DEFAULT FALSE
);
```

#### Saved Views Table

```sql
CREATE TABLE saved_views (
    id SERIAL PRIMARY KEY,
    user_email VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    job_ids TEXT[] NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 11. Authentication & Security

### 11.1 JWT Token Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        AUTHENTICATION FLOW                               │
└─────────────────────────────────────────────────────────────────────────┘

    Register              Verify OTP            Login                Access
    ────────              ──────────            ─────                ──────

┌───────────┐         ┌───────────────┐     ┌───────────┐      ┌──────────┐
│ Email     │ ───────→│ OTP (6 digit) │────→│ Email     │─────→│ JWT      │
│ Password  │         │ Email sent    │     │ Password  │      │ Cookie   │
│           │         │ 10 min expiry │     │ Verify    │      │ 24h exp  │
└───────────┘         └───────────────┘     └───────────┘      └──────────┘
     │                       │                    │                  │
     ↓                       ↓                    ↓                  ↓
┌───────────┐         ┌───────────────┐     ┌───────────┐      ┌──────────┐
│ Hash pwd  │         │ Check OTP     │     │ Verify    │      │ Decode   │
│ Store DB  │         │ Mark verified │     │ password  │      │ on each  │
│ Send OTP  │         │               │     │ Create JWT│      │ request  │
└───────────┘         └───────────────┘     └───────────┘      └──────────┘
```

### 11.2 Security Considerations

| Aspect | Implementation |
|--------|----------------|
| **Password Hashing** | bcrypt with salt |
| **JWT Algorithm** | HS256 |
| **Token Expiry** | 24 hours |
| **Cookie Security** | HttpOnly (recommended) |
| **CORS** | Configurable allowed origins |
| **File Upload** | Filename sanitization |
| **OTP** | 6-digit, 10-minute expiry |

---

## 12. Deployment Guide

### 12.1 Local Development

```bash
# 1. Clone repository
git clone <repository-url>
cd GPR_VR_VIEWER

# 2. Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
copy .env.example .env
# Edit .env with your credentials

# 5. Start server
python main.py

# Server runs at https://localhost:5007 (SSL required for WebXR)
```

### 12.2 Environment Variables

```bash
# .env file
SECRET_KEY=your-secret-key-here
JWT_SECRET_KEY=your-jwt-secret-key

# Database
DATABASE_URL=postgresql://user:pass@host:5432/dbname

# Email (SMTP)
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=app-specific-password
MAIL_DEFAULT_SENDER=your-email@gmail.com

# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key
SUPABASE_BUCKET=gpr-files
```

### 12.3 Production Deployment

#### Docker Compose

```yaml
version: '3.8'
services:
  gpr-viewer:
    build: .
    ports:
      - "5007:5007"
    environment:
      - SECRET_KEY=${SECRET_KEY}
      - DATABASE_URL=${DATABASE_URL}
      - SUPABASE_URL=${SUPABASE_URL}
      - SUPABASE_KEY=${SUPABASE_KEY}
      - SUPABASE_BUCKET=${SUPABASE_BUCKET}
    volumes:
      - ./uploads:/app/uploads
      - ./processed:/app/processed
    restart: unless-stopped
```

#### Nginx Reverse Proxy

```nginx
server {
    listen 80;
    server_name gpr-viewer.example.com;
    
    location / {
        proxy_pass http://localhost:5007;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
    
    location /session/ws {
        proxy_pass http://localhost:5007;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
    
    client_max_body_size 500M;
}
```

---

## 13. Configuration Reference

### 13.1 Processing Parameters

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `threshold_percentile` | float | 0.63 | 0.0 - 1.0 | Minimum amplitude percentile to include |
| `iso_bins` | int | 5 | 1 - 20 | Number of amplitude layers |
| `depth_offset_per_level` | float | 0.05 | 0.0 - 1.0 | Vertical separation between layers (meters) |
| `vr_point_size` | float | 0.015 | 0.001 - 1.0 | Point size in VR view |
| `vr_drag_multiplier` | float | 1.0 | 0.1 - 25.0 | Sensitivity of VR horizontal dragging |
| `max_points_per_layer` | int | 500000 | 10000 - 5000000 | Maximum points per layer |
| `invert_depth` | bool | true | - | Flip Z-axis for depth display |
| `center_coordinates` | bool | true | - | Center data at origin |

### 13.2 Color Palette Reference

| Palette | Colors | Best Use |
|---------|--------|----------|
| Standard | Red → Yellow → Green → Blue | General purpose |
| Viridis | Purple → Blue → Green → Yellow | Perceptually uniform |
| Plasma | Purple → Pink → Orange → Yellow | High dynamic range |
| Inferno | Black → Purple → Orange → Yellow | Heat maps |
| Seismic | Blue → White → Red | Bidirectional data |
| Thermal | Black → Red → Orange → Yellow → White | Temperature-like |
| Ocean | Dark Blue → Light Blue → White | Depth emphasis |
| Grayscale | Black → White | Monochrome displays |
| Geology | Brown tones | Subsurface geology |
| HighContrast | Alternating bright colors | Maximum differentiation |

### 13.3 CSV Column Mapping

Expected CSV structure:

```csv
X,Y,Depth,Amplitude,...
234.5,678.9,1.25,0.85,...
```

| Index | Default Column | Data Type |
|-------|---------------|-----------|
| 0 | X (Easting) | float |
| 1 | Y (Northing) | float |
| 7 | Depth | float |
| 8 | Amplitude | float (0-1) |

---

## 14. Troubleshooting

### 14.1 Common Issues

#### VR Not Loading on Quest

**Symptoms:** Black screen, loading spinner stuck

**Solutions:**
1. Ensure HTTPS (required for WebXR)
2. Check Supabase CORS settings
3. Reduce file size (< 500K points per layer)
4. Enable foveated rendering

#### Processing Fails

**Symptoms:** Job status shows "error"

**Diagnostics:**
```bash
# Check status file
cat processed/{job_id}/status.json

# Common causes:
# - Column index out of range
# - Invalid file encoding
# - Insufficient memory
```

#### Map Tiles Not Loading

**Symptoms:** Ground plane visible but no imagery

**Solutions:**
1. Verify geo-reference anchor is set
2. Check map provider availability
3. Verify zoom level (15-19 recommended)
4. Check browser console for CORS errors

### 14.2 Performance Optimization

| Issue | Solution |
|-------|----------|
| Slow loading | Reduce `max_points_per_layer` |
| Low FPS | Reduce `iso_bins`, increase `threshold_percentile` |
| Memory crash | Process in smaller chunks, reduce grid count |
| Upload timeout | Increase `client_max_body_size` in nginx |

### 14.3 Log Locations

| Log | Location |
|-----|----------|
| Server stdout | Console / systemd journal |
| Job status | `processed/{job_id}/status.json` |
| Processing details | `processed/{job_id}/metadata.json` |

---

## 15. Appendix

### 15.1 Supported File Formats

| Format | Extension | Notes |
|--------|-----------|-------|
| CSV | .csv | Comma-separated, Latin-1 encoding |
| HDF5 | .h5, .hdf, .hdf5, .he5 | Multi-grid datasets |
| PLY | .ply | Pipe model import |
| GLB | .glb | 3D mesh overlay |
| KML | .kml | Geo-reference polygons |
| Shapefile | .zip | Zipped .shp, .shx, .dbf, .prj |

### 15.2 Browser Compatibility

| Browser | Desktop | VR |
|---------|---------|-----|
| Chrome 119+ | ✅ Full | ✅ Full |
| Firefox 120+ | ✅ Full | ⚠️ Limited |
| Safari 17+ | ⚠️ Limited | ❌ No |
| Edge 119+ | ✅ Full | ✅ Full |
| Quest Browser | N/A | ✅ Recommended |

### 15.3 Glossary

| Term | Definition |
|------|------------|
| **GPR** | Ground Penetrating Radar - subsurface imaging technology |
| **Iso-surface** | 3D surface of constant amplitude value |
| **PLY** | Polygon File Format - 3D point cloud format |
| **WebXR** | Web API for VR/AR experiences |
| **6-DoF** | Six Degrees of Freedom (position + rotation) |
| **UTM** | Universal Transverse Mercator - coordinate system |
| **TMS** | Tile Map Service - slippy map format |
| **MoM** | Minutes of Meeting - session summary document |

### 15.4 Techniques, Algorithms, and Mathematical Formulas

This section summarizes the core computational techniques used across ingestion, filtering, reconstruction, geospatial alignment, rendering, and interaction subsystems.

#### A. GPR Data Filtering and Layering

1. **Percentile threshold filtering**
  - Technique: distribution-based outlier rejection / high-signal extraction.
  - Formula:

$$
T = Q_p(A)
$$

Where $A$ is amplitude samples, $Q_p$ is the $p$-th quantile, and points are retained when $a_i \ge T$.

2. **Iso-bin layer partitioning**
  - Technique: quantile/range binning over filtered amplitudes.
  - Formula (uniform bin edges over range):

$$
e_k = a_{\min} + k\cdot\frac{a_{\max}-a_{\min}}{N_{bins}},\quad k=0..N_{bins}
$$

3. **Depth offset stacking per layer**
  - Technique: visual layer separation for readability.
  - Formula:

$$
z' = z + i\cdot\Delta z
$$

Where $i$ is layer index and $\Delta z$ is `depth_offset_per_level`.

#### B. Solid Reconstruction Pipeline

1. **Centroid computation**

$$
\mathbf{c} = \frac{1}{N}\sum_{i=1}^{N}\mathbf{p}_i
$$

2. **Principal axis estimation (PCA-like via power iteration)**
  - Technique: dominant eigenvector of covariance matrix for pipe direction.

$$
\mathbf{C}=\sum_i(\mathbf{p}_i-\mathbf{c})(\mathbf{p}_i-\mathbf{c})^T,
\quad
\mathbf{v}_{k+1}=\frac{\mathbf{C}\mathbf{v}_k}{\lVert \mathbf{C}\mathbf{v}_k\rVert}
$$

3. **Projection onto axis**

$$
t_i = \mathbf{v}\cdot(\mathbf{p}_i-\mathbf{c})
$$

4. **Axial binning and centerline sampling**
  - Technique: aggregate point clusters by projected coordinate, use bin centroids as centerline points.

5. **Robust radius estimation by quantile**
  - Technique: radial distances to axis; robust percentile (e.g., 0.7 quantile) per bin.

$$
r_b = Q_{0.7}(\{d_{i,b}\})
$$

6. **Iterative centerline smoothing**
  - Technique: neighbor-averaging relaxation.

$$
\mathbf{x}_i^{(k+1)} = (1-\alpha)\mathbf{x}_i^{(k)} + \alpha\cdot\frac{\mathbf{x}_{i-1}^{(k)}+\mathbf{x}_{i+1}^{(k)}}{2}
$$

7. **Curve fitting and tube generation**
  - Technique: centripetal Catmull-Rom interpolation and `THREE.TubeGeometry` sweep.
  - Radius model:

$$
r = \mathrm{clamp}(r_{min}, r_{max}, Q_{0.5}(\{r_b\})\cdot f_{type}\cdot s_{radius})
$$

#### C. Lasso/Branch Selection Algorithms

1. **Point-in-polygon (ray casting / crossing number)**
  - Technique: odd-even rule for polygon inclusion in screen space.

2. **Point-to-segment distance for path mode**
  - Technique: corridor selection around polyline.

$$
t = \mathrm{clamp}\left(0,1,\frac{(\mathbf{p}-\mathbf{a})\cdot(\mathbf{b}-\mathbf{a})}{\lVert\mathbf{b}-\mathbf{a}\rVert^2}\right),
\quad
d = \left\lVert \mathbf{p}-(\mathbf{a}+t(\mathbf{b}-\mathbf{a}))\right\rVert
$$

Hit condition: $d \le \frac{w}{2}$, where $w$ is path width in pixels.

#### D. Geospatial and Coordinate Transformations

1. **Local meter conversion from lat/lon deltas**

$$
x = \Delta\lambda\,R\cos\phi_0,
\quad
z = -\Delta\phi\,R
$$

Where $R$ is Earth radius, $\phi_0$ origin latitude, $\Delta\phi,\Delta\lambda$ in radians.

2. **Approximate meters-to-lat/lon inverse used in viewer tools**

$$
\Delta\text{lat} \approx -\frac{z}{111320},
\quad
\Delta\text{lon} \approx \frac{x}{111320\cos(\text{lat}_0)}
$$

3. **UTM projection support**
  - Technique: ellipsoidal Transverse Mercator equations (WGS84 constants) for survey conversion utilities.

#### E. Rendering and Interaction Techniques

1. **Point cloud rendering**
  - Technique: GPU point sprites (`THREE.Points` + `PointsMaterial`) with size attenuation.

2. **Depth slicing**
  - Technique: clipping planes in shader pipeline.
  - Planes represented by $\mathbf{n}\cdot\mathbf{x} + c = 0$ and applied as material clipping constraints.

3. **Saved-solid scan reveal animation**
  - Technique: animated clipping plane sweep + emissive envelope.
  - Sweep position:

$$
y_{scan}(t)=y_{min}+t\,(y_{max}-y_{min}),\quad t\in[0,1]
$$

4. **Camera control**
  - Technique: orbit control in spherical coordinates for stable yaw/pitch updates.

5. **VR interaction scaling**
  - Technique: controller-driven transform updates with configurable drag multiplier.

#### F. Collaboration and Session Data Flow

1. **WebSocket event synchronization**
  - Technique: publish/relay message architecture for camera, depth state, annotation, and session signals.

2. **WebRTC signaling relay**
  - Technique: targeted signal forwarding for peer negotiation in multi-participant call mesh.

#### G. Export and File Algorithms

1. **PLY mesh export**
  - Technique: non-indexed triangle expansion and face list writing.

2. **Shapefile export (ruler tool)**
  - Technique: direct binary writer for SHP/SHX/DBF/PRJ structure according to ESRI shapefile spec.

3. **KML/KMZ export**
  - Technique: dynamic XML generation and ZIP packaging (KMZ).

### 15.5 Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-01 | Initial release |
| 1.1.0 | 2026-01 | HDF5 support, multi-grid views |
| 1.2.0 | 2026-02 | VR performance optimizations |
| 1.3.0 | 2026-02 | Collaboration sessions, MoM export |
| 1.4.0 | 2026-02 | Parallel processing, Server TTS, VR button mapping updates |
| 1.5.0 | 2026-04 | Pipe isolation workflow, branch region path mode, solid smoothness/radius enhancements |
| 1.6.0 | 2026-04 | Saved branch solids APIs/UI, per-item visibility, scan-reveal animation, 2D-only depth-slice behavior fix |
| 1.7.0 | 2026-04 | Added project-wide techniques, algorithms, and mathematical formulas reference |

---

## Contact & Support

For technical support or feature requests, please contact:

- **Documentation Version:** 1.7.0
- **Last Updated:** 2026-04-21
- **Maintained By:** Stratum XR Development Team

---

*This documentation is intended for software developers, system administrators, and technical stakeholders. For end-user guides, please refer to the USER_MANUAL.md.*

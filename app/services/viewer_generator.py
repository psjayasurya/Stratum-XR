"""
Viewer Generator Service
Functions for generating HTML viewer files (Cesium and VR viewers).
"""
import os
import json
from datetime import datetime, date
from decimal import Decimal
from app.config import COLOR_PALETTES
from app.utils.colors import get_color_from_palette
from app.storage import get_base_url
from app.config import SUPABASE_URL


def safe_json_serialize(obj):
    """
    Convert non-JSON-serializable types to JSON-compatible values.
    Handles datetime, date, Decimal, numpy types, etc.
    
    Args:
        obj: Object to convert
        
    Returns:
        JSON-serializable object
    """
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    elif isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, dict):
        return {k: safe_json_serialize(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [safe_json_serialize(item) for item in obj]
    elif hasattr(obj, '__dict__'):
        # Handle objects with __dict__ (like custom classes)
        return safe_json_serialize(obj.__dict__)
    else:
        try:
            # Try converting numpy types, etc.
            if isinstance(obj, type) or callable(obj):
                return str(obj)
            # Check for numpy types
            if hasattr(obj, 'item'):
                return obj.item()
            return obj
        except:
            return str(obj)


def generate_layer_loaders(ply_files, amplitude_ranges, output_dir, job_id):
    """
    Generate JavaScript code to load PLY layers
    
    Args:
        ply_files: List of PLY file paths
        amplitude_ranges: List of (min, max) amplitude tuples for each layer
        output_dir: Output directory path
        job_id: Job identifier
        
    Returns:
        JavaScript code string for loading layers
    """
    loaders = []
    for i, ply_file in enumerate(ply_files):
        amp_min, amp_max = amplitude_ranges[i]
        filename = os.path.basename(ply_file)
        loaders.append(f'''
        layerPromises.push(
            new Promise((resolve) => {{
                plyLoader.load('[[BASE_URL]]/{filename}', (geometry) => {{
                    const isTransparent = window.currentPointShape !== 'square';
                    const material = new THREE.PointsMaterial({{
                        size: pointSize, 
                        vertexColors: true,
                        sizeAttenuation: true,
                        map: window.pointShapeTextures[window.currentPointShape] || null,
                        transparent: isTransparent,
                        alphaTest: isTransparent ? 0.05 : 0,
                        depthWrite: true
                    }});
                    const points = new THREE.Points(geometry, material);
                    points.renderOrder = 5; // Standard order
                    
                    // VR Performance Optimization
                    if (typeof optimizeModel === 'function') optimizeModel(points);

                    points.userData.layerIndex = {i};
                    points.userData.amplitudeMin = {amp_min};
                    points.userData.amplitudeMax = {amp_max};
                    pointCloudGroup.add(points);
                    layers[{i}] = points;
                    loadedCount++;
                    updateLoadingProgress((loadedCount / totalFiles) * 100, 'Loaded layer {i+1}');
                    resolve();
                }},
                undefined,
                (error) => {{
                    console.error('Error loading layer {i+1}:', error);
                    loadedCount++;
                    resolve();
                }});
            }})
        );''')
    return '\\n'.join(loaders)


def create_cesium_viewer(cesium_data, output_dir, job_id):
    """
    Create the Cesium viewer HTML file
    
    Args:
        cesium_data: Dictionary containing Cesium viewer data
        output_dir: Output directory path
        job_id: Job identifier
    """
    try:
        template_name = 'cesium_viewer_template.html'
        template_path = os.path.join('templates', template_name)
        if not os.path.exists(template_path):
             template_path = os.path.join(os.path.dirname(__file__), '..', '..', 'templates', template_name)
        
        with open(template_path, 'r', encoding='utf-8') as f:
            html = f.read()
        
        html = html.replace('[[CESIUM_DATA_JSON]]', json.dumps(cesium_data))
        html = html.replace('[[GEO_ANCHOR]]', "0, 0, 0")
        
        with open(os.path.join(output_dir, 'cesium.html'), 'w', encoding='utf-8') as f:
            f.write(html)
            
        print(f"Created Cesium viewer for job {job_id}")
    except Exception as e:
        print(f"Error creating Cesium viewer: {e}")


def create_vr_viewer(ply_files, layer_info, legend_info, output_dir, settings, data_info, job_id,
                      cesium_data=None, has_surface=False, surface_info=None, num_slices=0, 
                      total_files=0, pipe_file=None, multi_grids=None):
    """
    Create the VR viewer HTML file
    
    Args:
        ply_files: List of PLY file paths
        layer_info: HTML string with layer information
        legend_info: HTML string with legend information
        output_dir: Output directory path
        settings: Processing settings dictionary
        data_info: Data information dictionary
        job_id: Job identifier
        cesium_data: Optional Cesium data dictionary
        has_surface: Whether surface is generated
        surface_info: Optional surface information
        num_slices: Number of depth slices
        total_files: Total number of files
        pipe_file: Optional pipe file name
        multi_grids: Optional multi-grid configuration
        
    Returns:
        HTML content string if multi_grids, else writes to file
    """
    if total_files == 0 and ply_files:
        total_files = len(ply_files)

    if not multi_grids:
        amplitude_ranges = []
        for i in range(len(ply_files)):
            amp_min = data_info['amp_min'] + (i / len(ply_files)) * (data_info['amp_max'] - data_info['amp_min'])
            amp_max = data_info['amp_min'] + ((i + 1) / len(ply_files)) * (data_info['amp_max'] - data_info['amp_min'])
            amplitude_ranges.append((amp_min, amp_max))
        
        layer_loaders_js = generate_layer_loaders(ply_files, amplitude_ranges, output_dir, job_id)
        if has_surface and surface_info:
            sf_file = surface_info.get('filename', 'surface.obj')
            surface_loader_js = f'''
            const surfaceLoader = new OBJLoader();
            surfaceLoader.load('[[BASE_URL]]/{sf_file}', (object) => {{
                object.traverse((child) => {{
                    if (child.isMesh) {{
                        child.material = new THREE.MeshStandardMaterial({{
                            color: 0x00ff00, 
                            roughness: 0.3,
                            metalness: 0.2,
                            transparent: true,
                            opacity: 0.7,
                            side: THREE.DoubleSide
                        }});
                        // Optimize for VR
                        child.geometry.computeVertexNormals();
                    }}
                }});
                surfaceGroup.add(object);
                surfaceGroup.visible = true; // Show by default
                
                // Add Checkbox for Surface
                const layerList = document.getElementById('layer-list');
                const surfDiv = document.createElement('div');
                surfDiv.className = 'layer-item';
                surfDiv.innerHTML = `
                    <input type="checkbox" id="showSurface" checked onchange="surfaceGroup.visible = this.checked">
                    <label for="showSurface" class="layer-label">
                        <span class="color-swatch" style="background:#00ff00"></span>
                        Isosurface Mesh
                    </label>
                `;
                layerList.insertBefore(surfDiv, layerList.firstChild);
                
                console.log('Loaded Surface Mesh');
            }}, undefined, (err) => {{ console.error('Surface load error', err); }});
            '''
        
        slice_loader_js = ""
        
        pipe_loader_js = ""
        if pipe_file:
            pipe_loader_js = f'''
            pipeGroup = new THREE.Group();
            pipeGroup.visible = false;
            mainGroup.add(pipeGroup);
            const pipeLoader = new PLYLoader();
            pipeLoader.load('[[BASE_URL]]/{pipe_file}', (geometry) => {{
                geometry.computeVertexNormals();
                const material = new THREE.MeshStandardMaterial({{ 
                    color: 0xaaaaaa, metalness: 0.5, roughness: 0.5, side: THREE.DoubleSide
                }});
                const mesh = new THREE.Mesh(geometry, material);
                
                // VR Performance Optimization
                if (typeof optimizeModel === 'function') optimizeModel(mesh);

                const offsetX = {data_info.get('offset_x', 0)};
                const offsetY = {data_info.get('offset_y', 0)};
                mesh.position.set(-offsetX, -offsetY, 0);
                const sf = {data_info.get('scale_factor', 1.0)};
                mesh.scale.setScalar(sf);
                mesh.rotation.x = Math.PI / 2;
                pipeGroup.add(mesh);
                console.log('Loaded Pipe');
            }}, undefined, (err) => {{ console.error('Pipe load error', err); }});
            '''
        
        x_len = data_info['x_max'] - data_info['x_min']
        y_len = data_info['y_max'] - data_info['y_min']
        z_len = abs(data_info['z_max'] - data_info['z_min'])
        
        ground_size_calc = round(max(x_len, y_len) * 1.5, 3)
        pipe_display_style = 'block' if pipe_file else 'none'
        
        kml_lat = settings.get('kml_anchor', {}).get('lat', 13.717392)
        kml_lon = settings.get('kml_anchor', {}).get('lon', 79.591314)
        kml_alt = settings.get('kml_anchor', {}).get('alt', 0.0)
        kml_polygon = settings.get('kml_polygon', [])
        
        grids_json = "[]"
        is_multi = "false"
    else:
        is_multi = "true"
        # Safely serialize multi_grids, converting non-JSON-serializable types
        safe_grids = safe_json_serialize(multi_grids)
        grids_json = json.dumps(safe_grids)
        total_files = sum(len(grid['ply_files']) for grid in multi_grids)
        num_ply_files = total_files
        
        first = multi_grids[0]
        data_info = first['data_info']
        settings = first['settings']
        job_id = first['job_id']
        
        x_len = data_info['x_max'] - data_info['x_min']
        y_len = data_info['y_max'] - data_info['y_min']
        z_len = abs(data_info['z_max'] - data_info['z_min'])
        
        ground_size_calc = 500
        pipe_display_style = 'none'
        
        kml_lat = settings.get('kml_anchor', {}).get('lat', 13.717392)
        kml_lon = settings.get('kml_anchor', {}).get('lon', 79.591314)
        kml_alt = settings.get('kml_anchor', {}).get('alt', 0.0)
        kml_polygon = settings.get('kml_polygon', [])
        
        layer_loaders_js = "// Multi-grid handle in JS"
        surface_loader_js = ""
        slice_loader_js = ""
        pipe_loader_js = ""
        
        avg_amp_min = sum(g['data_info'].get('amp_min', 0) for g in multi_grids) / len(multi_grids)
        avg_amp_max = sum(g['data_info'].get('amp_max', 1000) for g in multi_grids) / len(multi_grids)
        
        legend_info = ""
        steps = 10
        for i in range(steps):
            norm = i / (steps - 1)
            val = avg_amp_min + norm * (avg_amp_max - avg_amp_min)
            r, g, b = get_color_from_palette(norm, settings['color_palette'])
            color_hex = '#{:02x}{:02x}{:02x}'.format(r, g, b)
            legend_info = f'<div style="display:flex; justify-content: space-between; font-size:10px;"><span style="color:{color_hex}">■</span><span>{val:.0f}</span></div>' + legend_info

    base_url = get_base_url(job_id)

    template_path = os.path.join(os.path.dirname(__file__), '..', '..', 'templates', 'vr_viewer_template.html')
    
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
    except FileNotFoundError:
        print(f"Error: Template file not found at {template_path}")
        return

    replacements = {
        '[[ORIGINAL_FILENAME]]': str(data_info['original_filename']) if not multi_grids else "Multi-Grid Project",
        '[[TOTAL_POINTS_FORMATTED]]': f"{data_info['total_points']:,}" if not multi_grids else "Varies",
        '[[X_LEN]]': f"{x_len:.2f}",
        '[[Y_LEN]]': f"{y_len:.2f}",
        '[[Z_LEN]]': f"{z_len:.2f}",
        '[[COLOR_PALETTE]]': str(settings['color_palette']),
        '[[VR_POINT_SIZE]]': str(settings['vr_point_size']),
        '[[SURFACE_OPACITY]]': str(settings.get('surface_opacity', 0.6)),
        '[[NUM_SLICES]]': str(num_slices if not multi_grids else 0),
        '[[TOTAL_FILES]]': str(total_files),
        '[[PROCESSING_DATE]]': str(data_info['processing_date']),
        '[[GROUND_SIZE_CALC]]': str(ground_size_calc),
        '[[FONT_SIZE_MULTIPLIER]]': str(settings.get('font_size_multiplier', 1.0)),
        '[[FONT_FAMILY]]': str(settings.get('font_family', 'Arial')),
        '[[NUM_PLY_FILES]]': str(len(ply_files) if not multi_grids else num_ply_files),
        '[[PIPE_DISPLAY]]': pipe_display_style,
        '[[AMP_MIN]]': str(data_info.get('amp_min', 0)),
        '[[AMP_MAX]]': str(data_info.get('amp_max', 1000)),
        '[[LAYER_INFO]]': layer_info,
        '[[LEGEND_INFO]]': legend_info,
        '[[LAYER_LOADERS_JS]]': layer_loaders_js,
        '[[SURFACE_LOADER_JS]]': surface_loader_js,
        '[[SLICE_LOADER_JS]]': slice_loader_js,
        '[[PIPE_LOADER_JS]]': pipe_loader_js,
        '[[CESIUM_DATA_JSON]]': json.dumps(safe_json_serialize(cesium_data)) if cesium_data else "{}",
        '[[KML_LAT]]': str(kml_lat),
        '[[KML_LON]]': str(kml_lon),
        '[[KML_ALT]]': str(kml_alt),
        '[[KML_POLYGON_JSON]]': json.dumps(safe_json_serialize(kml_polygon)),
        '[[COLOR_PALETTES_JSON]]': json.dumps(safe_json_serialize(COLOR_PALETTES)),
        '[[GRIDS_DATA_JSON]]': grids_json,
        '[[IS_MULTI]]': is_multi,
        '[[BASE_URL]]': base_url,
        '[[SUPABASE_URL]]': str(SUPABASE_URL) if SUPABASE_URL else "",
        '[[MODEL_BUCKET]]': "testing",
        '[[DEPTH_MIN]]': f"{abs(data_info.get('z_max', 0)):.1f}",
        '[[DEPTH_MAX]]': f"{abs(data_info.get('z_min', 10)):.1f}",
        '[[JOB_ID]]': str(job_id) if job_id else ''
    }

    for key, value in replacements.items():
        html_content = html_content.replace(key, value)

    if multi_grids:
        return html_content
    else:
        with open(os.path.join(output_dir, 'index.html'), 'w', encoding='utf-8') as f:
            f.write(html_content)


__all__ = ['generate_layer_loaders', 'create_cesium_viewer', 'create_vr_viewer']

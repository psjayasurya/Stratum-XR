"""
KML Parser Service
Functions for parsing KML files and extracting geolocation data.
"""
import xml.etree.ElementTree as ET


def extract_kml_data(filepath):
    """
    Extract center and all coordinates from a KML file
    
    Args:
        filepath: Path to the KML file
        
    Returns:
        Dictionary with 'center' (lat/lon/alt) and 'points' list,
        or None if parsing fails
    """
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
        namespace = {'kml': 'http://www.opengis.net/kml/2.2'}
        
        coords_elements = root.findall('.//kml:coordinates', namespace)
        if not coords_elements:
            coords_elements = root.findall('.//coordinates')
        
        all_lons = []
        all_lats = []
        all_alts = []
        all_points = []
        
        for elem in coords_elements:
            coords_text = elem.text.strip() if elem.text else ""
            points = coords_text.split()
            for p in points:
                parts = p.split(',')
                if len(parts) >= 2:
                    lon = float(parts[0])
                    lat = float(parts[1])
                    alt = float(parts[2]) if len(parts) >= 3 else 0.0
                    
                    all_lons.append(lon)
                    all_lats.append(lat)
                    all_alts.append(alt)
                    all_points.append({'lat': lat, 'lon': lon, 'alt': alt})
        
        if not all_lats or not all_lons:
            return None
        
        center_lat = sum(all_lats) / len(all_lats)
        center_lon = sum(all_lons) / len(all_lons)
        center_alt = sum(all_alts) / len(all_alts) if all_alts else 0.0
        
        return {
            'center': {'lat': center_lat, 'lon': center_lon, 'alt': center_alt},
            'points': all_points
        }
    except Exception as e:
        print(f"Error parsing KML: {e}")
        return None


__all__ = ['extract_kml_data']

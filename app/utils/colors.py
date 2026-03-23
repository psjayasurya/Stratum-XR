"""
Color Utilities
Functions for color palette management and interpolation.
"""
import numpy as np
from app.config import COLOR_PALETTES


def interpolate_color(palette, value):
    """
    Interpolate color from palette for a value between 0 and 1
    
    Args:
        palette: List of RGB colors [[r,g,b], ...]
        value: Float between 0 and 1
        
    Returns:
        List [r, g, b] representing interpolated color
    """
    if len(palette) == 1:
        return palette[0]
    
    val_scaled = value * (len(palette) - 1)
    idx = int(val_scaled)
    
    if idx >= len(palette) - 1:
        return palette[-1]
    
    t = val_scaled - idx
    c1 = np.array(palette[idx])
    c2 = np.array(palette[idx + 1])
    
    return (c1 * (1 - t) + c2 * t).astype(int).tolist()


def get_color_from_palette(value, palette_name='Viridis'):
    """
    Get RGB color for a normalized value (0-1) or index from a palette.
    
    Args:
        value: Float (0-1) for interpolated color or int for direct index
        palette_name: Name of the color palette to use
        
    Returns:
        List [r, g, b] representing  color
    """
    palette = COLOR_PALETTES.get(palette_name, COLOR_PALETTES['Viridis'])
    
    if isinstance(value, (int, np.integer)):
        idx = value % len(palette)
        return palette[idx]
    else:
        return interpolate_color(palette, float(value))


def create_iso_colormap(iso_level, total_levels, palette_name='Viridis'):
    """
    Wrapper for backward compatibility
    Creates a colormap for iso-surface levels
    
    Args:
        iso_level: Current iso-surface level
        total_levels: Total number of iso-surface levels
        palette_name: Name of the color palette
        
    Returns:
        List [r, g, b] representing color
    """
    return get_color_from_palette(iso_level, palette_name)


__all__ = ['interpolate_color', 'get_color_from_palette', 'create_iso_colormap']

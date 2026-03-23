"""
PLY Generator Service
Functions for generating PLY (Polygon File Format) point cloud files.
"""
import numpy as np


def write_ply_fast(filename, points, colors):
    """
    Write points and colors to a PLY file in binary format
    
    Args:
        filename: Output PLY file path
        points: Numpy array of shape (N, 3) with x, y, z coordinates
        colors: Numpy array of shape (N, 3) with r, g, b values (0-255)
    """
    vertex_dtype = [
        ('x', '<f4'), ('y', '<f4'), ('z', '<f4'),
        ('red', 'u1'), ('green', 'u1'), ('blue', 'u1')
    ]
    
    vertices = np.empty(len(points), dtype=vertex_dtype)
    vertices['x'] = points[:, 0].astype(np.float32)
    vertices['y'] = points[:, 1].astype(np.float32)
    vertices['z'] = points[:, 2].astype(np.float32)
    vertices['red'] = colors[:, 0].astype(np.uint8)
    vertices['green'] = colors[:, 1].astype(np.uint8)
    vertices['blue'] = colors[:, 2].astype(np.uint8)

    header = f"""ply
format binary_little_endian 1.0
element vertex {len(points)}
property float x
property float y
property float z
property uchar red
property uchar green
property uchar blue
end_header
"""
    with open(filename, 'wb') as f:
        f.write(header.encode('utf-8'))
        vertices.tofile(f)


__all__ = ['write_ply_fast']

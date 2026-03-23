"""
File Utilities
Functions for file operations and filename sanitization.
"""
import re


def secure_filename(filename: str) -> str:
    """
    Sanitize filename while preserving @ for email addresses
    
    Args:
        filename: Original filename
        
    Returns:
        Sanitized filename safe for filesystem
    """
    # Allow word characters, spaces, dots, hyphens, and @ symbol
    filename = re.sub(r'[^\w\s.@-]', '', filename)
    filename = re.sub(r'\s+', '_', filename)
    return filename


__all__ = ['secure_filename']

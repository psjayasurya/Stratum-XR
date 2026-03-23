
import pandas as pd
from typing import Dict, Any
from .base import DataParser

class CSVDataParser(DataParser):
    """Parser for CSV / Text based GPR data."""

    def parse(self, filepath: str, settings: Dict[str, Any]) -> pd.DataFrame:
        """
        Parse CSV file with encoding detection.
        """
        df = None
        encodings = ['utf-8', 'latin1', 'ISO-8859-1', 'cp1252', 'utf-16', 'ascii']
        
        for encoding in encodings:
            try:
                df = pd.read_csv(filepath, encoding=encoding)
                print(f"Successfully read with {encoding} encoding")
                break
            except (UnicodeDecodeError, pd.errors.ParserError) as e:
                # print(f"Failed with {encoding}: {e}") # Optional logging
                continue
        
        if df is None:
            try:
                df = pd.read_csv(filepath, encoding_errors='ignore')
                print("Read with encoding errors ignored")
            except Exception as e:
                raise ValueError(f"Failed to read CSV file: {str(e)}")
        
        # Check columns
        required_idx = max(
            settings.get('col_idx_x', 0),
            settings.get('col_idx_y', 1), 
            settings.get('col_idx_z', 2),
            settings.get('col_idx_amplitude', 3)
        )
        
        if len(df.columns) <= required_idx:
            raise ValueError(f"CSV file has only {len(df.columns)} columns, but index {required_idx} is required.")
            
        # Extract columns based on settings
        raw_x = pd.to_numeric(df.iloc[:, settings.get('col_idx_x', 0)], errors='coerce')
        raw_y = pd.to_numeric(df.iloc[:, settings.get('col_idx_y', 1)], errors='coerce')
        raw_z = pd.to_numeric(df.iloc[:, settings.get('col_idx_z', 2)], errors='coerce')
        raw_amp = pd.to_numeric(df.iloc[:, settings.get('col_idx_amplitude', 3)], errors='coerce')
        
        data = pd.DataFrame({
            'x': raw_x, 'y': raw_y, 'z': raw_z, 'amp': raw_amp
        }).dropna()

        if len(data) == 0:
            raise ValueError("No valid numeric data found in specified columns.")
            
        return data

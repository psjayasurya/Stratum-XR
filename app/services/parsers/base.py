from abc import ABC, abstractmethod
import pandas as pd
from typing import Dict, Any

class DataParser(ABC):
    """Abstract base class for GPR data parsers."""

    @abstractmethod
    def parse(self, filepath: str, settings: Dict[str, Any]) -> pd.DataFrame:
        """
        Parse a data file and return a DataFrame with x, y, z, amp columns.
        
        Args:
            filepath: Path to the file to parse.
            settings: Dictionary of processing settings.
            
        Returns:
            pandas.DataFrame including 'x', 'y', 'z', 'amp' columns.
        """
        pass

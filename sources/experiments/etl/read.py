import os
import json
import gzip
from typing import List, Dict, Optional, Union

def read_cpi_file(filepath: str) -> Dict:
    """
    Read a single CPI file (.cpi)
    
    Args:
        filepath (str): Path to the CPI file
        
    Returns:
        Dict: The CPI dictionary
        
    Raises:
        FileNotFoundError: If file doesn't exist
        json.JSONDecodeError: If file isn't valid JSON
    """
    with open(filepath, 'r') as f:
        return json.load(f)

def read_cpi_bundle(filepath: str) -> List[Dict]:
    """
    Read a compressed CPI bundle file (.cpis.gz)
    
    Args:
        filepath (str): Path to the bundle file
        
    Returns:
        List[Dict]: List of CPI dictionaries
        
    Raises:
        FileNotFoundError: If file doesn't exist
        json.JSONDecodeError: If file isn't valid JSON
    """
    with gzip.open(filepath, 'rt', encoding='utf-8') as f:
        return json.load(f)

def read_cpi_bundles(
    directory: str = 'CPIs',
    bundle_pattern: Optional[str] = None,
    x: Optional[int] = None,
    y: Optional[int] = None
) -> List[Dict]:
    """
    Read multiple CPI bundle files
    
    Args:
        directory (str): Directory containing the bundle files
        bundle_pattern (str, optional): Pattern to match bundle files (e.g., "x1_y*")
        x (int, optional): Specific x value to load
        y (int, optional): Specific y value to load
        
    Returns:
        List[Dict]: Combined list of CPI dictionaries from all matching bundles
    """
    all_cpis = []
    
    # Determine which files to process
    if x is not None and y is not None:
        files = [f"cpi_bundle_x{x}_y{y}.cpis.gz"]
    elif bundle_pattern:
        files = [f for f in os.listdir(directory) 
                if f.endswith('.cpis.gz') and bundle_pattern in f]
    else:
        files = [f for f in os.listdir(directory) if f.endswith('.cpis.gz')]
    
    # Process each file
    for filename in files:
        try:
            filepath = os.path.join(directory, filename)
            if os.path.exists(filepath):
                bundle_data = read_cpi_bundle(filepath)
                all_cpis.extend(bundle_data)
        except Exception as e:
            print(f"Error reading bundle {filename}: {str(e)}")
            
    return all_cpis

def read_cpi(path: str) -> Union[Dict, List[Dict]]:
    """
    Read either a CPI file or bundle based on file extension
    
    Args:
        path (str): Path to the CPI file or bundle
        
    Returns:
        Union[Dict, List[Dict]]: Single CPI dict for .cpi files,
                                list of CPI dicts for .cpis.gz files
    """
    if path.endswith('.cpis.gz'):
        return read_cpi_bundle(path)
    elif path.endswith('.cpi'):
        return read_cpi_file(path)
    else:
        raise ValueError("File must have .cpi or .cpis.gz extension")
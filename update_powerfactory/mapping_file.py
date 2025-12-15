"""
Mapping file handling for IPS to PowerFactory settings transfer.

This module manages the CSV mapping files that define how IPS settings
are mapped to PowerFactory relay attributes. It provides:
- Type mapping lookup (IPS pattern -> PF relay type + mapping file)
- Detailed mapping file parsing
- Curve mapping for IDMT characteristics
- CB alternate name mapping

Performance optimizations:
- All CSV files are cached after first read
- Type mapping is indexed by relay pattern for O(1) lookup
- Mapping files are cached by filename
- Curve mapping is loaded once and reused
"""

import csv
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any

logger = logging.getLogger(__name__)

# Network path to mapping files
MAP_FILE_LOC = "\\\\ecasd01\\WksMgmt\\PowerFactory\\ScriptsDEV\\IPSProtectionDeviceSettings\\mapping"


# =============================================================================
# Cache storage
# =============================================================================

@dataclass
class MappingCache:
    """
    Cache for all mapping file data.
    
    This class stores parsed CSV data to avoid repeated file I/O.
    All caches are populated on first access and reused thereafter.
    
    Attributes:
        type_mapping: Dict mapping relay pattern -> (mapping_filename, relay_type)
        mapping_files: Dict mapping filename -> parsed mapping data
        curve_mapping: List of curve mapping rows
        cb_alt_names: List of CB alternate name dictionaries
        initialized: Whether the type_mapping has been loaded
    """
    type_mapping: Dict[str, Tuple[str, str]] = field(default_factory=dict)
    mapping_files: Dict[str, List[List[str]]] = field(default_factory=dict)
    curve_mapping: List[List[str]] = field(default_factory=list)
    cb_alt_names: List[Dict[str, str]] = field(default_factory=list)
    initialized: bool = False


# Global cache instance
_cache = MappingCache()


def clear_cache() -> None:
    """
    Clear all cached mapping data.
    
    Call this if mapping files have been updated and need to be reloaded.
    """
    global _cache
    _cache = MappingCache()
    logger.info("Mapping file cache cleared")


def get_cache_stats() -> Dict[str, int]:
    """
    Get statistics about the current cache state.
    
    Returns:
        Dictionary with counts of cached items
    """
    return {
        "type_mappings": len(_cache.type_mapping),
        "mapping_files": len(_cache.mapping_files),
        "curve_mappings": len(_cache.curve_mapping),
        "cb_alt_names": len(_cache.cb_alt_names),
    }


# =============================================================================
# Type mapping (relay pattern -> mapping file + relay type)
# =============================================================================

def _load_type_mapping() -> None:
    """
    Load and index the type_mapping.csv file.
    
    This creates a dictionary for O(1) lookup of relay patterns.
    Called automatically on first access.
    """
    global _cache
    
    if _cache.initialized:
        return
    
    try:
        filepath = f"{MAP_FILE_LOC}\\type_mapping.csv"
        with open(filepath, "r") as csv_file:
            for row in csv_file.readlines():
                line = row.strip().split(",")
                if len(line) >= 3 and line[0]:
                    # Index by relay pattern: pattern -> (mapping_file, relay_type)
                    _cache.type_mapping[line[0]] = (line[1], line[2])
        
        _cache.initialized = True
        logger.info(f"Type mapping loaded: {len(_cache.type_mapping)} patterns indexed")
        
    except FileNotFoundError:
        logger.error(f"Type mapping file not found: {filepath}")
        _cache.initialized = True  # Mark as initialized to avoid repeated attempts
    except Exception as e:
        logger.error(f"Error loading type mapping: {e}")
        _cache.initialized = True


def get_type_mapping(rel_pattern: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Get the mapping filename and relay type for a relay pattern.
    
    Uses cached data with O(1) lookup.
    
    Args:
        rel_pattern: The IPS relay pattern name
        
    Returns:
        Tuple of (mapping_filename, relay_type), or (None, None) if not found
    """
    _load_type_mapping()
    
    result = _cache.type_mapping.get(rel_pattern)
    if result:
        return result
    return (None, None)


# =============================================================================
# Individual mapping files
# =============================================================================

def _load_mapping_file(filename: str) -> Optional[List[List[str]]]:
    """
    Load and parse a mapping CSV file.
    
    The parsed data is cached for reuse. Note that device-specific
    substitutions (replacing "Default" with device name) are done
    at read time, so we cache the raw data and apply substitutions
    when returning.
    
    Args:
        filename: Name of the mapping file (without path)
        
    Returns:
        List of parsed rows, or None if file not found
    """
    global _cache
    
    # Check cache first
    if filename in _cache.mapping_files:
        return _cache.mapping_files[filename]
    
    try:
        filepath = f"{MAP_FILE_LOC}\\{filename}.csv"
        mapping_data = []
        
        with open(filepath, "r") as csv_file:
            reader = csv.reader(csv_file, skipinitialspace=True)
            for row in reader:
                # Skip header row
                if len(row) >= 2 and "FOLDER" in row[0] and "ELEMENT" in row[1]:
                    continue
                
                # Skip rows with None in column 3 (unless it's a dip switch)
                if len(row) > 3 and row[3] == "None" and "_dip" not in row[1]:
                    if len(row) > 4:
                        if not row[4]:
                            continue
                    else:
                        continue
                
                # Remove empty elements from the row
                element_line = [element for element in row if element]
                if element_line:
                    mapping_data.append(element_line)
        
        # Cache the parsed data
        _cache.mapping_files[filename] = mapping_data
        logger.debug(f"Mapping file loaded and cached: {filename} ({len(mapping_data)} rows)")
        
        return mapping_data
        
    except FileNotFoundError:
        logger.warning(f"Mapping file not found: {filename}")
        # Cache the miss to avoid repeated file access attempts
        _cache.mapping_files[filename] = None
        return None
    except Exception as e:
        logger.error(f"Error loading mapping file {filename}: {e}")
        return None


def _apply_device_substitution(
    mapping_data: List[List[str]], 
    device_name: str
) -> List[List[str]]:
    """
    Apply device-specific substitutions to mapping data.
    
    Replaces "Relay Model", "Default", or "default" in column 0
    with the actual device name.
    
    Args:
        mapping_data: Raw mapping data from cache
        device_name: Name of the PowerFactory device
        
    Returns:
        Copy of mapping data with substitutions applied
    """
    result = []
    for row in mapping_data:
        # Create a copy of the row to avoid modifying cached data
        new_row = row.copy()
        if new_row[0] in ["Relay Model", "Default", "default"]:
            new_row[0] = device_name
        result.append(new_row)
    return result


# =============================================================================
# Public API - main entry points
# =============================================================================

def read_mapping_file(
    app, 
    rel_pattern: str, 
    pf_device: Any
) -> Tuple[Optional[List[List[str]]], Optional[str]]:
    """
    Read and return the mapping file for a relay pattern.
    
    This is the main entry point for getting mapping data. It uses
    cached data where available and applies device-specific substitutions.
    
    Args:
        app: PowerFactory application object
        rel_pattern: The IPS relay pattern name
        pf_device: The PowerFactory device object (for name substitution)
        
    Returns:
        Tuple of (mapping_file_data, relay_type), or (None, None) if not found
    """
    # Get the mapping filename and relay type
    mapping_filename, relay_type = get_type_mapping(rel_pattern)
    
    if not mapping_filename:
        logger.debug(f"No type mapping found for pattern: {rel_pattern}")
        return (None, None)
    
    # Load the mapping file (from cache if available)
    raw_mapping = _load_mapping_file(mapping_filename)
    
    if raw_mapping is None:
        return (None, None)
    
    # Apply device-specific substitutions
    device_name = pf_device.loc_name
    mapping_data = _apply_device_substitution(raw_mapping, device_name)
    
    return (mapping_data, relay_type)


# =============================================================================
# Curve mapping
# =============================================================================

def _load_curve_mapping() -> List[List[str]]:
    """
    Load the curve mapping file.
    
    Returns cached data if available.
    
    Returns:
        List of curve mapping rows
    """
    global _cache
    
    if _cache.curve_mapping:
        return _cache.curve_mapping
    
    try:
        filepath = f"{MAP_FILE_LOC}\\curve_mapping.csv"
        with open(filepath, "r") as csv_file:
            for row in csv_file.readlines():
                line = row.strip().split(",")
                if len(line) >= 3:
                    _cache.curve_mapping.append(line)
        
        logger.debug(f"Curve mapping loaded: {len(_cache.curve_mapping)} entries")
        
    except FileNotFoundError:
        logger.warning("Curve mapping file not found")
    except Exception as e:
        logger.error(f"Error loading curve mapping: {e}")
    
    return _cache.curve_mapping


def get_pf_curve(app, setting_value: str, element: Any) -> Optional[Any]:
    """
    Get the PowerFactory curve object matching a setting value.
    
    Curves are the one setting that requires a PF object to be assigned
    to the attribute. This function tries multiple matching strategies:
    1. Exact name match
    2. Partial name match
    3. Curve mapping file lookup
    4. Keyword-based matching (Extreme, Standard, Very, etc.)
    5. Default to Standard Inverse
    
    Args:
        app: PowerFactory application object
        setting_value: The curve setting value from IPS
        element: The PowerFactory element containing the curve
        
    Returns:
        The matching PowerFactory curve object, or None if not found
    """
    idmt_type = element.typ_id
    curves = idmt_type.GetAttribute("e:pcharac")
    
    if not curves:
        return None
    
    # Strategy 1: Exact match
    for curve in curves:
        if curve.loc_name == setting_value:
            return curve
    
    # Strategy 2: Partial match (collect candidates)
    reduced_curves = []
    for curve in curves:
        if setting_value in curve.loc_name or curve.loc_name in setting_value:
            reduced_curves.append(curve)
    
    for curve in reduced_curves:
        if setting_value in curve.loc_name:
            return curve
    
    for curve in reduced_curves:
        if curve.loc_name in setting_value:
            return curve
    
    # Strategy 3: Curve mapping file lookup
    curve_mapping = _load_curve_mapping()
    
    for mapping_row in curve_mapping:
        if len(mapping_row) < 3:
            continue
        
        mapped_value = mapping_row[1]
        
        # Handle binary values - pad with leading zeros
        try:
            int(mapped_value)
            while len(mapped_value) < len(setting_value):
                mapped_value = "0" + mapped_value
        except ValueError:
            pass
        
        if setting_value == mapped_value:
            target_name = mapping_row[2]
            for curve in curves:
                if curve.loc_name == target_name:
                    return curve
    
    # Strategy 4: Keyword-based matching
    keyword_map = [
        ("Extreme", "Extreme"),
        ("Standard", "Standard"),
        ("Very", "Very"),
        ("DT", "Definite"),
        ("Curve A", "Curve A"),
        ("Curve B", "Curve B"),
        ("Curve C", "Curve C"),
        ("Curve D", "Curve D"),
    ]
    
    for setting_keyword, curve_keyword in keyword_map:
        if setting_keyword in setting_value:
            for curve in curves:
                if curve_keyword in curve.loc_name:
                    return curve
    
    # Strategy 5: Default to Standard Inverse
    for curve in curves:
        if "Standard" in curve.loc_name:
            return curve
    
    # No match found
    logger.warning(f"No curve match found for: {setting_value}")
    return None


# =============================================================================
# CB alternate name mapping
# =============================================================================

def _load_cb_alt_names() -> List[Dict[str, str]]:
    """
    Load the CB alternate name mapping file.
    
    Returns cached data if available.
    
    Returns:
        List of CB alternate name dictionaries
    """
    global _cache
    
    if _cache.cb_alt_names:
        return _cache.cb_alt_names
    
    try:
        filepath = f"{MAP_FILE_LOC}\\CB_ALT_NAME.csv"
        columns = ["PROJECT", "GRID", "SUBSTATION", "CB_NAME", "NEW_NAME"]
        skip_values = ["not needed", "no active setting", "wrong sub name", "unknown"]
        
        with open(filepath, "r") as csv_file:
            for row in csv_file.readlines():
                line = row.strip().split(",")
                
                # Skip header
                if line[0] == "PROJECT":
                    continue
                
                # Skip invalid entries
                if len(line) >= 5 and line[-1].lower() in skip_values:
                    continue
                
                # Build dictionary
                if len(line) >= 5:
                    line_dict = {col: line[i] for i, col in enumerate(columns)}
                    _cache.cb_alt_names.append(line_dict)
        
        logger.info(f"CB alt names loaded: {len(_cache.cb_alt_names)} entries")
        
    except FileNotFoundError:
        logger.warning("CB alt name file not found")
    except Exception as e:
        logger.error(f"Error loading CB alt names: {e}")
    
    return _cache.cb_alt_names


def get_cb_alt_name_list(app) -> List[Dict[str, str]]:
    """
    Get the list of CB alternate name mappings.
    
    Due to project creation in the SEQ space, some CBs don't have names
    that map to IPS. This function returns the mapping list.
    
    Uses cached data after first call.
    
    Args:
        app: PowerFactory application object
        
    Returns:
        List of dictionaries with PROJECT, GRID, SUBSTATION, CB_NAME, NEW_NAME
    """
    return _load_cb_alt_names()


# =============================================================================
# Preload function for explicit cache warming
# =============================================================================

def preload_cache(app=None) -> Dict[str, int]:
    """
    Preload all mapping caches.
    
    Call this at the start of processing to ensure all files are loaded
    before device iteration begins. This avoids file I/O during the
    main processing loop.
    
    Args:
        app: PowerFactory application object (optional, for logging)
        
    Returns:
        Dictionary with counts of loaded items
    """
    if app:
        app.PrintInfo("Preloading mapping file cache...")
    
    # Load type mapping (indexes all relay patterns)
    _load_type_mapping()
    
    # Load curve mapping
    _load_curve_mapping()
    
    # Load CB alternate names
    _load_cb_alt_names()
    
    # Note: Individual mapping files are loaded on-demand
    # since we don't know which patterns will be used
    
    stats = get_cache_stats()
    
    if app:
        app.PrintInfo(
            f"Cache preloaded: {stats['type_mappings']} type mappings, "
            f"{stats['curve_mappings']} curve mappings, "
            f"{stats['cb_alt_names']} CB alt names"
        )
    
    logger.info(f"Mapping cache preloaded: {stats}")
    
    return stats

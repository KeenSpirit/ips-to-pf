"""
Mapping file handling for IPS to PowerFactory settings transfer.

This module manages the CSV mapping files that define how IPS settings
are mapped to PowerFactory relay attributes. It provides:
- Type mapping lookup (IPS pattern -> PF relay type + mapping file)
- Detailed mapping file parsing
- Curve mapping for IDMT characteristics

Performance optimizations:
- Type mapping is loaded once and cached
- Individual mapping files are cached after first read
- Curve mapping is loaded once and cached
- Cache can be cleared if files are updated during runtime

Cache Statistics:
    Call get_cache_stats() to see cache hit/miss statistics for
    performance monitoring and debugging.

File Locations:
    - Type mapping: {project_root}/mapping_files/type_mapping/type_mapping.csv
    - Curve mapping: {project_root}/mapping_files/curve_mapping/curve_mapping.csv
    - Relay maps: {project_root}/mapping_files/relay_maps/*.csv
"""

import csv
import os
from typing import Dict, List, Optional, Tuple, Any

# Import paths from config
from config.paths import (
    get_type_mapping_file,
    get_curve_mapping_file,
    get_relay_map_file,
    RELAY_MAPS_DIR,
)


# =============================================================================
# Cache Storage
# =============================================================================

# Type mapping cache: {pattern_name: (mapping_filename, relay_type)}
_type_mapping_cache: Optional[Dict[str, Tuple[str, str]]] = None

# Individual mapping file cache: {filename: list_of_rows}
_mapping_file_cache: Dict[str, List[List[str]]] = {}

# Curve mapping cache: list of [ips_name, code, pf_name] rows
_curve_mapping_cache: Optional[List[List[str]]] = None

# Cache statistics for monitoring
_cache_stats = {
    "type_mapping_hits": 0,
    "type_mapping_misses": 0,
    "mapping_file_hits": 0,
    "mapping_file_misses": 0,
    "curve_mapping_hits": 0,
    "curve_mapping_misses": 0,
}


# =============================================================================
# Cache Management
# =============================================================================

def clear_cache() -> None:
    """
    Clear all cached mapping data.

    Call this if mapping files have been updated during runtime
    and you need to reload them.
    """
    global _type_mapping_cache, _mapping_file_cache, _curve_mapping_cache
    _type_mapping_cache = None
    _mapping_file_cache.clear()
    _curve_mapping_cache = None


def get_cache_stats() -> Dict[str, Any]:
    """
    Get cache statistics for monitoring and debugging.

    Returns:
        Dictionary with cache hit/miss counts and current cache sizes
    """
    return {
        **_cache_stats,
        "type_mapping_loaded": _type_mapping_cache is not None,
        "mapping_files_cached": len(_mapping_file_cache),
        "curve_mapping_loaded": _curve_mapping_cache is not None,
    }


def preload_cache() -> None:
    """
    Preload all caches at startup.

    Call this during initialization to front-load all file I/O
    rather than incurring it during device processing.
    """
    _load_type_mapping()
    _load_curve_mapping()
    # Note: Individual mapping files are loaded on-demand since
    # we may not need all of them for a given run


# =============================================================================
# Type Mapping (pattern -> mapping file + relay type)
# =============================================================================

def _load_type_mapping() -> Dict[str, Tuple[str, str]]:
    """
    Load and cache the type mapping from type_mapping.csv.

    The type mapping file has the format:
        pattern_name,mapping_filename,relay_type

    Returns:
        Dictionary mapping pattern names to (mapping_filename, relay_type) tuples
    """
    global _type_mapping_cache, _cache_stats

    if _type_mapping_cache is not None:
        _cache_stats["type_mapping_hits"] += 1
        return _type_mapping_cache

    _cache_stats["type_mapping_misses"] += 1
    _type_mapping_cache = {}

    filepath = get_type_mapping_file()

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for row in f.readlines():
                line = row.strip().split(",")
                if len(line) >= 3:
                    pattern_name = line[0]
                    mapping_filename = line[1]
                    relay_type = line[2]
                    _type_mapping_cache[pattern_name] = (mapping_filename, relay_type)
    except FileNotFoundError:
        pass  # Return empty cache if file not found
    except Exception:
        pass  # Silently handle other errors

    return _type_mapping_cache


def get_type_mapping(pattern_name: str) -> Optional[Tuple[str, str]]:
    """
    Get the mapping file name and relay type for a pattern.

    Args:
        pattern_name: The IPS relay pattern name

    Returns:
        Tuple of (mapping_filename, relay_type) or None if not found
    """
    type_mapping = _load_type_mapping()
    return type_mapping.get(pattern_name)


# =============================================================================
# Individual Mapping Files
# =============================================================================

def _load_mapping_file(filename: str) -> Optional[List[List[str]]]:
    """
    Load and cache an individual mapping file.

    Args:
        filename: The mapping file name (without .csv extension)

    Returns:
        List of rows from the mapping file, or None if file not found
    """
    global _mapping_file_cache, _cache_stats

    if filename in _mapping_file_cache:
        _cache_stats["mapping_file_hits"] += 1
        return _mapping_file_cache[filename]

    _cache_stats["mapping_file_misses"] += 1

    filepath = get_relay_map_file(filename)

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            rows = []
            reader = csv.reader(f, skipinitialspace=True)
            for row in reader:
                # Skip header row
                if "FOLDER" in row[0] and "ELEMENT" in row[1]:
                    continue
                rows.append(row)

            _mapping_file_cache[filename] = rows
            return rows

    except FileNotFoundError:
        return None
    except Exception:
        return None


# =============================================================================
# Curve Mapping
# =============================================================================

def _load_curve_mapping() -> List[List[str]]:
    """
    Load and cache the curve mapping from curve_mapping.csv.

    Returns:
        List of [ips_curve_name, code, pf_curve_name] rows
    """
    global _curve_mapping_cache, _cache_stats

    if _curve_mapping_cache is not None:
        _cache_stats["curve_mapping_hits"] += 1
        return _curve_mapping_cache

    _cache_stats["curve_mapping_misses"] += 1
    _curve_mapping_cache = []

    filepath = get_curve_mapping_file()

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for row in f.readlines():
                line = row.strip().split(",")
                if len(line) >= 3:
                    _curve_mapping_cache.append(line)
    except FileNotFoundError:
        pass
    except Exception:
        pass

    return _curve_mapping_cache


def _find_curve_in_mapping(setting_value: str) -> Optional[str]:
    """
    Look up a curve name in the curve mapping.

    Args:
        setting_value: The IPS curve setting value

    Returns:
        The PowerFactory curve name, or None if not found
    """
    curve_mapping = _load_curve_mapping()

    for line in curve_mapping:
        mapping_value = line[1]

        # Handle binary curve codes - pad with leading zeros
        try:
            int(mapping_value)
            while len(mapping_value) < len(setting_value):
                mapping_value = "0" + mapping_value
        except ValueError:
            pass

        if setting_value == mapping_value:
            return line[2]  # Return PF curve name

    return None


# =============================================================================
# Public API - Main Functions
# =============================================================================

def get_pf_curve(app, setting_value: str, element) -> Any:
    """
    Get the PowerFactory curve object for an IPS curve setting.

    Curves require a PowerFactory object to be assigned to the attribute.
    This function finds the matching curve from the relay type's available
    curves.

    Args:
        app: PowerFactory application object
        setting_value: The curve name/code from IPS
        element: The PowerFactory element (must have typ_id with pcharac)

    Returns:
        The PowerFactory curve object
    """
    idmt_type = element.typ_id
    curves = idmt_type.GetAttribute("e:pcharac")

    # Try exact match first
    for curve in curves:
        if curve.loc_name == setting_value:
            return curve

    # Try partial matches
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

    # Try curve mapping lookup (cached)
    mapped_curve_name = _find_curve_in_mapping(setting_value)
    if mapped_curve_name:
        for curve in curves:
            if curve.loc_name == mapped_curve_name:
                return curve

    # Try keyword-based matching as fallback
    keyword_matches = [
        ("Extreme", "Extreme"),
        ("Standard", "Standard"),
        ("Very", "Very"),
        ("Definite", "DT"),
        ("Curve A", "Curve A"),
        ("Curve B", "Curve B"),
        ("Curve C", "Curve C"),
        ("Curve D", "Curve D"),
    ]

    for curve in curves:
        for curve_keyword, setting_keyword in keyword_matches:
            if curve_keyword in curve.loc_name and setting_keyword in setting_value:
                return curve

    # Default to Standard Inverse if no match found
    for curve in curves:
        if "Standard" in curve.loc_name:
            return curve

    # Return first available curve as last resort
    return curves[0] if curves else None


def read_mapping_file(
    app,
    rel_pattern: str,
    pf_device
) -> Tuple[Optional[List[List[str]]], Optional[str]]:
    """
    Read the mapping file for a relay pattern.

    Looks up the relay pattern in the type mapping, then loads and
    processes the corresponding mapping file.

    Args:
        app: PowerFactory application object
        rel_pattern: The IPS relay pattern name
        pf_device: The PowerFactory device object (for name substitution)

    Returns:
        Tuple of (mapping_file_rows, relay_type) or (None, None) if not found
    """
    # Look up pattern in type mapping (cached)
    type_info = get_type_mapping(rel_pattern)

    if not type_info:
        return None, None

    mapping_filename, relay_type = type_info

    # Load the mapping file (cached)
    raw_rows = _load_mapping_file(mapping_filename)

    if raw_rows is None:
        return None, None

    # Process the rows for this device
    # Note: We create a new list here because we modify rows based on pf_device
    mapping_file = []
    device_name = pf_device.loc_name

    for row in raw_rows:
        # Skip rows without meaningful data
        if len(row) < 4:
            continue

        if row[3] == "None" and "_dip" not in row[1]:
            if len(row) > 4:
                if not row[4]:
                    continue
            else:
                continue

        # Create a copy of the row to avoid modifying the cache
        processed_row = list(row)

        # Replace placeholder folder names with device name
        if processed_row[0] in ["Relay Model", "Default", "default"]:
            processed_row[0] = device_name

        # Remove trailing empty elements
        while processed_row and processed_row[-1] == "":
            processed_row.pop()

        mapping_file.append(processed_row)

    return mapping_file, relay_type


# =============================================================================
# Utility Functions
# =============================================================================

def get_available_patterns() -> List[str]:
    """
    Get all available relay patterns from the type mapping.

    Returns:
        List of pattern names that have mapping files configured
    """
    type_mapping = _load_type_mapping()
    return list(type_mapping.keys())


def is_pattern_mapped(pattern_name: str) -> bool:
    """
    Check if a relay pattern has a mapping file configured.

    Args:
        pattern_name: The IPS relay pattern name

    Returns:
        True if the pattern has a mapping configuration
    """
    return get_type_mapping(pattern_name) is not None


def get_relay_type_for_pattern(pattern_name: str) -> Optional[str]:
    """
    Get the PowerFactory relay type name for a pattern.

    Args:
        pattern_name: The IPS relay pattern name

    Returns:
        The relay type name, or None if pattern not mapped
    """
    type_info = get_type_mapping(pattern_name)
    if type_info:
        return type_info[1]  # relay_type is second element
    return None
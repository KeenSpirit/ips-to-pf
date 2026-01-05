"""
Circuit breaker name mapping utilities.

This module handles the mapping of circuit breaker names between
PowerFactory and IPS naming conventions. Some CBs in the SEQ space
have names that don't directly map to IPS, so this module provides
lookup functionality for alternate names.

The mapping data is loaded from CB_ALT_NAME.csv in the cb_alt_names directory.
"""

from typing import List, Dict, Optional

# Import path from config
from config.paths import get_cb_alt_name_file

# Cache for CB alternate names
_cb_alt_name_cache: Optional[List[Dict[str, str]]] = None


def get_cb_alt_name_list(app=None) -> List[Dict[str, str]]:
    """
    Get the list of CB alternate name mappings.

    Some circuit breakers in PowerFactory have names that don't directly
    map to IPS. This function returns a list of mappings that can be used
    to find the correct IPS name.

    The app parameter is kept for backward compatibility but is not used.
    Results are cached after first load.

    Args:
        app: PowerFactory application object (unused, kept for compatibility)

    Returns:
        List of dictionaries with keys:
        - PROJECT: PowerFactory project name
        - GRID: Grid name
        - SUBSTATION: Substation name
        - CB_NAME: Original CB name in PowerFactory
        - NEW_NAME: Alternate name to use for IPS lookup

    Example:
        >>> alt_names = get_cb_alt_name_list()
        >>> for mapping in alt_names:
        ...     if mapping["CB_NAME"] == "CB01":
        ...         print(f"Use {mapping['NEW_NAME']} instead")
    """
    global _cb_alt_name_cache

    if _cb_alt_name_cache is not None:
        return _cb_alt_name_cache

    cb_alt_name_list = []
    filepath = get_cb_alt_name_file()

    # Values in NEW_NAME column that indicate the mapping should be skipped
    skip_values = {
        "not needed",
        "no active setting",
        "wrong sub name",
        "unknown",
    }

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for row in f.readlines():
                line = row.strip().split(",")

                # Skip header row
                if line[0] == "PROJECT":
                    continue

                # Skip rows with invalid/skip values
                if len(line) > 4 and line[4].lower() in skip_values:
                    continue

                # Build dictionary from row
                columns = ["PROJECT", "GRID", "SUBSTATION", "CB_NAME", "NEW_NAME"]
                line_dict = {}
                for i, col in enumerate(columns):
                    if i < len(line):
                        line_dict[col] = line[i]
                    else:
                        line_dict[col] = ""

                cb_alt_name_list.append(line_dict)

    except FileNotFoundError:
        pass
    except (PermissionError, UnicodeDecodeError, IndexError, OSError):
        pass

    _cb_alt_name_cache = cb_alt_name_list
    return cb_alt_name_list


def find_alternate_name(
        cb_name: str,
        substation: Optional[str] = None,
        grid: Optional[str] = None
) -> Optional[str]:
    """
    Find an alternate name for a circuit breaker.

    Searches the CB alternate name mappings for a matching entry.
    Can optionally filter by substation and/or grid.

    Args:
        cb_name: The original CB name to look up
        substation: Optional substation to filter by
        grid: Optional grid to filter by

    Returns:
        The alternate name if found, otherwise None

    Example:
        >>> alt_name = find_alternate_name("CB01", substation="ABC")
        >>> if alt_name:
        ...     print(f"Using alternate name: {alt_name}")
    """
    alt_names = get_cb_alt_name_list()

    for mapping in alt_names:
        if mapping.get("CB_NAME") != cb_name:
            continue

        # Check optional filters
        if substation and mapping.get("SUBSTATION") != substation:
            continue
        if grid and mapping.get("GRID") != grid:
            continue

        return mapping.get("NEW_NAME")

    return None


def clear_cache() -> None:
    """Clear the cached CB alternate name list."""
    global _cb_alt_name_cache
    _cb_alt_name_cache = None


def get_cache_stats() -> Dict[str, int]:
    """
    Get statistics about the CB alternate name cache.

    Returns:
        Dictionary with cache statistics
    """
    global _cb_alt_name_cache

    if _cb_alt_name_cache is None:
        return {"loaded": False, "count": 0}

    return {
        "loaded": True,
        "count": len(_cb_alt_name_cache),
    }
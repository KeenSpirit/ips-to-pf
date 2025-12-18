"""
Region-specific configuration for Energex (SEQ) and Ergon.

This module contains configuration that varies between the Energex
and Ergon regions, including:
- Substation name mappings
- Device name suffix expansions (double cable boxes)
- Region-specific constants

Maintenance Notes:
    When new substations with numeric codes are added to PowerFactory,
    add the mapping to get_substation_mapping().
    
    When new double cable box naming patterns are encountered,
    add them to SUFFIX_EXPANSIONS (order matters - longer suffixes first).
"""

from typing import Dict, List, Tuple, Optional


# =============================================================================
# Substation Mapping
# =============================================================================

def get_substation_mapping() -> Dict[str, Optional[str]]:
    """
    Get the mapping of numeric substation codes to alpha codes.
    
    PowerFactory stores all SEQ substation names as three-character
    alpha strings. Some SEQ substations in IPS use numeric codes.
    This mapping allows switches at these substations to be processed
    correctly.
    
    Returns:
        Dictionary mapping numeric codes to alpha codes.
        A None value indicates the substation should be skipped.
        
    Example:
        >>> sub_map = get_substation_mapping()
        >>> sub_map["H22"]
        'LGL'
        >>> sub_map.get("T124")  # Returns None - skip this substation
    """
    return {
        "H22": "LGL",
        "H31": "MRD",
        "H38": "GNA",
        "H4": "MGB",
        "T108": "BLH",
        "T11": "CBT",
        "T124": None,  # Skip this substation
        "T128": "RBA",
        "T136": "ABM",
        "T142": "TSN",
        "T16": "NBR",
        "T160": "SMR",
        "T161": "AGT",
        "T162": "BDB",
        "T187": "RLD",
        "T24": "RBS",
        "T29": "PRG",
        "T30": "AGW",
        "T70": "CRY",
        "T75": "NRG",
        "T78": "LRE",
        "T8": "GYM",
        "T80": "RPN",
        "T81": "CCY",
    }


# Cached version for repeated access
_SUBSTATION_MAPPING: Optional[Dict[str, Optional[str]]] = None


def get_substation_code(numeric_code: str) -> Optional[str]:
    """
    Get the alpha substation code for a numeric code.
    
    Uses caching to avoid recreating the mapping dictionary.
    
    Args:
        numeric_code: The numeric substation code (e.g., "H22")
        
    Returns:
        The alpha code (e.g., "LGL") or None if not mapped or should skip
    """
    global _SUBSTATION_MAPPING
    if _SUBSTATION_MAPPING is None:
        _SUBSTATION_MAPPING = get_substation_mapping()
    
    return _SUBSTATION_MAPPING.get(numeric_code)


# =============================================================================
# Double Cable Box Configuration
# =============================================================================

# Names of IPS relays that protect double cable boxes must be matched to
# the switch name of each cable box. This list defines how combined names
# (e.g., "NIP1A+B") are expanded into individual switch names.
#
# ORDER MATTERS: Check longer suffixes first to avoid partial matches.
# For example, "A+B+C" must be checked before "A+B".
SUFFIX_EXPANSIONS: List[Tuple[str, List[str]]] = [
    ("A+B+C", ["A", "B", "C"]),
    ("A+B+CP11", ["A", "B", "CP11"]),
    ("A+B+CP12", ["A", "B", "CP12"]),
    ("A+B", ["A", "B"]),
]


def expand_device_name(name: str) -> List[str]:
    """
    Expand a double cable box device name into individual switch names.
    
    If the name ends with a known suffix (like "A+B"), returns the
    individual switch names. Otherwise returns the original name.
    
    Args:
        name: The device/switch name to expand
        
    Returns:
        List of individual switch names
        
    Examples:
        >>> expand_device_name("NIP1A+B")
        ['NIP1A', 'NIP1B']
        >>> expand_device_name("CB01A+B+C")
        ['CB01A', 'CB01B', 'CB01C']
        >>> expand_device_name("NIP1A")
        ['NIP1A']
    """
    for suffix, components in SUFFIX_EXPANSIONS:
        if name.endswith(suffix):
            base = name[:-len(suffix)]
            return [base + comp for comp in components]
    
    # No expansion needed - return original name in a list
    return [name]


def is_double_cable_box(name: str) -> bool:
    """
    Check if a device name represents a double cable box configuration.
    
    Args:
        name: The device/switch name to check
        
    Returns:
        True if the name has a double cable box suffix
    """
    for suffix, _ in SUFFIX_EXPANSIONS:
        if name.endswith(suffix):
            return True
    return False


# =============================================================================
# Region Identification
# =============================================================================

# Region identifiers used throughout the application
REGION_ENERGEX = "Energex"
REGION_ERGON = "Ergon"

# Alternative names/codes for regions
REGION_ALIASES = {
    "SEQ": REGION_ENERGEX,
    "EX": REGION_ENERGEX,
    "EE": REGION_ERGON,
    "REG": REGION_ERGON,
}


def normalize_region(region: str) -> str:
    """
    Normalize a region name/code to the standard form.
    
    Args:
        region: Region name or alias
        
    Returns:
        Normalized region name ("Energex" or "Ergon")
        
    Raises:
        ValueError: If the region is not recognized
    """
    # Check if already normalized
    if region in (REGION_ENERGEX, REGION_ERGON):
        return region
    
    # Check aliases
    normalized = REGION_ALIASES.get(region.upper())
    if normalized:
        return normalized
    
    raise ValueError(f"Unknown region: {region}")


def is_energex(region: str) -> bool:
    """Check if a region is Energex."""
    try:
        return normalize_region(region) == REGION_ENERGEX
    except ValueError:
        return False


def is_ergon(region: str) -> bool:
    """Check if a region is Ergon."""
    try:
        return normalize_region(region) == REGION_ERGON
    except ValueError:
        return False

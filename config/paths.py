"""
Centralized path configuration for IPS to PowerFactory settings transfer.

This module contains all file paths and network locations used by the
application. Centralizing paths here makes it easy to:
- Update paths when infrastructure changes
- Support different environments (dev, test, prod)
- Document where external dependencies are located

All paths use raw strings (r"...") to handle Windows backslashes correctly.

Network Paths:
    These paths point to shared network drives and must be accessible
    from the machine running the script.

Local Paths:
    Fallback paths used when network drives are unavailable (e.g., Citrix).
"""

import os
from pathlib import Path
from typing import Optional

# =============================================================================
# Base Paths
# =============================================================================

# Base path for all PowerFactory scripts on the network
SCRIPTS_BASE = r"\\ecasd01\WksMgmt\PowerFactory"

# =============================================================================
# External Library Paths
# =============================================================================

# NetDash Reader library for IPS database access
NETDASH_READER_PATH = os.path.join(SCRIPTS_BASE, "ScriptsLIB", "NetDash-Reader")

# Asset Classes library for corporate data access
ASSET_CLASSES_PATH = os.path.join(SCRIPTS_BASE, "Scripts", "AssetClasses")

# Add Protection Relay Skeletons script
RELAY_SKELETONS_PATH = os.path.join(
    SCRIPTS_BASE,
    "ScriptsDEV",
    "AddProtectionRelaySkeletons",
    "addprotectionrelayskeletons"
)

# =============================================================================
# Mapping Files
# =============================================================================

# Directory containing relay pattern mapping CSV files
MAPPING_FILES_DIR = os.path.join(
    SCRIPTS_BASE,
    "ScriptsDEV",
    "IPSProtectionDeviceSettings",
    "mapping"
)

# =============================================================================
# Output Paths
# =============================================================================

# Network location for batch update results
OUTPUT_BATCH_DIR = os.path.join(
    SCRIPTS_BASE,
    "ScriptsDEV",
    "IPSDataTransferMastering",
    "Script_Results"
)

# Local fallback for output when network is unavailable (Citrix environment)
OUTPUT_LOCAL_DIR = r"C:\LocalData\PowerFactory Output Folders\IPS Data Transfer"


# =============================================================================
# Helper Functions
# =============================================================================

def get_output_directory(batch_mode: bool = False) -> str:
    """
    Get the appropriate output directory based on mode and environment.

    In batch mode, attempts to use the network directory first, falling
    back to local directory if the network path is unavailable.

    In interactive mode, always uses the local directory.

    Args:
        batch_mode: True for batch updates, False for interactive

    Returns:
        Path to the output directory

    Example:
        >>> output_dir = get_output_directory(batch_mode=True)
        >>> print(output_dir)
        '\\\\ecasd01\\WksMgmt\\PowerFactory\\...'
    """
    if batch_mode:
        # Try network path first for batch mode
        if os.path.exists(OUTPUT_BATCH_DIR):
            return OUTPUT_BATCH_DIR
        else:
            # Fall back to local path
            return OUTPUT_LOCAL_DIR
    else:
        # Interactive mode uses local path
        return OUTPUT_LOCAL_DIR


def ensure_path_exists(path: str) -> str:
    """
    Ensure a directory path exists, creating it if necessary.

    Args:
        path: Directory path to check/create

    Returns:
        The path (unchanged)

    Raises:
        OSError: If the directory cannot be created
    """
    os.makedirs(path, exist_ok=True)
    return path


def get_mapping_file_path(filename: str) -> str:
    """
    Get the full path to a mapping file.

    Args:
        filename: Name of the mapping file (e.g., "type_mapping.csv")

    Returns:
        Full path to the mapping file
    """
    return os.path.join(MAPPING_FILES_DIR, filename)


def add_external_library_paths() -> None:
    """
    Add external library paths to sys.path.

    This function should be called early in the application startup
    to ensure all external libraries are importable.

    Note:
        This function modifies sys.path as a side effect.
    """
    import sys

    paths_to_add = [
        NETDASH_READER_PATH,
        ASSET_CLASSES_PATH,
        RELAY_SKELETONS_PATH,
    ]

    for path in paths_to_add:
        if path not in sys.path:
            sys.path.append(path)


# =============================================================================
# Path Validation
# =============================================================================

def validate_paths() -> dict:
    """
    Validate that required paths exist and are accessible.

    Returns:
        Dictionary with path names as keys and (exists, accessible) tuples

    Example:
        >>> results = validate_paths()
        >>> for name, (exists, accessible) in results.items():
        ...     print(f"{name}: exists={exists}, accessible={accessible}")
    """
    paths_to_check = {
        "MAPPING_FILES_DIR": MAPPING_FILES_DIR,
        "OUTPUT_BATCH_DIR": OUTPUT_BATCH_DIR,
        "NETDASH_READER_PATH": NETDASH_READER_PATH,
        "ASSET_CLASSES_PATH": ASSET_CLASSES_PATH,
        "RELAY_SKELETONS_PATH": RELAY_SKELETONS_PATH,
    }

    results = {}
    for name, path in paths_to_check.items():
        exists = os.path.exists(path)
        accessible = os.access(path, os.R_OK) if exists else False
        results[name] = (exists, accessible)

    return results

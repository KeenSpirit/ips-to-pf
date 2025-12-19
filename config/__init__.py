"""
Configuration package for IPS to PowerFactory settings transfer.

This package centralizes all configuration, constants, and paths used
throughout the application. By keeping configuration in one place, we:
- Make it easier to update paths when infrastructure changes
- Avoid hardcoded values scattered across the codebase
- Provide clear documentation of all configurable values
- Enable environment-specific configuration

Modules:
    paths: Network paths and file locations
    relay_patterns: Relay classification constants
    region_config: Region-specific settings (Energex/Ergon)

Usage:
    from config import paths, relay_patterns, region_config

    # Access paths
    mapping_dir = paths.MAPPING_FILES_DIR

    # Access relay patterns
    if pattern in relay_patterns.SINGLE_PHASE_RELAYS:
        ...

    # Access region config
    sub_map = region_config.get_substation_mapping()
"""

from config.paths import (
    # Base paths
    SCRIPTS_BASE,
    # External library paths
    NETDASH_READER_PATH,
    ASSET_CLASSES_PATH,
    RELAY_SKELETONS_PATH,
    # Mapping files
    MAPPING_FILES_DIR,
    # Output paths
    OUTPUT_BATCH_DIR,
    OUTPUT_LOCAL_DIR,
    # Path helper functions
    get_output_directory,
    ensure_path_exists,
)

from config.relay_patterns import (
    SINGLE_PHASE_RELAYS,
    MULTI_PHASE_RELAYS,
    RELAYS_OOS,
    EXCLUDED_PATTERNS,
)

from config.region_config import (
    get_substation_mapping,
    SUFFIX_EXPANSIONS,
)

__all__ = [
    # Paths
    "SCRIPTS_BASE",
    "NETDASH_READER_PATH",
    "ASSET_CLASSES_PATH",
    "RELAY_SKELETONS_PATH",
    "MAPPING_FILES_DIR",
    "OUTPUT_BATCH_DIR",
    "OUTPUT_LOCAL_DIR",
    "get_output_directory",
    "ensure_path_exists",
    # Relay patterns
    "SINGLE_PHASE_RELAYS",
    "MULTI_PHASE_RELAYS",
    "RELAYS_OOS",
    "EXCLUDED_PATTERNS",
    # Region config
    "get_substation_mapping",
    "SUFFIX_EXPANSIONS",
]

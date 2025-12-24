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
    validation: Configuration validation at startup

Usage:
    from config import paths, relay_patterns, region_config

    # Access paths
    cb_alt_file = paths.get_cb_alt_name_file()
    type_mapping_file = paths.get_type_mapping_file()

    # Access relay patterns
    if pattern in relay_patterns.SINGLE_PHASE_RELAYS:
        ...

    # Access region config
    sub_map = region_config.get_substation_mapping()

    # Validate configuration at startup
    from config.validation import require_valid_config
    require_valid_config(app)  # Exits if invalid
"""

from config.paths import (
    # Base paths
    SCRIPTS_BASE,
    PROJECT_ROOT,
    # External library paths
    NETDASH_READER_PATH,
    ASSET_CLASSES_PATH,
    RELAY_SKELETONS_PATH,
    # Mapping file directories
    MAPPING_FILES_BASE,
    CB_ALT_NAMES_DIR,
    CURVE_MAPPING_DIR,
    RELAY_MAPS_DIR,
    TYPE_MAPPING_DIR,
    # Legacy path (deprecated)
    MAPPING_FILES_DIR,
    # Output paths
    OUTPUT_BATCH_DIR,
    OUTPUT_LOCAL_DIR,
    # Path helper functions
    get_output_directory,
    ensure_path_exists,
    get_cb_alt_name_file,
    get_curve_mapping_file,
    get_type_mapping_file,
    get_relay_map_file,
    ensure_mapping_directories_exist,
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

from config.validation import (
    # Main classes
    ValidationResult,
    ValidationConfig,
    ValidationLevel,
    # Primary functions
    validate_startup,
    require_valid_config,
    quick_validate,
    print_config_status,
    # Configuration presets
    get_minimal_config,
    get_standard_config,
    get_full_config,
    get_strict_config,
    # Context-specific validation
    validate_for_batch_mode,
    validate_for_interactive_mode,
    # Custom validator registration
    register_validator,
    clear_custom_validators,
)

__all__ = [
    # Base Paths
    "SCRIPTS_BASE",
    "PROJECT_ROOT",
    # External library paths
    "NETDASH_READER_PATH",
    "ASSET_CLASSES_PATH",
    "RELAY_SKELETONS_PATH",
    # Mapping file directories
    "MAPPING_FILES_BASE",
    "CB_ALT_NAMES_DIR",
    "CURVE_MAPPING_DIR",
    "RELAY_MAPS_DIR",
    "TYPE_MAPPING_DIR",
    # Legacy (deprecated)
    "MAPPING_FILES_DIR",
    # Output paths
    "OUTPUT_BATCH_DIR",
    "OUTPUT_LOCAL_DIR",
    # Path helper functions
    "get_output_directory",
    "ensure_path_exists",
    "get_cb_alt_name_file",
    "get_curve_mapping_file",
    "get_type_mapping_file",
    "get_relay_map_file",
    "ensure_mapping_directories_exist",
    # Relay patterns
    "SINGLE_PHASE_RELAYS",
    "MULTI_PHASE_RELAYS",
    "RELAYS_OOS",
    "EXCLUDED_PATTERNS",
    # Region config
    "get_substation_mapping",
    "SUFFIX_EXPANSIONS",
    # Validation
    "ValidationResult",
    "ValidationConfig",
    "ValidationLevel",
    "validate_startup",
    "require_valid_config",
    "quick_validate",
    "print_config_status",
    "get_minimal_config",
    "get_standard_config",
    "get_full_config",
    "get_strict_config",
    "validate_for_batch_mode",
    "validate_for_interactive_mode",
    "register_validator",
    "clear_custom_validators",
]
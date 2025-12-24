"""
Configuration validation for IPS to PowerFactory settings transfer.

This module validates that all required configuration, paths, and
dependencies are available before processing begins. This catches
issues early with clear error messages rather than failing mid-run.

Features:
- Path existence and accessibility checks
- Required and optional file validation
- External library import validation
- PowerFactory environment validation
- Database connectivity testing (optional)
- Configurable validation behavior

Usage:
    from config.validation import validate_startup, require_valid_config

    # Quick validation with exit on failure
    require_valid_config(app)

    # Detailed validation with custom handling
    result = validate_startup(app, check_database=True)
    if not result.is_valid:
        for error in result.errors:
            handle_error(error)
"""

import os
import sys
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Set
from enum import Enum

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================

class ValidationLevel(Enum):
    """Validation strictness levels."""
    MINIMAL = "minimal"  # Only critical paths and files
    STANDARD = "standard"  # Paths, files, libraries
    FULL = "full"  # Everything including PowerFactory checks
    STRICT = "strict"  # Treat warnings as errors


@dataclass
class ValidationConfig:
    """
    Configuration for validation behavior.

    Attributes:
        level: Validation strictness level
        check_database: Whether to test database connectivity (slow)
        treat_warnings_as_errors: If True, any warning fails validation
        required_mapping_files: Dict of {description: filepath} that must exist
        optional_mapping_files: Dict of {description: filepath} that should exist
        skip_library_imports: If True, skip import testing (faster)
        timeout_seconds: Timeout for database connectivity test
        custom_paths: Additional paths to validate {name: path}
        custom_files: Additional files to validate {name: filepath}
    """
    level: ValidationLevel = ValidationLevel.STANDARD
    check_database: bool = False
    treat_warnings_as_errors: bool = False
    required_mapping_files: Dict[str, str] = field(default_factory=dict)
    optional_mapping_files: Dict[str, str] = field(default_factory=dict)
    skip_library_imports: bool = False
    timeout_seconds: int = 10
    custom_paths: Dict[str, str] = field(default_factory=dict)
    custom_files: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        """Initialize default mapping files if not provided."""
        from config.paths import (
            get_type_mapping_file,
            get_cb_alt_name_file,
            get_curve_mapping_file,
        )

        # Set default required files if not provided
        if not self.required_mapping_files:
            self.required_mapping_files = {
                "type_mapping.csv": str(get_type_mapping_file()),
                "CB_ALT_NAME.csv": str(get_cb_alt_name_file()),
            }

        # Set default optional files if not provided
        if not self.optional_mapping_files:
            self.optional_mapping_files = {
                "curve_mapping.csv": str(get_curve_mapping_file()),
            }


# Default configuration instance - created lazily to avoid import issues
_default_config: Optional[ValidationConfig] = None


def _get_default_config() -> ValidationConfig:
    """Get or create the default configuration."""
    global _default_config
    if _default_config is None:
        _default_config = ValidationConfig()
    return _default_config


# =============================================================================
# Validation Result
# =============================================================================

@dataclass
class ValidationResult:
    """
    Results of configuration validation.

    Collects errors, warnings, and informational data during validation.
    Provides methods to check validity and generate reports.

    Attributes:
        errors: List of error messages (validation failures)
        warnings: List of warning messages (non-critical issues)
        info: Dictionary of successful validation info
        checks_performed: Set of validation check names that were run
    """
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    info: Dict[str, Any] = field(default_factory=dict)
    checks_performed: Set[str] = field(default_factory=set)

    @property
    def is_valid(self) -> bool:
        """True if no errors (warnings are acceptable by default)."""
        return len(self.errors) == 0

    def is_valid_strict(self) -> bool:
        """True if no errors and no warnings."""
        return len(self.errors) == 0 and len(self.warnings) == 0

    def add_error(self, message: str) -> None:
        """Add an error message."""
        self.errors.append(message)
        # logger.error(f"Validation error: {message}")

    def add_warning(self, message: str) -> None:
        """Add a warning message."""
        self.warnings.append(message)
        # logger.warning(f"Validation warning: {message}")

    def add_info(self, key: str, value: Any) -> None:
        """Add informational data."""
        self.info[key] = value
        # logger.debug(f"Validation info: {key} = {value}")

    def mark_check(self, check_name: str) -> None:
        """Mark a validation check as performed."""
        self.checks_performed.add(check_name)

    def summary(self, verbose: bool = False) -> str:
        """
        Get a summary of validation results.

        Args:
            verbose: If True, include all info details

        Returns:
            Formatted summary string
        """
        lines = []

        if self.errors:
            lines.append(f"ERRORS ({len(self.errors)}):")
            for error in self.errors:
                lines.append(f"  ✗ {error}")

        if self.warnings:
            lines.append(f"WARNINGS ({len(self.warnings)}):")
            for warning in self.warnings:
                lines.append(f"  ⚠ {warning}")

        if not self.errors and not self.warnings:
            lines.append("✓ All configuration validated successfully")

        if verbose and self.info:
            lines.append("")
            lines.append("DETAILS:")
            for key, value in sorted(self.info.items()):
                lines.append(f"  {key}: {value}")

        if verbose and self.checks_performed:
            lines.append("")
            lines.append(f"Checks performed: {', '.join(sorted(self.checks_performed))}")

        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "is_valid": self.is_valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "info": self.info,
            "checks_performed": list(self.checks_performed),
        }

    def merge(self, other: 'ValidationResult') -> 'ValidationResult':
        """
        Merge another ValidationResult into this one.

        Args:
            other: Another ValidationResult to merge

        Returns:
            Self for method chaining
        """
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)
        self.info.update(other.info)
        self.checks_performed.update(other.checks_performed)
        return self


# =============================================================================
# Main Validation Functions
# =============================================================================

def validate_startup(
        app=None,
        config: Optional[ValidationConfig] = None,
        check_database: Optional[bool] = None
) -> ValidationResult:
    """
    Validate all configuration at startup.

    Performs comprehensive validation of paths, files, libraries,
    and optionally PowerFactory and database connectivity.

    Args:
        app: PowerFactory application object (optional)
        config: Validation configuration (uses default if None)
        check_database: Override config's check_database setting

    Returns:
        ValidationResult with any errors/warnings found

    Example:
        >>> result = validate_startup(app)
        >>> if not result.is_valid:
        ...     print(result.summary())
        ...     sys.exit(1)
    """
    if config is None:
        config = _get_default_config()

    # Allow override of database check
    if check_database is not None:
        config = ValidationConfig(
            level=config.level,
            check_database=check_database,
            treat_warnings_as_errors=config.treat_warnings_as_errors,
            required_mapping_files=config.required_mapping_files,
            optional_mapping_files=config.optional_mapping_files,
            skip_library_imports=config.skip_library_imports,
            timeout_seconds=config.timeout_seconds,
            custom_paths=config.custom_paths,
            custom_files=config.custom_files,
        )

    result = ValidationResult()

    # Always validate paths (all levels)
    _validate_paths(result, config)

    # Always validate required files (all levels)
    _validate_required_files(result, config)

    # Validate libraries (standard and above)
    if config.level in (ValidationLevel.STANDARD, ValidationLevel.FULL, ValidationLevel.STRICT):
        if not config.skip_library_imports:
            _validate_libraries(result, config)

    # Validate PowerFactory (full and strict, if app provided)
    if config.level in (ValidationLevel.FULL, ValidationLevel.STRICT) and app:
        _validate_powerfactory(app, result, config)

    # Validate database connectivity (if requested)
    if config.check_database:
        _validate_database(result, config)

    # Validate custom paths and files
    _validate_custom(result, config)

    # In strict mode, convert warnings to errors
    if config.treat_warnings_as_errors or config.level == ValidationLevel.STRICT:
        result.errors.extend(result.warnings)
        result.warnings.clear()

    return result


def _validate_paths(result: ValidationResult, config: ValidationConfig) -> None:
    """
    Validate that required paths exist and are accessible.

    Args:
        result: ValidationResult to update
        config: Validation configuration
    """
    result.mark_check("paths")

    # Import paths from config
    from config.paths import (
        SCRIPTS_BASE,
        CB_ALT_NAMES_DIR,
        CURVE_MAPPING_DIR,
        RELAY_MAPS_DIR,
        TYPE_MAPPING_DIR,
        OUTPUT_BATCH_DIR,
        OUTPUT_LOCAL_DIR,
        NETDASH_READER_PATH,
        ASSET_CLASSES_PATH,
        RELAY_SKELETONS_PATH,
    )

    # Critical paths that must exist (mapping directories in project)
    critical_paths = {
        "CB_ALT_NAMES_DIR": str(CB_ALT_NAMES_DIR),
        "TYPE_MAPPING_DIR": str(TYPE_MAPPING_DIR),
        "RELAY_MAPS_DIR": str(RELAY_MAPS_DIR),
    }

    # Optional paths that should exist
    optional_paths = {
        "CURVE_MAPPING_DIR": str(CURVE_MAPPING_DIR),
        "OUTPUT_BATCH_DIR": OUTPUT_BATCH_DIR,
        "OUTPUT_LOCAL_DIR": OUTPUT_LOCAL_DIR,
        "NETDASH_READER_PATH": NETDASH_READER_PATH,
        "ASSET_CLASSES_PATH": ASSET_CLASSES_PATH,
        "RELAY_SKELETONS_PATH": RELAY_SKELETONS_PATH,
        "SCRIPTS_BASE": SCRIPTS_BASE,
    }

    # Check critical paths
    for name, path in critical_paths.items():
        status = _check_path(path)
        if status == "not_found":
            result.add_error(f"Required path not found: {name} = {path}")
        elif status == "not_readable":
            result.add_error(f"Path not readable: {name} = {path}")
        else:
            result.add_info(f"path:{name}", "OK")

    # Check optional paths (warnings only)
    for name, path in optional_paths.items():
        status = _check_path(path)
        if status == "not_found":
            result.add_warning(f"Optional path not found: {name} = {path}")
        elif status == "not_readable":
            result.add_warning(f"Optional path not readable: {name} = {path}")
        else:
            result.add_info(f"path:{name}", "OK")


def _check_path(path: str) -> str:
    """
    Check path existence and accessibility.

    Args:
        path: Path to check

    Returns:
        "ok", "not_found", or "not_readable"
    """
    if not os.path.exists(path):
        return "not_found"
    if not os.access(path, os.R_OK):
        return "not_readable"
    return "ok"


def _validate_required_files(result: ValidationResult, config: ValidationConfig) -> None:
    """
    Validate that required mapping files exist.

    Args:
        result: ValidationResult to update
        config: Validation configuration
    """
    result.mark_check("required_files")

    # Check required files
    for filename, filepath in config.required_mapping_files.items():
        if not os.path.exists(filepath):
            result.add_error(f"Required mapping file not found: {filename} at {filepath}")
        elif os.path.getsize(filepath) == 0:
            result.add_warning(f"Mapping file is empty: {filename}")
        else:
            result.add_info(f"file:{filename}", "OK")

    # Check optional files
    for filename, filepath in config.optional_mapping_files.items():
        if not os.path.exists(filepath):
            result.add_warning(f"Optional mapping file not found: {filename} at {filepath}")
        elif os.path.getsize(filepath) == 0:
            result.add_warning(f"Optional mapping file is empty: {filename}")
        else:
            result.add_info(f"file:{filename}", "OK")


def _validate_libraries(result: ValidationResult, config: ValidationConfig) -> None:
    """
    Validate that external libraries can be imported.

    Args:
        result: ValidationResult to update
        config: Validation configuration
    """
    result.mark_check("libraries")

    from config.paths import (
        NETDASH_READER_PATH,
        ASSET_CLASSES_PATH,
    )

    # Check NetDash Reader
    if os.path.exists(NETDASH_READER_PATH):
        try:
            if NETDASH_READER_PATH not in sys.path:
                sys.path.append(NETDASH_READER_PATH)
            import netdashread  # noqa: F401
            result.add_info("library:netdashread", "OK")
        except ImportError as e:
            result.add_error(f"Cannot import netdashread: {e}")
    else:
        result.add_warning("NetDash Reader path not found, skipping import check")

    # Check Asset Classes
    if os.path.exists(ASSET_CLASSES_PATH):
        try:
            if ASSET_CLASSES_PATH not in sys.path:
                sys.path.append(ASSET_CLASSES_PATH)
            import assetclasses  # noqa: F401
            result.add_info("library:assetclasses", "OK")
        except ImportError as e:
            result.add_warning(f"Cannot import assetclasses: {e}")
    else:
        result.add_warning("Asset Classes path not found, skipping import check")


def _validate_powerfactory(
        app,
        result: ValidationResult,
        config: ValidationConfig
) -> None:
    """
    Validate PowerFactory environment.

    Args:
        app: PowerFactory application object
        result: ValidationResult to update
        config: Validation configuration
    """
    result.mark_check("powerfactory")

    # Check for active project
    try:
        prjt = app.GetActiveProject()
    except Exception as e:
        result.add_error(f"Cannot access PowerFactory application: {e}")
        return

    if prjt is None:
        result.add_error("No active PowerFactory project")
        return

    result.add_info("project:name", prjt.loc_name)

    # Get project path
    try:
        folder = prjt.GetAttribute("fold_id")
        if folder:
            result.add_info("project:folder", folder.loc_name)
    except Exception:
        pass

    # Check for required project folders
    required_folders = ["netmod", "netdat", "equip"]
    for folder_name in required_folders:
        try:
            folder = app.GetProjectFolder(folder_name)
            if folder is None:
                result.add_error(f"Project folder not found: {folder_name}")
            else:
                result.add_info(f"pf_folder:{folder_name}", "OK")
        except Exception as e:
            result.add_error(f"Error accessing project folder {folder_name}: {e}")

    # Check for global library
    try:
        global_lib = app.GetGlobalLibrary()
        if global_lib is None:
            result.add_warning("Global library not accessible")
        else:
            result.add_info("pf:global_library", "OK")
    except Exception as e:
        result.add_warning(f"Error accessing global library: {e}")

    # Check for local library
    try:
        local_lib = app.GetLocalLibrary()
        if local_lib is None:
            result.add_warning("Local library not accessible")
        else:
            result.add_info("pf:local_library", "OK")
    except Exception as e:
        result.add_warning(f"Error accessing local library: {e}")

    # Check for protection library in global library
    try:
        if global_lib:
            protection_folders = global_lib.GetContents("Protection")
            if protection_folders:
                result.add_info("pf:protection_library", "OK")
            else:
                result.add_warning("Protection folder not found in global library")
    except Exception as e:
        result.add_warning(f"Error checking protection library: {e}")


def _validate_database(result: ValidationResult, config: ValidationConfig) -> None:
    """
    Validate database connectivity (optional, slow).

    Args:
        result: ValidationResult to update
        config: Validation configuration
    """
    result.mark_check("database")

    try:
        # Attempt to import and use netdashread
        from netdashread import get_json_data

        # Try a minimal query to test connectivity
        # Using a non-existent ID to get empty result quickly
        test_data = get_json_data(
            report="Protection-SettingRelay-EX",
            params={"setting_id": "__CONNECTIVITY_TEST__"},
            timeout=config.timeout_seconds
        )
        # If we get here without exception, database is reachable
        result.add_info("database:netdash", "OK (reachable)")

    except ImportError:
        result.add_warning("Cannot test database: netdashread not available")
    except Exception as e:
        error_msg = str(e)
        if "timeout" in error_msg.lower():
            result.add_warning(f"Database connectivity test timed out after {config.timeout_seconds}s")
        elif "connection" in error_msg.lower():
            result.add_warning(f"Database connection failed: {e}")
        else:
            result.add_warning(f"Database connectivity test failed: {e}")


def _validate_custom(result: ValidationResult, config: ValidationConfig) -> None:
    """
    Validate custom paths and files from configuration.

    Args:
        result: ValidationResult to update
        config: Validation configuration
    """
    # Validate custom paths
    for name, path in config.custom_paths.items():
        result.mark_check(f"custom_path:{name}")
        status = _check_path(path)
        if status == "not_found":
            result.add_error(f"Custom path not found: {name} = {path}")
        elif status == "not_readable":
            result.add_error(f"Custom path not readable: {name} = {path}")
        else:
            result.add_info(f"custom_path:{name}", "OK")

    # Validate custom files
    for name, filepath in config.custom_files.items():
        result.mark_check(f"custom_file:{name}")
        if not os.path.exists(filepath):
            result.add_error(f"Custom file not found: {name} = {filepath}")
        elif not os.access(filepath, os.R_OK):
            result.add_error(f"Custom file not readable: {name} = {filepath}")
        else:
            result.add_info(f"custom_file:{name}", "OK")


# =============================================================================
# Convenience Functions
# =============================================================================

def require_valid_config(
        app=None,
        config: Optional[ValidationConfig] = None,
        exit_on_failure: bool = True,
        print_warnings: bool = True
) -> ValidationResult:
    """
    Validate configuration and optionally exit if invalid.

    This is the recommended way to validate configuration at startup.
    Call this at the beginning of main() to ensure all configuration
    is valid before processing begins.

    Args:
        app: PowerFactory application object
        config: Validation configuration (uses default if None)
        exit_on_failure: If True, call sys.exit(1) on validation failure
        print_warnings: If True, print warnings even on success

    Returns:
        ValidationResult (only if exit_on_failure is False or validation passes)

    Raises:
        SystemExit: If validation fails and exit_on_failure is True

    Example:
        >>> # In main.py
        >>> require_valid_config(app)  # Exits if invalid
        >>> # ... rest of script (only runs if config is valid)
    """
    result = validate_startup(app, config)

    if not result.is_valid:
        _print_validation_failure(result, app)
        if exit_on_failure:
            sys.exit(1)
    elif print_warnings and result.warnings:
        _print_validation_warnings(result, app)

    return result


def _print_validation_failure(result: ValidationResult, app=None) -> None:
    """Print validation failure message."""
    separator = "=" * 60

    print(separator)
    print("CONFIGURATION VALIDATION FAILED")
    print(separator)
    print(result.summary())
    print(separator)
    print("Please fix the above errors before running the script.")
    print()

    if app:
        try:
            app.PrintError("Configuration validation failed. See output for details.")
            for error in result.errors:
                app.PrintError(f"  {error}")
        except Exception:
            pass


def _print_validation_warnings(result: ValidationResult, app=None) -> None:
    """Print validation warnings."""
    print("Configuration validation passed with warnings:")
    for warning in result.warnings:
        print(f"  ⚠ {warning}")

    if app:
        try:
            for warning in result.warnings:
                app.PrintWarn(warning)
        except Exception:
            pass


def print_config_status(
        app=None,
        config: Optional[ValidationConfig] = None,
        verbose: bool = True
) -> ValidationResult:
    """
    Print current configuration status (for debugging).

    Useful for troubleshooting configuration issues or verifying
    that all dependencies are correctly set up.

    Args:
        app: PowerFactory application object
        config: Validation configuration
        verbose: If True, print detailed information

    Returns:
        ValidationResult from validation

    Example:
        >>> # For debugging
        >>> print_config_status(app)
    """
    # Use full validation for status check
    if config is None:
        config = ValidationConfig(level=ValidationLevel.FULL)

    result = validate_startup(app, config)

    print("=" * 60)
    print("CONFIGURATION STATUS")
    print("=" * 60)
    print(result.summary(verbose=verbose))
    print("=" * 60)

    return result


def quick_validate(app=None) -> bool:
    """
    Perform quick validation and return boolean result.

    Use this for simple pass/fail checks without detailed reporting.

    Args:
        app: PowerFactory application object

    Returns:
        True if configuration is valid, False otherwise

    Example:
        >>> if not quick_validate(app):
        ...     print("Configuration invalid!")
        ...     return
    """
    config = ValidationConfig(level=ValidationLevel.MINIMAL)
    result = validate_startup(app, config)
    return result.is_valid


# =============================================================================
# Configuration Presets
# =============================================================================

def get_minimal_config() -> ValidationConfig:
    """Get minimal validation configuration (fast, basic checks only)."""
    return ValidationConfig(
        level=ValidationLevel.MINIMAL,
        check_database=False,
        skip_library_imports=True,
    )


def get_standard_config() -> ValidationConfig:
    """Get standard validation configuration (recommended for most uses)."""
    return ValidationConfig(
        level=ValidationLevel.STANDARD,
        check_database=False,
    )


def get_full_config(check_database: bool = False) -> ValidationConfig:
    """
    Get full validation configuration (thorough checks).

    Args:
        check_database: Whether to test database connectivity
    """
    return ValidationConfig(
        level=ValidationLevel.FULL,
        check_database=check_database,
    )


def get_strict_config() -> ValidationConfig:
    """Get strict validation configuration (warnings become errors)."""
    return ValidationConfig(
        level=ValidationLevel.STRICT,
        check_database=True,
        treat_warnings_as_errors=True,
    )


# =============================================================================
# Validation for Specific Contexts
# =============================================================================

def validate_for_batch_mode(app) -> ValidationResult:
    """
    Validate configuration for batch update mode.

    Batch mode has stricter requirements since it will process
    many devices unattended.

    Args:
        app: PowerFactory application object

    Returns:
        ValidationResult
    """
    config = ValidationConfig(
        level=ValidationLevel.FULL,
        check_database=True,  # Must have database access for batch
        treat_warnings_as_errors=False,
        timeout_seconds=30,  # Longer timeout for batch
    )
    return validate_startup(app, config)


def validate_for_interactive_mode(app) -> ValidationResult:
    """
    Validate configuration for interactive mode.

    Interactive mode can be more lenient since user can respond
    to issues as they arise.

    Args:
        app: PowerFactory application object

    Returns:
        ValidationResult
    """
    config = ValidationConfig(
        level=ValidationLevel.STANDARD,
        check_database=False,  # Don't slow down startup
    )
    return validate_startup(app, config)


# =============================================================================
# Registry for Custom Validators
# =============================================================================

_custom_validators: List[callable] = []


def register_validator(validator: callable) -> None:
    """
    Register a custom validation function.

    Custom validators are called during validate_startup() and can
    add errors/warnings to the result.

    Args:
        validator: Function taking (result: ValidationResult, config: ValidationConfig)

    Example:
        >>> def validate_my_feature(result, config):
        ...     if not my_feature_available():
        ...         result.add_warning("My feature not available")
        >>> register_validator(validate_my_feature)
    """
    _custom_validators.append(validator)


def clear_custom_validators() -> None:
    """Clear all registered custom validators."""
    _custom_validators.clear()


def _run_custom_validators(result: ValidationResult, config: ValidationConfig) -> None:
    """Run all registered custom validators."""
    for validator in _custom_validators:
        try:
            validator(result, config)
        except Exception as e:
            result.add_warning(f"Custom validator failed: {e}")
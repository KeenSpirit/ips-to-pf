# Configuration Validation Module

## Overview

The `config/validation.py` module provides comprehensive configuration validation at startup. This catches configuration issues early with clear error messages rather than failing mid-run with cryptic stack traces.

## Problem Solved

Previously, configuration issues were discovered at runtime:

| Issue | When Discovered | Impact |
|-------|-----------------|--------|
| Missing network path | First file read attempt | Wasted time, partial updates |
| Inaccessible library | Import statement | Confusing import error |
| Missing mapping file | Processing specific pattern | Mid-run crash |
| Database unavailable | First query | Minutes into processing |

With validation, all issues are found immediately at startup with clear remediation guidance.

## Quick Start

### Basic Usage (Recommended)

```python
from config.validation import require_valid_config

def main(app=None, batch=False):
    if not app:
        app = pf.GetApplication()
    
    # Validate configuration - exits automatically if invalid
    require_valid_config(app)
    
    # ... rest of script (only runs if config is valid)
```

### Custom Handling

```python
from config.validation import validate_startup

result = validate_startup(app)
if not result.is_valid:
    for error in result.errors:
        handle_error(error)
    sys.exit(1)
```

## Validation Levels

| Level | What's Checked | Use Case |
|-------|----------------|----------|
| `MINIMAL` | Critical paths and required files | Quick checks, testing |
| `STANDARD` | Paths, files, library imports | Interactive mode (default) |
| `FULL` | All above + PowerFactory environment | Production use |
| `STRICT` | All above + warnings become errors | Critical batch jobs |

## What Gets Validated

### Paths
- `SCRIPTS_BASE` - Base network path (critical)
- `MAPPING_FILES_DIR` - Mapping files location (critical)
- `OUTPUT_BATCH_DIR` - Batch output location (optional)
- `OUTPUT_LOCAL_DIR` - Local output location (optional)
- `NETDASH_READER_PATH` - NetDash library (optional)
- `ASSET_CLASSES_PATH` - Asset classes library (optional)
- `RELAY_SKELETONS_PATH` - Relay skeletons script (optional)

### Required Files
- `type_mapping.csv` - Relay type mapping (critical)
- `CB_ALT_NAME.csv` - CB alternate names (critical)

### Optional Files
- `curve_mapping.csv` - IDMT curve mappings

### External Libraries
- `netdashread` - Database access
- `assetclasses` - Corporate data

### PowerFactory (Full level)
- Active project exists
- Required folders accessible (netmod, netdat, equip)
- Global library accessible
- Local library accessible
- Protection library exists

### Database (Optional)
- NetDash API connectivity test

## Configuration Presets

```python
from config.validation import (
    get_minimal_config,    # Fast, basic checks only
    get_standard_config,   # Recommended for interactive
    get_full_config,       # Thorough, for production
    get_strict_config,     # Warnings become errors
)

# Use a preset
config = get_full_config(check_database=True)
result = validate_startup(app, config)
```

## Context-Specific Validation

```python
from config.validation import (
    validate_for_batch_mode,
    validate_for_interactive_mode,
)

# Batch mode: stricter, checks database
result = validate_for_batch_mode(app)

# Interactive mode: faster startup
result = validate_for_interactive_mode(app)
```

## Custom Configuration

```python
from config.validation import ValidationConfig, ValidationLevel

config = ValidationConfig(
    level=ValidationLevel.FULL,
    check_database=True,
    treat_warnings_as_errors=False,
    required_mapping_files=[
        "type_mapping.csv",
        "CB_ALT_NAME.csv",
        "my_custom_mapping.csv",  # Add custom requirement
    ],
    optional_mapping_files=[
        "curve_mapping.csv",
    ],
    skip_library_imports=False,
    timeout_seconds=30,  # Database timeout
    custom_paths={
        "MY_CUSTOM_PATH": r"\\server\custom\path",
    },
    custom_files={
        "MY_CUSTOM_FILE": r"\\server\data\file.csv",
    },
)

result = validate_startup(app, config)
```

## ValidationResult Object

```python
result = validate_startup(app)

# Check validity
if result.is_valid:            # No errors (warnings OK)
    pass
if result.is_valid_strict():   # No errors AND no warnings
    pass

# Access details
result.errors      # List of error messages
result.warnings    # List of warning messages
result.info        # Dict of successful checks
result.checks_performed  # Set of check names run

# Get summary
print(result.summary())           # Basic summary
print(result.summary(verbose=True))  # With details

# Convert to dict (for logging/serialization)
data = result.to_dict()
```

## Example Output

### Validation Failure
```
============================================================
CONFIGURATION VALIDATION FAILED
============================================================
ERRORS (2):
  ✗ Required path not found: MAPPING_FILES_DIR = \\server\path\mapping
  ✗ Required mapping file not found: type_mapping.csv
WARNINGS (1):
  ⚠ Optional path not found: OUTPUT_BATCH_DIR = \\server\path\output
============================================================
Please fix the above errors before running the script.
```

### Validation Success with Warnings
```
Configuration validation passed with warnings:
  ⚠ Optional mapping file not found: curve_mapping.csv
```

### Verbose Status
```
============================================================
CONFIGURATION STATUS
============================================================
✓ All configuration validated successfully

DETAILS:
  file:CB_ALT_NAME.csv: OK
  file:type_mapping.csv: OK
  library:assetclasses: OK
  library:netdashread: OK
  path:ASSET_CLASSES_PATH: OK
  path:MAPPING_FILES_DIR: OK
  path:SCRIPTS_BASE: OK
  pf:global_library: OK
  pf:local_library: OK
  pf_folder:equip: OK
  pf_folder:netdat: OK
  pf_folder:netmod: OK
  project:name: MyProject

Checks performed: libraries, paths, powerfactory, required_files
============================================================
```

## Custom Validators

Register custom validation logic:

```python
from config.validation import register_validator, ValidationResult, ValidationConfig

def validate_my_feature(result: ValidationResult, config: ValidationConfig):
    """Custom validator for my specific requirements."""
    import os
    my_path = r"\\server\my\feature"
    if not os.path.exists(my_path):
        result.add_warning("My feature path not available")

# Register before calling validate_startup()
register_validator(validate_my_feature)

# Now validation will include your custom check
result = validate_startup(app)
```

## Debugging Configuration Issues

Use `print_config_status()` for troubleshooting:

```python
from config.validation import print_config_status

# Print detailed configuration status
print_config_status(app, verbose=True)
```

## Integration Pattern

### For Interactive Scripts

```python
def main(app=None, batch=False):
    if not app:
        app = pf.GetApplication()
    
    # Quick validation - exits on failure
    require_valid_config(app)
    
    # ... continue with script
```

### For Batch Scripts

```python
def main(app, batch=True):
    # Stricter validation for unattended operation
    result = validate_for_batch_mode(app)
    
    if not result.is_valid:
        # Log errors and skip this project
        for error in result.errors:
            logging.error(error)
        return None
    
    # Log warnings but continue
    for warning in result.warnings:
        logging.warning(warning)
    
    # ... continue with script
```

### For Testing

```python
def test_with_validation():
    # Quick boolean check
    from config.validation import quick_validate
    
    if not quick_validate(app):
        pytest.skip("Configuration not available")
    
    # ... run tests
```

## API Reference

### Main Functions

| Function | Description |
|----------|-------------|
| `validate_startup(app, config)` | Run full validation |
| `require_valid_config(app)` | Validate and exit if invalid |
| `quick_validate(app)` | Fast boolean check |
| `print_config_status(app)` | Print detailed status |

### Configuration Presets

| Function | Description |
|----------|-------------|
| `get_minimal_config()` | Fast, basic checks |
| `get_standard_config()` | Recommended default |
| `get_full_config(check_db)` | Thorough validation |
| `get_strict_config()` | Warnings as errors |

### Context Functions

| Function | Description |
|----------|-------------|
| `validate_for_batch_mode(app)` | Strict, checks database |
| `validate_for_interactive_mode(app)` | Fast, standard checks |

### Custom Validators

| Function | Description |
|----------|-------------|
| `register_validator(func)` | Add custom validation |
| `clear_custom_validators()` | Remove all custom validators |

## Files

| File | Purpose |
|------|---------|
| `config/validation.py` | Main validation module |
| `config/__init__.py` | Exports validation functions |

## Performance

- `MINIMAL` validation: ~10ms
- `STANDARD` validation: ~50ms (includes library imports)
- `FULL` validation: ~100ms (includes PowerFactory checks)
- Database check: +5-30 seconds (network dependent)

For interactive use, `STANDARD` is recommended. For batch jobs, `FULL` with database check ensures all dependencies are available before processing hundreds of devices.

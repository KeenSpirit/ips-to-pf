# Phase 2: Config Package Refactoring - Summary

## Overview

This document summarizes the changes made in Phase 2 of the codebase modularization effort, which focused on creating a `config/` package to centralize all configuration, constants, and paths.

## Problem Solved

Before this refactoring:
- Hardcoded network paths were scattered across multiple files
- Configuration constants were mixed in `external_variables.py`
- Difficult to update paths when infrastructure changes
- No clear documentation of configurable values

## Solution

Created a new `config/` package with three focused modules:

```
config/
├── __init__.py           # Package exports
├── paths.py              # All network paths and file locations
├── relay_patterns.py     # Relay classification constants
└── region_config.py      # Region-specific settings (Energex/Ergon)
```

## New Module Details

### config/paths.py

Centralizes all file paths and network locations:

| Constant | Purpose |
|----------|---------|
| `SCRIPTS_BASE` | Base path for all PowerFactory scripts |
| `NETDASH_READER_PATH` | NetDash Reader library location |
| `ASSET_CLASSES_PATH` | Asset Classes library location |
| `RELAY_SKELETONS_PATH` | Add Protection Relay Skeletons script |
| `MAPPING_FILES_DIR` | Relay pattern mapping CSV files |
| `OUTPUT_BATCH_DIR` | Network location for batch results |
| `OUTPUT_LOCAL_DIR` | Local fallback for Citrix environment |

Helper functions:
- `get_output_directory(batch_mode)` - Get appropriate output path
- `ensure_path_exists(path)` - Create directory if needed
- `get_mapping_file_path(filename)` - Get full path to mapping file
- `add_external_library_paths()` - Add libraries to sys.path
- `validate_paths()` - Check path accessibility

### config/relay_patterns.py

Relay classification constants:

| Constant | Purpose |
|----------|---------|
| `SINGLE_PHASE_RELAYS` | IPS patterns for single/2-phase relays |
| `MULTI_PHASE_RELAYS` | IPS patterns for multi-phase with earth |
| `RELAYS_OOS` | Relay types to set out of service |
| `EXCLUDED_PATTERNS` | Patterns to filter during lookups |

Helper functions:
- `is_single_phase_relay(pattern)` - Check if single phase
- `is_multi_phase_relay(pattern)` - Check if multi-phase
- `should_set_out_of_service(relay_type)` - Check OOS status
- `is_excluded_pattern(pattern)` - Check if should exclude

### config/region_config.py

Region-specific configuration:

| Item | Purpose |
|------|---------|
| `get_substation_mapping()` | Numeric to alpha substation codes |
| `SUFFIX_EXPANSIONS` | Double cable box name expansions |
| `REGION_ENERGEX`, `REGION_ERGON` | Region identifiers |

Helper functions:
- `get_substation_code(numeric)` - Get alpha code (cached)
- `expand_device_name(name)` - Expand "A+B" names
- `is_double_cable_box(name)` - Check if combined name
- `normalize_region(region)` - Normalize region string
- `is_energex(region)`, `is_ergon(region)` - Region checks

## Files Changed

### Files Modified to Use Config

| File | Changes |
|------|---------|
| `ips_data/setting_index.py` | Imports from `config.relay_patterns`, `config.region_config` |
| `ips_data/query_database.py` | Imports paths from `config.paths` |
| `ips_data/ips_settings.py` | Imports `RELAY_SKELETONS_PATH` from `config.paths` |
| `ips_data/ex_settings.py` | Removed unused `external_variables` import |
| `update_powerfactory/mapping_file.py` | Imports `MAPPING_FILES_DIR` from `config.paths` |
| `update_powerfactory/relay_settings.py` | Imports from `config.relay_patterns` |
| `update_powerfactory/update_powerfactory.py` | Imports `RELAYS_OOS` from `config.relay_patterns` |
| `ips_to_pf.py` | Imports output paths from `config.paths` |

### Backward Compatibility

`external_variables.py` has been converted to a redirect module:
- Re-exports all constants from `config` package
- Issues deprecation warning when imported
- Maintains exact same API for existing code

## Import Migration Guide

### Old Way (Deprecated)
```python
import external_variables as ev

# Using constants
if pattern in ev.EXCLUDED_PATTERNS:
    ...
sub_map = ev.sub_mapping()
```

### New Way (Recommended)
```python
from config.relay_patterns import EXCLUDED_PATTERNS
from config.region_config import get_substation_mapping

# Using constants
if pattern in EXCLUDED_PATTERNS:
    ...
sub_map = get_substation_mapping()
```

### For Paths
```python
# Old
sys.path.append(r"\\ecasd01\WksMgmt\PowerFactory\ScriptsLIB\NetDash-Reader")

# New
from config.paths import NETDASH_READER_PATH
sys.path.append(NETDASH_READER_PATH)
```

## Benefits

1. **Single Source of Truth** - All paths in one place
2. **Easy Maintenance** - Update paths in one location
3. **Better Documentation** - Clear docstrings for all constants
4. **Helper Functions** - Utility functions for common operations
5. **Environment Support** - Easy to add dev/test/prod configurations
6. **Path Validation** - Built-in validation function

## Configuration Hierarchy

```
config/
├── __init__.py          ← Convenience imports for common use
├── paths.py             ← Infrastructure/file locations
├── relay_patterns.py    ← Relay classification (IPS-related)
└── region_config.py     ← Region-specific (Energex/Ergon)
```

## Next Steps (Future Phases)

- **Phase 3**: Create `utils/` package for shared utilities
- **Phase 4**: Further refactor ips_data to remove remaining external dependencies
- **Phase 5**: Rename and cleanup (cosmetic improvements)

# Phase 3: Utils Package Refactoring - Summary

## Overview

This document summarizes the changes made in Phase 3 of the codebase modularization effort, which focused on creating a `utils/` package to centralize shared utility functions.

## Problem Solved

Before this refactoring:
- Utility functions like `all_relevant_objects()` were in `update_powerfactory/get_objects.py`
- `format_time()` was defined inline in `ips_to_pf.py`
- `determine_region()` was defined inline in `ips_to_pf.py`
- File handling code was duplicated across modules
- No consistent interface for common operations

## Solution

Created a new `utils/` package with three focused modules:

```
utils/
├── __init__.py       # Package exports
├── pf_utils.py       # PowerFactory-specific utilities
├── file_utils.py     # File and CSV handling utilities
└── time_utils.py     # Time formatting and measurement utilities
```

## New Module Details

### utils/pf_utils.py

PowerFactory-specific utility functions:

| Function | Purpose |
|----------|---------|
| `all_relevant_objects()` | Recursively get objects from folder hierarchy |
| `get_all_protection_devices()` | Get all relays and fuses from network model |
| `get_all_switches()` | Get all switches/CBs from network model |
| `get_active_feeders()` | Get all active feeders from network data |
| `determine_region()` | Determine Energex/Ergon from project structure |
| `get_relay_types()` | Get all relay types from equipment library |
| `get_fuse_types()` | Get all fuse types from equipment library |

### utils/file_utils.py

File and CSV handling utilities:

| Function | Purpose |
|----------|---------|
| `read_csv_to_dict_list()` | Read CSV into list of dictionaries |
| `read_csv_raw()` | Read CSV into list of lists |
| `write_dict_list_to_csv()` | Write list of dicts to CSV |
| `ensure_directory_exists()` | Create directory if needed |
| `get_citrix_adjusted_path()` | Adjust path for Citrix environment |
| `get_user_directory()` | Get user directory (Citrix-aware) |
| `safe_file_remove()` | Safely remove a file if it exists |
| `get_file_modification_time()` | Get file modification timestamp |
| `is_file_recent()` | Check if file was modified recently |

### utils/time_utils.py

Time formatting and measurement:

| Item | Purpose |
|------|---------|
| `format_duration()` | Format seconds to "X hours Y minutes Z seconds" |
| `format_duration_short()` | Format seconds to "HH:MM:SS" |
| `Timer` class | Timer with context manager support |
| `timed_operation()` | Context manager that logs duration |
| `get_current_timestamp()` | Get current time as "HH:MM:SS" |
| `get_current_datetime()` | Get current datetime as "YYYY-MM-DD HH:MM:SS" |

## Files Changed

### Files Modified to Use Utils

| File | Changes |
|------|---------|
| `ips_to_pf.py` | Uses `Timer`, `format_duration`, `determine_region`, file utils |
| `update_powerfactory/get_objects.py` | Now redirects to `utils.pf_utils` |

### Backward Compatibility

`update_powerfactory/get_objects.py` has been converted to a redirect module:
- Re-exports `all_relevant_objects` from `utils.pf_utils`
- Issues deprecation warning when imported

## Usage Examples

### Timer Class

```python
from utils.time_utils import Timer

# As context manager
with Timer() as t:
    do_something()
print(f"Took {t.formatted}")

# Manual usage
timer = Timer(name="My Operation", auto_log=True)
timer.start()
do_something()
timer.stop()  # Automatically logs duration
```

### File Utilities

```python
from utils.file_utils import (
    read_csv_to_dict_list,
    write_dict_list_to_csv,
    ensure_directory_exists,
    get_citrix_adjusted_path,
)

# Read CSV
data = read_csv_to_dict_list("input.csv")

# Write CSV
write_dict_list_to_csv(results, "output.csv")

# Handle Citrix paths
path = get_citrix_adjusted_path("C:\\LocalData\\output")

# Ensure directory exists
ensure_directory_exists("C:\\Output\\Results")
```

### PowerFactory Utilities

```python
from utils.pf_utils import (
    all_relevant_objects,
    get_all_protection_devices,
    determine_region,
)

# Get all relays
net_mod = app.GetProjectFolder("netmod")
relays = all_relevant_objects(app, [net_mod], "*.ElmRelay")

# Get protection devices with metadata
devices, device_dict = get_all_protection_devices(app)

# Determine region
region = determine_region(prjt)
```

## Import Migration Guide

### Old Way (Still Works with Deprecation Warning)
```python
from update_powerfactory.get_objects import all_relevant_objects
```

### New Way (Recommended)
```python
from utils.pf_utils import all_relevant_objects
```

## Combined Package Structure

After Phase 1, 2, and 3, the package structure is:

```
project/
├── config/                  # Phase 2: Configuration
│   ├── __init__.py
│   ├── paths.py            # Network paths and locations
│   ├── relay_patterns.py   # Relay classification constants
│   └── region_config.py    # Region-specific settings
├── utils/                   # Phase 3: Utilities
│   ├── __init__.py
│   ├── pf_utils.py         # PowerFactory utilities
│   ├── file_utils.py       # File handling utilities
│   └── time_utils.py       # Time utilities
├── ips_data/               # IPS data retrieval
├── update_powerfactory/    # PowerFactory updates
├── external_variables.py   # Deprecated (redirects to config)
└── ips_to_pf.py           # Main entry point
```

## Benefits

1. **Reduced Duplication** - Common functions in one place
2. **Consistent Interfaces** - Standardized function signatures
3. **Better Testability** - Utilities can be unit tested independently
4. **Improved Documentation** - Clear docstrings for all functions
5. **Timer Class** - Easy performance measurement with context manager
6. **Citrix Support** - Centralized path handling for Citrix environment

## Next Steps (Future Phases)

- **Phase 4**: Further refactor ips_data to remove remaining external dependencies
- **Phase 5**: Rename and cleanup (cosmetic improvements)

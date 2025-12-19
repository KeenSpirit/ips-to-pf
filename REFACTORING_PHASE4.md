# Phase 4: Remove ips_data External Dependencies - Summary

## Overview

This document summarizes the changes made in Phase 4 of the codebase modularization effort, which focused on removing external dependencies from the `ips_data/` package to create a clean separation between the data retrieval layer and the data application layer.

## Problem Solved

Before this refactoring, `ips_data/` had dependencies on:
1. `update_powerfactory.update_result` - Circular dependency risk
2. `update_powerfactory.mapping_file` - Wrong layer dependency (data retrieval depending on data application)
3. `external_variables` - Scattered configuration

## Solution

Created a clean architecture with:
1. **`core/` package** - Shared domain objects (UpdateResult)
2. **`ips_data/cb_mapping.py`** - Moved CB alternate name lookup to data layer
3. All `ips_data/` modules now import from `core/` and `config/` instead of `update_powerfactory/`

## New Dependency Architecture

```
                        ┌─────────────┐
                        │  ips_to_pf  │
                        └──────┬──────┘
                               │
                ┌──────────────┼──────────────┐
                │              │              │
                ▼              ▼              ▼
        ┌─────────────┐ ┌─────────────┐ ┌─────────────────┐
        │  ips_data/  │ │   devices   │ │update_powerfactory│
        └──────┬──────┘ └──────┬──────┘ └────────┬────────┘
                │              │                 │
                └──────────────┼─────────────────┘
                               │
                        ┌──────┴──────┐
                        │             │
                        ▼             ▼
                  ┌─────────┐   ┌──────────┐
                  │  core/  │   │  config/ │
                  └─────────┘   └──────────┘
```

## Files Created

### core/ Package (Shared Domain Objects)

| File | Purpose |
|------|---------|
| `core/__init__.py` | Package exports (UpdateResult) |
| `core/update_result.py` | UpdateResult dataclass (moved from update_powerfactory) |

### ips_data/cb_mapping.py (New)

CB alternate name lookup moved from `update_powerfactory/mapping_file.py`:

| Function | Purpose |
|----------|---------|
| `get_cb_alt_name_list()` | Get all CB alternate name mappings (cached) |
| `find_alternate_name()` | Find alternate name for a specific CB |
| `clear_cache()` | Clear the cached mappings |
| `get_cache_stats()` | Get cache statistics |

## Files Modified

### ips_data/ Package

| File | Changes |
|------|---------|
| `__init__.py` | Added exports for cb_mapping functions |
| `setting_index.py` | Imports from `config.relay_patterns`, `config.region_config` |
| `query_database.py` | Imports paths from `config.paths` |
| `ips_settings.py` | Imports from `config.paths` and `core` |
| `ee_settings.py` | Imports `UpdateResult` from `core` |
| `ex_settings.py` | Imports from `ips_data.cb_mapping` instead of `update_powerfactory.mapping_file` |

### update_powerfactory/ Package

| File | Changes |
|------|---------|
| `__init__.py` | Re-exports UpdateResult from core |
| `update_result.py` | Now redirects to `core.update_result` with deprecation warning |
| `get_objects.py` | Redirects to `utils.pf_utils` |
| `update_powerfactory.py` | Imports from `core` and `config` |
| `relay_settings.py` | Imports from `core` and `config` |
| `fuse_settings.py` | Imports `UpdateResult` from `core` |
| `ct_settings.py` | Imports `UpdateResult` from `core` |
| `vt_settings.py` | Imports `UpdateResult` from `core` |
| `mapping_file.py` | Uses `config.paths.MAPPING_FILES_DIR` |

## Import Migration Guide

### UpdateResult

```python
# Old (deprecated, still works with warning)
from update_powerfactory.update_result import UpdateResult

# New (recommended)
from core import UpdateResult
```

### CB Alternate Names

```python
# Old (in ex_settings.py)
from update_powerfactory import mapping_file as mf
cb_list = mf.get_cb_alt_name_list(app)

# New
from ips_data.cb_mapping import get_cb_alt_name_list
cb_list = get_cb_alt_name_list()  # app parameter now optional
```

### Configuration

```python
# Old
import external_variables as ev
patterns = ev.EXCLUDED_PATTERNS
sub_map = ev.sub_mapping()

# New
from config.relay_patterns import EXCLUDED_PATTERNS
from config.region_config import get_substation_mapping
sub_map = get_substation_mapping()
```

## Backward Compatibility

All changes maintain backward compatibility:

1. **`update_powerfactory.update_result`** - Re-exports from `core` with deprecation warning
2. **`update_powerfactory.get_objects`** - Re-exports from `utils.pf_utils` with deprecation warning
3. **`update_powerfactory.__init__`** - Re-exports `UpdateResult` from `core`
4. **`external_variables`** - Re-exports from `config` with deprecation warning

## Benefits

1. **Clean Layer Separation** - Data retrieval (`ips_data/`) no longer depends on data application (`update_powerfactory/`)
2. **No Circular Dependencies** - Both layers depend on `core/` and `config/`, not each other
3. **Better Testability** - Each package can be tested independently
4. **Clearer Architecture** - Easy to understand data flow

## Complete Package Structure (After Phase 4)

```
project/
├── core/                    # Phase 4: Shared domain objects
│   ├── __init__.py
│   └── update_result.py     # UpdateResult dataclass
├── config/                  # Phase 2: Configuration
│   ├── __init__.py
│   ├── paths.py            # Network paths
│   ├── relay_patterns.py   # Relay constants
│   └── region_config.py    # Region settings
├── utils/                   # Phase 3: Utilities
│   ├── __init__.py
│   ├── pf_utils.py         # PowerFactory utilities
│   ├── file_utils.py       # File handling
│   └── time_utils.py       # Time utilities
├── ips_data/               # Data retrieval layer
│   ├── __init__.py
│   ├── cb_mapping.py       # NEW: CB alternate name lookups
│   ├── setting_index.py    # Indexed settings
│   ├── query_database.py   # IPS database queries
│   ├── ee_settings.py      # Ergon processing
│   ├── ex_settings.py      # Energex processing
│   └── ips_settings.py     # Main orchestration
├── update_powerfactory/    # Data application layer
│   ├── __init__.py
│   ├── update_result.py    # Redirect to core (deprecated)
│   ├── get_objects.py      # Redirect to utils (deprecated)
│   ├── update_powerfactory.py
│   ├── relay_settings.py
│   ├── fuse_settings.py
│   ├── ct_settings.py
│   ├── vt_settings.py
│   ├── mapping_file.py
│   └── type_index.py
├── external_variables.py   # Redirect to config (deprecated)
└── ips_to_pf.py           # Main entry point
```

## Next Steps (Phase 5)

- **Phase 5**: Rename and cleanup (cosmetic improvements)
  - Consider renaming packages for clarity
  - Remove deprecated redirect modules (after grace period)
  - Update all imports to new locations
  - Final documentation updates

# Changelog

All notable changes to the IPS to PowerFactory Settings Transfer project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [2.0.0] - 2024-12-18

### Added

- **core/ package**: New package for shared domain objects
  - `UpdateResult` dataclass moved here from `update_powerfactory/`
  - Eliminates circular dependencies between packages

- **config/ package**: Centralized configuration management
  - `paths.py`: All network paths and file locations in one place
  - `relay_patterns.py`: Relay classification constants (SINGLE_PHASE, MULTI_PHASE, OOS, EXCLUDED)
  - `region_config.py`: Region-specific settings (substation mappings, suffix expansions)

- **utils/ package**: Shared utility functions
  - `pf_utils.py`: PowerFactory utilities (`all_relevant_objects`, `determine_region`, etc.)
  - `file_utils.py`: File handling (`read_csv_to_dict_list`, `write_dict_list_to_csv`, etc.)
  - `time_utils.py`: Time utilities (`format_duration`, `Timer` class)

- **ips_data/cb_mapping.py**: New module for CB alternate name lookups
  - Moved from `update_powerfactory/mapping_file.py`
  - Added caching for performance
  - Added `find_alternate_name()` helper function

- **Documentation**:
  - Comprehensive `README.md` with usage examples
  - `ARCHITECTURE.md` describing system design
  - `CHANGELOG.md` (this file)
  - Phase-specific refactoring summaries (REFACTORING_PHASE1-5.md)

### Changed

- **ips_data/ package**: No longer depends on `update_powerfactory/`
  - Uses `core.UpdateResult` instead of `update_powerfactory.update_result`
  - Uses `ips_data.cb_mapping` instead of `update_powerfactory.mapping_file`
  - Uses `config/` for all constants and paths

- **update_powerfactory/ package**: 
  - Uses `core.UpdateResult` for all result objects
  - Uses `config/` for all constants and paths
  - Uses `utils.pf_utils` for PowerFactory utilities

- **ips_to_pf.py**:
  - Uses `utils.time_utils.Timer` for performance measurement
  - Uses `utils.pf_utils.determine_region()` instead of local function
  - Uses `config.paths` for output directories

### Deprecated

- **external_variables.py**: Now redirects to `config/` package
  - Emits deprecation warning when imported
  - Will be removed in future version

- **update_powerfactory/update_result.py**: Now redirects to `core/`
  - Emits deprecation warning when imported
  - Import from `core` instead: `from core import UpdateResult`

- **update_powerfactory/get_objects.py**: Now redirects to `utils.pf_utils`
  - Emits deprecation warning when imported
  - Import from `utils` instead: `from utils.pf_utils import all_relevant_objects`

### Fixed

- Eliminated circular dependency risks between `ips_data/` and `update_powerfactory/`
- Consistent import paths across all modules

## [1.1.0] - 2024-XX-XX

### Added

- `SettingIndex` class for O(1) setting lookups
- `RelayTypeIndex` and `FuseTypeIndex` for O(1) type matching
- `UpdateResult` dataclass replacing dictionary-based patterns
- Comprehensive docstrings throughout codebase

### Changed

- Refactored setting lookups from O(n) to O(1) complexity
- Improved error handling with structured result objects

### Performance

- ~833x improvement in device lookup performance (indexed vs linear)
- Reduced batch update time significantly

## [1.0.0] - 2024-XX-XX

### Added

- Initial release
- Support for Energex (SEQ) and Ergon regions
- Relay and fuse settings transfer
- CT/VT configuration
- Batch and interactive modes
- CSV result output

---

## Migration Guide

### Migrating from 1.x to 2.0

#### Import Changes

```python
# Old imports (deprecated, still work with warnings)
import external_variables as ev
from update_powerfactory.update_result import UpdateResult
from update_powerfactory.get_objects import all_relevant_objects

# New imports (recommended)
from config.relay_patterns import EXCLUDED_PATTERNS, SINGLE_PHASE_RELAYS
from config.region_config import get_substation_mapping
from config.paths import MAPPING_FILES_DIR
from core import UpdateResult
from utils.pf_utils import all_relevant_objects
```

#### Configuration Changes

Configuration is now in `config/` package:

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

#### CB Alternate Names

```python
# Old
from update_powerfactory import mapping_file as mf
cb_list = mf.get_cb_alt_name_list(app)

# New
from ips_data.cb_mapping import get_cb_alt_name_list
cb_list = get_cb_alt_name_list()  # app parameter now optional
```

# Engineering Assumptions and Architecture

This document describes the architecture and high-level engineering assumptions of the IPS to PowerFactory Settings Transfer system.

## System Overview

The system transfers protection device settings from the IPS (Intelligent Protection System) database to DIgSILENT PowerFactory network models. It supports both Energex (SEQ) and Ergon regional configurations.

## Architectural Layers

```
┌─────────────────────────────────────────────────────────────┐
│                      Entry Point                             │
│                      main.py                                │
└─────────────────────────────┬───────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────────┐
│   ips_data/   │    │   devices.py  │    │update_powerfactory/│
│ Data Retrieval│    │ Domain Model  │    │  Data Application │
└───────┬───────┘    └───────┬───────┘    └─────────┬─────────┘
        │                    │                      │
        └────────────────────┼──────────────────────┘
                             │
              ┌──────────────┼──────────────┬───────────────┐
              │              │              │               │
              ▼              ▼              ▼               ▼
        ┌─────────┐    ┌──────────┐   ┌─────────┐   ┌──────────────┐
        │  core/  │    │  config/ │   │  utils/ │   │logging_config/│
        │ Shared  │    │  Config  │   │ Utility │   │   Logging    │
        │ Objects │    │ Settings │   │Functions│   │   System     │
        └─────────┘    └──────────┘   └─────────┘   └──────────────┘
```

### Dependency Flow

```
main.py
    ├── ips_data/     ──┐
    └── update_powerfactory/ ──┼── core/, config/, utils/, logging_config/
```

## Package Descriptions

### core/ - Shared Domain Objects

Contains domain objects shared between the data retrieval and application layers.

| Module | Purpose |
|--------|---------|
| `update_result.py` | `UpdateResult` dataclass for tracking device update status |
| `protection_device.py` | `ProtectionDevice` class for device data |
| `setting_record.py` | `SettingRecord` dataclass for IPS settings |

**Why it exists**: Prevents circular dependencies between `ips_data/` and `update_powerfactory/`.

### config/ - Configuration Management

Centralizes all configuration, constants, and paths.

| Module | Purpose |
|--------|---------|
| `paths.py` | Network paths, file locations, output directories |
| `relay_patterns.py` | Relay classification (single-phase, multi-phase, OOS) |
| `region_config.py` | Region-specific settings (substation mappings, suffix expansions) |
| `validation.py` | Configuration validation at startup |

**Why it exists**: Single source of truth for configuration. Easy to update paths when infrastructure changes.

### utils/ - Shared Utilities

General-purpose utility functions used throughout the application.

| Module | Purpose |
|--------|---------|
| `pf_utils.py` | PowerFactory-specific utilities (object retrieval, region detection) |
| `file_utils.py` | File and CSV handling (read, write, path management) |
| `time_utils.py` | Time formatting and performance measurement |

**Why it exists**: Avoids code duplication and provides consistent interfaces.

### logging_config/ - Logging System

Centralized, queue-based logging for thread-safe concurrent writes.

| Module | Purpose |
|--------|---------|
| `logging_utils.py` | Core logging setup with queue-based handler |
| `configure_logging.py` | Device attribute logging helper |

**Key Features**:
- Queue-based logging for thread-safe concurrent writes
- Rotating file handler (10MB max, 5 backups)
- JSON Lines format for machine parsing
- Username injection into log records
- External library log suppression (netdash, assetclasses, etc.)

**Log File Location**: `{project_root}/results_log/ips_to_pf.log`

**Usage restricted to**: `main.py`, `orchestrator.py`, `query_database.py`

### ips_data/ - Data Retrieval Layer

Handles all interactions with the IPS database.

| Module | Purpose |
|--------|---------|
| `query_database.py` | IPS database queries via NetDash API |
| `setting_index.py` | Indexed data structures for O(1) lookups |
| `cb_mapping.py` | CB alternate name lookups |
| `ee_settings.py` | Ergon region-specific processing |
| `ex_settings.py` | Energex region-specific processing |
| `ips_settings.py` | Main orchestration for IPS data retrieval |

**Key Design Decision**: This layer does NOT depend on `update_powerfactory/`. All shared objects come from `core/`.

### update_powerfactory/ - Data Application Layer

Applies retrieved settings to PowerFactory models.

| Module | Purpose |
|--------|---------|
| `orchestrator.py` | Main update orchestration |
| `relay_settings.py` | Relay device configuration |
| `relay_reclosing.py` | Reclosing logic configuration |
| `relay_logic_elements.py` | Dip switch configuration |
| `fuse_settings.py` | Fuse device configuration |
| `ct_settings.py` | Current transformer configuration |
| `vt_settings.py` | Voltage transformer configuration |
| `mapping_file.py` | Settings mapping file handling |
| `type_index.py` | Relay/fuse type indexes for O(1) lookups |

## Data Flow

```
1. User starts script (main.py)
   └── setup_logging() initializes logging system
        │
        ▼
2. Validate configuration
   (config/validation.py)
        │
        ▼
3. Determine region from project structure
        │
        ▼
4. Query IPS database for setting IDs
   (ips_data/query_database.py)
   └── Logs: index creation, retry attempts
        │
        ▼
5. Build indexed lookups
   (ips_data/setting_index.py)
        │
        ▼
6. Match PF devices to IPS records
   (ips_data/ee_settings.py or ex_settings.py)
        │
        ▼
7. Create ProtectionDevice objects
   (core/protection_device.py)
        │
        ▼
8. Update PowerFactory models
   (update_powerfactory/orchestrator.py)
   └── Logs: type index build, errors, completion
        │
        ▼
9. Generate results CSV
   (main.py)
   └── Logs: script completion
```

## Key Design Patterns

### 1. Indexed Lookups (O(1) Performance)

The `SettingIndex` class pre-processes raw IPS data into dictionaries keyed by various attributes:

```python
class SettingIndex:
    by_asset_name: Dict[str, List[SettingRecord]]
    by_switch_name: Dict[str, List[SettingRecord]]
    by_setting_id: Dict[str, SettingRecord]
```

This reduces lookup complexity from O(n) to O(1), achieving approximately 833x performance improvement when processing thousands of device settings.

### 2. Factory Methods for Result Creation

`UpdateResult` uses factory methods for common scenarios:

```python
result = UpdateResult.from_device(device)
result = UpdateResult.not_in_ips(device)
result = UpdateResult.script_failed(device, error)
result = UpdateResult.info_record(pf_device, message)
```

### 3. Caching

Several components cache data after first load:
- `SettingIndex`: Cached by region
- `RelayTypeIndex` / `FuseTypeIndex`: Built once per update run
- CB alternate names: Cached in `cb_mapping.py`
- Mapping files: Cached in `mapping_file.py`

### 4. Backward Compatibility via Re-exports

Deprecated modules re-export from new locations with deprecation warnings:

```python
# update_powerfactory/update_result.py
from core.update_result import UpdateResult  # Re-export
warnings.warn("Import from core instead", DeprecationWarning)
```

### 5. Queue-Based Logging

The logging system uses Python's `QueueHandler` and `QueueListener` for thread-safe writes:

```python
from logging_config import setup_logging, get_logger

setup_logging()  # Initialize once at startup
logger = get_logger(__name__)

logger.info("Message")  # Thread-safe, non-blocking
```

## Region-Specific Processing

### Energex (SEQ)

- Uses switch names to match IPS records
- Handles double cable box configurations (A+B, A+B+C)
- CB alternate name lookups for non-standard names
- The index handles double cable box expansion (e.g., "NIP1A+B" is indexed under both "NIP1A" and "NIP1B")

### Ergon

- Uses plant numbers extracted from device names
- Different relay pattern conventions
- Separate settings processing logic

## Mapping Files Structure

All mapping files are stored in the project root under `mapping_files/`:

```
mapping_files/
├── cb_alt_names/           # CB alternate name mappings
│   └── CB_ALT_NAME.csv     # Maps PF CB names to IPS names
├── curve_mapping/          # IDMT curve mappings
│   └── curve_mapping.csv   # Maps IPS curve codes to PF curve names
├── relay_maps/             # Relay pattern mapping files
│   └── *.csv               # Individual relay pattern mappings
└── type_mapping/           # Type mapping configuration
    └── type_mapping.csv    # Maps IPS patterns to PF types + mapping files
```

### Path Configuration

Paths are configured in `config/paths.py`:

```python
PROJECT_ROOT = Path(__file__).parent.parent

MAPPING_FILES_BASE = PROJECT_ROOT / "mapping_files"
CB_ALT_NAMES_DIR = MAPPING_FILES_BASE / "cb_alt_names"
CURVE_MAPPING_DIR = MAPPING_FILES_BASE / "curve_mapping"
RELAY_MAPS_DIR = MAPPING_FILES_BASE / "relay_maps"
TYPE_MAPPING_DIR = MAPPING_FILES_BASE / "type_mapping"
```

### Helper Functions

```python
from config.paths import (
    get_cb_alt_name_file,    # Returns path to CB_ALT_NAME.csv
    get_curve_mapping_file,  # Returns path to curve_mapping.csv
    get_type_mapping_file,   # Returns path to type_mapping.csv
    get_relay_map_file,      # Returns path to specific relay map file
)
```

## Configuration Validation

The `config/validation.py` module provides comprehensive configuration validation at startup. This catches configuration issues early with clear error messages rather than failing mid-run with cryptic stack traces.

### Validation Levels

| Level | What's Checked | Use Case |
|-------|----------------|----------|
| `MINIMAL` | Critical paths and required files | Quick checks, testing |
| `STANDARD` | Paths, files, library imports | Interactive mode (default) |
| `FULL` | All above + PowerFactory environment | Production use |
| `STRICT` | All above + warnings become errors | Critical batch jobs |

### Usage

```python
from config.validation import require_valid_config

def main(app=None, batch=False):
    if not app:
        app = pf.GetApplication()
    
    # Validate configuration - exits automatically if invalid
    require_valid_config(app)
    
    # ... rest of script (only runs if config is valid)
```

### What Gets Validated

**Paths**: SCRIPTS_BASE, MAPPING_FILES_DIR, OUTPUT_BATCH_DIR, OUTPUT_LOCAL_DIR, library paths

**Required Files**: type_mapping.csv, CB_ALT_NAME.csv

**Optional Files**: curve_mapping.csv

**External Libraries**: netdashread, assetclasses

**PowerFactory (Full level)**: Active project, required folders (netmod, netdat, equip), libraries

## Error Handling Assumptions

- All update operations return `UpdateResult` objects
- Errors are captured but don't stop batch processing
- Results are written to CSV for review
- Logging in `orchestrator.py` captures exceptions with full device attributes

## Performance Assumptions

1. **Batch Mode Write Caching**: PowerFactory write cache enabled during batch updates
2. **Progress Reporting**: Every 10 devices to avoid UI freeze
3. **Lazy Loading**: Mapping files loaded only when needed
4. **Index Pre-computation**: Indexes built once, used for all lookups
5. **Queue-Based Logging**: Non-blocking log writes for better performance

## Logging Architecture

### Log Format

JSON Lines format - each line is a self-contained JSON object:

```json
{"timestamp": "2024-01-15T10:30:45+00:00", "name": "module_name", "level": "INFO", "username": "user", "message": "Message text"}
```

### What Gets Logged

| Location | What is Logged |
|----------|----------------|
| `main.py` | Script start/end, overall timing |
| `query_database.py` | Index creation, retry attempts, batch progress |
| `orchestrator.py` | Type index build, device errors, completion summary |

### Rotation Policy

- Maximum file size: 10MB
- Backup count: 5 files
- Oldest logs automatically deleted

## Key Engineering Assumptions

1. **Network Accessibility**: Network paths (`\\ecasd01\WksMgmt\PowerFactory`) must be accessible from the machine running the script

2. **PowerFactory Environment**: Script runs within the PowerFactory Python environment with access to the `powerfactory` module

3. **IPS Database**: NetDash API is available and the IPS database is accessible

4. **Device Matching**: 
   - Energex uses switch names for matching
   - Ergon uses plant numbers for matching
   - Devices with identical attributes but different switches are allowed by design

5. **Double Cable Box Handling**: The same setting record may create multiple device objects if it protects multiple switches (e.g., "NIP1A+B" creates devices for both switch "NIP1A" and switch "NIP1B")

6. **Region Detection**: Region (Energex vs Ergon) is automatically detected from the PowerFactory project structure

7. **Mapping File Format**: All mapping files are CSV format with specific column structures

8. **Citrix Environment**: Local fallback paths are used when network locations are unavailable (Citrix environment)
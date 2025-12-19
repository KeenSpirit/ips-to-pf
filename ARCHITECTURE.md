# Architecture Documentation

This document describes the architecture of the IPS to PowerFactory Settings Transfer system.

## System Overview

The system transfers protection device settings from the IPS (Intelligent Protection System) database to DIgSILENT PowerFactory network models. It supports both Energex (SEQ) and Ergon regional configurations.

## Architectural Layers

```
┌─────────────────────────────────────────────────────────────┐
│                      Entry Point                             │
│                      ips_to_pf.py                           │
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
              ┌──────────────┼──────────────┐
              │              │              │
              ▼              ▼              ▼
        ┌─────────┐    ┌──────────┐   ┌─────────┐
        │  core/  │    │  config/ │   │  utils/ │
        │ Shared  │    │  Config  │   │ Utility │
        │ Objects │    │ Settings │   │Functions│
        └─────────┘    └──────────┘   └─────────┘
```

## Package Descriptions

### core/ - Shared Domain Objects

Contains domain objects shared between the data retrieval and application layers.

| Module | Purpose |
|--------|---------|
| `update_result.py` | `UpdateResult` dataclass for tracking device update status |

**Why it exists**: Prevents circular dependencies between `ips_data/` and `update_powerfactory/`.

### config/ - Configuration Management

Centralizes all configuration, constants, and paths.

| Module | Purpose |
|--------|---------|
| `paths.py` | Network paths, file locations, output directories |
| `relay_patterns.py` | Relay classification (single-phase, multi-phase, OOS) |
| `region_config.py` | Region-specific settings (substation mappings, suffix expansions) |

**Why it exists**: Single source of truth for configuration. Easy to update paths when infrastructure changes.

### utils/ - Shared Utilities

General-purpose utility functions used throughout the application.

| Module | Purpose |
|--------|---------|
| `pf_utils.py` | PowerFactory-specific utilities (object retrieval, region detection) |
| `file_utils.py` | File and CSV handling (read, write, path management) |
| `time_utils.py` | Time formatting and performance measurement |

**Why it exists**: Avoids code duplication and provides consistent interfaces.

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
| `update_powerfactory.py` | Main update orchestration |
| `relay_settings.py` | Relay device configuration |
| `fuse_settings.py` | Fuse device configuration |
| `ct_settings.py` | Current transformer configuration |
| `vt_settings.py` | Voltage transformer configuration |
| `mapping_file.py` | Settings mapping file handling |
| `type_index.py` | Relay/fuse type indexes for O(1) lookups |

## Data Flow

```
1. User starts script (ips_to_pf.py)
        │
        ▼
2. Determine region from project structure
        │
        ▼
3. Query IPS database for setting IDs
   (ips_data/query_database.py)
        │
        ▼
4. Build indexed lookups
   (ips_data/setting_index.py)
        │
        ▼
5. Match PF devices to IPS records
   (ips_data/ee_settings.py or ex_settings.py)
        │
        ▼
6. Create ProtectionDevice objects
   (devices.py)
        │
        ▼
7. Update PowerFactory models
   (update_powerfactory/update_powerfactory.py)
        │
        ▼
8. Generate results CSV
   (ips_to_pf.py)
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

This reduces lookup complexity from O(n) to O(1).

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

Deprecated modules re-export from new locations:

```python
# update_powerfactory/update_result.py
from core.update_result import UpdateResult  # Re-export
warnings.warn("Import from core instead", DeprecationWarning)
```

## Region-Specific Processing

### Energex (SEQ)

- Uses switch names to match IPS records
- Handles double cable box configurations (A+B, A+B+C)
- CB alternate name lookups for non-standard names

### Ergon

- Uses plant numbers extracted from device names
- Different relay pattern conventions
- Separate settings processing logic

## Error Handling

- All update operations return `UpdateResult` objects
- Errors are captured but don't stop batch processing
- Results are written to CSV for review
- Logging throughout for debugging

## Performance Considerations

1. **Batch Mode Write Caching**: PowerFactory write cache enabled during batch updates
2. **Progress Reporting**: Every 10 devices to avoid UI freeze
3. **Lazy Loading**: Mapping files loaded only when needed
4. **Index Pre-computation**: Indexes built once, used for all lookups

## Future Enhancements

Potential improvements identified:

1. **Strategy Pattern**: For region-specific logic (currently using if/else branches)
2. **Async Processing**: For large batch updates
3. **Configuration Validation**: Startup checks for required paths/files
4. **Unit Test Suite**: Comprehensive testing with mocked PowerFactory

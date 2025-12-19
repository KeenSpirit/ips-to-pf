# IPS to PowerFactory Settings Transfer

A Python application for transferring protection device settings from the IPS (Intelligent Protection System) database to DIgSILENT PowerFactory network models.

## Overview

This tool automates the transfer of relay and fuse protection settings between Energy Queensland's IPS database and PowerFactory models, supporting both Energex (SEQ) and Ergon regions.

## Features

- **Automated Settings Transfer**: Transfers relay and fuse settings from IPS to PowerFactory
- **Region Support**: Handles both Energex (SEQ) and Ergon regional configurations
- **Performance Optimized**: Uses indexed lookups (O(1)) instead of linear scans
- **Batch Processing**: Supports both interactive and batch update modes
- **CT/VT Configuration**: Automatically configures instrument transformers
- **Result Logging**: Generates CSV reports of all updates

## Project Structure

```
ips_to_powerfactory/
├── core/                    # Shared domain objects
│   ├── __init__.py
│   └── protection_device.py # ProtectionDevice dataclass
│   └── setting_record.py    # SettingRecord dataclass
│   └── update_result.py     # UpdateResult dataclass
│
├── config/                  # Configuration management
│   ├── __init__.py
│   ├── paths.py            # Network paths and file locations
│   ├── relay_patterns.py   # Relay classification constants
│   └── region_config.py    # Region-specific settings
│
├── utils/                   # Shared utilities
│   ├── __init__.py
│   ├── pf_utils.py         # PowerFactory utilities
│   ├── file_utils.py       # File handling utilities
│   └── time_utils.py       # Time formatting utilities
│
├── ips_data/               # IPS data retrieval layer
│   ├── __init__.py
│   ├── query_database.py   # IPS database queries
│   ├── setting_index.py    # Indexed setting lookups
│   ├── cb_mapping.py       # CB alternate name mappings
│   ├── ee_settings.py      # Ergon region processing
│   ├── ex_settings.py      # Energex region processing
│   └── ips_settings.py     # Main orchestration
│
├── update_powerfactory/    # PowerFactory update layer
│   ├── __init__.py
│   ├── orchestrator.py     # Main update orchestration
│   ├── relay_settings.py   # Relay configuration
│   ├── fuse_settings.py    # Fuse configuration
│   ├── ct_settings.py      # CT configuration
│   ├── vt_settings.py      # VT configuration
│   ├── mapping_file.py     # Settings mapping files
│   └── type_index.py       # Type lookup indexes
│
├── mapping/                # CSV mapping files
│   └── *.csv              # Relay pattern mappings
│
├── main.py           # Main entry point
└── user_inputs.py         # User input handling
```

## Installation

1. Ensure PowerFactory Python environment is configured
2. Clone or copy the project to your PowerFactory scripts directory
3. Verify network paths in `config/paths.py` are accessible

## Usage

### Interactive Mode (Single Project)

```python
# In PowerFactory Python console
import main

ips_to_pf.main()
```

### Batch Mode (Multiple Projects)

```python
# Called from batch update script
import main

ips_to_pf.main(app=app, batch=True)
```

## Configuration

### Network Paths

Edit `config/paths.py` to update network locations:

```python
SCRIPTS_BASE = r"\\\\server\\path\\to\\PowerFactory"
MAPPING_FILES_DIR = os.path.join(SCRIPTS_BASE, "mapping")
```

### Relay Patterns

Add new relay patterns to `config/relay_patterns.py`:

```python
SINGLE_PHASE_RELAYS = [
    "Pattern1",
    "Pattern2",
]
```

### Region Settings

Configure region-specific settings in `config/region_config.py`:

```python
def get_substation_mapping():
    return {
        "H22": "LGL",
        # Add new mappings here
    }
```

## Architecture

The application follows a layered architecture:

1. **Core Layer** (`core/`): Shared domain objects used across all layers
2. **Config Layer** (`config/`): Centralized configuration management
3. **Utils Layer** (`utils/`): Shared utility functions
4. **Data Layer** (`ips_data/`): IPS database interactions and data retrieval
5. **Application Layer** (`update_powerfactory/`): PowerFactory model updates

### Dependency Flow

```
ips_to_pf.py
    ├── ips_data/     ──┐
    └── update_powerfactory/ ──┼── core/, config/, utils/
```

## Performance

Key optimizations implemented:

- **Indexed Lookups**: `SettingIndex` provides O(1) lookups by asset name, switch name, etc.
- **Type Indexes**: `RelayTypeIndex` and `FuseTypeIndex` for O(1) type matching
- **Caching**: Mapping files and CB alternate names are cached after first load
- **Write Caching**: PowerFactory write cache enabled during batch updates

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development guidelines.

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history.

## License

Internal Energy Queensland use only.

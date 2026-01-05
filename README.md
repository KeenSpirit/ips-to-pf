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
- **Configuration Validation**: Validates all paths and dependencies at startup
- **Result Logging**: Generates CSV reports and JSON Lines log files for all updates

## Project Structure

```
ips_to_powerfactory/
├── core/                    # Shared domain objects
│   ├── __init__.py
│   ├── protection_device.py # ProtectionDevice dataclass
│   ├── setting_record.py    # SettingRecord dataclass
│   └── update_result.py     # UpdateResult dataclass
│
├── config/                  # Configuration management
│   ├── __init__.py
│   ├── paths.py            # Network paths and file locations
│   ├── relay_patterns.py   # Relay classification constants
│   ├── region_config.py    # Region-specific settings
│   └── validation.py       # Configuration validation at startup
│
├── utils/                   # Shared utilities
│   ├── __init__.py
│   ├── pf_utils.py         # PowerFactory utilities
│   ├── file_utils.py       # File handling utilities
│   └── time_utils.py       # Time formatting utilities
│
├── logging_config/         # Logging system
│   ├── __init__.py
│   ├── logging_utils.py    # Core logging setup
│   └── configure_logging.py # Device attribute logging
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
│   ├── relay_settings.py   # Relay configuration entry point
│   ├── relay_reclosing.py  # Reclosing logic configuration
│   ├── relay_logic_elements.py # Dip switch logic configuration
│   ├── setting_utils.py    # Shared utility functions
│   ├── fuse_settings.py    # Fuse configuration
│   ├── ct_settings.py      # CT configuration
│   ├── vt_settings.py      # VT configuration
│   ├── mapping_file.py     # Settings mapping files
│   └── type_index.py       # Type lookup indexes
│
├── ui/                     # User interface
│   ├── __init__.py
│   ├── device_selection.py # Device selection dialog
│   ├── widgets.py          # Reusable UI widgets
│   ├── utils.py            # UI utilities
│   └── constants.py        # UI constants
│
├── mapping_files/          # CSV mapping files (project root)
│   ├── cb_alt_names/       # CB alternate name mappings
│   │   └── CB_ALT_NAME.csv
│   ├── curve_mapping/      # IDMT curve mappings
│   │   └── curve_mapping.csv
│   ├── relay_maps/         # Relay pattern mapping files
│   │   └── *.csv
│   └── type_mapping/       # Type mapping configuration
│       └── type_mapping.csv
│
├── results_log/            # Log files (project root)
│   └── ips_to_pf.log
│
├── main.py                 # Main entry point
└── user_inputs.py          # User input handling
```

## Installation

1. Ensure PowerFactory Python environment is configured
2. Clone or copy the project to your PowerFactory scripts directory
3. Verify network paths in `config/paths.py` are accessible
4. Ensure mapping file directories exist under `mapping_files/`

## Usage

### Interactive Mode (Single Project)

```python
# In PowerFactory Python console
import main

main.main()
```

This will:
1. Validate configuration at startup
2. Present a device selection dialog
3. Transfer settings for selected devices
4. Generate a results CSV file

### Batch Mode (Multiple Projects)

```python
# Called from batch update script
import main

main.main(app=app, batch=True)
```

Batch mode:
- Skips device selection dialog
- Processes all devices in the active project
- Uses stricter configuration validation
- Outputs results to network location

## Configuration

### Mapping Files

Mapping files are stored in the project root under `mapping_files/`:

| Directory | File | Purpose |
|-----------|------|---------|
| `cb_alt_names/` | `CB_ALT_NAME.csv` | Maps PowerFactory CB names to IPS naming conventions |
| `curve_mapping/` | `curve_mapping.csv` | Maps IPS IDMT curve codes to PowerFactory curve names |
| `relay_maps/` | `*.csv` | Individual mapping files for each relay pattern |
| `type_mapping/` | `type_mapping.csv` | Maps IPS relay patterns to PF relay types and mapping files |

### Network Paths

Edit `config/paths.py` to update network locations:

```python
SCRIPTS_BASE = r"\\server\path\to\PowerFactory"
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

## Output

### Results CSV

Each run generates a CSV file containing update results for all processed devices, including:
- Substation and plant number
- Relay pattern and date setting
- Update result status
- CT/VT configuration results
- Any error details

### Log Files

Log files are stored in `{project_root}/results_log/ips_to_pf.log`:
- JSON Lines format for machine parsing
- 10MB max file size with 5 backup files
- Automatic rotation

To parse logs:

```python
import json

with open("results_log/ips_to_pf.log") as f:
    for line in f:
        record = json.loads(line)
        print(record["timestamp"], record["level"], record["message"])
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development guidelines.

## Architecture

See [Assumptions.md](Assumptions.md) for detailed architecture documentation and engineering assumptions.

## Contact

For questions about the codebase, contact dan.park@energyq.com.au
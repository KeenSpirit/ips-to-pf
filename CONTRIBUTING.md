# Contributing Guidelines

Thank you for contributing to the IPS to PowerFactory Settings Transfer project!

## Code Organization

### Package Structure

```
project/
├── core/              # Shared domain objects (NO external deps)
├── config/            # Configuration (NO external deps)
├── utils/             # Utilities (depends on: config)
├── logging_config/    # Logging system (NO external deps)
├── ips_data/          # Data retrieval (depends on: core, config, utils)
├── ui/                # User device selection (NO external deps)
├── update_powerfactory/  # Data application (depends on: core, config, utils)
├── results_log/       # Log files directory
└── ips_to_pf.py       # Entry point (depends on: all packages)
```

### Dependency Rules

1. **core/** and **config/** must not depend on any other packages
2. **logging_config/** must not depend on any other packages
3. **utils/** may depend on **config/** only
4. **ips_data/** may depend on **core/**, **config/**, **utils/** only
5. **update_powerfactory/** may depend on **core/**, **config/**, **utils/** only
6. **ips_data/** must NOT depend on **update_powerfactory/** (and vice versa)

## Coding Standards

### Python Style

- Follow PEP 8 style guidelines
- Maximum line length: 88 characters
- Use type hints for function signatures
- Use f-strings for string formatting

### Docstrings

Use Google-style docstrings:

```python
def function_name(param1: str, param2: int) -> bool:
    """
    Brief description of function.
    
    Longer description if needed, explaining the function's
    purpose and any important details.
    
    Args:
        param1: Description of param1
        param2: Description of param2
        
    Returns:
        Description of return value
        
    Raises:
        ValueError: When invalid input is provided
        
    Example:
        >>> result = function_name("test", 42)
        >>> print(result)
        True
    """
```

### Imports

Order imports as follows:

```python
# 1. Standard library imports
import os
import sys
from typing import Dict, List, Optional

# 2. Third-party imports
from tenacity import retry

# 3. Local package imports (absolute)
from core import UpdateResult
from config.paths import MAPPING_FILES_DIR
from utils.pf_utils import all_relevant_objects
from logging_config import get_logger

# 4. Relative imports (within same package)
from .setting_index import SettingIndex
```

## Adding New Features

### New Relay Pattern

1. Add pattern to `config/relay_patterns.py`:
   ```python
   SINGLE_PHASE_RELAYS = [
       "ExistingPattern",
       "NewPattern",  # Add here
   ]
   ```

2. Create mapping CSV in `mapping_files/relay_maps/` directory

3. Add entry to `mapping_files/type_mapping/type_mapping.csv`

4. If the relay uses non-standard curve names, add entry to `mapping_files/curve_mapping/curve_mapping.csv`

### Unrecognised IPS Bay Name

Map the bay name to a new name format in `mapping_files/cb_alt_names/CB_ALT_NAME.csv`

### New Substation Mapping

Add to `config/region_config.py`:

```python
def get_substation_mapping():
    return {
        "H22": "LGL",
        "NEW": "ABC",  # Add here
    }
```

### New Utility Function

1. Determine appropriate module in `utils/`:
   - `pf_utils.py`: PowerFactory-specific
   - `file_utils.py`: File handling
   - `time_utils.py`: Time-related

2. Add function with type hints and docstring

3. Export from `utils/__init__.py`

## Testing

### Manual Testing

1. Test in interactive mode first:
   ```python
   import ips_to_pf
   ips_to_pf.main()
   ```

2. Verify results CSV is generated correctly

3. Check PowerFactory output window for errors

4. Check log file at `results_log/ips_to_pf.log`

### Test Cases to Cover

- [ ] Single device update (interactive)
- [ ] Batch update (multiple devices)
- [ ] Energex region
- [ ] Ergon region
- [ ] Relay with CT/VT
- [ ] Fuse device
- [ ] Device not in IPS
- [ ] Invalid relay pattern

## Common Issues

### Import Errors

If you get circular import errors:
- Move shared classes to `core/`
- Check dependency rules above

### Path Not Found

If network paths fail:
- Check `config/paths.py` settings
- Verify network connectivity
- Check for Citrix environment

### Type Lookup Failures

If relay/fuse types aren't found:
- Check mapping CSV exists
- Verify `type_mapping.csv` has correct entry
- Check for typos in pattern name

### Logging Issues

If logs aren't appearing:
- Ensure `setup_logging()` is called in main script
- Check log file location: `results_log/` in project root
- Verify write permissions to log directory

## Contact

For questions about the codebase, contact dan.park@energyq.com.au
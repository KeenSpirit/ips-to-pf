# Maintenance Notes

## Code Organization

### Package Structure

```
project/
├── core/              # Shared domain objects (NO external deps)
├── config/            # Configuration (NO external deps)
├── utils/             # Utilities (depends on: config)
├── ips_data/          # Data retrieval (depends on: core, config, utils)
├── update_powerfactory/  # Data application (depends on: core, config, utils)
└── ips_to_pf.py       # Entry point (depends on: all packages)
```

### Dependency Rules

1. **core/** and **config/** must not depend on any other packages
2. **utils/** may depend on **config/** only
3. **ips_data/** may depend on **core/**, **config/**, **utils/** only
4. **update_powerfactory/** may depend on **core/**, **config/**, **utils/** only
5. **ips_data/** must NOT depend on **update_powerfactory/** (and vice versa)

## Coding Standards

### Python Style

- Follow PEP 8 style guidelines
- Maximum line length: 100 characters
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

# 4. Relative imports (within same package)
from .setting_index import SettingIndex
```

### Logging

Use module-level logger:

```python
import logging

logger = logging.getLogger(__name__)

def some_function():
    logger.info("Processing started")
    logger.debug("Detailed debug info")
    logger.warning("Something unexpected")
    logger.error("Something failed")
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

2. Create mapping CSV in `mapping/` directory

3. Add entry to `mapping/type_mapping.csv`

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
   import main
   ips_to_pf.main()
   ```

2. Verify results CSV is generated correctly

3. Check PowerFactory output window for errors

### Test Cases to Cover

- [ ] Single device update (interactive)
- [ ] Batch update (multiple devices)
- [ ] Energex region
- [ ] Ergon region
- [ ] Relay with CT/VT
- [ ] Fuse device
- [ ] Device not in IPS
- [ ] Invalid relay pattern

## Pull Request Process

1. Create feature branch from main
2. Make changes following coding standards
3. Test thoroughly
4. Update documentation if needed
5. Update CHANGELOG.md
6. Submit PR with clear description

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

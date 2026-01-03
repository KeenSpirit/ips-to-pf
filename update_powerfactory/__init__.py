"""
Update PowerFactory package.

This package handles the transfer of protection device settings from
IPS database to PowerFactory models.

Package Structure:
    orchestrator.py       - Main update orchestration
    relay_settings.py     - Relay configuration entry point
    relay_reclosing.py    - Reclosing logic configuration
    relay_logic_elements.py - Dip switch logic configuration
    setting_utils.py      - Shared utility functions
    fuse_settings.py      - Fuse configuration
    ct_settings.py        - Current transformer configuration
    vt_settings.py        - Voltage transformer configuration
    mapping_file.py       - Settings mapping file handling
    type_index.py         - Relay/fuse type indexes for O(1) lookups

Main entry points:
    update_pf(): Main function to update all devices
    RelayTypeIndex: Indexed relay type lookups
    FuseTypeIndex: Indexed fuse type lookups

Performance optimizations in this version:
    - O(1) relay type lookups via RelayTypeIndex
    - O(1) fuse type lookups via FuseTypeIndex
    - Write caching during batch updates
    - Mapping file caching

Usage:
    from update_powerfactory.orchestrator import update_pf
    from update_powerfactory.type_index import RelayTypeIndex, FuseTypeIndex

    # Build indexes once
    relay_index = RelayTypeIndex.build(app)
    fuse_index = FuseTypeIndex.build(app)

    # Update devices
    results, has_updates = update_pf(app, device_list, data_capture_list)

Note: UpdateResult has been moved to the core package.
Import from core instead:
    from core import UpdateResult
"""

# Re-export UpdateResult from core for backward compatibility
from core import UpdateResult

# Re-export type indexes for convenience
from update_powerfactory.type_index import (
    RelayTypeIndex,
    FuseTypeIndex,
    build_type_indexes,
)

# Re-export utility functions that may be used externally
from update_powerfactory.setting_utils import (
    build_setting_key,
    determine_on_off,
    convert_binary,
    setting_adjustment,
    convert_string_to_list,
)

__all__ = [
    # Core types (backward compatibility)
    "UpdateResult",
    # Type indexes
    "RelayTypeIndex",
    "FuseTypeIndex",
    "build_type_indexes",
    # Utility functions
    "build_setting_key",
    "determine_on_off",
    "convert_binary",
    "setting_adjustment",
    "convert_string_to_list",
]
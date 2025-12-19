"""
IPS Data package for retrieving protection device settings.

This package handles all interactions with the IPS database and
provides functions for:
- Querying setting IDs for devices in a region
- Fetching detailed relay/fuse settings
- Matching PowerFactory devices to IPS records
- CB alternate name lookups

Modules:
    query_database: IPS database query functions
    setting_index: Indexed data structures for efficient lookups
    ee_settings: Ergon region-specific processing
    ex_settings: Energex region-specific processing
    ips_settings: Main orchestration module
    cb_mapping: Circuit breaker name mapping utilities

Usage:
    from ips_data import ips_settings
    devices, data = ips_settings.get_ips_settings(app, region, batch, called_function)

Note: SettingRecord has been moved to the core package.
Import from core instead:
    from core import SettingRecord
"""

from ips_data.setting_index import SettingIndex, create_setting_index
from ips_data.cb_mapping import get_cb_alt_name_list, find_alternate_name

# Re-export SettingRecord from core for backward compatibility
from core import SettingRecord

__all__ = [
    "SettingIndex",
    "SettingRecord",
    "create_setting_index",
    "get_cb_alt_name_list",
    "find_alternate_name",
]

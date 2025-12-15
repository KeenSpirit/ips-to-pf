"""
Update PowerFactory package.

This package handles the transfer of protection device settings from
IPS database to PowerFactory models.

Main entry points:
- update_pf(): Main function to update all devices
- RelayTypeIndex: Indexed relay type lookups
- FuseTypeIndex: Indexed fuse type lookups

Performance optimizations in this version:
- O(1) relay type lookups via RelayTypeIndex
- O(1) fuse type lookups via FuseTypeIndex
- Mapping file caching (type_mapping, curve_mapping, individual mapping files)
- Write caching during batch updates
"""

from update_powerfactory.update_powerfactory import update_pf, get_relay_types
from update_powerfactory.type_index import (
    RelayTypeIndex,
    FuseTypeIndex,
    build_type_indexes,
)
from update_powerfactory.relay_settings import relay_settings
from update_powerfactory.fuse_settings import fuse_setting
from update_powerfactory.mapping_file import (
    preload_cache,
    clear_cache,
    get_cache_stats,
)

__all__ = [
    "update_pf",
    "get_relay_types",
    "RelayTypeIndex",
    "FuseTypeIndex",
    "build_type_indexes",
    "relay_settings",
    "fuse_setting",
    "preload_cache",
    "clear_cache",
    "get_cache_stats",
]

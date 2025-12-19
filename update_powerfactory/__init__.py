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
- Write caching during batch updates

Note: UpdateResult has been moved to the core package.
Import from core instead:
    from core import UpdateResult
"""

# Re-export UpdateResult from core for backward compatibility
from core import UpdateResult

__all__ = [
    "UpdateResult",
]

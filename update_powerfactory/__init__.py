"""
Update PowerFactory package.

This package handles the transfer of protection device settings from
IPS database to PowerFactory models.

Main entry points:
- update_pf(): Main function to update all devices
- RelayTypeIndex: Indexed relay type lookups
- FuseTypeIndex: Indexed fuse type lookups
- UpdateResult: Dataclass for update results/status

Logging utilities:
- get_logger(): Get a dual-output logger
- LogContext: Context manager for structured logging
- configure_logging(): Configure file logging

Performance optimizations in this version:
- O(1) relay type lookups via RelayTypeIndex
- O(1) fuse type lookups via FuseTypeIndex
- Write caching during batch updates
- UpdateResult dataclass replaces dictionary-based update_info
"""

from update_powerfactory.update_result import UpdateResult, dict_to_result, result_to_dict
from update_powerfactory.type_index import (
    RelayTypeIndex,
    FuseTypeIndex,
    build_type_indexes,
)
from update_powerfactory.update_powerfactory import update_pf, get_relay_types
from update_powerfactory.relay_settings import relay_settings
from update_powerfactory.fuse_settings import fuse_setting
from update_powerfactory.logging_utils import (
    get_logger,
    set_app,
    clear_context,
    LogContext,
    BatchProgress,
    configure_logging,
    log_performance,
    log_exceptions,
    timed_operation,
)

__all__ = [
    # Main entry point
    "update_pf",
    "get_relay_types",
    # Type indexes
    "RelayTypeIndex",
    "FuseTypeIndex",
    "build_type_indexes",
    # Result class
    "UpdateResult",
    "dict_to_result",
    "result_to_dict",
    # Settings functions
    "relay_settings",
    "fuse_setting",
    # Logging utilities
    "get_logger",
    "set_app",
    "clear_context",
    "LogContext",
    "BatchProgress",
    "configure_logging",
    "log_performance",
    "log_exceptions",
    "timed_operation",
]
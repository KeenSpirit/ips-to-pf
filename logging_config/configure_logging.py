"""
Logging configuration for IPS to PowerFactory settings transfer.

This module provides backward compatibility and specialized logging functions.
The core logging functionality is in logging_utils.py.

Usage:
    from logging_config.configure_logging import log_device_atts

    log_device_atts(protection_device)
"""

from logging_config.logging_utils import (
    setup_logging,
    get_logger,
    get_log_path,
)

# Re-export for backward compatibility
getpath = get_log_path

# Module logger
_logger = get_logger(__name__)


def log_device_atts(prot_dev) -> None:
    """
    Log protection device attributes for debugging.

    Settings attribute is logged as 'settings loaded/no settings loaded'
    to keep logged data to manageable levels.

    Args:
        prot_dev: ProtectionDevice object to log
    """
    device_name = getattr(prot_dev, 'device', 'Unknown')
    _logger.info(f"Attributes for protection device {device_name}:")

    attributes = [
        'device', 'device_id', 'name', 'setting_id', 'date',
        'ct_primary', 'ct_secondary', 'vt_primary', 'vt_secondary',
        'fuse_type', 'fuse_size'
    ]

    for attr in attributes:
        if hasattr(prot_dev, attr):
            value = getattr(prot_dev, attr)
            _logger.info(f"  {attr}: {value}")

    # Log settings presence without full content
    if hasattr(prot_dev, 'settings'):
        settings = prot_dev.settings
        if settings and len(settings) > 0:
            _logger.info(f"  settings: {len(settings)} settings loaded")
        else:
            _logger.info("  settings: no settings loaded")
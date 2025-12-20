"""
Logging configuration package for IPS to PowerFactory settings transfer.

This package provides logging utilities that:
- Store log files on a network drive (handling Citrix environments)
- Handle multiple simultaneous file writes via queue-based logging
- Log script execution, device processing, and errors

Usage:
    from logging_config import setup_logging, get_logger

    # Initialize logging once at script startup
    setup_logging()

    # Get logger in any module that needs it
    logger = get_logger(__name__)
    logger.info("Processing started")
"""

from logging_config.logging_utils import (
    setup_logging,
    get_logger,
    get_log_path,
)

from logging_config.configure_logging import (
    log_device_atts,
)

__all__ = [
    "setup_logging",
    "get_logger",
    "get_log_path",
    "log_device_atts",
]
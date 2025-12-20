"""
Logging utilities for IPS to PowerFactory settings transfer.

This module provides a simple logging setup that:
- Stores log files on a network drive
- Handles multiple simultaneous file writes via queue-based logging
- Logs script execution, device processing, and errors

Usage:
    from logging_config import setup_logging, get_logger

    # Call once at script startup
    setup_logging()

    # Get logger in any module
    logger = get_logger(__name__)
    logger.info("Processing started")
"""

import logging
import logging.handlers
import os
import queue
import atexit
from pathlib import Path
from typing import Optional

# Module-level state
_logging_initialized = False
_log_queue: Optional[queue.Queue] = None
_queue_listener: Optional[logging.handlers.QueueListener] = None


def get_log_path(subdir: str = "IPStoPFlog") -> Path:
    """
    Get the path for log files, handling Citrix environments.

    Args:
        subdir: Subdirectory name for log files

    Returns:
        Path object for the log directory
    """
    user = Path.home().name

    # Try Citrix path first
    citrix_path = Path("//client/c$/Users") / user
    if citrix_path.exists():
        log_path = citrix_path / subdir
    else:
        log_path = Path.home() / subdir

    log_path.mkdir(exist_ok=True)
    return log_path


def setup_logging(log_level: int = logging.INFO) -> None:
    """
    Initialize the logging system.

    Sets up a queue-based logging system that safely handles
    concurrent writes from multiple threads/processes.

    Call this once at the start of your script.

    Args:
        log_level: Logging level (default: logging.INFO)
    """
    global _logging_initialized, _log_queue, _queue_listener

    if _logging_initialized:
        return

    # Create log directory and file path
    log_dir = get_log_path()
    log_file = log_dir / "ips_to_pf.log"

    # Create rotating file handler (10MB max, keep 5 backups)
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        delay=True
    )

    # Format: timestamp - module - level - username - message
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(username)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(formatter)
    file_handler.addFilter(_UsernameFilter())

    # Set up queue-based logging for thread safety
    _log_queue = queue.Queue(-1)
    queue_handler = logging.handlers.QueueHandler(_log_queue)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.addHandler(queue_handler)

    # Start queue listener (processes log records in background thread)
    _queue_listener = logging.handlers.QueueListener(
        _log_queue,
        file_handler,
        respect_handler_level=True
    )
    _queue_listener.start()

    # Register cleanup on exit
    atexit.register(_shutdown_logging)

    _logging_initialized = True


def _shutdown_logging() -> None:
    """Clean up logging resources on script exit."""
    global _queue_listener

    if _queue_listener:
        _queue_listener.stop()
        _queue_listener = None


class _UsernameFilter(logging.Filter):
    """Filter that adds username to log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.username = os.getenv("USERNAME", os.getenv("USER", "unknown"))
        return True


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance.

    Automatically initializes logging if not already done.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured logger instance
    """
    if not _logging_initialized:
        setup_logging()

    return logging.getLogger(name)
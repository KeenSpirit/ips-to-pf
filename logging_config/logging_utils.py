"""
Logging utilities for IPS to PowerFactory settings transfer.

This module provides a simple logging setup that:
- Stores log files on a network drive
- Handles multiple simultaneous file writes via queue-based logging
- Logs script execution, device processing, and errors
- Suppresses logs from external libraries
- Outputs JSON Lines format for easy machine parsing

Usage:
    from logging_config import setup_logging, get_logger

    # Call once at script startup
    setup_logging()

    # Get logger in any module
    logger = get_logger(__name__)
    logger.info("Processing started")

Log Format (JSON Lines):
    Each line is a self-contained JSON object:
    {"timestamp": "2024-01-15T10:30:45+00:00", "name": "module", "level": "INFO", "username": "user", "message": "text"}

Parsing Logs:
    import json

    with open("ips_to_pf.log") as f:
        for line in f:
            record = json.loads(line)
            print(record["timestamp"], record["level"], record["message"])

    # Or with pandas:
    import pandas as pd
    df = pd.read_json("ips_to_pf.log", lines=True)
"""

import logging
import logging.handlers
import json
import os
import queue
import atexit
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Any, Dict

# Module-level state
_logging_initialized = False
_log_queue: Optional[queue.Queue] = None
_queue_listener: Optional[logging.handlers.QueueListener] = None

# Application logger prefixes - only these will log at INFO level
# All other loggers (external libraries) will be set to WARNING
_APP_LOGGER_PREFIXES = (
    "__main__",
    "ips_data",
    "update_powerfactory",
    "logging_config",
    "config",
    "core",
    "utils",
)

# External libraries to explicitly suppress (set to WARNING)
# Note: netdashread loggers may still output if they configure their own
# handlers before setup_logging() is called. This is a known limitation.
_SUPPRESSED_LOGGERS = [
    "netdash",
    "netdashread",
    "netdashread.query",
    "netdashread.getdata",
    "assetclasses",
]


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

    External library logs are suppressed (set to WARNING level).
    Only application loggers will log at INFO level.

    Log output is in JSON Lines format for machine parsing.

    Call this once at the start of your script.

    Args:
        log_level: Logging level for application loggers (default: logging.INFO)
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

    # Use JSON Lines format for machine parsing
    formatter = _JsonFormatter()
    file_handler.setFormatter(formatter)

    # Set up queue-based logging for thread safety
    _log_queue = queue.Queue(-1)
    queue_handler = logging.handlers.QueueHandler(_log_queue)

    # Configure root logger to WARNING to suppress external libraries by default
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.WARNING)
    root_logger.addHandler(queue_handler)

    # Explicitly suppress known external library loggers
    # Also remove any handlers they may have added
    for lib_name in _SUPPRESSED_LOGGERS:
        lib_logger = logging.getLogger(lib_name)
        lib_logger.setLevel(logging.WARNING)
        lib_logger.handlers.clear()

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


class _JsonFormatter(logging.Formatter):
    """
    Formatter that outputs JSON Lines format.

    Each log record becomes a single JSON object on one line.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        # Build the log entry dictionary
        log_entry: Dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "name": record.name,
            "level": record.levelname,
            "username": os.getenv("USERNAME", os.getenv("USER", "unknown")),
            "message": record.getMessage(),
        }

        # Add exception info if present
        if record.exc_info:
            log_entry["exc_info"] = self.formatException(record.exc_info)

        # Add extra fields if any were passed
        if hasattr(record, "extra_data"):
            log_entry["extra"] = record.extra_data

        return json.dumps(log_entry, ensure_ascii=False)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance.

    Automatically initializes logging if not already done.
    Application loggers are set to INFO level, while external
    library loggers remain at WARNING level.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured logger instance
    """
    if not _logging_initialized:
        setup_logging()

    logger = logging.getLogger(name)

    # Set application loggers to INFO level
    if name.startswith(_APP_LOGGER_PREFIXES) or name == "__main__":
        logger.setLevel(logging.INFO)

    return logger
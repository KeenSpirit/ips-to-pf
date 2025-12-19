"""
Logging utilities for IPS to PowerFactory settings transfer.

This module provides a consistent logging framework that:
- Outputs to both Python logging and PowerFactory output window
- Provides structured context (device name, substation, operation)
- Includes performance timing decorators
- Offers consistent exception handling

Usage:
    from update_powerfactory.logging_utils import get_logger, LogContext

    logger = get_logger(__name__)

    with LogContext(app, device_name="RC-12345", substation="SUB_A"):
        logger.info("Processing device")
        logger.error("Something went wrong")

    @log_performance
    def slow_function(app, ...):
        ...
"""

import logging
import time
import functools
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Optional, Any, Callable, Dict, List
from enum import Enum


# =============================================================================
# Log Level Enum
# =============================================================================

class LogLevel(Enum):
    """Log levels matching Python logging module."""
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL


# =============================================================================
# Context Storage
# =============================================================================

@dataclass
class _LogContextData:
    """Thread-local storage for logging context."""
    app: Optional[Any] = None
    device_name: Optional[str] = None
    substation: Optional[str] = None
    operation: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)


# Global context - in PowerFactory scripts, we're single-threaded
_current_context = _LogContextData()


# =============================================================================
# Dual-Output Logger
# =============================================================================

class DualLogger:
    """
    Logger that outputs to both Python logging and PowerFactory.

    This ensures messages appear in:
    1. PowerFactory output window (for real-time visibility)
    2. Python log files (for post-run analysis)

    The logger automatically includes context information (device name,
    substation, operation) when available.

    Attributes:
        name: Logger name (typically __name__ of the calling module)
        _logger: Underlying Python logger instance
    """

    def __init__(self, name: str):
        """
        Initialize the dual logger.

        Args:
            name: Logger name, typically __name__ from calling module
        """
        self.name = name
        self._logger = logging.getLogger(name)

    def _format_message(self, message: str) -> str:
        """
        Format message with context information.

        Args:
            message: The raw log message

        Returns:
            Formatted message with context prefix
        """
        parts = []

        if _current_context.substation:
            parts.append(f"[{_current_context.substation}]")

        if _current_context.device_name:
            parts.append(f"[{_current_context.device_name}]")

        if _current_context.operation:
            parts.append(f"({_current_context.operation})")

        if parts:
            prefix = " ".join(parts)
            return f"{prefix} {message}"

        return message

    def _output_to_pf(self, level: LogLevel, message: str) -> None:
        """
        Output message to PowerFactory output window.

        Args:
            level: The log level
            message: The formatted message
        """
        app = _current_context.app
        if not app:
            return

        try:
            if level == LogLevel.DEBUG:
                app.PrintPlain(f"DEBUG: {message}")
            elif level == LogLevel.INFO:
                app.PrintInfo(message)
            elif level == LogLevel.WARNING:
                app.PrintWarn(message)
            elif level in (LogLevel.ERROR, LogLevel.CRITICAL):
                app.PrintError(message)
        except (AttributeError, RuntimeError):
            # PowerFactory app not available or invalid
            pass

    def debug(self, message: str, *args, pf_output: bool = False, **kwargs) -> None:
        """
        Log debug message.

        Debug messages go to Python logging only by default.
        Set pf_output=True to also show in PowerFactory.

        Args:
            message: Log message (may contain % formatting)
            pf_output: Whether to also output to PowerFactory
        """
        formatted = self._format_message(message % args if args else message)
        self._logger.debug(formatted, **kwargs)
        if pf_output:
            self._output_to_pf(LogLevel.DEBUG, formatted)

    def info(self, message: str, *args, pf_output: bool = True, **kwargs) -> None:
        """
        Log info message.

        Info messages go to both Python logging and PowerFactory by default.

        Args:
            message: Log message (may contain % formatting)
            pf_output: Whether to also output to PowerFactory
        """
        formatted = self._format_message(message % args if args else message)
        self._logger.info(formatted, **kwargs)
        if pf_output:
            self._output_to_pf(LogLevel.INFO, formatted)

    def warning(self, message: str, *args, pf_output: bool = True, **kwargs) -> None:
        """
        Log warning message.

        Warning messages go to both Python logging and PowerFactory by default.

        Args:
            message: Log message (may contain % formatting)
            pf_output: Whether to also output to PowerFactory
        """
        formatted = self._format_message(message % args if args else message)
        self._logger.warning(formatted, **kwargs)
        if pf_output:
            self._output_to_pf(LogLevel.WARNING, formatted)

    def error(self, message: str, *args, pf_output: bool = True, **kwargs) -> None:
        """
        Log error message.

        Error messages go to both Python logging and PowerFactory by default.

        Args:
            message: Log message (may contain % formatting)
            pf_output: Whether to also output to PowerFactory
        """
        formatted = self._format_message(message % args if args else message)
        self._logger.error(formatted, **kwargs)
        if pf_output:
            self._output_to_pf(LogLevel.ERROR, formatted)

    def critical(self, message: str, *args, pf_output: bool = True, **kwargs) -> None:
        """
        Log critical message.

        Critical messages go to both Python logging and PowerFactory by default.

        Args:
            message: Log message (may contain % formatting)
            pf_output: Whether to also output to PowerFactory
        """
        formatted = self._format_message(message % args if args else message)
        self._logger.critical(formatted, **kwargs)
        if pf_output:
            self._output_to_pf(LogLevel.CRITICAL, formatted)

    def exception(
            self,
            message: str,
            *args,
            exc_info: bool = True,
            pf_output: bool = True,
            **kwargs
    ) -> None:
        """
        Log exception with traceback.

        Use this in except blocks to capture full exception details.

        Args:
            message: Log message describing the error context
            exc_info: Whether to include exception traceback (default True)
            pf_output: Whether to also output to PowerFactory
        """
        formatted = self._format_message(message % args if args else message)
        self._logger.exception(formatted, exc_info=exc_info, **kwargs)
        if pf_output:
            self._output_to_pf(LogLevel.ERROR, formatted)

    def progress(
            self,
            current: int,
            total: int,
            item_name: str = "item",
            interval: int = 10
    ) -> None:
        """
        Log progress for batch operations.

        Only logs every `interval` items to avoid flooding output.

        Args:
            current: Current item index (0-based)
            total: Total number of items
            item_name: Name of items being processed
            interval: How often to log (every N items)

        Example:
            for i, device in enumerate(devices):
                logger.progress(i, len(devices), "device")
                process(device)
        """
        if current % interval == 0 or current == total - 1:
            self.info(
                f"Processing {item_name} {current + 1} of {total}",
                pf_output=True
            )


# =============================================================================
# Logger Factory
# =============================================================================

_loggers: Dict[str, DualLogger] = {}


def get_logger(name: str) -> DualLogger:
    """
    Get or create a DualLogger instance.

    This is the primary entry point for obtaining a logger.

    Args:
        name: Logger name, typically __name__ from calling module

    Returns:
        DualLogger instance for the given name

    Example:
        logger = get_logger(__name__)
        logger.info("Starting process")
    """
    if name not in _loggers:
        _loggers[name] = DualLogger(name)
    return _loggers[name]


# =============================================================================
# Context Manager
# =============================================================================

@contextmanager
def LogContext(
        app: Any = None,
        device_name: Optional[str] = None,
        substation: Optional[str] = None,
        operation: Optional[str] = None,
        **extra
):
    """
    Context manager for structured logging.

    Sets context information that will be automatically included
    in all log messages within the context.

    Args:
        app: PowerFactory application object
        device_name: Current device being processed
        substation: Current substation
        operation: Current operation name
        **extra: Additional context key-value pairs

    Example:
        with LogContext(app, device_name="RC-12345", operation="relay_settings"):
            logger.info("Starting update")  # Outputs: [RC-12345] (relay_settings) Starting update

    Contexts can be nested - inner contexts override outer values:
        with LogContext(app, substation="SUB_A"):
            with LogContext(device_name="RC-001"):
                logger.info("Processing")  # [SUB_A] [RC-001] Processing
    """
    global _current_context

    # Save previous context
    previous = _LogContextData(
        app=_current_context.app,
        device_name=_current_context.device_name,
        substation=_current_context.substation,
        operation=_current_context.operation,
        extra=_current_context.extra.copy()
    )

    # Update context (only override non-None values)
    if app is not None:
        _current_context.app = app
    if device_name is not None:
        _current_context.device_name = device_name
    if substation is not None:
        _current_context.substation = substation
    if operation is not None:
        _current_context.operation = operation
    _current_context.extra.update(extra)

    try:
        yield
    finally:
        # Restore previous context
        _current_context.app = previous.app
        _current_context.device_name = previous.device_name
        _current_context.substation = previous.substation
        _current_context.operation = previous.operation
        _current_context.extra = previous.extra


def set_app(app: Any) -> None:
    """
    Set the PowerFactory app globally for logging.

    Call this once at script startup to enable PowerFactory output
    for all loggers.

    Args:
        app: PowerFactory application object
    """
    _current_context.app = app


def clear_context() -> None:
    """
    Clear all logging context.

    Useful for cleanup between runs or tests.
    """
    global _current_context
    _current_context = _LogContextData()


# =============================================================================
# Performance Decorators
# =============================================================================

def log_performance(
        func: Optional[Callable] = None,
        *,
        operation_name: Optional[str] = None,
        log_args: bool = False,
        threshold_ms: float = 0
) -> Callable:
    """
    Decorator to log function execution time.

    Args:
        func: The function to wrap (when used without parentheses)
        operation_name: Custom name for the operation (default: function name)
        log_args: Whether to log function arguments
        threshold_ms: Only log if execution exceeds this threshold (milliseconds)

    Example:
        @log_performance
        def process_device(app, device):
            ...

        @log_performance(operation_name="Type Lookup", threshold_ms=100)
        def find_relay_type(app, name):
            ...
    """

    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            name = operation_name or fn.__name__
            logger = get_logger(fn.__module__)

            start_time = time.perf_counter()

            try:
                result = fn(*args, **kwargs)
                elapsed_ms = (time.perf_counter() - start_time) * 1000

                if elapsed_ms >= threshold_ms:
                    if log_args:
                        logger.debug(
                            f"{name} completed in {elapsed_ms:.1f}ms "
                            f"(args={args}, kwargs={kwargs})",
                            pf_output=False
                        )
                    else:
                        logger.debug(
                            f"{name} completed in {elapsed_ms:.1f}ms",
                            pf_output=False
                        )

                return result

            except Exception as e:
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                logger.error(
                    f"{name} failed after {elapsed_ms:.1f}ms: {e}",
                    pf_output=True
                )
                raise

        return wrapper

    # Handle both @log_performance and @log_performance() syntax
    if func is not None:
        return decorator(func)
    return decorator


def log_exceptions(
        func: Optional[Callable] = None,
        *,
        reraise: bool = True,
        default_return: Any = None,
        message: Optional[str] = None
) -> Callable:
    """
    Decorator for consistent exception logging.

    Args:
        func: The function to wrap
        reraise: Whether to re-raise the exception after logging
        default_return: Value to return if exception caught and not reraised
        message: Custom error message prefix

    Example:
        @log_exceptions
        def risky_operation():
            ...

        @log_exceptions(reraise=False, default_return=None)
        def optional_operation():
            ...
    """

    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            logger = get_logger(fn.__module__)
            error_msg = message or f"Error in {fn.__name__}"

            try:
                return fn(*args, **kwargs)
            except Exception as e:
                logger.exception(f"{error_msg}: {e}")
                if reraise:
                    raise
                return default_return

        return wrapper

    if func is not None:
        return decorator(func)
    return decorator


# =============================================================================
# Performance Timer Context Manager
# =============================================================================

@contextmanager
def timed_operation(name: str, threshold_ms: float = 0):
    """
    Context manager for timing code blocks.

    Args:
        name: Name of the operation being timed
        threshold_ms: Only log if execution exceeds this threshold

    Example:
        with timed_operation("Database Query"):
            results = fetch_settings(app, setting_ids)
    """
    logger = get_logger(__name__)
    start_time = time.perf_counter()

    try:
        yield
    finally:
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        if elapsed_ms >= threshold_ms:
            logger.debug(f"{name} completed in {elapsed_ms:.1f}ms", pf_output=False)


# =============================================================================
# Batch Processing Helper
# =============================================================================

class BatchProgress:
    """
    Helper class for tracking and logging batch operation progress.

    Provides:
    - Progress logging at configurable intervals
    - Elapsed time tracking
    - Estimated time remaining
    - Summary statistics

    Example:
        progress = BatchProgress(app, total=len(devices), item_name="device")
        for device in devices:
            with progress.item(device.name):
                process(device)
        progress.finish()
    """

    def __init__(
            self,
            app: Any,
            total: int,
            item_name: str = "item",
            log_interval: int = 10
    ):
        """
        Initialize batch progress tracker.

        Args:
            app: PowerFactory application object
            total: Total number of items to process
            item_name: Name of items for logging
            log_interval: How often to log progress
        """
        self.app = app
        self.total = total
        self.item_name = item_name
        self.log_interval = log_interval
        self.current = 0
        self.start_time = time.perf_counter()
        self.errors: List[str] = []
        self._logger = get_logger(__name__)

    @contextmanager
    def item(self, name: Optional[str] = None):
        """
        Context manager for processing a single item.

        Args:
            name: Optional name of the current item

        Yields:
            None - use for side effects only
        """
        # Log progress at intervals
        if self.current % self.log_interval == 0:
            elapsed = time.perf_counter() - self.start_time
            if self.current > 0:
                rate = self.current / elapsed
                remaining = (self.total - self.current) / rate
                self._logger.info(
                    f"Processing {self.item_name} {self.current + 1} of {self.total} "
                    f"(~{remaining:.0f}s remaining)",
                    pf_output=True
                )
            else:
                self._logger.info(
                    f"Processing {self.item_name} {self.current + 1} of {self.total}",
                    pf_output=True
                )

        # Set context for this item
        ctx_kwargs = {"operation": f"processing_{self.item_name}"}
        if name:
            ctx_kwargs["device_name"] = name

        try:
            with LogContext(**ctx_kwargs):
                yield
        except Exception as e:
            error_desc = f"{name or f'{self.item_name} {self.current}'}: {e}"
            self.errors.append(error_desc)
            self._logger.exception(f"Error processing {error_desc}")
        finally:
            self.current += 1

    def finish(self) -> Dict[str, Any]:
        """
        Complete batch processing and log summary.

        Returns:
            Dictionary with processing statistics
        """
        elapsed = time.perf_counter() - self.start_time
        success_count = self.current - len(self.errors)

        summary = {
            "total": self.total,
            "processed": self.current,
            "success": success_count,
            "errors": len(self.errors),
            "elapsed_seconds": elapsed,
            "rate_per_second": self.current / elapsed if elapsed > 0 else 0
        }

        self._logger.info(
            f"Batch complete: {success_count}/{self.current} {self.item_name}s "
            f"processed successfully in {elapsed:.1f}s",
            pf_output=True
        )

        if self.errors:
            self._logger.warning(
                f"{len(self.errors)} errors occurred during processing",
                pf_output=True
            )

        return summary


# =============================================================================
# Logging Configuration
# =============================================================================

def configure_logging(
        log_file: Optional[str] = None,
        level: int = logging.INFO,
        format_string: Optional[str] = None
) -> None:
    """
    Configure the Python logging system.

    Call this once at script startup to configure file logging.

    Args:
        log_file: Path to log file (None for console only)
        level: Logging level (default: INFO)
        format_string: Custom format string for log messages

    Example:
        configure_logging(
            log_file="C:/logs/ips_transfer.log",
            level=logging.DEBUG
        )
    """
    if format_string is None:
        format_string = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    handlers: List[logging.Handler] = []

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(logging.Formatter(format_string))
    handlers.append(console_handler)

    # File handler (if specified)
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(level)
        file_handler.setFormatter(logging.Formatter(format_string))
        handlers.append(file_handler)

    # Configure root logger
    logging.basicConfig(
        level=level,
        format=format_string,
        handlers=handlers,
        force=True  # Override any existing configuration
    )
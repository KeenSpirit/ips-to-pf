"""
Time formatting and measurement utilities.

This module provides utility functions for:
- Formatting durations in human-readable format
- Measuring execution time with context managers
- Time-related helper functions
"""

import time
import logging
from typing import Optional
from contextlib import contextmanager

logger = logging.getLogger(__name__)


def format_duration(seconds: float) -> str:
    """
    Format a duration in seconds to a human-readable string.

    Converts seconds to hours, minutes, and seconds with proper
    pluralization.

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted string like "2 hours 30 minutes 15 seconds"

    Examples:
        >>> format_duration(90)
        '1 minute 30 seconds'
        >>> format_duration(3661)
        '1 hour 1 minute 1 second'
        >>> format_duration(0.5)
        '0 seconds'
    """
    hours, remainder = divmod(int(seconds), 3600)
    minutes, secs = divmod(remainder, 60)

    time_parts = []

    if hours > 0:
        time_parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    if minutes > 0:
        time_parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
    if secs > 0 or not time_parts:
        time_parts.append(f"{secs} second{'s' if secs != 1 else ''}")

    return " ".join(time_parts)


def format_duration_short(seconds: float) -> str:
    """
    Format a duration in seconds to a short format (HH:MM:SS).

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted string like "02:30:15" or "30:15" if less than an hour

    Examples:
        >>> format_duration_short(90)
        '01:30'
        >>> format_duration_short(3661)
        '01:01:01'
    """
    hours, remainder = divmod(int(seconds), 3600)
    minutes, secs = divmod(remainder, 60)

    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes:02d}:{secs:02d}"


class Timer:
    """
    A simple timer class for measuring execution time.

    Can be used as a context manager or manually with start/stop.

    Examples:
        # As context manager
        >>> with Timer() as t:
        ...     do_something()
        >>> print(f"Took {t.elapsed:.2f} seconds")

        # Manual usage
        >>> timer = Timer()
        >>> timer.start()
        >>> do_something()
        >>> timer.stop()
        >>> print(timer.formatted)
    """

    def __init__(self, name: Optional[str] = None, auto_log: bool = False):
        """
        Initialize a timer.

        Args:
            name: Optional name for the timer (used in logging)
            auto_log: If True, log the elapsed time when stopped
        """
        self.name = name
        self.auto_log = auto_log
        self._start_time: Optional[float] = None
        self._stop_time: Optional[float] = None

    def start(self) -> 'Timer':
        """Start the timer."""
        self._start_time = time.time()
        self._stop_time = None
        return self

    def stop(self) -> 'Timer':
        """Stop the timer."""
        self._stop_time = time.time()

        if self.auto_log:
            name = self.name or "Timer"
            logger.info(f"{name}: {self.formatted}")

        return self

    @property
    def elapsed(self) -> float:
        """
        Get elapsed time in seconds.

        If timer is still running, returns time since start.
        If timer is stopped, returns time between start and stop.
        """
        if self._start_time is None:
            return 0.0

        end_time = self._stop_time or time.time()
        return end_time - self._start_time

    @property
    def formatted(self) -> str:
        """Get elapsed time as formatted string."""
        return format_duration(self.elapsed)

    @property
    def formatted_short(self) -> str:
        """Get elapsed time as short formatted string (HH:MM:SS)."""
        return format_duration_short(self.elapsed)

    def __enter__(self) -> 'Timer':
        """Start timer when entering context."""
        self.start()
        return self

    def __exit__(self, *args) -> None:
        """Stop timer when exiting context."""
        self.stop()

    def __str__(self) -> str:
        """String representation."""
        return self.formatted

    def __repr__(self) -> str:
        """Detailed representation."""
        state = "running" if self._stop_time is None else "stopped"
        return f"Timer(name={self.name!r}, state={state}, elapsed={self.elapsed:.3f}s)"


@contextmanager
def timed_operation(name: str, log_level: int = logging.INFO):
    """
    Context manager that logs the duration of an operation.

    Args:
        name: Name of the operation (for logging)
        log_level: Logging level to use

    Example:
        >>> with timed_operation("Database query"):
        ...     results = query_database()
        # Logs: "Database query completed in 1.5 seconds"
    """
    start = time.time()
    try:
        yield
    finally:
        elapsed = time.time() - start
        logger.log(log_level, f"{name} completed in {format_duration(elapsed)}")


def get_current_timestamp() -> str:
    """
    Get the current time as a formatted timestamp string.

    Returns:
        Timestamp in format "HH:MM:SS"
    """
    return time.strftime("%H:%M:%S")


def get_current_datetime() -> str:
    """
    Get the current date and time as a formatted string.

    Returns:
        DateTime in format "YYYY-MM-DD HH:MM:SS"
    """
    return time.strftime("%Y-%m-%d %H:%M:%S")

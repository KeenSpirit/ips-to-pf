"""
File and CSV handling utilities.

This module provides utility functions for file operations, including:
- CSV reading and writing with consistent interfaces
- Directory creation and path handling
- Citrix environment path adjustment

These utilities centralize file handling logic that was previously
scattered across multiple modules.
"""

import csv
import os
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Union

logger = logging.getLogger(__name__)


def read_csv_to_dict_list(
        filepath: str,
        encoding: str = "utf-8",
        skip_header: bool = True
) -> List[Dict[str, str]]:
    """
    Read a CSV file into a list of dictionaries.

    Each row becomes a dictionary with column headers as keys.

    Args:
        filepath: Path to the CSV file
        encoding: File encoding (default: utf-8)
        skip_header: Whether first row is headers (default: True)

    Returns:
        List of dictionaries, one per row

    Example:
        >>> data = read_csv_to_dict_list("mapping.csv")
        >>> for row in data:
        ...     print(row["column_name"])
    """
    result = []

    try:
        with open(filepath, "r", encoding=encoding, newline="") as f:
            if skip_header:
                reader = csv.DictReader(f)
            else:
                reader = csv.reader(f)

            for row in reader:
                result.append(dict(row) if skip_header else row)

    except FileNotFoundError:
        logger.error(f"CSV file not found: {filepath}")
        raise
    except Exception as e:
        logger.error(f"Error reading CSV file {filepath}: {e}")
        raise

    return result


def read_csv_raw(
        filepath: str,
        encoding: str = "utf-8"
) -> List[List[str]]:
    """
    Read a CSV file into a list of lists (raw format).

    Each row becomes a list of string values.

    Args:
        filepath: Path to the CSV file
        encoding: File encoding (default: utf-8)

    Returns:
        List of lists, one per row
    """
    result = []

    try:
        with open(filepath, "r", encoding=encoding, newline="") as f:
            reader = csv.reader(f, skipinitialspace=True)
            for row in reader:
                result.append(row)
    except FileNotFoundError:
        logger.error(f"CSV file not found: {filepath}")
        raise

    return result


def write_dict_list_to_csv(
        data: List[Dict[str, Any]],
        filepath: str,
        encoding: str = "utf-8",
        append: bool = False
) -> None:
    """
    Write a list of dictionaries to a CSV file.

    Column headers are determined from the union of all dictionary keys.

    Args:
        data: List of dictionaries to write
        filepath: Path to the output CSV file
        encoding: File encoding (default: utf-8)
        append: Whether to append to existing file (default: False)

    Example:
        >>> data = [{"name": "A", "value": 1}, {"name": "B", "value": 2}]
        >>> write_dict_list_to_csv(data, "output.csv")
    """
    if not data:
        logger.warning(f"No data to write to {filepath}")
        return

    # Collect all column headings from all rows
    col_headings = []
    for row_dict in data:
        for key in row_dict:
            if key not in col_headings:
                col_headings.append(key)

    mode = "a" if append else "w"

    try:
        with open(filepath, mode, newline="", encoding=encoding) as f:
            writer = csv.DictWriter(f, fieldnames=col_headings)

            # Only write header if not appending or file is empty
            if not append or os.path.getsize(filepath) == 0:
                writer.writeheader()

            for row in data:
                writer.writerow(row)

        logger.debug(f"Wrote {len(data)} rows to {filepath}")

    except Exception as e:
        logger.error(f"Error writing CSV file {filepath}: {e}")
        raise


def ensure_directory_exists(path: str) -> str:
    """
    Ensure a directory exists, creating it if necessary.

    Args:
        path: Directory path to check/create

    Returns:
        The path (unchanged)

    Raises:
        OSError: If the directory cannot be created
    """
    os.makedirs(path, exist_ok=True)
    return path


def get_citrix_adjusted_path(local_path: str) -> str:
    """
    Adjust a local path for Citrix environment if necessary.

    When running in Citrix, local C: drive paths need to be accessed
    through the \\Client\C$ path.

    Args:
        local_path: The local file path (e.g., "C:\\Users\\...")

    Returns:
        Adjusted path for Citrix, or original path if not in Citrix

    Example:
        >>> path = get_citrix_adjusted_path("C:\\LocalData\\output")
        >>> # In Citrix: "\\\\Client\\C$\\LocalData\\output"
        >>> # Not in Citrix: "C:\\LocalData\\output"
    """
    # Check if running in Citrix
    citrix = os.path.isdir("\\\\Client\\C$\\localdata")

    if citrix and "C:" in local_path:
        return "\\\\Client\\" + local_path.replace("C:", "C$")

    return local_path


def get_user_directory(subdir: Optional[str] = None) -> Path:
    """
    Get a path in the user's home directory, handling Citrix environment.

    Args:
        subdir: Optional subdirectory name to append

    Returns:
        Path object pointing to the user directory
    """
    user = Path.home().name

    # Try Citrix path first
    basepath = Path("//client/c$/Users") / user
    if basepath.exists():
        client_path = basepath
    else:
        client_path = Path("c:/Users") / user

    if subdir:
        client_path = client_path / subdir
        client_path.mkdir(exist_ok=True)

    return client_path


def safe_file_remove(filepath: str) -> bool:
    """
    Safely remove a file if it exists.

    Args:
        filepath: Path to the file to remove

    Returns:
        True if file was removed, False if it didn't exist
    """
    try:
        os.remove(filepath)
        return True
    except FileNotFoundError:
        return False
    except Exception as e:
        logger.error(f"Error removing file {filepath}: {e}")
        raise


def get_file_modification_time(filepath: str) -> Optional[float]:
    """
    Get the modification time of a file.

    Args:
        filepath: Path to the file

    Returns:
        Modification time as timestamp, or None if file doesn't exist
    """
    try:
        return os.stat(filepath).st_mtime
    except FileNotFoundError:
        return None


def is_file_recent(filepath: str, max_age_seconds: float = 86400) -> bool:
    """
    Check if a file was modified within the specified time period.

    Args:
        filepath: Path to the file
        max_age_seconds: Maximum age in seconds (default: 24 hours)

    Returns:
        True if file exists and was modified within the time period
    """
    import time

    mod_time = get_file_modification_time(filepath)
    if mod_time is None:
        return False

    current_time = time.time()
    return (current_time - mod_time) < max_age_seconds

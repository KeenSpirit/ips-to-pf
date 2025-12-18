"""
Utilities package for IPS to PowerFactory settings transfer.

This package contains shared utility functions and classes used throughout
the application. By centralizing utilities here, we:
- Avoid code duplication
- Provide consistent interfaces
- Make testing easier
- Improve maintainability

Modules:
    pf_utils: PowerFactory-specific utilities
    file_utils: File and CSV handling utilities
    time_utils: Time formatting and measurement utilities

Usage:
    from utils import pf_utils, file_utils, time_utils
    
    # PowerFactory utilities
    objects = pf_utils.all_relevant_objects(app, folders, "*.ElmRelay")
    
    # File utilities  
    data = file_utils.read_csv_to_dict_list("mapping.csv")
    
    # Time utilities
    formatted = time_utils.format_duration(seconds)
"""

from utils.pf_utils import (
    all_relevant_objects,
    get_all_protection_devices,
    get_all_switches,
    get_active_feeders,
    determine_region,
)

from utils.file_utils import (
    read_csv_to_dict_list,
    write_dict_list_to_csv,
    ensure_directory_exists,
    get_citrix_adjusted_path,
)

from utils.time_utils import (
    format_duration,
    Timer,
)

__all__ = [
    # PowerFactory utilities
    "all_relevant_objects",
    "get_all_protection_devices",
    "get_all_switches",
    "get_active_feeders",
    "determine_region",
    # File utilities
    "read_csv_to_dict_list",
    "write_dict_list_to_csv",
    "ensure_directory_exists",
    "get_citrix_adjusted_path",
    # Time utilities
    "format_duration",
    "Timer",
]

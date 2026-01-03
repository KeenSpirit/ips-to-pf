"""
Shared utility functions for setting processing.

This module contains utility functions used across relay and fuse settings
modules for common operations like:
- Setting key construction
- Binary conversion
- On/off state determination
- Setting value adjustments
- String-to-list conversion

Usage:
    from update_powerfactory.setting_utils import (
        build_setting_key,
        determine_on_off,
        convert_binary,
        setting_adjustment,
    )
"""

import ast
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# =============================================================================
# Key Construction
# =============================================================================

def build_setting_key(mapping_line: List) -> str:
    """
    Build a setting dictionary key from a mapping file line.

    The key combines folder, element, and attribute names from the first
    three columns of the mapping file line.

    Format: "{folder}{element}{attribute}"

    Args:
        mapping_line: Mapping file row [folder, element, attribute, ...]

    Returns:
        Combined key string for setting dictionary lookup

    Example:
        >>> line = ["Protection", "OC1", "Ipset", "use_setting"]
        >>> build_setting_key(line)
        'ProtectionOC1Ipset'
    """
    return "".join(mapping_line[:3])


# =============================================================================
# String/List Conversion
# =============================================================================

def convert_string_to_list(string: str) -> List[str]:
    """
    Convert a string representation of a list to an actual list.

    Used for parsing multiple disable conditions from mapping file entries
    that contain list-like strings.

    Args:
        string: String in format "[item1, item2, item3]"

    Returns:
        List of lowercase strings

    Example:
        >>> convert_string_to_list("[ON, Off, AUTO]")
        ['on', 'off', 'auto']
    """
    try:
        # Use ast.literal_eval for safe parsing of list literals
        parsed = ast.literal_eval(string)
        if isinstance(parsed, list):
            return [str(item).lower() for item in parsed]
    except (ValueError, SyntaxError):
        pass

    # Fallback: manual parsing for non-standard formats
    result = []
    element = ""

    for char in string:
        if char in ["[", " "]:
            continue
        elif char == ",":
            if element:
                result.append(element.lower())
            element = ""
        elif char == "]":
            if element:
                result.append(element.lower())
            break
        else:
            element += char

    return result if result else [string.lower().strip("[]")]


# =============================================================================
# Binary Conversion
# =============================================================================

def convert_binary(app, setting_value: Any, line: List) -> str:
    """
    Convert binary settings to the format required by PowerFactory.

    Extracts specific bits from a binary representation of the setting
    value based on bit positions defined in the mapping file.

    Args:
        app: PowerFactory application object
        setting_value: The binary setting value (integer or string)
        line: Mapping file line containing bit positions in line[-2]

    Returns:
        String of extracted bits (e.g., "101")

    Example:
        >>> # If setting_value is 5 (binary: 101) and line[-2] is "012"
        >>> # This extracts bits at positions 0, 1, 2 from right
        >>> convert_binary(app, 5, [..., "012", ...])
        '101'
    """
    try:
        binary_val = str(bin(int(setting_value))).replace("0b", "")
    except (ValueError, TypeError):
        return "0"

    # Get bit positions from mapping file (negative indices from right)
    bits_of_int = [-int(num) for num in str(line[-2])]

    # Pad binary value with leading zeros
    binary_val = "0000000000000" + binary_val

    new_setting_value = ""
    for bit_of_int in bits_of_int:
        try:
            new_setting_value += binary_val[bit_of_int]
        except IndexError:
            new_setting_value += "0"

    return new_setting_value


# =============================================================================
# On/Off Determination
# =============================================================================

def determine_on_off(app, setting_value: Any, disable_cond: Any) -> int:
    """
    Determine the on/off state based on setting value and disable condition.

    This function handles multiple formats of disable conditions:
    - String conditions: "ON", "OFF", etc.
    - Integer bit positions: Check specific bit in binary representation
    - List conditions: "[on, off, auto]"

    Args:
        app: PowerFactory application object
        setting_value: The setting value to evaluate
        disable_cond: The condition that indicates disabled state

    Returns:
        0 for disabled/off, 1 for enabled/on
    """
    # Handle empty/None setting values
    if not setting_value:
        if str(disable_cond).upper() == "ON":
            return 0
        elif str(disable_cond).upper() == "OFF":
            return 1
        return 1

    # Try to handle integer disable condition (bit checking)
    if _is_integer(disable_cond):
        return _check_bit_condition(setting_value, int(disable_cond))

    # Handle list-based disable conditions
    disable_list = _parse_disable_condition(disable_cond)

    if str(setting_value).lower() in disable_list:
        return 1

    return 0


def _is_integer(value: Any) -> bool:
    """Check if a value can be converted to an integer."""
    try:
        int(value)
        return True
    except (ValueError, TypeError):
        return False


def _parse_disable_condition(disable_cond: Any) -> List[str]:
    """
    Parse a disable condition into a list of lowercase strings.

    Args:
        disable_cond: The disable condition (string or list-like string)

    Returns:
        List of lowercase condition strings
    """
    cond_str = str(disable_cond)

    if "[" in cond_str and "]" in cond_str:
        return convert_string_to_list(cond_str)

    return [cond_str.lower()]


def _check_bit_condition(setting_value: Any, bit_position: int) -> int:
    """
    Check a specific bit position in the setting value.

    Args:
        setting_value: The setting value to check
        bit_position: The bit position to examine

    Returns:
        0 if bit is set (disabled), 1 if bit is clear (enabled)
    """
    normalized = _normalize_binary_string(str(setting_value))

    # Check for valid binary string (all 0s and 1s)
    for char in normalized:
        if char not in ["0", "1"]:
            return 1  # Default to enabled for non-binary values

    try:
        if normalized[bit_position] == "1":
            return 0  # Bit set = disabled
        return 1  # Bit clear = enabled
    except IndexError:
        return 1  # Default to enabled if bit position out of range


def _normalize_binary_string(setting_str: str) -> str:
    """
    Normalize a setting value to a binary-like string.

    Handles exponential notation (e.g., "1.1e5") and decimal points.

    Args:
        setting_str: The setting value as a string

    Returns:
        Normalized string suitable for bit checking
    """
    result = ""
    expected_len = len(setting_str)

    # Handle exponential notation
    if "e" in setting_str:
        try:
            expected_len = int(setting_str[-1]) + 1
        except (ValueError, IndexError):
            pass

    for char in setting_str:
        if char == "e":
            break
        if char == ".":
            continue
        result += char

    # Pad to expected length
    while len(result) < expected_len:
        result += "0"

    return result


# =============================================================================
# Setting Adjustment
# =============================================================================

def setting_adjustment(
    app,
    line: List,
    setting_dictionary: Dict[str, Any],
    device_object: Any
) -> Optional[float]:
    """
    Adjust a setting value based on CT ratios or mathematical operations.

    The adjustment type is determined by the last column of the mapping file:
    - "primary": Divide by CT primary
    - "secondary": Divide by CT secondary
    - "ctr": Apply CT ratio (setting * secondary / primary)
    - "perc_pu": Convert percentage to per-unit using CT secondary
    - Mathematical operation: Apply +, -, *, / with value from mapping file

    Args:
        app: PowerFactory application object
        line: Mapping file line containing adjustment parameters
        setting_dictionary: Dictionary of all settings
        device_object: The ProtectionDevice (for CT ratios)

    Returns:
        Adjusted setting value, or None if adjustment failed
    """
    key = build_setting_key(line)

    try:
        setting = float(setting_dictionary[key])
    except (KeyError, ValueError, TypeError):
        # Try to handle as on/off value
        try:
            setting_value = determine_on_off(app, setting_dictionary[key], line[6])
            return setting_value
        except (KeyError, IndexError, ValueError, TypeError):
            setting = 0

    adjustment_type = line[-1]

    if adjustment_type == "primary":
        primary = device_object.ct_primary
        if primary == 0:
            return None
        return setting / primary

    elif adjustment_type == "ctr":
        primary = device_object.ct_primary
        secondary = device_object.ct_secondary
        if primary == 0:
            return None
        return setting * secondary / primary

    elif adjustment_type == "secondary":
        secondary = device_object.ct_secondary
        if secondary == 0:
            return None
        return setting / secondary

    elif adjustment_type == "perc_pu":
        secondary = device_object.ct_secondary
        return (setting / 100) * secondary

    else:
        # Mathematical operation
        return _apply_math_operation(setting, line)


def _apply_math_operation(
    setting: float,
    line: List
) -> Optional[float]:
    """
    Apply a mathematical operation to a setting value.

    The operation and operand are read from the mapping file line.

    Args:
        setting: The base setting value
        line: Mapping file line with operator at [6] and value at [7]

    Returns:
        Result of the operation, or the original setting if operation fails
    """
    try:
        math_sym = line[6]
        manipulator_value = float(line[7])
    except (IndexError, ValueError, TypeError):
        return setting

    if math_sym == "+":
        return setting + manipulator_value
    elif math_sym == "-":
        return setting - manipulator_value
    elif math_sym == "/":
        if manipulator_value == 0:
            return 0
        return setting / manipulator_value
    elif math_sym == "*":
        return setting * manipulator_value
    else:
        return setting


# =============================================================================
# Name Extraction Utilities
# =============================================================================

def extract_base_name(full_name: str, delimiter: str = "_") -> str:
    """
    Extract the base name from a full device name.

    Splits on the delimiter and returns the first part.

    Args:
        full_name: The full device name
        delimiter: Character to split on (default: "_")

    Returns:
        The base name (part before first delimiter)

    Example:
        >>> extract_base_name("RC001_CT")
        'RC001'
    """
    result = ""
    for char in full_name:
        if char == delimiter:
            break
        result += char
    return result
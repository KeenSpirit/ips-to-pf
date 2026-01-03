"""
Dip switch logic element configuration for relays.

This module handles the configuration of RelLogdip elements in PowerFactory
relays. Dip switch elements control relay functionality through binary
switch configurations.

Dip switches are configured by matching IPS setting values to specific
switch positions in the relay's logic element. The resulting configuration
is a binary string (e.g., "10110") where each position represents a
switch state.

This module was extracted from relay_settings.py to:
- Isolate dip switch logic from general relay settings
- Fix mutation issues in the original implementation
- Improve maintainability and testability

Usage:
    from update_powerfactory.relay_logic_elements import update_logic_elements

    update_logic_elements(
        app, pf_device, mapping_file, setting_dict, find_element
    )
"""

import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

from update_powerfactory.setting_utils import build_setting_key

logger = logging.getLogger(__name__)


# Type alias for the find_element function signature
FindElementFunc = Callable[[Any, Any, List], Optional[Any]]


def update_logic_elements(
    app,
    pf_device: Any,
    mapping_file: List[List],
    setting_dict: Dict[str, Any],
    find_element_func: FindElementFunc
) -> None:
    """
    Update logic elements with dip switch configurations.

    Some relays require logic elements with dip switches configured
    to control the functionality of elements in a relay. This function
    processes all dip switch elements found in the mapping file.

    Args:
        app: PowerFactory application object
        pf_device: The PowerFactory relay object
        mapping_file: List of mapping file rows
        setting_dict: Dictionary of all settings
        find_element_func: Function to find PF elements (dependency injection
            to avoid circular imports)
    """
    dip_elements = _get_dip_element_names(mapping_file)

    if not dip_elements:
        return

    for element_name in dip_elements:
        _process_dip_element(
            app, pf_device, element_name, mapping_file,
            setting_dict, find_element_func
        )


def _get_dip_element_names(mapping_file: List[List]) -> List[str]:
    """
    Extract unique element names that have dip switch configurations.

    Scans the mapping file for entries containing "_dip" in the element
    name and returns unique names in order of first appearance.

    Args:
        mapping_file: List of mapping file rows

    Returns:
        List of unique element names containing "_dip"
    """
    # Use dict.fromkeys to preserve order while deduplicating (Python 3.7+)
    dip_elements = dict.fromkeys(
        line[1] for line in mapping_file if "_dip" in line[1]
    )
    return list(dip_elements.keys())


def _process_dip_element(
    app,
    pf_device: Any,
    element_name: str,
    mapping_file: List[List],
    setting_dict: Dict[str, Any],
    find_element_func: FindElementFunc
) -> None:
    """
    Process a single dip switch element.

    Finds the PowerFactory element, collects relevant mapping lines,
    and applies the calculated dip switch settings.

    Args:
        app: PowerFactory application object
        pf_device: The PowerFactory relay object
        element_name: Name of the dip element (e.g., "SomeElement_dip")
        mapping_file: List of mapping file rows
        setting_dict: Dictionary of all settings
        find_element_func: Function to find PF elements
    """
    # Find the PowerFactory element and collect relevant mapping lines
    pf_element, element_mapping = _find_dip_element_and_mappings(
        app, pf_device, element_name, mapping_file, find_element_func
    )

    if not pf_element:
        app.PrintError(f"Element - {element_name} could not be found")
        return

    # Get and validate existing dip switch configuration
    existing_dip_set = pf_element.GetAttribute("e:aDipset")

    if len(existing_dip_set) != len(element_mapping):
        # Mismatch between mapping and actual element
        logger.warning(
            "Dip switch count mismatch for %s: mapping has %d entries, "
            "element has %d switches",
            element_name, len(element_mapping), len(existing_dip_set)
        )
        return

    # Calculate and apply new dip switch settings
    new_dip_set = _calculate_dip_settings(
        pf_element, element_mapping, setting_dict, existing_dip_set
    )

    pf_element.SetAttribute("e:aDipset", new_dip_set)


def _find_dip_element_and_mappings(
    app,
    pf_device: Any,
    element_name: str,
    mapping_file: List[List],
    find_element_func: FindElementFunc
) -> Tuple[Optional[Any], List[List]]:
    """
    Find the PowerFactory dip element and collect its mapping lines.

    Searches for the RelLogdip element corresponding to the element name
    and gathers all mapping file lines that apply to it.

    IMPORTANT: This function creates copies of mapping lines when searching
    to avoid mutating the original mapping file data.

    Args:
        app: PowerFactory application object
        pf_device: The PowerFactory relay object
        element_name: Name of the dip element
        mapping_file: List of mapping file rows
        find_element_func: Function to find PF elements

    Returns:
        Tuple of (PowerFactory element or None, list of mapping lines)
    """
    element_mapping = []
    pf_element = None

    for line in mapping_file:
        if element_name not in line[1]:
            continue

        element_mapping.append(line)

        # Only search for the PF element once
        if pf_element is None:
            pf_element = _find_pf_dip_element(
                app, pf_device, line, find_element_func
            )

    return pf_element, element_mapping


def _find_pf_dip_element(
    app,
    pf_device: Any,
    line: List,
    find_element_func: FindElementFunc
) -> Optional[Any]:
    """
    Find the PowerFactory RelLogdip element for a mapping line.

    Creates a modified COPY of the line to search without the "_dip" suffix,
    avoiding mutation of the original mapping file data.

    Args:
        app: PowerFactory application object
        pf_device: The PowerFactory relay object
        line: Mapping file line with "_dip" in element name
        find_element_func: Function to find PF elements

    Returns:
        The RelLogdip element, or None if not found or wrong type
    """
    # CRITICAL: Create a shallow copy to avoid mutating the original line
    search_line = line.copy()
    search_line[1] = line[1].replace("_dip", "")

    pf_element = find_element_func(app, pf_device, search_line)

    # Validate it's the correct element type
    if pf_element and pf_element.GetClassName() == "RelLogdip":
        return pf_element

    return None


def _calculate_dip_settings(
    pf_element: Any,
    element_mapping: List[List],
    setting_dict: Dict[str, Any],
    existing_dip_set: str
) -> str:
    """
    Calculate the new dip switch settings based on IPS values.

    Processes each mapping line to determine the appropriate dip switch
    state (0 or 1) and builds the complete dip switch string.

    Args:
        pf_element: The PowerFactory RelLogdip element
        element_mapping: List of mapping lines for this element
        setting_dict: Dictionary of all settings
        existing_dip_set: Current dip switch string (e.g., "10110")

    Returns:
        New dip switch string with updated values
    """
    # Start with all switches OFF
    dip_set = list(existing_dip_set.replace("1", "0"))

    # Get the dip switch names from the element type
    dip_names = _get_dip_names(pf_element)

    for line in element_mapping:
        dip_set_name = line[2]
        key = build_setting_key(line)

        # Get setting value, default to 0
        setting = setting_dict.get(key, 0)

        # Find the index of this dip switch
        dip_index = _find_dip_index(dip_names, dip_set_name)

        if dip_index is not None:
            logic_value = _determine_dip_logic_value(setting, line)
            dip_set[dip_index] = logic_value

    return "".join(dip_set)


def _get_dip_names(pf_element: Any) -> List[str]:
    """
    Get the list of dip switch names from the element type.

    Args:
        pf_element: The PowerFactory RelLogdip element

    Returns:
        List of dip switch names
    """
    try:
        dip_input = pf_element.GetAttribute("r:typ_id:e:sInput")
        if dip_input and len(dip_input) > 0:
            return dip_input[0].split(",")
    except (AttributeError, TypeError, IndexError):
        pass

    return []


def _find_dip_index(dip_names: List[str], target_name: str) -> Optional[int]:
    """
    Find the index of a dip switch by name.

    Args:
        dip_names: List of dip switch names from the element type
        target_name: Name of the dip switch to find

    Returns:
        Index of the dip switch, or None if not found
    """
    for i, name in enumerate(dip_names):
        if name == target_name:
            return i
    return None


def _determine_dip_logic_value(setting: Any, line: List) -> str:
    """
    Determine the logic value (0 or 1) for a dip switch.

    The logic for determining switch state:
    1. If setting is integer 1, switch is ON
    2. If setting is integer 0, switch is OFF
    3. If mapping line pattern matches setting string, switch is ON
    4. If "32" appears in setting string (special case), switch is ON
    5. Otherwise, switch is OFF

    Args:
        setting: The IPS setting value
        line: The mapping file line (last element may contain match pattern)

    Returns:
        "1" for ON, "0" for OFF
    """
    # Try to convert to integer for direct comparison
    try:
        setting_int = int(setting)
        if setting_int == 1:
            return "1"
        elif setting_int == 0:
            return "0"
    except (ValueError, TypeError):
        pass

    # Check if line's pattern matches the setting
    setting_str = str(setting)
    pattern = str(line[-1]) if line else ""

    if pattern and pattern in setting_str:
        return "1"

    # Special case: check for "32" in setting
    # (This appears to be a legacy convention for certain relay types)
    if "32" in setting_str:
        return "1"

    return "0"
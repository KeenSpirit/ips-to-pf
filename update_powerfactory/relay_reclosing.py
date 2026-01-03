"""
Reclosing logic configuration for relay devices.

This module handles the configuration of reclosing elements in PowerFactory
relays. Reclosing elements control automatic reclosure sequences after
fault trips.

The reclosing logic is configured through a logic table that specifies
the behavior for each trip number (1st trip, 2nd trip, etc.) and
protection element (OC1+, OC2+, etc.).

Logic table values:
- 0.0: No action (disabled)
- 1.0: Reclose (continue reclosing sequence)
- 2.0: Lockout (stop reclosing sequence)

This module was extracted from relay_settings.py to:
- Isolate complex reclosing logic
- Improve maintainability
- Enable independent testing

Usage:
    from update_powerfactory.relay_reclosing import update_reclosing_logic

    update_reclosing_logic(app, device_object, mapping_file, setting_dict)
"""

import logging
from typing import Any, Dict, List, Optional

from update_powerfactory.setting_utils import build_setting_key, setting_adjustment
from config.relay_patterns import NOJA_RECLOSERS

logger = logging.getLogger(__name__)


def update_reclosing_logic(
    app,
    device_object: Any,
    mapping_file: List[List],
    setting_dictionary: Dict[str, Any]
) -> None:
    """
    Update reclosing element logic based on trip settings.

    The reclosing element has a logic table that controls outputs to
    protection elements depending on the trip number. This function
    updates each row with either Reclosing, Lockout, or Disable.

    Args:
        app: PowerFactory application object
        device_object: The ProtectionDevice being configured
        mapping_file: List of mapping file rows
        setting_dictionary: Dictionary of all settings
    """
    pf_device = device_object.pf_obj
    device_type = device_object.device

    # Handle NOJA reclosers separately (different configuration approach)
    if _is_noja_recloser(device_type):
        _configure_noja_reclosing(
            app, pf_device, mapping_file, setting_dictionary
        )
        return

    # Standard reclosing logic configuration
    element = _find_reclosing_element(app, pf_device, mapping_file)
    if not element:
        return

    op_to_lockout = element.GetAttribute("e:oplockout")
    trip_setting = get_trip_num(app, mapping_file, setting_dictionary)

    row_dict = _build_logic_rows(
        app,
        mapping_file,
        setting_dictionary,
        device_object,
        op_to_lockout,
        trip_setting
    )

    _apply_logic_to_element(element, row_dict)


def _is_noja_recloser(device_type: str) -> bool:
    """
    Check if the device is a NOJA recloser.

    NOJA reclosers use a simplified reclosing configuration.

    Args:
        device_type: The device type string

    Returns:
        True if the device is a NOJA recloser
    """
    return any(noja in device_type for noja in NOJA_RECLOSERS)


def _configure_noja_reclosing(
    app,
    pf_device: Any,
    mapping_file: List[List],
    setting_dictionary: Dict[str, Any]
) -> None:
    """
    Configure reclosing for NOJA reclosers.

    NOJA reclosers don't have a specific "number of trips to lockout" setting.
    If a NOJA recloser isn't properly configured, the reclosing logic will
    be left blank, which may cause PowerFactory to crash during fault analysis.

    Args:
        app: PowerFactory application object
        pf_device: The PowerFactory relay object
        mapping_file: List of mapping file rows
        setting_dictionary: Dictionary of all settings
    """
    trip_setting = get_trip_num(app, mapping_file, setting_dictionary)

    element = _find_element_by_name(app, pf_device, "Reclosing Element")
    if element:
        element.SetAttribute("e:oplockout", trip_setting)


def _find_reclosing_element(
    app,
    pf_device: Any,
    mapping_file: List[List]
) -> Optional[Any]:
    """
    Find the reclosing element (RelRecl) from the mapping file.

    Searches the mapping file for entries with "_logic" suffix to
    identify the reclosing element configuration.

    Args:
        app: PowerFactory application object
        pf_device: The PowerFactory relay object
        mapping_file: List of mapping file rows

    Returns:
        The RelRecl element, or None if not found
    """
    for mapped_set in mapping_file:
        if "_logic" not in mapped_set[1]:
            continue

        # Create a search line without the "_logic" suffix
        search_line = mapped_set.copy()
        search_line[1] = mapped_set[1].replace("_logic", "")

        element = _find_element_in_relay(app, pf_device, search_line)

        if element and element.GetClassName() == "RelRecl":
            return element

    return None


def _find_element_in_relay(
    app,
    pf_device: Any,
    line: List
) -> Optional[Any]:
    """
    Find a PowerFactory element within a relay.

    This is a simplified version of find_element from relay_settings.py
    used specifically for reclosing element lookup.

    Args:
        app: PowerFactory application object
        pf_device: The PowerFactory relay object
        line: Mapping line with [folder, element_name, ...]

    Returns:
        The PowerFactory element, or None if not found
    """
    obj_contents = pf_device.GetContents(line[1], True)

    if not obj_contents:
        return None

    for obj in obj_contents:
        if obj.fold_id.loc_name == line[0]:
            return obj

    return None


def _find_element_by_name(
    app,
    pf_device: Any,
    element_name: str
) -> Optional[Any]:
    """
    Find an element by name within a relay.

    Args:
        app: PowerFactory application object
        pf_device: The PowerFactory relay object
        element_name: Name of the element to find

    Returns:
        The element, or None if not found
    """
    line = [pf_device.loc_name, element_name]
    return _find_element_in_relay(app, pf_device, line)


def _build_logic_rows(
    app,
    mapping_file: List[List],
    setting_dictionary: Dict[str, Any],
    device_object: Any,
    op_to_lockout: int,
    trip_setting: int
) -> Dict[str, List[float]]:
    """
    Build the logic row dictionary from the mapping file.

    Each row in the logic table defines behavior for a specific
    protection element (e.g., OC1+, OC2+) across all trip numbers.

    Args:
        app: PowerFactory application object
        mapping_file: List of mapping file rows
        setting_dictionary: Dictionary of all settings
        device_object: The ProtectionDevice being configured
        op_to_lockout: Number of operations to lockout
        trip_setting: Trip-to-lockout setting value

    Returns:
        Dictionary mapping row names to lists of logic values
    """
    row_dict = {}

    for mapped_set in mapping_file:
        if "_logic" not in mapped_set[1]:
            continue

        row_name = mapped_set[2]

        # Parse trip number from mapping
        try:
            trip_num = int(mapped_set[-3])
        except ValueError:
            trip_num = mapped_set[-3]

        on_off_key = mapped_set[-2]
        recl = mapped_set[-1]
        key = build_setting_key(mapped_set)

        # Get setting value
        setting = setting_dictionary.get(key, mapped_set[-2])

        # Try to apply setting adjustment
        try:
            if mapped_set[6] != "None":
                setting = setting_adjustment(
                    app, mapped_set, setting_dictionary, device_object
                )
        except (IndexError, KeyError, ValueError, TypeError):
            if mapped_set[3] == "ON":
                trip_num = "ALL"
                setting = trip_setting
            else:
                setting = "off"
                recl = "N"
                trip_num = "ALL"
                on_off_key = "off"

        # Build the logic string for this row
        logic_str = _build_single_row_logic(
            setting, trip_num, on_off_key, recl, op_to_lockout
        )

        row_dict[row_name] = logic_str

    return row_dict


def _build_single_row_logic(
    setting: Any,
    trip_num: Any,
    on_off_key: str,
    recl: str,
    op_to_lockout: int
) -> List[float]:
    """
    Build the logic values for a single row.

    Args:
        setting: The setting value
        trip_num: Trip number (int) or "ALL"
        on_off_key: Key indicating on/off state
        recl: "N" for no reclosing, otherwise allows reclosing
        op_to_lockout: Number of operations to lockout

    Returns:
        List of logic values [trip1, trip2, ..., tripN]
    """
    logic_str = []

    # Check if element allows reclosing
    if recl == "N":
        # No reclosing - determine if disabled or lockout
        if str(setting).lower() == on_off_key.lower():
            set_log = 0.0  # Disabled
        else:
            set_log = 2.0  # Lockout

        for i in range(op_to_lockout):
            if trip_num == "ALL":
                logic_str.append(set_log)
            elif i + 1 == trip_num:
                logic_str.append(set_log)
            else:
                logic_str.append(0.0)

        return logic_str

    # Check if it applies to all trips
    if trip_num == "ALL":
        if setting == "None":
            setting = 1

        for i in range(op_to_lockout):
            if i + 1 < op_to_lockout and i + 1 < float(setting):
                logic_str.append(1.0)  # Reclose
            elif i + 1 == op_to_lockout or i + 1 == float(setting):
                logic_str.append(2.0)  # Lockout
            elif i + 1 > float(setting):
                logic_str.append(0.0)  # Disabled

        return logic_str

    # Row is associated with a specific trip
    for i in range(op_to_lockout):
        if i + 1 != trip_num:
            logic_str.append(0.0)  # Disabled
        elif i + 1 == trip_num and trip_num < op_to_lockout:
            logic_str.append(1.0)  # Reclose
        elif i + 1 == trip_num and trip_num == op_to_lockout:
            logic_str.append(2.0)  # Lockout

    return logic_str


def _apply_logic_to_element(
    element: Any,
    row_dict: Dict[str, List[float]]
) -> None:
    """
    Apply the logic row dictionary to the reclosing element.

    Updates the element's ilogic attribute with the calculated values.

    Args:
        element: The RelRecl element
        row_dict: Dictionary mapping row names to logic values
    """
    if not element:
        return

    block_ids = element.GetAttribute("r:typ_id:e:blockid")

    # Replace row names with their logic values
    for row_name, logic_values in row_dict.items():
        block_ids = [
            logic_values if x == row_name else x
            for x in block_ids
        ]

    element.SetAttribute("e:ilogic", block_ids)

    # If reclosing is not active, set to single operation lockout
    if element.GetAttribute("e:reclnotactive"):
        element.SetAttribute("e:oplockout", 1)


def get_trip_num(
    app,
    mapping_file: List[List],
    setting_dictionary: Dict[str, Any]
) -> int:
    """
    Get the number of trips to lockout setting.

    Counts the number of active trip-to-lockout settings in the mapping.

    Args:
        app: PowerFactory application object
        mapping_file: List of mapping file rows
        setting_dictionary: Dictionary of all settings

    Returns:
        Number of trips to lockout (default: 1)
    """
    trips_to_lockout = 1

    for mapped_set in mapping_file:
        if "_TripstoLockout" not in mapped_set[1]:
            continue

        reclosing_key = mapped_set[-1]
        key = build_setting_key(mapped_set)
        setting = setting_dictionary.get(key)

        if setting == reclosing_key:
            trips_to_lockout += 1

    return trips_to_lockout
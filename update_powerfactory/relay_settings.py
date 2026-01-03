"""
Relay settings configuration for PowerFactory.

This module is the main entry point for configuring relay devices in
PowerFactory using settings from the IPS database. It orchestrates:
- Device function determination (SWER/switch/sectionaliser)
- Mapping file lookup
- Relay type validation and update
- Phase determination for single-phase relays
- Setting application
- CT/VT updates

Sub-modules handle specialized functionality:
- relay_reclosing: Reclosing logic configuration
- relay_logic_elements: Dip switch configuration
- setting_utils: Shared utility functions

Performance optimizations:
- Uses RelayTypeIndex for O(1) relay type lookups
- Mapping file results are cached in mapping_file.py

Usage:
    from update_powerfactory import relay_settings as rs

    result, updates = rs.relay_settings(app, device_object, relay_index, updates)
"""

import logging
from typing import Dict, List, Tuple, Optional, Any, Union

from update_powerfactory import mapping_file as mf
from update_powerfactory import ct_settings as cs
from update_powerfactory import vt_settings as vs
from update_powerfactory.type_index import RelayTypeIndex
from update_powerfactory.setting_utils import (
    build_setting_key,
    determine_on_off,
    convert_binary,
    setting_adjustment,
)
from update_powerfactory.relay_reclosing import update_reclosing_logic
from update_powerfactory.relay_logic_elements import update_logic_elements
from core import UpdateResult
from config.relay_patterns import SINGLE_PHASE_RELAYS, MULTI_PHASE_RELAYS

logger = logging.getLogger(__name__)


# =============================================================================
# Phase Determination Constants
# =============================================================================

# Phase mapping based on name suffix patterns
PHASE_SUFFIX_MAP: Dict[str, int] = {
    "_A": 0, "A-A": 0, "-A": 0, "-R": 0,  # Phase A
    "_B": 1, "B-B": 1, "-B": 1, "-W": 1,  # Phase B
    "C-C": 2, "-C": 2, "_C": 2,           # Phase C
}

# Patterns indicating earth fault relays
EARTH_FAULT_PATTERNS: Tuple[str, ...] = (
    "N-E", "N", "EF-E", "E-E", "DEF", "-EF"
)


# =============================================================================
# Main Entry Point
# =============================================================================

def relay_settings(
    app,
    device_object: Any,
    relay_index: Union[RelayTypeIndex, List],
    updates: bool
) -> Tuple[UpdateResult, bool]:
    """
    Configure a relay device with settings from IPS.

    This is the main entry point for relay configuration. It handles:
    1. Device function determination (SWER/switch/sectionaliser)
    2. Mapping file lookup
    3. Relay type validation and update
    4. Phase determination for single-phase relays
    5. Setting application
    6. Reclosing logic configuration
    7. CT/VT updates

    Args:
        app: PowerFactory application object
        device_object: The ProtectionDevice to configure
        relay_index: RelayTypeIndex for O(1) lookups, or list for backward
            compatibility
        updates: Current updates flag

    Returns:
        Tuple of (UpdateResult, updated updates flag)
    """
    # Classify device as SWER/switch/sectionaliser if applicable
    update_device_function(device_object)

    # Create result object from device
    result = UpdateResult.from_device(device_object)
    result.relay_pattern = device_object.device
    result.used_pattern = device_object.device

    # Load mapping file for this relay pattern
    mapping_file, mapping_type = mf.read_mapping_file(
        app, device_object.device, device_object.pf_obj
    )

    # Validate and update relay type if needed
    result = check_relay_type(
        app, device_object, mapping_type, relay_index, result
    )

    # Configure phase for single-phase relays
    phase = determine_phase(app, device_object)
    if phase is not None:
        meas_obj = device_object.pf_obj.GetContents("*.RelMeasure")[0]
        meas_obj.SetAttribute("e:iphase", phase)

    # Build setting dictionary and apply settings
    if mapping_file:
        setting_dict = create_setting_dictionary(
            app, device_object.settings, mapping_file, device_object.pf_obj
        )
        result.date_setting = device_object.date
        device_object.pf_obj.SetAttribute("e:sernum", str(device_object.date))
    else:
        result.result = "Mapping file not found"
        device_object.pf_obj.SetAttribute("outserv", 1)
        return result, updates

    # Apply settings from mapping file
    updates = apply_settings(app, device_object, mapping_file, setting_dict, updates)

    # Delegate specialized configuration to sub-modules
    update_reclosing_logic(app, device_object, mapping_file, setting_dict)
    update_logic_elements(
        app, device_object.pf_obj, mapping_file, setting_dict, find_element
    )

    # Update CT and VT settings
    result = cs.update_ct(app, device_object, result)
    result = vs.update_vt(app, device_object, result)

    return result, updates


# =============================================================================
# Device Classification
# =============================================================================

def update_device_function(device_object: Any) -> None:
    """
    Determine whether the device is SWER, switch, or sectionaliser.

    Updates the device.device attribute with appropriate prefix:
    - "swer_" for single/two phase devices
    - "switch_" for devices without protection settings
    - "sect_" for sectionaliser devices

    Args:
        device_object: The ProtectionDevice to classify
    """
    # Determine whether the device is a SWER device
    try:
        num_of_phases = device_object.pf_obj.GetAttribute("r:fold_id:e:nphase")
    except AttributeError:
        num_of_phases = 3

    if num_of_phases < 3:
        device_object.device = f"swer_{device_object.device}"

    # Determine whether the device is a switch or sectionaliser
    if not device_object.settings and device_object.device not in ["SOLKOR-RF_Energex"]:
        # No protection settings typically means it's a switch
        device_object.device = f"switch_{device_object.device}"
    else:
        # Check if the device is a sectionaliser
        for setting in device_object.settings:
            if setting[1] in ["Sectionaliser"]:
                if setting[2].lower() in ["on", "auto"]:
                    device_object.device = f"sect_{device_object.device}"
                break
            if setting[1] in ["Detection"]:
                if setting[2].lower() == "on":
                    device_object.device = f"switch_{device_object.device}"


# =============================================================================
# Relay Type Management
# =============================================================================

def check_relay_type(
    app,
    device_object: Any,
    mapping_type: Optional[str],
    relay_index: Union[RelayTypeIndex, List],
    result: UpdateResult
) -> UpdateResult:
    """
    Check that the relay type is correct and update if necessary.

    If the relay type doesn't match the mapping type, attempts to find
    and assign the correct type. If the type cannot be found, places
    the relay out of service.

    Args:
        app: PowerFactory application object
        device_object: The ProtectionDevice being configured
        mapping_type: Expected relay type from mapping file
        relay_index: RelayTypeIndex for O(1) lookups, or list
        result: UpdateResult to update

    Returns:
        Updated UpdateResult
    """
    if not mapping_type:
        return result

    pf_device = device_object.pf_obj

    try:
        current_type = pf_device.typ_id.loc_name
    except AttributeError:
        current_type = None

    if current_type == mapping_type:
        return result

    # Need to update the relay type
    new_type = _find_relay_type(relay_index, mapping_type)

    if new_type:
        pf_device.typ_id = new_type
        result.used_pattern = mapping_type
    else:
        # Cannot find the required type - put device out of service
        app.PrintWarn(
            f"Relay type '{mapping_type}' not found for {device_object.name}"
        )
        pf_device.SetAttribute("outserv", 1)
        result.result = f"Type not found: {mapping_type}"

    return result


def _find_relay_type(
    relay_index: Union[RelayTypeIndex, List],
    type_name: str
) -> Optional[Any]:
    """
    Find a relay type by name using indexed or linear lookup.

    Args:
        relay_index: RelayTypeIndex for O(1) lookups, or list for O(n)
        type_name: Name of the relay type to find

    Returns:
        The PowerFactory TypRelay object, or None if not found
    """
    # Use indexed lookup if available (O(1))
    if isinstance(relay_index, RelayTypeIndex):
        return relay_index.get(type_name)

    # Fall back to linear search (O(n))
    for relay_type in relay_index:
        if relay_type.loc_name == type_name:
            return relay_type

    return None


# =============================================================================
# Phase Determination
# =============================================================================

def determine_phase(app, device_object: Any) -> Optional[int]:
    """
    Determine the correct phase for single-phase relays.

    Single pole and phase specific relays need to be mapped correctly.
    This function analyzes the device name to determine the correct phase.

    Args:
        app: PowerFactory application object
        device_object: The ProtectionDevice to analyze

    Returns:
        Phase index (0=A, 1=B, 2=C), or None if not a single-phase relay
    """
    # Two phase relays have a unique type - don't assign phase
    if device_object.device in MULTI_PHASE_RELAYS:
        return None

    if device_object.device not in SINGLE_PHASE_RELAYS:
        return None

    try:
        name = device_object.seq_name
    except AttributeError:
        name = device_object.name

    # Check for phase suffix in last 6 characters of name
    name_suffix = name[-6:]

    for suffix, phase in PHASE_SUFFIX_MAP.items():
        if suffix in name_suffix:
            return phase

    # Check if it is an Earth Fault relay
    for pattern in EARTH_FAULT_PATTERNS:
        if pattern in name_suffix:
            device_object.device = f"{device_object.device}_Earth"
            return None

    # Check for trailing "E" indicating earth fault
    if name and name[-1] == "E":
        device_object.device = f"{device_object.device}_Earth"
        return None

    # Default to Phase A if no match found
    return 0


# =============================================================================
# Setting Dictionary Creation
# =============================================================================

def create_setting_dictionary(
    app,
    settings: List[List],
    mapping_file: List[List],
    pf_device: Any
) -> Dict[str, Any]:
    """
    Create a dictionary mapping PF attribute keys to IPS setting values.

    The key format is: "{folder}{element}{attribute}"

    This function processes the IPS settings through the mapping file
    to create a lookup dictionary for applying settings to PF elements.

    Args:
        app: PowerFactory application object
        settings: List of IPS setting rows
        mapping_file: List of mapping file rows
        pf_device: The PowerFactory device object

    Returns:
        Dictionary mapping attribute keys to setting values
    """
    setting_dictionary = {}

    for setting in settings:
        lines = mapping_file
        for i, value in enumerate(setting):
            prob_lines = []
            for line in lines:
                if line[3] in ["None", "ON", "On", "OFF", "Off"]:
                    # This setting is not required as part of this relay
                    if len(line) < 5:
                        continue

                # Determine the index of the associated setting reference
                # from the line in the mapping file
                index = i + 3  # Adjusted to start at Column D in mapping file

                if line[index] == "use_setting":
                    key = build_setting_key(line)
                    # Apply unit conversions
                    if setting[-1] in ["mA", "ms"]:
                        setting[i] = float(setting[i]) / 1000
                    elif setting[-1] in ["kA"]:
                        setting[i] = float(setting[i]) * 1000
                    setting_dictionary[key] = setting[i]
                    continue
                elif (
                    str(line[index]) != str(value)
                    and "0{}".format(line[index]) != value
                ):
                    # Setting address might drop leading zero
                    continue
                else:
                    # Multiple lines may have similar values until full key determined
                    prob_lines.append(line)

            if not prob_lines:
                break
            lines = prob_lines

    return setting_dictionary


# =============================================================================
# Setting Application
# =============================================================================

def apply_settings(
    app,
    device_object: Any,
    mapping_file: List[List],
    setting_dict: Dict[str, Any],
    updates: bool
) -> bool:
    """
    Apply settings from the mapping file to the relay.

    Iterates through the mapping file and applies each setting
    to the appropriate PowerFactory element.

    Args:
        app: PowerFactory application object
        device_object: The ProtectionDevice being configured
        mapping_file: List of mapping file rows
        setting_dict: Dictionary of setting values
        updates: Current updates flag

    Returns:
        Updated updates flag
    """
    pf_device = device_object.pf_obj

    for mapped_set in mapping_file:
        # Skip logic elements (handled by sub-modules)
        if (
            "_logic" in mapped_set[1]
            or "_dip" in mapped_set[1]
            or "_Trips" in mapped_set[1]
        ):
            continue

        # Get the PowerFactory object for the setting
        element = find_element(app, pf_device, mapped_set)
        if not element:
            app.PrintError(f"Unable to find an element for {mapped_set}")
            continue

        key = build_setting_key(mapped_set)
        try:
            setting = setting_dict[key]
        except KeyError:
            # Handle outserv attributes
            if mapped_set[2] == "outserv":
                setting = None
            else:
                continue

        attribute = f"e:{mapped_set[2]}"
        updates = set_attribute(
            app,
            mapped_set,
            setting,
            element,
            attribute,
            device_object,
            setting_dict,
            updates,
        )

    return updates


def find_element(app, pf_object: Any, line: List) -> Optional[Any]:
    """
    Find the PowerFactory element for a setting.

    The line contains the folder name and element name that identify
    where the setting should be applied.

    Args:
        app: PowerFactory application object
        pf_object: The parent PowerFactory object to search
        line: Mapping file line [folder, element, attribute, ...]

    Returns:
        The PowerFactory element object, or None if not found
    """
    obj_contents = pf_object.GetContents(line[1], True)

    if not obj_contents:
        # GetContents may not work due to object naming
        # Fall back to manual search
        obj_contents = pf_object.GetContents()
        if not obj_contents:
            return None

        for obj in obj_contents:
            if obj.fold_id.loc_name == line[0] and obj.loc_name == line[1]:
                return obj

        # Recursive search
        for obj in obj_contents:
            found = find_element(app, obj, line)
            if found:
                return found

        return None
    else:
        for obj in obj_contents:
            if obj.fold_id.loc_name == line[0]:
                return obj
        return None


def set_attribute(
    app,
    line: List,
    setting_value: Any,
    element: Any,
    attribute: str,
    device_object: Any,
    setting_dictionary: Dict[str, Any],
    updates: bool
) -> bool:
    """
    Set a single attribute on a PowerFactory element.

    Handles special cases for curves, out-of-service flags, and
    various data type conversions.

    Args:
        app: PowerFactory application object
        line: Mapping file line
        setting_value: The value to set
        element: The PowerFactory element
        attribute: The attribute name (e.g., "e:Ipset")
        device_object: The ProtectionDevice
        setting_dictionary: Dictionary of all settings
        updates: Current updates flag

    Returns:
        Updated updates flag
    """
    if line[2] == "pcharac":
        # Curve setting requires a PF object
        if line[-1] == "binary":
            setting_value = convert_binary(app, setting_value, line)
        setting_value = mf.get_pf_curve(app, setting_value, element)
        existing_setting = element.GetAttribute(attribute)
        if setting_value != existing_setting:
            element.SetAttribute(attribute, setting_value)
        return True

    elif line[2] == "outserv":
        # Out of service setting requires special handling
        if line[-1] == "binary":
            setting_value = convert_binary(app, setting_value, line)
            if setting_value == "1":
                setting_value = "OFF"
                line[-1] = "OFF"
            else:
                setting_value = "ON"
                line[-1] = "NF"
        setting_value = determine_on_off(app, setting_value, line[-1])
        element.SetAttribute(attribute, setting_value)
        return updates

    if line[6] == "None":
        # Setting can be directly applied without adjustment
        existing_setting = element.GetAttribute(attribute)
        try:
            if setting_value != existing_setting:
                element.SetAttribute(attribute, setting_value)
                return True
        except TypeError:
            # Try numeric conversions
            try:
                setting_value = float(setting_value)
                if setting_value != round(existing_setting, 3):
                    element.SetAttribute(attribute, setting_value)
                    return True
            except (ValueError, TypeError):
                try:
                    setting_value = int(setting_value)
                    if setting_value != existing_setting:
                        element.SetAttribute(attribute, setting_value)
                        return True
                except ValueError:
                    # Set to maximum as last resort
                    element.SetAttribute(attribute, 9999)
                    return updates
    else:
        # Setting needs adjustment based on mapping file
        setting_value = setting_adjustment(app, line, setting_dictionary, device_object)
        if not setting_value:
            return updates
        existing_setting = element.GetAttribute(attribute)
        try:
            if setting_value != existing_setting:
                element.SetAttribute(attribute, setting_value)
                return True
        except TypeError:
            setting_value = int(setting_value)
            if setting_value != existing_setting:
                element.SetAttribute(attribute, setting_value)
                return True

    return updates
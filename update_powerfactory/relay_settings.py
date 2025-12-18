"""
Relay settings configuration for PowerFactory.

This module handles the configuration of relay devices in PowerFactory
using settings from the IPS database. It includes:
- Relay type validation and update
- Setting dictionary creation from IPS data
- Application of settings to relay elements
- Reclosing logic configuration
- Phase-specific relay handling

Performance optimizations:
- Uses RelayTypeIndex for O(1) relay type lookups
- Mapping file results could be cached (future enhancement)
"""

import logging
from typing import Dict, List, Tuple, Optional, Any, Union

from update_powerfactory import mapping_file as mf
from update_powerfactory import ct_settings as cs
from update_powerfactory import vt_settings as vs
from update_powerfactory.type_index import RelayTypeIndex
from core import UpdateResult

# Import from config package
from config.relay_patterns import SINGLE_PHASE_RELAYS, MULTI_PHASE_RELAYS

logger = logging.getLogger(__name__)


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
        relay_index: RelayTypeIndex for O(1) lookups, or list for backward compatibility
        updates: Current updates flag

    Returns:
        Tuple of (UpdateResult, updated updates flag)
    """
    # If the device is a SWER/switch/sectionaliser, update the device attribute
    update_device_function(device_object)

    # Create result object from device
    result = UpdateResult.from_device(device_object)
    # Update pattern after classification (may have been modified by update_device_function)
    result.relay_pattern = device_object.device
    result.used_pattern = device_object.device

    mapping_file, mapping_type = mf.read_mapping_file(
        app, device_object.device, device_object.pf_obj
    )

    result = check_relay_type(
        app, device_object, mapping_type, relay_index, result
    )

    # Manage single pole and phase specific relays
    phase = determine_phase(app, device_object)
    if phase is not None:
        meas_obj = device_object.pf_obj.GetContents("*.RelMeasure")[0]
        meas_obj.SetAttribute("e:iphase", phase)

    # Obtain the relay setting dictionary
    if mapping_file:
        setting_dict = create_setting_dictionary(
            app, device_object.settings, mapping_file, device_object.pf_obj
        )
        # Set the relay with the information about which setting from IPS was used
        result.date_setting = device_object.date
        device_object.pf_obj.SetAttribute("e:sernum", str(device_object.date))
    else:
        result.result = "Not mapped"
        device_object.pf_obj.SetAttribute("outserv", 1)
        return result, updates

    updates = apply_settings(app, device_object, mapping_file, setting_dict, updates)
    update_reclosing_logic(app, device_object, mapping_file, setting_dict)
    update_logic_elements(app, device_object.pf_obj, mapping_file, setting_dict)

    # Update CT and VT settings
    result = cs.update_ct(app, device_object, result)
    result = vs.update_vt(app, device_object, result)

    return result, updates


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
        device_object: The ProtectionDevice to check
        mapping_type: The expected relay type name from mapping file
        relay_index: RelayTypeIndex for O(1) lookups, or list for compatibility
        result: UpdateResult to update with status

    Returns:
        Updated UpdateResult
    """
    try:
        # Check if user has set the type, or if relay was previously configured
        exist_relay_type = device_object.pf_obj.GetAttribute("r:typ_id:e:loc_name")
        # Check if existing type has been deleted (in recycle bin)
        type_is_deleted = device_object.pf_obj.typ_id.IsDeleted()
    except AttributeError:
        exist_relay_type = "None"
        type_is_deleted = 0

    if exist_relay_type != mapping_type or type_is_deleted == 1:
        updated = update_relay_type(
            app, device_object.pf_obj, mapping_type, relay_index
        )
        if not updated:
            result.result = "Unable to find the appropriate type"
            device_object.pf_obj.SetAttribute("e:outserv", 1)
            return result
        else:
            # Found a type and turn the relay in service
            device_object.pf_obj.SetAttribute("e:outserv", 0)
    else:
        device_object.pf_obj.SetAttribute("e:outserv", 0)

    return result


def update_relay_type(
    app,
    pf_device: Any,
    mapping_type: Optional[str],
    relay_index: Union[RelayTypeIndex, List]
) -> bool:
    """
    Update the relay type if it doesn't match the mapping type.
    
    Uses O(1) indexed lookup if relay_index is a RelayTypeIndex,
    otherwise falls back to O(n) linear search for backward compatibility.
    
    Args:
        app: PowerFactory application object
        pf_device: The PowerFactory relay object
        mapping_type: The target relay type name
        relay_index: RelayTypeIndex for O(1) lookups, or list for compatibility
        
    Returns:
        True if type was found and updated, False otherwise
    """
    if not mapping_type:
        return False
    
    # Use indexed lookup if available (O(1))
    if isinstance(relay_index, RelayTypeIndex):
        relay_type = relay_index.get(mapping_type)
    else:
        # Fall back to linear search for backward compatibility (O(n))
        relay_type = None
        for rt in relay_index:
            if rt.loc_name == mapping_type:
                relay_type = rt
                break
    
    if not relay_type:
        logger.warning(f"Relay type not found: {mapping_type}")
        return False
    
    pf_device.SetAttribute("e:typ_id", relay_type)
    pf_device.SlotUpdate()
    return True


def determine_phase(app, device_object: Any) -> Optional[int]:
    """
    Determine the phase for single-phase and phase-specific relays.
    
    Single pole and phase specific relays need to be mapped correctly.
    This function analyzes the device name to determine the correct phase.
    
    Args:
        app: PowerFactory application object
        device_object: The ProtectionDevice to analyze
        
    Returns:
        Phase index (0=A, 1=B, 2=C), or None if not a single-phase relay
    """
    # Two phase relays have a unique type
    if device_object.device in MULTI_PHASE_RELAYS:
        return None
    
    if device_object.device not in SINGLE_PHASE_RELAYS:
        return None
    
    try:
        name = device_object.seq_name
    except AttributeError:
        name = device_object.name
    
    # Phase mapping based on name suffix patterns
    phase_dict = {
        "_A": 0, "A-A": 0, "-A": 0, "-R": 0,
        "_B": 1, "B-B": 1, "-B": 1, "-W": 1,
        "C-C": 2, "-C": 2, "_C": 2,
    }
    
    for string, phase in phase_dict.items():
        if string in name[-6:]:
            return phase
    
    # Check if it is an EF (Earth Fault) Relay
    ef_patterns = ["N-E", "N", "EF-E", "E-E", "DEF", "-EF"]
    for string in ef_patterns:
        if string in name[-6:]:
            device_object.device = f"{device_object.device}_Earth"
            return None
    
    if name[-1] == "E":
        device_object.device = f"{device_object.device}_Earth"
        return None
    
    # Default to A Phase if no match found
    return 0


def create_setting_dictionary(
    app,
    settings: List[List],
    mapping_file: List[List],
    pf_device: Any
) -> Dict[str, Any]:
    """
    Create a dictionary mapping PF attribute keys to IPS setting values.
    
    The key format is: f"{folder}{element}{attribute}"
    
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
                    key = str().join(line[:3])
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
        # Skip logic elements (handled separately)
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
        
        key = str().join(mapped_set[:3])
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


def convert_binary(app, setting_value: Any, line: List) -> str:
    """
    Convert binary settings to the format required by PowerFactory.
    
    Args:
        app: PowerFactory application object
        setting_value: The binary setting value
        line: Mapping file line containing bit positions
        
    Returns:
        Converted binary string
    """
    binary_val = str(bin(int(setting_value))).replace("0b", "")
    bits_of_int = [-int(num) for num in line[-2]]
    binary_val = "0000000000000" + binary_val
    
    new_setting_value = str()
    for bit_of_int in bits_of_int:
        new_setting_value += binary_val[bit_of_int]
    
    return new_setting_value


def setting_adjustment(
    app,
    line: List,
    setting_dictionary: Dict[str, Any],
    device_object: Any
) -> Optional[float]:
    """
    Adjust a setting value based on CT ratios or mathematical operations.
    
    Args:
        app: PowerFactory application object
        line: Mapping file line
        setting_dictionary: Dictionary of all settings
        device_object: The ProtectionDevice (for CT ratios)
        
    Returns:
        Adjusted setting value, or None if adjustment failed
    """
    key = str().join(line[:3])
    try:
        setting = float(setting_dictionary[key])
    except (KeyError, ValueError, TypeError):
        try:
            setting_value = determine_on_off(app, setting_dictionary[key], line[6])
            return setting_value
        except (KeyError, IndexError, ValueError, TypeError):
            setting = 0
    
    adjustment_type = line[-1]
    
    if adjustment_type == "primary":
        primary = device_object.ct_primary
        setting_value = setting / primary
    elif adjustment_type == "ctr":
        primary = device_object.ct_primary
        secondary = device_object.ct_secondary
        setting_value = setting * secondary / primary
    elif adjustment_type == "secondary":
        secondary = device_object.ct_secondary
        setting_value = setting / secondary
    elif adjustment_type == "perc_pu":
        secondary = device_object.ct_secondary
        setting_value = (setting / 100) * secondary
    else:
        # Mathematical operation
        math_sym = line[6]
        manipulator_value = float(line[7])
        
        if math_sym == "+":
            setting_value = setting + manipulator_value
        elif math_sym == "-":
            setting_value = setting - manipulator_value
        elif math_sym == "/":
            try:
                setting_value = setting / manipulator_value
            except ZeroDivisionError:
                setting_value = 0
        elif math_sym == "*":
            setting_value = setting * manipulator_value
        else:
            setting_value = setting
    
    return setting_value


def determine_on_off(
    app,
    setting_value: Any,
    disable_cond: Any
) -> int:
    """
    Determine the on/off state based on setting value and disable condition.
    
    Args:
        app: PowerFactory application object
        setting_value: The setting value to evaluate
        disable_cond: The condition that indicates disabled state
        
    Returns:
        0 for disabled/off, 1 for enabled/on
    """
    try:
        disable_cond = int(disable_cond)
    except (ValueError, TypeError):
        # Disable condition should be in list format
        disable_list = []
        if "[" in str(disable_cond) and "]" in str(disable_cond):
            disable_list = convert_string_to_list(disable_cond)
        else:
            disable_list.append(str(disable_cond).lower())
    
    if not setting_value and disable_cond == "ON":
        return 0
    elif not setting_value and disable_cond == "OFF":
        return 1
    elif not setting_value:
        return 1
    elif isinstance(disable_cond, int):
        setting_value = str(setting_value)
        new_setting_value = str()
        
        if "e" in setting_value:
            # Handle exponential values
            setting_len = int(setting_value[-1]) + 1
        else:
            setting_len = len(setting_value)
        
        for char in setting_value:
            if char == "e":
                break
            if char == ".":
                continue
            new_setting_value = new_setting_value + char
        
        while len(new_setting_value) < setting_len:
            new_setting_value = new_setting_value + "0"
        
        # Check if all characters are binary
        for char in new_setting_value:
            if char not in ["0", "1"]:
                break
        else:
            try:
                bit_condition = new_setting_value[disable_cond]
            except IndexError:
                bit_condition = "0"
            if bit_condition == "1":
                return 0
            else:
                return 1
    elif str(setting_value).lower() in disable_list:
        return 1
    else:
        return 0


def convert_string_to_list(string: str) -> List[str]:
    """
    Convert a string representation of a list to an actual list.
    
    Used for parsing multiple off conditions from mapping file.
    
    Args:
        string: String in format "[item1, item2, item3]"
        
    Returns:
        List of lowercase strings
    """
    new_list = []
    element = str()
    
    for char in string:
        if char in ["[", " "]:
            continue
        elif char == ",":
            new_list.append(element)
            element = str()
            continue
        elif char == "]":
            new_list.append(element)
            break
        element += char.lower()
    
    return new_list


def update_reclosing_logic(
    app,
    device_object: Any,
    mapping_file: List[List],
    setting_dictionary: Dict[str, Any]
) -> None:
    """
    Update reclosing element logic based on trip settings.
    
    The reclosing element has logic that controls the output to elements
    depending on the trip number. This function updates each row with
    either Reclosing, Lockout, or Disable.
    
    Args:
        app: PowerFactory application object
        device_object: The ProtectionDevice
        mapping_file: List of mapping file rows
        setting_dictionary: Dictionary of all settings
    """
    pf_device = device_object.pf_obj
    device_type = device_object.device
    
    # RC01 do not have a specific number of trips to lockout setting
    setting = None
    trip_setting = None
    
    if "RC01" in device_type:
        trip_setting = get_trip_num(app, mapping_file, setting_dictionary)
        element = find_element(
            app, pf_device, [pf_device.loc_name, "Reclosing Element"]
        )
        if element:
            element.SetAttribute("e:oplockout", trip_setting)
    
    row_dict = {}
    element = None
    
    for mapped_set in mapping_file:
        if "_logic" not in mapped_set[1]:
            continue
        
        if not element:
            mapped_set[1] = mapped_set[1].replace("_logic", "")
            element = find_element(app, pf_device, mapped_set)
            mapped_set[1] = mapped_set[1] + "_logic"
            
            if not element or element.GetClassName() != "RelRecl":
                element = None
                continue
            
            op_to_lockout = element.GetAttribute("e:oplockout")
        
        if element.loc_name not in mapped_set[1]:
            continue
        
        row_name = mapped_set[2]
        
        try:
            trip_num = int(mapped_set[-3])
        except ValueError:
            trip_num = mapped_set[-3]
        
        on_off_key = mapped_set[-2]
        recl = mapped_set[-1]
        key = str().join(mapped_set[:3])
        
        try:
            setting = setting_dictionary[key]
        except KeyError:
            setting = mapped_set[-2]
        
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
        
        logic_str = []
        
        # Check if element allows reclosing
        if recl == "N":
            if str(setting).lower() == on_off_key.lower():
                set_log = 0.0
            else:
                set_log = 2.0
            
            for i in range(0, op_to_lockout):
                if trip_num == "ALL":
                    logic_str.append(set_log)
                elif i + 1 == trip_num:
                    logic_str.append(set_log)
                else:
                    logic_str.append(0.0)
            
            row_dict[row_name] = logic_str
            continue
        
        # Check if it's not an individual trip
        if trip_num == "ALL":
            if setting == "None":
                setting = 1
            
            for i in range(0, op_to_lockout):
                if i + 1 < op_to_lockout and i + 1 < float(setting):
                    logic_str.append(1.0)
                elif i + 1 == op_to_lockout or i + 1 == float(setting):
                    logic_str.append(2.0)
                elif i + 1 > float(setting):
                    logic_str.append(0.0)
            
            row_dict[row_name] = logic_str
            continue
        
        # Row is associated with a specific trip
        for i in range(0, op_to_lockout):
            if i + 1 != trip_num:
                logic_str.append(0.0)
            elif i + 1 == trip_num and trip_num < op_to_lockout:
                logic_str.append(1.0)
            elif i + 1 == trip_num and trip_num == op_to_lockout:
                logic_str.append(2.0)
        
        row_dict[row_name] = logic_str
    
    if not element:
        return
    
    block_ids = element.GetAttribute("r:typ_id:e:blockid")
    for row in row_dict:
        block_ids = [row_dict[row] if x == row else x for x in block_ids]
    
    element.SetAttribute("e:ilogic", block_ids)
    
    if element.GetAttribute("e:reclnotactive"):
        element.SetAttribute("e:oplockout", 1)


def get_trip_num(
    app,
    mapping_file: List[List],
    setting_dictionary: Dict[str, Any]
) -> int:
    """
    Get the number of trips to lockout setting.
    
    Args:
        app: PowerFactory application object
        mapping_file: List of mapping file rows
        setting_dictionary: Dictionary of all settings
        
    Returns:
        Number of trips to lockout
    """
    trips_to_lockout = 1
    
    for mapped_set in mapping_file:
        if "_TripstoLockout" not in mapped_set[1]:
            continue
        
        reclosing_key = mapped_set[-1]
        key = str().join(mapped_set[:3])
        setting = setting_dictionary.get(key)
        
        if setting == reclosing_key:
            trips_to_lockout += 1
    
    return trips_to_lockout


def update_logic_elements(
    app,
    pf_device: Any,
    mapping_file: List[List],
    setting_dict: Dict[str, Any]
) -> None:
    """
    Update logic elements with dip switch configurations.
    
    Some relays require logic elements with dip switches configured
    to control the functionality of elements in a relay.
    
    Args:
        app: PowerFactory application object
        pf_device: The PowerFactory relay object
        mapping_file: List of mapping file rows
        setting_dict: Dictionary of all settings
    """
    # Build list of all element names containing logic
    element_list = []
    for line in mapping_file:
        if "_dip" in line[1]:
            element_name = line[1]
            if element_name not in element_list:
                element_list.append(element_name)
    
    if not element_list:
        return
    
    for element in element_list:
        element_mapping = []
        pf_element = None
        
        # Get PF object and mapping lines for this element
        for line in mapping_file:
            if element not in line[1]:
                continue
            
            element_mapping.append(line)
            
            if not pf_element:
                line[1] = line[1].replace("_dip", "")
                pf_element = find_element(app, pf_device, line)
                line[1] = line[1] + "_dip"
                
                if not pf_element or pf_element.GetClassName() != "RelLogdip":
                    pf_element = None
                    continue
        
        if not pf_element:
            app.PrintError(f"Element - {element} could not be found")
            continue
        
        # Reset dip switches to all OFF
        existing_dip_set = pf_element.GetAttribute("e:aDipset")
        
        if len(existing_dip_set) != len(element_mapping):
            # Mismatch between mapping and actual element
            continue
        
        existing_dip_set = existing_dip_set.replace("1", "0")
        dip_names = pf_element.GetAttribute("r:typ_id:e:sInput")[0].split(",")
        
        for line in element_mapping:
            dip_set_name = line[2]
            key = str().join(line[:3])
            
            try:
                setting = setting_dict[key]
            except KeyError:
                setting = 0
            
            dip_name_index = [
                i for i, dip_set in enumerate(dip_names) if dip_set_name == dip_set
            ]
            
            try:
                setting = int(setting)
            except ValueError:
                pass
            
            if setting == 1:
                logic_value = "1"
            elif setting == 0:
                logic_value = "0"
            elif line[-1] in str(setting):
                logic_value = "1"
            elif "32" in str(setting):
                logic_value = "1"
            else:
                logic_value = "0"
            
            if dip_name_index:
                new_dip_set = list(existing_dip_set)
                new_dip_set[dip_name_index[0]] = logic_value
                existing_dip_set = "".join(new_dip_set)
        
        pf_element.SetAttribute("e:aDipset", existing_dip_set)

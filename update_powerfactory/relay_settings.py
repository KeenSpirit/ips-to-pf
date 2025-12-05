from update_powerfactory import mapping_file as mf
from update_powerfactory import ct_settings as cs
from update_powerfactory import vt_settings as vs

from importlib import reload
reload(cs)

# Define the IPS name of all single phase and 2 phase relays so that they can be placed on the correct phase
SINGLE_PHASE_RELAYS = [
    "I>+ I>> 1Ph I in % + T in TMS_Energex",
    "I> 1Ph I in A + I>> in xIs + T in %_Energex",
    "I> 2Ph I in A + T in TMS_Energex",
    "MCGG22",
    "MCGG21",
    "RXIDF",
    "I> 1Ph I in A + I>> in xIs + T in %_Energex",
]
MULTI_PHASE_RELAYS = [
    "I> 2Ph +IE>1Ph I in A + T in TMS_Energex",
    "I>+ I>> 2Ph +IE>+IE>> I in A + T in TMS_Energex",
    "CDG61",
]


def relay_settings(app, device_object, relay_types, updates):
    """This function can either use the settings from IPS."""

    # If the device is a SWER/switch/sectionaliser, update the device attribute accordingly
    update_device_function(device_object)

    update_info = {}
    update_info["SUBSTATION"] = device_object.pf_obj.GetAttribute("r:cpGrid:e:loc_name")
    update_info["PLANT_NUMBER"] = device_object.pf_obj.loc_name
    update_info["RELAY_PATTERN"] = device_object.device
    update_info["USED_PATTERN"] = device_object.device

    mapping_file, mapping_type = mf.read_mapping_file(
        app, device_object.device, device_object.pf_obj
    )

    update_info = check_relay_type(app, device_object, mapping_type, relay_types, update_info)

    # Manage single pole and phase specific relays.
    phase = determine_phase(app, device_object)
    if phase:
        meas_obj = device_object.pf_obj.GetContents("*.RelMeasure")[0]
        meas_obj.SetAttribute("e:iphase", phase)

    # Obtain the relay setting dictionary
    if mapping_file:
        setting_dict = create_setting_dictionary(
            app, device_object.settings, mapping_file, device_object.pf_obj
        )
        # Set the relay with the information about which setting from IPS was used
        update_info["DATE_SETTING"] = device_object.date
        device_object.pf_obj.SetAttribute("e:sernum", str(device_object.date))
    else:
        update_info["RESULT"] = "Not mapped"
        device_object.pf_obj.SetAttribute("outserv", 1)
        return [update_info, updates]

    updates = apply_settings(app, device_object, mapping_file, setting_dict, updates)
    update_reclosing_logic(app, device_object, mapping_file, setting_dict)
    update_logic_elements(app, device_object.pf_obj, mapping_file, setting_dict)
    update_info = cs.update_ct(app, device_object, update_info)
    update_info = vs.update_vt(app, device_object, update_info)

    return update_info, updates


def update_device_function(device_object):
    """
    Determine whether the device is SWER, or a switch, or a sectionaliser.
    If so, update the device attribute accordingly.
    """

    # Detemine whether the device is a SWER device
    try:
        num_of_phases = device_object.pf_obj.GetAttribute("r:fold_id:e:nphase")
    except AttributeError:
        num_of_phases = 3
    if num_of_phases < 3:
        device_object.device = f"swer_{device_object.device}"

    # Determine whether the device is a switch or if it is a sectionaliser.
    if not device_object.settings and device_object.device not in ["SOLKOR-RF_Energex"]:
        # This indicates that there is no protection settings. This typically
        # means that the device is a switch
        device_object.device = f"switch_{device_object.device}"
    else:
        # Determine if the device is a sectionaliser
        for setting in device_object.settings:
            if setting[1] in ["Sectionaliser"]:
                if setting[2].lower() in ["on", "auto"]:
                    device_object.device = f"sect_{device_object.device}"
                break
            if setting[1] in ["Detection"]:
                if setting[2].lower() == "on":
                    device_object.device = f"switch_{device_object.device}"


def determine_phase(app, device_object):
    """Single pole and phase specific relays need to be mapped correctly to
    the correct type. Keys can exist in different locations, this function
    is configured to map the keys and determine the correct relay type."""

    # If the relay is a two phase relay then these will have a unique type.
    if device_object.device in MULTI_PHASE_RELAYS:
        return None
    if device_object.device not in SINGLE_PHASE_RELAYS:
        return None
    try:
        name = device_object.seq_name
    except AttributeError:
        name = device_object.name
    # Check to see if it is an A-Phase Relay
    phase_dict = {
        "_A": 0,
        "A-A": 0,
        "-A": 0,
        "-R": 0,
        "_B": 1,
        "B-B": 1,
        "-B": 1,
        "-W": 1,
        "C-C": 2,
        "-C": 2,
        "_C": 2,
    }
    for string in phase_dict:
        if string in name[-6:]:
            return phase_dict[string]
    # Check to see if it is an EF Relay
    for string in ["N-E", "N", "EF-E", "E-E", "DEF", "-EF"]:
        if string in name[-6:]:
            device_object.device = f"{device_object.device}_Earth"
            return None
    if name[-1] == "E":
        device_object.device = f"{device_object.device}_Earth"
        return None
    # If all else fails set it as A Phase
    return 0


def create_setting_dictionary(app, settings, mapping_file, pf_device):
    """The settings will have an associated key that maps a setting value to
    an attribute in PF. This function will take the settings and create a
    dictionary"""
    setting_dictionary = {}
    for setting in settings:
        lines = mapping_file
        for i, value in enumerate(setting):
            prob_lines = []
            for line in lines:
                if line[3] in ["None", "ON", "On", "OFF", "Off"]:
                    # This setting is not required as part of this relay.
                    if len(line) < 5:
                        continue
                # Determine the index of the associated setting reference from the
                # line in the mapping file.
                index = i + 3  # This allows the index to be adjusted to start at
                # Column D in the mapping file.
                if line[index] == "use_setting":
                    key = str().join(line[:3])
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
                    # Where the setting address is a number it has the ability
                    # to drop the front 0.
                    continue
                else:
                    # Multiple lines in the mapping file could have a couple of
                    # similar values until the full key is determined.
                    # app.PrintError(line)
                    prob_lines.append(line)
            if not prob_lines:
                break
            lines = prob_lines
    return setting_dictionary


def check_relay_type(app, device_object, mapping_type, relay_types, update_info):
    """
    Check that the relay type is correct. If not, place it OOS and don't update settings.
    """
    try:
        # This tests if the user has set the type, or if the relay had previously
        # been configured.
        exist_relay_type = device_object.pf_obj.GetAttribute("r:typ_id:e:loc_name")
        # Determine if the existing type has been replaced and therefore
        # the existing type would be in a recycle bin
        type_is_deleted = device_object.pf_obj.typ_id.IsDeleted()
    except AttributeError:
        exist_relay_type = "None"
        type_is_deleted = 0
    if exist_relay_type != mapping_type or type_is_deleted == 1:
        updated = update_relay_type(
            app, device_object.pf_obj, mapping_type, relay_types
        )
        if not updated:
            update_info["RESULT"] = "Unable to find the appropriate type"
            device_object.pf_obj.SetAttribute("e:outserv", 1)
            return update_info
        else:
            # Found a type and turn the relay in service.
            device_object.pf_obj.SetAttribute("e:outserv", 0)
    else:
        device_object.pf_obj.SetAttribute("e:outserv", 0)
    return update_info


def update_relay_type(app, pf_device, mapping_type, relay_types):
    """Update the type if the exsting type does not match the mapping type"""
    # Initially the new types do not exist in the ErgonLibrry
    # The Ergon created relays will be located in the ErgonLibrary
    for relay_type in relay_types:
        if relay_type.loc_name == mapping_type:
            break
    else:
        relay_type = None
    if not relay_type:
        return False
    pf_device.SetAttribute("e:typ_id", relay_type)
    pf_device.SlotUpdate()
    return True


def apply_settings(app, device_object, mapping_file, setting_dict, updates):
    """This function will go through each line of the mapping file and
    apply the setting."""
    pf_device = device_object.pf_obj
    for mapped_set in mapping_file:
        # This function is not used to deal with AND logic elements
        if (
            "_logic" in mapped_set[1]
            or "_dip" in mapped_set[1]
            or "_Trips" in mapped_set[1]
        ):
            continue
        # Get the PowerFactory object for the setting to be applied to
        element = find_element(app, pf_device, mapped_set)
        if not element:
            app.PrintError("Unable to find an element for {}".format(mapped_set))
            continue
        key = str().join(mapped_set[:3])
        try:
            setting = setting_dict[key]
        except KeyError:
            # This is to deal with the outserv attributes.
            if mapped_set[2] == "outserv":
                setting = None
            else:
                continue
        attribute = "e:{}".format(mapped_set[2])
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


def update_reclosing_logic(app, device_object, mapping_file, setting_dictionary):
    """The reclosing element has logic that controls the output to elements
    depending on the trip number. Using the following logic and the mapped
    settings update each row with either Reclosing, Lockout or Disable."""
    pf_device = device_object.pf_obj
    device_type = device_object.device
    # RC01 do not have a specific number of trips to lockout setting
    setting = None
    if "RC01" in device_type:
        trip_setting = get_trip_num(app, mapping_file, setting_dictionary)
        element = find_element(
            app, pf_device, [pf_device.loc_name, "Reclosing Element"]
        )
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
            if element.GetClassName() != "RelRecl":
                # This function is only used to setting reclosing logic
                element = None
                continue
            op_to_lockout = element.GetAttribute("e:oplockout")
        if element.loc_name not in mapped_set[1]:
            # This means this line is not associated with a reclosing element
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
        # The first check is to see if the element allows reclosing
        if recl == "N":
            # Determine if the element is to be on
            if setting.lower() == on_off_key.lower():
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
        # Check to see if it is not an individual trip
        if trip_num == "ALL":
            # Some IPS data might be missing. If this is the case then
            # The setting will be set to 1 trip to lockout
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
        # The only other option now is that the row is associated with a
        # Specific trip
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


def set_attribute(
    app,
    line,
    setting_value,
    element,
    attribute,
    device_object,
    setting_dictionary,
    updates,
):
    """Using the setting and attribute this will set the attribute."""
    if line[2] == "pcharac":
        # A curve setting requires an actual PF object to update the
        # setting
        if line[-1] == "binary":
            setting_value = convert_binary(app, setting_value, line)
        setting_value = mf.get_pf_curve(app, setting_value, element)
        existing_setting = element.GetAttribute(attribute)
        if setting_value != existing_setting:
            element.SetAttribute(attribute, setting_value)
        return True
    elif line[2] == "outserv":
        # This setting is used to set the element out of service. This
        # requires further analysis of the setting to determine how to
        # set PowerFactory
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
        # The final entry in the line determines if the setting needs
        # adjusting. If this is none then the setting can be directly applied.
        existing_setting = element.GetAttribute(attribute)
        try:
            # Due to the variable type this might not be correct to go directly
            # into PowerFactory.
            if setting_value != existing_setting:
                element.SetAttribute(attribute, setting_value)
                return True
        except TypeError:
            # Generally all settings will be a string.
            try:
                # Converting it to float is the first option as it maintains
                # the decimal numbers.
                setting_value = float(setting_value)
                if setting_value != round(existing_setting, 3):
                    element.SetAttribute(attribute, setting_value)
                    return True
            except (ValueError, TypeError):
                # The setting might be a legit string. This is typically used
                # to indicate that the element is not used.
                try:
                    # This try will convert the setting to an integer.
                    setting_value = int(setting_value)
                    if setting_value != existing_setting:
                        element.SetAttribute(attribute, setting_value)
                        return True
                except ValueError:
                    # As a last resort this will set the element to its maximum
                    element.SetAttribute(attribute, 9999)
                    return updates
    else:
        # This will adjust the setting based on the mapping file.
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


def convert_binary(app, setting_value, line):
    """Some settings are provided in binary. These need to be converted to
    be properly configured in PF"""
    binary_val = str(bin(int(setting_value))).replace("0b", "")
    bits_of_int = [-int(num) for num in line[-2]]
    binary_val = "0000000000000" + binary_val
    new_setting_value = str()
    for bit_of_int in bits_of_int:
        new_setting_value += binary_val[bit_of_int]
    return new_setting_value


def setting_adjustment(app, line, setting_dictionary, device_object):
    """If a setting needs to be adjusted to allow correct application for what is required in Powerfactory."""
    key = str().join(line[:3])
    try:
        setting = float(setting_dictionary[key])
    except (KeyError, ValueError, TypeError):
        try:
            setting_value = determine_on_off(app, setting_dictionary[key], line[6])
            return setting_value
        except  (KeyError, IndexError, ValueError, TypeError):
            setting = 0
    if line[-1] == "primary":
        primary = device_object.ct_primary
        setting_value = setting / primary
    elif line[-1] == "ctr":
        primary = device_object.ct_primary
        secondary = device_object.ct_secondary
        setting_value = setting * secondary / primary
    elif line[-1] == "secondary":
        secondary = device_object.ct_secondary
        setting_value = setting / secondary
    elif line[-1] == "perc_pu":
        secondary = device_object.ct_secondary
        setting_value = (setting / 100) * secondary
    else:
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
    return setting_value


def determine_on_off(app, setting_value, disable_cond):
    """Each device can have different ways of enabling or disabling an element"""
    try:
        disable_cond = int(disable_cond)
    except (ValueError, TypeError):
        # The Disabled condition should be in a list format. Each entry should be
        # in lower case.
        disable_list = []
        if "[" in disable_cond and "]" in disable_cond:
            disable_list = convert_string_to_list(disable_cond)
        else:
            disable_list.append(disable_cond.lower())
    if not setting_value and disable_cond == "ON":
        return 0
    elif not setting_value and disable_cond == "OFF":
        return 1
    elif not setting_value:
        return 1
    elif type(disable_cond).__name__ == "int":
        setting_value = str(setting_value)
        new_setting_value = str()
        if "e" in setting_value:
            # Deal with exponential setting values
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
    elif setting_value.lower() in disable_list:
        return 1
    else:
        return 0


def convert_string_to_list(string):
    """This provides the user the ability to set an Off statement for the
    out of service attribute by multiple things"""
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


def find_element(app, pf_object, line):
    """The setting is associated with an element. The line knows the
    element name and the folder name that it is located in. The element
    PowerFactory object is needed to apply the setting."""
    obj_contents = pf_object.GetContents(line[1], True)
    if not obj_contents:
        # Due to obj naming the get contents function does work all the time.
        # But it is the most efficent way so it is given priority.
        obj_contents = pf_object.GetContents()
        if not obj_contents:
            return None
        for obj in obj_contents:
            if obj.fold_id.loc_name == line[0] and obj.loc_name == line[1]:
                break
        else:
            for obj in obj_contents:
                obj = find_element(app, obj, line)
                if obj:
                    break
            else:
                return None
    else:
        for obj in obj_contents:
            if obj.fold_id.loc_name == line[0]:
                break
        else:
            obj = None
    return obj


def get_trip_num(app, mapping_file, setting_dictionary):
    """This will find the get the setting that is associated with
    the number of trips."""
    trips_to_lockout = 1
    for mapped_set in mapping_file:
        if "_TripstoLockout" not in mapped_set[1]:
            continue
        reclosing_key = mapped_set[-1]
        key = str().join(mapped_set[:3])
        setting = setting_dictionary[key]
        if setting == reclosing_key:
            trips_to_lockout += 1
    return trips_to_lockout


def update_logic_elements(app, pf_device, mapping_file, setting_dict):
    """Some relays will require logic elements with dip switches configured
    to control the functionality of the elements in a relay"""
    # There could be multiple elements that are logic. Make a list of all
    # Element names that contain logic
    element_list = []
    for line in mapping_file:
        if "_dip" in line[1]:
            element_name = line[1]
            if element_name not in element_list:
                element_list.append(element_name)
    if not element_list:
        # Not all relays will have logic
        return
    for element in element_list:
        element_mapping = []
        pf_element = None
        # Obtain the PF object for the element and determine all lines in the
        # mapping file associated with this element
        for line in mapping_file:
            if element not in line[1]:
                # This line is not associated with this element
                continue
            element_mapping.append(line)
            if not pf_element:
                line[1] = line[1].replace("_dip", "")
                pf_element = find_element(app, pf_device, line)
                line[1] = line[1] + "_dip"
                if pf_element.GetClassName() != "RelLogdip":
                    # This function is only used to setting reclosing logic
                    element = None
                    continue
            if not pf_element:
                app.PrintError("Element - {} could not be found".format(element))
                continue
        # Reset the dip switches to be all OFF
        existing_dip_set = pf_element.GetAttribute("e:aDipset")
        if len(existing_dip_set) != len(element_mapping):
            # This indicates that there is not a match for all dip settings in
            # the mapping file for what is in the actual element
            continue
        existing_dip_set.replace("1", "0")
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
                # Returned setting is high
                logic_value = "1"
            elif setting == 0:
                logic_value = "0"
            elif line[-1] in setting:
                # The logic key is found in the setting value string
                logic_value = "1"
            elif "32" in setting:
                logic_value = "1"
            else:
                # All else is disabled
                logic_value = "0"
            new_dip_set = list(existing_dip_set)
            new_dip_set[dip_name_index[0]] = logic_value
            existing_dip_set = "".join(new_dip_set)
        pf_element.SetAttribute("e:aDipset", existing_dip_set)

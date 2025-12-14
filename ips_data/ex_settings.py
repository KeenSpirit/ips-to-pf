import logging
from ips_data import query_database as qd
from update_powerfactory import mapping_file as mf
import devices as dev
from importlib import reload
reload(mf)

# List of IPS relay types with no protection settings. Script is instructed to ignore these relays.
NON_PROT_TYPES = [
    "SEL2505_Energex",
    "GenericRelayWithoutSetting_Energex",
    "SEL-2505",
    "GenericRelayWithoutSetting",
    "T> in TMS no Current_Energex",
    "I>> 3Ph no Time I>> in A_Energex",
    "I> 1Ph no Time I in A_Energex",
    "I> 1Ph no Time I in %_Energex",
]

def ex_device_list(app, selections, device_dict, ids_dict_list):
    """
    Function called when user has a list of devices (selections) they wish to update.

    First convert the protection device strings in to their associated PowerFactory switches
    Then map the switch names to the associated IPS relaysettingids
    Args:
        app:
        selections: list of protection device strings
        device_dict:
        ids_dict_list:

    Returns:
    setting_ids: list of relaysettingids associated with selections
    list_of_devices: list of protection device objects
    """

    # The setting id query requires the switch
    # Obtain a list of switches.
    # Each switch in the list is associated with a protection device in the list of selections
    prjt = app.GetActiveProject()
    raw_switches = prjt.GetContents("*.StaSwitch", True) + prjt.GetContents("*.ElmCoup", True)
    switches = []
    for i, device in enumerate(selections):
        if i % 10 == 0:
            # app.ClearOutputWindow()
            app.PrintInfo(
                f"IPS is being checked for switch {i} of {len(selections)}"
            )
        # Need to remove the device id from the name
        device_name = str()
        for char in device:
            if char == "_":
                break
            device_name = device_name + char
        assoc_switch = get_assoc_switch(app, device_dict[device][0], prjt, raw_switches)
        for switch in switches:
            if switch == assoc_switch:
                break
        else:
            switches.append(assoc_switch)

    # Convert this list of switches in to a list of corresponding IPS relaysettingids
    list_of_devices = []
    setting_ids = []
    cb_alt_name_list = mf.get_cb_alt_name_list(app)
    for switch in switches:
        new_setting_ids, list_of_devices = seq_get_setting_id(
            app,
            None,
            switch,
            list_of_devices,
            ids_dict_list,
            False,
            cb_alt_name_list,
        )
        setting_ids += new_setting_ids
    # Remove devices from the list of devices that were not explicitly called in the selections
    temp_list = []
    for device in list_of_devices:
        temp_list.append(device)
    logging.info(f"selections: {selections}")
    for device in temp_list:
        app.PrintInfo(f"{device.name}_{device.device_id}_{device.seq_name}")
        # Only have device that were selected in the list of devices
        if device.device_id:
            name = f"{device.name}_{device.device_id}".rstrip()
            if name not in selections:
                name = (
                    f"{device.name}_{device.device_id}_{device.seq_name}".rstrip()
                )  # noqa [E501]
                if name not in selections:
                    list_of_devices.remove(device)
                else:
                    device.pf_obj = device_dict[name][0]
            else:
                device.pf_obj = device_dict[name][0]
        else:
            name = f"{device.name}_{device.seq_name}".rstrip()
            if name not in selections:
                list_of_devices.remove(device)
            else:
                device.pf_obj = device_dict[name][0]

    return [setting_ids, list_of_devices]


def get_assoc_switch(app, pf_device, prjt, raw_switches):
    """To seach for a Setting ID the switch is needed. This function will
    return the switch that the relay is associated to."""
    for switch in raw_switches:
        try:
            if switch.GetClassName() == "StaSwitch":
                cub = switch.fold_id
                for obj in cub.GetContents():
                    if obj.loc_name == pf_device.loc_name:
                        return switch
            else:
                cub = switch.bus1
                for obj in cub.GetContents():
                    if obj == pf_device:
                        return switch
                cub = switch.bus2
                for obj in cub.GetContents():
                    if obj == pf_device:
                        return switch
        except AttributeError:
            pass
    return None


def create_new_devices(app, ids_dict_list, called_function):
    """
    Batch update for SEQ models.

    Obtain relevant switches in the active PowerFactory model.
    For each switch, try to find a match in the ids_dict_list.
    If a match is found then a device is added into the appropriate cubicle.
    Also return the protection device objects with their associated settings.
    """

    # Obtain relevant switches in the active PowerFactory model
    switches = get_pf_switches(app)
    cb_alt_name_list = mf.get_cb_alt_name_list(app)

    failed_cbs = []
    setting_ids = []
    list_of_devices = []
    for i, switch in enumerate(switches):
        if i % 10 == 0:
            app.PrintInfo(f"IPS is being checked for switch {i} of {len(switches)}")
        new_setting_ids, list_of_devices = seq_get_setting_id(
            app,
            None,
            switch,
            list_of_devices,
            ids_dict_list,
            called_function,
            cb_alt_name_list,
        )
        setting_ids += new_setting_ids
        # If a switch does not have any protection device in IPS, delete any existing pf protection devices
        # under the switch and record that no devices were detected in IPS for this switch (i.e. failed CB).
        if not new_setting_ids:  # No new setting IDs were found from IPS
            failed_cbs = update_failed_cbs(switch, failed_cbs)

    # Add the device to the switch cubicle if it doesn't already exist.
    # Assign the powerfactory element to its object attribute.
    list_of_devices = update_cubicle(list_of_devices)

    return [list_of_devices, failed_cbs, setting_ids]


def get_pf_switches(app):
    """
    Obtain all relevant switches in the active PowerFactory model.
    :param app:
    :return:
    """

    prjt = app.GetActiveProject()
    # Create a list of switches
    raw_switches = prjt.GetContents("*.StaSwitch", True) + prjt.GetContents(
        "*.ElmCoup", True
    )
    in_service_switches = [
        switch
        for switch in raw_switches
        if switch.GetAttribute("cpGrid")
        if not switch.IsOutOfService()
        if switch.IsCalcRelevant()
        if switch.IsEnergized()
    ]

    switches = []
    for switch in in_service_switches:
        # Filter unwanted switches
        try:
            # Dealing with ElmCoup switches that are not feeder bay switches
            int(switch.loc_name[2])
            if switch.GetClassName() != "StaSwitch":
                continue
        except (ValueError, IndexError):
            pass
        try:
            if switch.GetClassName() == "StaSwitch" and not switch.GetAttribute(
                    "r:fold_id:r:obj_id:e:loc_name"
            ):
                continue
        except AttributeError:
            continue
        switches.append(switch)

    return switches


def seq_get_setting_id(
    app,
    device,
    switch,
    list_of_devices,
    ids_dict_list,
    called_function,
    cb_alt_name_list,
):
    """
    Convert a switch in to a list of corresponding IPS relaysettingids
    Args:
        app:
        device:
        switch: pf switch (ElmCoup, StaSwitch)
        list_of_devices: [ProtectionDevice]
        ids_dict_list:
        called_function:
        cb_alt_name_list:

    Returns:
    setting_ids List of IPS relaysettingids
    list_of_devices List of protection device objects
    """
    setting_ids = []
    # Get the IPS switch_name
    switch_name = ips_switch_name(switch, cb_alt_name_list)
    if len(switch_name) < 4:
        return setting_ids, list_of_devices

    # Get the sub_code.
    # Different locations may have the same CB name. Determine the substation
    # that the CB belongs to.
    if switch.GetClassName() == "ElmCoup":
        sub_code = switch.fold_id.loc_name
    else:
        sub_code = None

    rows = match_switch_to_relays(app, sub_code, switch_name, ids_dict_list)
    # For each RSR that matches the switch name, create a device object and assign attribute
    setting_ids, list_of_devices = update_device(app, device, rows, list_of_devices, setting_ids, switch, called_function)

    return setting_ids, list_of_devices


def ips_switch_name(switch, cb_alt_name_list):
    """
    Get the IPS switch_name
    :param switch:
    :param cb_alt_name_list:
    :return:
    """

    for cb_dict in cb_alt_name_list:
        cb_name = cb_dict["CB_NAME"]
        elmnet_name = cb_dict["SUBSTATION"]
        if elmnet_name == switch.fold_id.loc_name and cb_name == switch.loc_name:
            pf_switch_name = cb_dict["NEW_NAME"]
            break
    else:
        pf_switch_name = switch.loc_name
    switch_name = str()
    for char in pf_switch_name:
        if char == "_":
            break
        switch_name = switch_name + char
    return switch_name


def match_switch_to_relays(app, sub_code, switch_name, ids_dict_list):
    """
    The rows list represents all RSRs that match the IPS switch name
    Args:
        sub_code: (str) PowerFactory sub acronym. Example: "NIP"
        switch_name: (str) IPS switch name
        ids_dict_list: List of rows of imported Report-Cache-ProtectionSettingIDs-EX.csv file.
        row["nameenu"] is the IPS device name (str). Example: "NIP10A"

    Returns:

    """
    app.PrintPlain(f"switch name: {switch_name}")
    app.PrintPlain(f"sub_code: {sub_code}")

    possible_bays = []
    rows = []
    for row in ids_dict_list:
        if not match_pf_ips_subs(row, sub_code):
            continue
        if row["nameenu"] != switch_name:
            # Check if the IPS relay is protecting a double cable box containing the given switch
            # To improve script run time, cable boxes for CP numberics 14 and above have been excluded from the lookup_dict
            # 'A+CP15':['A', 'CP15'], 'A+CP16':['A', 'CP16'], 'A+CP17':['A', 'CP17'],
            # 'B+CP15':['B', 'CP15'], 'B+CP16':['B', 'CP16'], 'B+CP17':['B', 'CP17'],
            # 'A+B+CP15':['A', 'B', 'CP15'], 'A+B+CP16':['A', 'B', 'CP16'], 'A+B+CP17':['A', 'B', 'CP17']
            check_str = row["nameenu"]
            lookup_dict = {'A+B': ['A', 'B'], 'A+B+C': ['A', 'B', 'C'], 'A+B+CP1': ['A', 'B', 'CP1'],
                'A+CP11':['A', 'CP11'], 'A+CP12':['A', 'CP12'], 'A+CP13':['A', 'CP13'], 'A+CP14':['A', 'CP14'],
                'B+CP11':['B', 'CP11'], 'B+CP12':['B', 'CP12'], 'B+CP13':['B', 'CP13'], 'B+CP14':['B', 'CP14'],
                'A+B+CP11':['A', 'B', 'CP11'], 'A+B+CP12':['A', 'B', 'CP12'], 'A+B+CP13':['A', 'B', 'CP13'],
                'A+B+CP14':['A', 'B', 'CP14']
            }
            #
            for key, value in lookup_dict.items():
                str_ln = len(key)
                if check_str[-str_ln:] == key:  # If the end of the relay name string matches the lookup key,
                    temp_list = []
                    for var in value:
                        temp_relay = check_str[:-str_ln] + var
                        temp_list.append(temp_relay)
                    if switch_name in temp_list:
                        rows.append(row)
        else:
            # The IPS relay matches the Powerfactory switch name
            rows.append(row)
    if not rows:
        rows = possible_bays
    app.PrintPlain(f"rows: {rows}")
    return rows


def update_device(app, device, rows, list_of_devices, setting_ids, switch, called_function):
    """
    Create the protection device object and add it to the list of devices.
    :param app:
    :param device:
    :param rows:
    :param list_of_devices:
    :param setting_ids:
    :param switch:
    :param called_function:
    :return:
    """

    # For each RSR that matches the switch name, create a device object and assign attribute
    for row in rows:
        if row["patternname"] in NON_PROT_TYPES:
            continue
        try:
            device_id = row["deviceid"]
            for char in ": /,":
                device_id = device_id.replace(char, "")
        except AttributeError:
            device_id = row["deviceid"]
        setting_ids.append(row["relaysettingid"])
        # Create the protection device object and add it to the list of devices.
        prot_dev = dev.ProtectionDevice(
            app,
            row["patternname"],
            row["nameenu"],
            row["relaysettingid"],
            row["datesetting"],
            device,
            device_id,
        )
        prot_dev.switch = switch
        prot_dev.seq_name = row["assetname"]
        already_added = False
        for chk_device in list_of_devices:
            if chk_device.pf_obj == device and device:
                already_added = True
                break
        else:
            list_of_devices.append(prot_dev)
        if already_added:
            continue
        if not called_function:
            ips_settings = qd.seq_get_ips_settings(app, row["relaysettingid"])
            prot_dev.associated_settings(ips_settings)
        if "fuse" in list_of_devices[-1].device.lower():
            list_of_devices[-1].fuse_type = "Line Fuse"

    return setting_ids, list_of_devices


def update_failed_cbs(switch, failed_cbs):
    """
    For switches that don't have any protection devices in IPS.

    Delete any existing pf protection devices under the switch and record that
    no devices were detected in IPS for this switch (i.e. failed CB).
    This indicates a possible mismatch between IPS and pf switch names.

    :param switch:
    :param failed_cbs:
    :return:
    """
    if switch.GetClassName() == "StaSwitch":
        contents = switch.fold_id.GetContents()
    else:
        root_cub = switch.GetCubicle(0)
        contents = root_cub.GetContents()
    for content in contents:
        if content.GetClassName() in ["ElmRelay", "RelFuse", "StaCt"]:
            content.Delete()
    if (
            switch.GetClassName() == "ElmCoup"
            and switch.GetAttribute("e:aUsage") == "cbk"  # switch is a CB, not a disconnector
    ):  # noqa [E501]
        if switch not in failed_cbs:
            failed_cbs.append(switch)
    return failed_cbs


def update_cubicle(list_of_devices):
    """
    Add the device to the switch cubicle if it doesn't already exist.
    Assign the powerfactory element to its object attribute.

    :param list_of_devices:
    :return:
    """
    used_names = []
    for device in list_of_devices:
        # Get the device name as it would be in pf
        if not device.device_id:
            device_name = f"{device.name}_{device.seq_name}".rstrip()
        else:
            device_name = f"{device.name}_{device.device_id}".rstrip()
            if device_name in used_names:
                # This will handle where the same device ID has been used
                device_name = (
                    f"{device.name}_{device.device_id}_{device.seq_name}".rstrip()
                )  # noqa [E501]
        used_names.append(device_name)
        # Check to see if the PF object already exists for that setting and switch.
        # If so, assign the pf element to its object attribute.
        switch = device.switch
        if switch.GetClassName() == "StaSwitch":
            # This indicates that the relay would be in the same cubicle
            contents = switch.fold_id.GetContents(f"{device_name}.ElmRelay")
            contents += switch.fold_id.GetContents(f"{device_name}.RelFuse")
        else:
            root_cub = switch.GetCubicle(0)
            contents = root_cub.GetContents(f"{device_name}.ElmRelay")
            contents += root_cub.GetContents(f"{device_name}.RelFuse")
        if contents:
            # This device already exists
            device.pf_obj = contents[0]
            continue
        # If a setting was found for a switch that doesn't already have an
        # associated protection device, create the device element in pf and
        # assign it to its object attribute.
        if "fuse" in device.device.lower():
            if switch.GetClassName() == "StaSwitch":
                device_pf = switch.fold_id.CreateObject("RelFuse", device_name)
                if device_pf.loc_name != device_name:
                    device_pf.Delete()
                    list_of_devices.remove(device)
                else:
                    device.pf_obj = device_pf
            elif switch.GetClassName() == "ElmCoup":
                root_cub = switch.GetCubicle(0)
                if device_pf.loc_name != device_name:
                    device_pf.Delete()
                    list_of_devices.remove(device)
                else:
                    device.pf_obj = device_pf
        else:
            if switch.GetClassName() == "StaSwitch":
                device_pf = switch.fold_id.CreateObject("ElmRelay", device_name)
                if device_pf.loc_name != device_name:
                    device_pf.Delete()
                    list_of_devices.remove(device)
                else:
                    device.pf_obj = device_pf
            elif switch.GetClassName() == "ElmCoup":
                root_cub = switch.GetCubicle(0)
                device_pf = root_cub.CreateObject("ElmRelay", device_name)
                if device_pf.loc_name != device_name:
                    device_pf.Delete()
                    list_of_devices.remove(device)
                else:
                    device.pf_obj = device_pf
    return list_of_devices


def match_pf_ips_subs(row, sub_code):
    """
    Some relays belong to a bulk supply that uses numerics in IPS name.
    PowerFactory projects use only alphas.
    Need a mapping between the two subs.
    Interim solution:
    When the script detects a sub with numerics, let the setting pass through.
    Implication: switches may be associated with settings from multiple subs
    if one of those subs has a numeric value.
    :param row: Row from imported Report-Cache-ProtectionSettingIDs-EX.csv file
    :param sub_code: (str) PowerFactory sub acronym. Example: "NIP"
    row["locationpathenu"] is the IPS location path (str). Example: "Energex/Substations/NIP/11 kV/NIP10A/"
    :return:
    """
    row_sub = row["locationpathenu"].split("/")[2]
    for char in row_sub:
        try:
            int(char)
            row_sub = None
            break
        except ValueError:
            return False
    if sub_code and row_sub:
        if sub_code != row_sub:
            return False
    return True
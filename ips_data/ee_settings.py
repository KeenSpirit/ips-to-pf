import devices as dev
from ips_data import query_database as qd


def ee_device_list(app, selections, device_dict, ids_dict_list, data_capture_list):

    list_of_devices = []
    setting_ids = []

    for i, device in enumerate(selections):
        # Go through each device and see if there is a setting ID.
        if i % 10 == 0:
            # app.ClearOutputWindow()
            app.PrintInfo(
                f"IPS is being checked for device {i} of {len(selections)}"
            )
        plant_number = get_plant_number(app, device)
        pf_device = device_dict[device][0]
        if not plant_number:
            update_info = info_dict(pf_device, "Not a protection device")
            data_capture_list.append(update_info)
            continue
        if device_dict[device][1] != "ElmRelay":
            [fuse_type, fuse_size] = dev.determine_fuse_type(app, pf_device)
            if fuse_type == "Tx Fuse":
                prot_dev = dev.ProtectionDevice(
                    app, fuse_type, pf_device.loc_name, None, None, pf_device, None
                )
                prot_dev.fuse_size = fuse_size
                prot_dev.fuse_type = fuse_type
                list_of_devices.append(prot_dev)
                continue
            if not fuse_type:
                update_info = info_dict(pf_device, "FAILED FUSE")
                data_capture_list.append(update_info)
                continue
        else:
            fuse_type = None
            fuse_size = None
        [setting_ids, list_of_devices] = reg_get_setting_id(
            app,
            plant_number,
            list_of_devices,
            setting_ids,
            pf_device,
            fuse_type,
            fuse_size,
            ids_dict_list,
            False,
        )
    return [setting_ids, list_of_devices, data_capture_list]


def get_plant_number(app, device_name):
    """A plant number will be structured. These structures differ depending on the
    device.
    - Reclosers will have either RC-{Number} or RE-{Number}
    - Relays should have {SUB}SS-{BAY}-{Device}
    - Fuse will be either DO-{Number} or FU-{number} or DL-{Number}"""
    meets_cond = False
    if (
        device_name[4:7] == "SS-"
        or device_name[:3] == "RC-"
        or device_name[:3] == "RE-"
        or device_name[:3] == "DO-"
        or device_name[:3] == "FU-"
        or device_name[:3] == "DL-"
    ):
        meets_cond = True
    if meets_cond:
        plant_number = ""
        for char in device_name:
            if char == " ":
                break
            else:
                plant_number = plant_number + char
    else:
        plant_number = None
    return plant_number


def ergon_all_dev_list(app, data_capture_list, ids_dict_list, called_function):
    """This will go through every protection device in the active project"""
    prot_devices = get_all_protection_devices(app)
    list_of_devices = []
    setting_ids = []
    for i, pf_device in enumerate(prot_devices):
        if i % 10 == 0:
            # app.ClearOutputWindow()
            app.PrintInfo(f"IPS is being checked for device {i} of {len(prot_devices)}")
        if pf_device.loc_name[-1] == ")":
            pf_device.Delete()
            continue
        # Get all the setting IDs and create an object for each ID
        plant_number = get_plant_number(app, pf_device.loc_name)
        if not plant_number:
            update_info = info_dict(pf_device, "Not a protection device")
            data_capture_list.append(update_info)
            continue
        if pf_device.GetClassName() != "ElmRelay":
            [fuse_type, fuse_size] = dev.determine_fuse_type(app, pf_device)
            if fuse_type == "Tx Fuse":
                prot_dev = dev.ProtectionDevice(
                    app, fuse_type, pf_device.loc_name, None, None, pf_device, None
                )
                prot_dev.fuse_size = fuse_size
                prot_dev.fuse_type = fuse_type
                list_of_devices.append(prot_dev)
                continue
            if not fuse_type:
                update_info = info_dict(pf_device, "FAILED FUSE")
                data_capture_list.append(update_info)
                continue
        else:
            fuse_type = None
            fuse_size = None
        [setting_ids, list_of_devices] = reg_get_setting_id(
            app,
            plant_number,
            list_of_devices,
            setting_ids,
            pf_device,
            fuse_type,
            fuse_size,
            ids_dict_list,
            called_function,
        )
    return [setting_ids, list_of_devices, data_capture_list]


def get_all_protection_devices(app):
    """Get all active protection devices"""
    net_mod = app.GetProjectFolder("netmod")
    all_devices = [
        relay
        for relay in net_mod.GetContents("*.ElmRelay", True)
        if relay.GetAttribute("cpGrid")
        if relay.cpGrid.IsCalcRelevant()
        if relay.GetParent().GetClassName() == "StaCubic"
    ]
    all_devices += [
        fuse
        for fuse in net_mod.GetContents("*.RelFuse", True)
        if fuse.GetAttribute("cpGrid")
        if fuse.cpGrid.IsCalcRelevant()
    ]
    return all_devices


def reg_get_setting_id(
    app,
    device,
    list_of_devices,
    setting_ids,
    pf_device,
    fuse_type,
    fuse_size,
    ids_dict_list,
    called_function,
):
    """Each device has a unique setting ID. This ID is to be used in another SQL
    query on the DB to extract settings."""
    setting_found = False
    # Need to deal with the wild card getting settings that may not be correct
    wild_card_issue = False
    new_rows = []
    for row in ids_dict_list:
        # This is because not all rows are needed
        if (
            "RTU" in row["patternname"]
            or device not in row["assetname"]
            or not row["active"]
            or "CMGR12" in row["patternname"]
        ):
            continue
        if row["assetname"] == device:
            # If the device name is an exact match to a name in IPS
            setting_ids.append(row["relaysettingid"])
            prot_dev = dev.ProtectionDevice(
                app,
                row["patternname"],
                row["assetname"],
                row["relaysettingid"],
                row["datesetting"],
                pf_device,
                None,
            )
            if not called_function:
                ips_settings = qd.reg_get_ips_settings(app, row["relaysettingid"])
                prot_dev.associated_settings(ips_settings)
            prot_dev.fuse_type = fuse_type
            prot_dev.fuse_size = fuse_size
            list_of_devices.append(prot_dev)
            wild_card_issue = True
            break
        if device in row["assetname"]:
            new_rows.append(row)
    if wild_card_issue:
        return [setting_ids, list_of_devices]
    pf_device_name = pf_device.loc_name
    for row in new_rows:
        # Rename or create a new devices with the name. This deals with multiple
        # devices in a single cubicle
        name = row["assetname"]
        for device in pf_device.fold_id.GetContents("*.ElmRelay"):
            if device.loc_name == name:
                # This finds another device in the cubicle with the same name
                break
            elif device.loc_name == pf_device_name:
                # Rename this device if it is the correct one to rename
                device.loc_name = name
                pf_device = device
                break
        else:
            cubicle = pf_device.fold_id
            pf_device = cubicle.CreateObject("ElmRelay", name)
        setting_ids.append(row["relaysettingid"])
        prot_dev = dev.ProtectionDevice(
            app,
            row["patternname"],
            row["assetname"],
            row["relaysettingid"],
            row["datesetting"],
            pf_device,
            None,
        )
        if not called_function:
            ips_settings = qd.reg_get_ips_settings(app, row["relaysettingid"])
            prot_dev.associated_settings(ips_settings)
        prot_dev.fuse_type = fuse_type
        prot_dev.fuse_size = fuse_size
        list_of_devices.append(prot_dev)
        setting_found = True
    if not setting_found:
        list_of_devices.append(
            dev.ProtectionDevice(app, None, None, None, None, pf_device, None)
        )
        list_of_devices[-1].fuse_type = fuse_type
        list_of_devices[-1].fuse_size = fuse_size
    return [setting_ids, list_of_devices]


def info_dict(pf_device, result):

    update_info = {}
    update_info["SUBSTATION"] = pf_device.GetAttribute("r:cpGrid:e:loc_name")
    update_info["PLANT_NUMBER"] = pf_device.loc_name
    update_info["RESULT"] = result
    return update_info
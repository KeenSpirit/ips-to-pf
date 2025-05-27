import logging

from update_powerfactory import relay_settings as rs
from update_powerfactory import fuse_settings as fs
from update_powerfactory import get_objects as go
import devices
from importlib import reload
reload(devices)
reload(rs)

# List of FD relays to switch OOS
RELAYS_OOS = [
    "7PG21 (SOLKOR-RF)",
    "7SG18 (SOLKOR-N)",
    "RED615 2.6 - 2.8",
    "SOLKOR-N_Energex",
    "SOLKOR-RF_Energex",
]

def update_pf(app, lst_of_devs, data_capture_list):
    """
    Begin to update the PowerFactory relays with data from IPS
    """

    # Create a list of all the device types
    ergon_lib = app.GetGlobalLibrary()
    app.PrintInfo("Creating a database of PowerFactory Fuse and Relay Types")
    fuse_folder = ergon_lib.SearchObject(r"\ErgonLibrary\Protection\Fuses.IntFolder")
    fuse_types = fuse_folder.GetContents("*.TypFuse", 0)
    relay_types = get_relay_types(app)

    update_info = {}
    updates = False
    app.SetWriteCacheEnabled(1)
    for i, device_object in enumerate(lst_of_devs):
        if i % 10 == 0:
            app.PrintInfo(f"Device {i} of {len(lst_of_devs)} is being updated")
        if not device_object.pf_obj:
            continue
        # Check to see if there is a setting for the device
        if not device_object.setting_id and not device_object.fuse_type:
            update_info["SUBSTATION"] = device_object.pf_obj.GetAttribute(
                "r:cpGrid:e:loc_name"
            )
            update_info["PLANT_NUMBER"] = device_object.pf_obj.loc_name
            update_info["RESULT"] = "Not in IPS"
            data_capture_list.append(update_info)
            update_info = {}
            app.PrintInfo(f"In IPS")
            continue
        try:
            # Start configuring the device
            if device_object.pf_obj.GetClassName() == "ElmRelay":
                update_info, updates = rs.relay_settings(
                    app, device_object, relay_types, updates
                )
            else:
                update_info = fs.fuse_setting(app, device_object, fuse_types)
        except:  # noqa [E722]
            logging.info(f"{device_object.pf_obj.loc_name} Result = Script Failed")
            logging.exception(f"{device_object.pf_obj.loc_name} Result = Script Failed")
            devices.log_device_atts(device_object)
            try:
                update_info["SUBSTATION"] = device_object.pf_obj.GetAttribute(
                    "r:cpGrid:e:loc_name"
                )  # noqa [E122]
            except AttributeError:
                update_info["SUBSTATION"] = "UNKNOWN"
            update_info["PLANT_NUMBER"] = device_object.pf_obj.loc_name
            update_info["RELAY_PATTERN"] = device_object.device
            update_info["RESULT"] = "Script Failed"
            device_object.pf_obj.SetAttribute("outserv", 1)
        data_capture_list.append(update_info)
        update_info = {}
        switch_relay_oos(RELAYS_OOS, device_object)
    app.WriteChangesToDb()
    app.SetWriteCacheEnabled(0)

    return data_capture_list, updates


def get_relay_types(app):
    """This will create a list of relay types. It searches the ErgonLibrary,
    and DIgSILENT library to find these types. As a last resort it will also
    look in the active project."""
    global_library = app.GetGlobalLibrary()
    protection_lib = global_library.GetContents("Protection")
    relay_types = go.all_relevant_objects(app, protection_lib, "*.TypRelay", None)
    database = global_library.fold_id
    dig_lib = database.GetContents("Lib")[0]
    prot_lib = dig_lib.GetContents("Prot")[0]
    relay_lib = prot_lib.GetContents("ProtRelay")

    dig_relay_types = go.all_relevant_objects(app, relay_lib, "*.TypRelay", None)
    relay_types = relay_types + dig_relay_types
    current_user = app.GetCurrentUser()
    protection_folder = current_user.GetContents("Protection")

    local_relays = go.all_relevant_objects(app, protection_folder, "*.TypRelay", None)
    if local_relays:
        for local_relay in local_relays:
            for relay_type in relay_types:
                if local_relay.loc_name == relay_type.loc_name:
                    break
            else:
                relay_types.append(local_relay)
    app.PrintInfo("Finished Getting Relay types")

    return relay_types


def switch_relay_oos(relays_oos, device_object):

    if device_object.device in relays_oos:
        device_object.pf_obj.SetAttribute("outserv", 1)
    try:
        if device_object.switch.on_off == 0:
            device_object.pf_obj.SetAttribute("outserv", 1)
    except:  # noqa [E722]
        pass

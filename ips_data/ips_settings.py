import logging
import sys
sys.path.append(
    r"\\ecasd01\WksMgmt\PowerFactory\ScriptsDEV\AddProtectionRelaySkeletons\addprotectionrelayskeletons"  # noqa [E501]
)
import add_protection_relay_skeletons

from ips_data import query_database as qd
from ips_data import ee_settings as ee
# from ips_data import add_protection_relay_skeletons as aprs
from ips_data import ex_settings as ex
from update_powerfactory import mapping_file as mf
import devices as dev
import user_inputs
from importlib import reload
reload(qd)
reload(ex)
reload(ee)
reload(ee)
reload(user_inputs)
# reload(aprs)


def get_ips_settings(app, region, batch, called_function):
    """
    Returns:
    lst_of_devs: A list of devices stored as classes with setting data attributes
    data_capture_list: a list for tracking data issues that were identified during the script run time.
    It is printed to the output.
    """
    data_capture_list = []
    # Create a dictionary of all device setting ids extracted from IPS
    ids_dict_list = qd.get_setting_ids(app, region)
    
    # Get the selected devices
    [set_ids, device_list, data_capture_list] = get_selected_devices(
        app, batch, region, data_capture_list, ids_dict_list, called_function
    )
    logging.info(f"set_ids: {set_ids}")
    logging.info(f"device_list: {device_list}")
    logging.info(f"data_capture_list: {data_capture_list}")

    ips_settings, ips_it_settings = qd.batch_settings(app, region, called_function, set_ids)
    logging.info(f"ips_settings (only if batch): {ips_settings}")
    logging.info(f"ips_it_settings: {ips_it_settings}")

    # Load all CT and VT settings for each device.
    # If it's a batch update, load settings for every relay.
    for i, device_object in enumerate(device_list):
        if i % 10 == 0:
            # app.ClearOutputWindow()
            app.PrintInfo(
                f"device number {i} of {len(device_list)} has had its"
                " setting attributes assigned"
            )
        if device_object.device:
            if called_function:
                # Load relay settings for batch run
                # Relay settings were only loaded in ex.create_new_devices() called_function = False
                device_object.associated_settings(ips_settings)
            if ips_it_settings:
                # Load CT settings
                if region == "Energex":
                    device_object.seq_instrument_attributes(ips_it_settings)
                else:
                    device_object.reg_instrument_attributes(ips_it_settings)
    return device_list, data_capture_list


def get_selected_devices(app, batch, region, data_capture_list, ids_dict_list, called_function):

    failed_cbs = []
    if not batch:
        # Update selected existing devices in PowerFactory
        [set_ids, lst_of_devs, data_capture_list] = prot_dev_lst(
            app, region, data_capture_list, ids_dict_list
        )
    if batch or set_ids == "Batch":
        # Update PowerFactory with all relays found in IPS
        if region == "Energex":
            app.PrintInfo("Creating a list of Setting IDs")
            # Create a list of setting ids for each device in the active project
            [lst_of_devs, failed_cbs, set_ids] = ex.create_new_devices(
                app, ids_dict_list,  called_function
            )
        else:
            # aprs.add_relay_skeletons(app)
            add_protection_relay_skeletons.main(app)
            app.ClearOutputWindow()
            app.PrintInfo("Creating a list of Setting IDs")
            [set_ids, lst_of_devs, data_capture_list] = ee.ergon_all_dev_list(
                app, data_capture_list, ids_dict_list, called_function
            )

    for cb in failed_cbs:
        update_info = {}
        update_info["SUBSTATION"] = cb.GetAttribute("r:cpGrid:e:loc_name")
        update_info["CB_NAME"] = cb.loc_name
        update_info["RESULT"] = "Failed to find match"
        data_capture_list.append(update_info)

    return [set_ids, lst_of_devs, data_capture_list]


def prot_dev_lst(app, region, data_capture_list, ids_dict_list):
    """
    This function is used to create a list of devices to update.
    The model configuration differs between the regional and SEQ models.
    """
    # User selection should be the same
    # Set up a database of the active devices in the PowerFactory model
    [devices, device_dict] = dev.prot_device(app)
    logging.info(f"Active PowerFactory protection devices: {devices}")

    # Ask the user to select which protection devices they want to study
    selections = user_inputs.user_selection(app, device_dict)

    if not selections:
        message = "User has selected to exit the script"
        logging.info(message)
        qd.error_message(app, message)
    elif selections == "Batch":
        return ["Batch", None, data_capture_list]
    if region == "Energex":
        [setting_ids, list_of_devices] = ex.ex_device_list(
            app, selections, device_dict, ids_dict_list
        )
    elif region == "Ergon":
        [setting_ids, list_of_devices, data_capture_list] = ee.ee_device_list(
            app, selections, device_dict, ids_dict_list, data_capture_list
        )
    return [setting_ids, list_of_devices, data_capture_list]


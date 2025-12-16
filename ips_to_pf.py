import powerfactory as pf
import os
import csv
from tkinter import *  # noqa [F403]
import time
import logging.config
import user_inputs
from importlib import reload

from ips_data import ips_settings as ips
import devices as dev
from update_powerfactory import update_powerfactory as up
reload(user_inputs)
reload(ips)
reload(up)

def main(app=None, batch=False):
    """This Script Will be used to transfer Settings from IPS to PF."""
    start_time = time.strftime("%H:%M:%S")
    start = time.time()
    if not app:
        # Change called_function to True if you want to mimic a batch update
        called_function = False
        app = pf.GetApplication()
    else:
        # If another script is executing this script, it will pass the app argument to it
        called_function = True
    app.ClearOutputWindow()

    # Determine which IPS database is to be queried
    prjt = app.GetActiveProject()
    if prjt is None:
        app.PrintError("No active project selected. Activate a project to use this script")
        logging.error(f"Script terminated because no active project was selected")
        exit()
    region = determine_region(prjt)

    # Query the IPS data
    dev_list, data_capture_list = ips.get_ips_settings(app, region, batch, called_function)
    for dev in dev_list:
        app.PrintPlain(vars(dev))

    logging.info(f"lst_of_devs: {dev_list}")

    # Update PowerFactory
    data_capture_list, updates = up.update_pf(app, dev_list, data_capture_list)
    logging.info(f"data_capture_list: {data_capture_list}")
    logging.info(f"updates: {updates}")

    # Create file to save script information
    save_file = create_save_file(app, prjt, called_function)
    if not save_file:
        return
    write_data(app, data_capture_list, save_file)
    if not batch:
        print_results(app, data_capture_list)
    stop_time = time.strftime("%H:%M:%S")
    app.PrintInfo(
        f"Script started at {start_time} and finished at {stop_time}"
    )
    if updates:
        app.PrintInfo("Of the devices selected there were updated settings")
    else:
        app.PrintInfo("Of the devices selected there were no updated settings")

    end = time.time()
    run_time = round(end - start, 6)
    run_time = format_time(run_time)
    app.PrintPlain(f"Query Script run time: {run_time}")

    return updates


def format_time(seconds):
    hours, remainder = divmod(int(seconds), 3600)
    minutes, seconds = divmod(remainder, 60)

    time_parts = []
    if hours > 0:
        time_parts.append(f"{hours} hour{'s' if hours > 1 else ''}")
    if minutes > 0:
        time_parts.append(f"{minutes} minute{'s' if minutes > 1 else ''}")
    if seconds > 0 or not time_parts:
        time_parts.append(f"{seconds} second{'s' if seconds > 1 else ''}")

    return " ".join(time_parts)


def log_devices():
    pass

def create_save_file(app, prjt, called_function):

    project_name = prjt.GetAttribute("loc_name")
    current_user = app.GetCurrentUser()
    current_user_name = current_user.GetAttribute("loc_name")
    parent_folder = prjt.GetAttribute("fold_id")
    parent_folder_name = parent_folder.GetAttribute("loc_name")
    file_name = f"{current_user_name}_{parent_folder_name}_{project_name}".replace(
        "/", "_"
    )
    if called_function:
        file_location = r"\\ecasd01\WksMgmt\PowerFactory\ScriptsDEV\IPSDataTransferMastering\Script_Results"  # noqa [E501]
        main_file_name = select_main_file(
            app, file_name, file_location, called_function
        )
    else:
        file_location = r"C:\LocalData\PowerFactory Output Folders\IPS Data Transfer"
        main_file_name = select_main_file(
            app, file_name, file_location, called_function
        )
    return main_file_name


def select_main_file(app, file_name, location, called_function):
    """Check to see if a folder structure exists and create it if it doesn't.
    Create the csv file to publish all the data."""
    citrix = os.path.isdir("\\\\Client\\C$\\localdata")
    if citrix and "C:" in location:
        location = "\\\\Client\\" + location.replace("C:", "C$")
    protection_folder_check = os.path.isdir(location)
    if not protection_folder_check:
        os.makedirs(location)
    set_file_name = location + "\\{}.csv".format(file_name)
    print(set_file_name)
    # Open the files
    try:
        last_mod_time = os.stat(set_file_name).st_mtime
        if called_function:
            check_time = time.time() - (24 * 60 * 60)
        else:
            check_time = last_mod_time
        if check_time < last_mod_time:
            print("Project had already been studied")
            return None
        os.remove(set_file_name)
    except FileNotFoundError:
        pass
    return set_file_name


def determine_region(prjt):
    """This function relies on the file structure under the Publisher"""
    base_prjt = prjt.der_baseproject
    if not base_prjt:
        base_prjt_fld = prjt.fold_id.loc_name
    else:
        base_prjt_fld = prjt.der_baseproject.fold_id.loc_name
    if base_prjt_fld == "SEQ Models":
        region = "Energex"
    else:
        region = "Ergon"
    logging.info(f"region: {region}")
    return region


def write_data(app, update_info_list, main_file_name):
    """This function records the results of the IPS to PF transfer."""
    # Get Column names
    col_headings = []
    for update_dict in update_info_list:
        for key in update_dict:
            if key in col_headings:
                continue
            else:
                col_headings.append(key)
    # Open the CSV
    with open(main_file_name, "a", newline="", encoding="UTF-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=col_headings)
        writer.writeheader()
        for data in update_info_list:
            writer.writerow(data)


def print_results(app, data_capture_list):
    """This is to provide information to the user about the results of the
    script."""
    [devices, device_object_dict] = dev.prot_device(app)
    print_string = str()
    # app.ClearOutputWindow()
    for i, info in enumerate(data_capture_list):
        if i % 40 == 0:
            app.PrintInfo(print_string)
            print_string = str()
        try:
            device = info["PLANT_NUMBER"]
            pf_device = device_object_dict[device][0]
        except KeyError:
            try:
                pf_device = info["CB_NAME"]
            except KeyError:
                pf_device = info["PLANT_NUMBER"]
        try:
            result = info["RESULT"]
        except KeyError:
            result = "Updated Successfully"
        print_string = print_string + "\n" + f"{pf_device}    Result = {result}"
    app.PrintInfo(print_string)


if __name__ == "__main__":

    # Configure logging
    # logging.basicConfig(
    #     filename=cl.getpath() / 'ips_to_pf_log.txt',
    #     level=logging.WARNING,
    #     format='%(asctime)s - %(levelname)s - %(message)s',
    # )

    updates = main()


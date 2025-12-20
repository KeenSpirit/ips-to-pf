import powerfactory as pf
import os
from tkinter import *  # noqa [F403]
import logging.config
from logging_config import configure_logging as cl
from importlib import reload

from ips_data import ips_settings as ips
from update_powerfactory import orchestrator as up

from config.paths import OUTPUT_BATCH_DIR, OUTPUT_LOCAL_DIR
from config.validation import (
    require_valid_config,
    validate_for_batch_mode,
    validate_for_interactive_mode,
    ValidationConfig,
    ValidationLevel,
)
from utils.time_utils import Timer, get_current_timestamp
from utils.file_utils import (
    ensure_directory_exists,
    get_citrix_adjusted_path,
    write_dict_list_to_csv,
    is_file_recent,
    safe_file_remove,
)
from utils.pf_utils import determine_region, get_all_protection_devices

reload(ips)
reload(up)


def main(app=None, batch=False):
    """This Script Will be used to transfer Settings from IPS to PF."""
    timer = Timer(name="IPS to PF Transfer", auto_log=True)
    timer.start()
    start_time = get_current_timestamp()

    if not app:
        # Change called_function to True if you want to mimic a batch update
        called_function = False
        app = pf.GetApplication()
    else:
        # If another script is executing this script, it will pass the app argument to it
        called_function = True
    app.ClearOutputWindow()

    # ==========================================================================
    # CONFIGURATION VALIDATION
    # ==========================================================================
    # Validate configuration before doing anything else.
    # This catches issues early with clear error messages rather than
    # failing mid-run with cryptic stack traces.

    if batch or called_function:
        # Batch mode: stricter validation, check database connectivity
        result = validate_for_batch_mode(app)
        if not result.is_valid:
            app.PrintError("Configuration validation failed for batch mode")
            for error in result.errors:
                app.PrintError(f"  {error}")
            return None
        # Print warnings but continue
        for warning in result.warnings:
            app.PrintWarn(warning)
    else:
        # Interactive mode: standard validation, faster startup
        # require_valid_config() will exit automatically if invalid
        require_valid_config(app)

    # ==========================================================================
    # MAIN PROCESSING
    # ==========================================================================

    # Determine which IPS database is to be queried
    prjt = app.GetActiveProject()
    if prjt is None:
        app.PrintError("No active project selected. Activate a project to use this script")
        logging.error(f"Script terminated because no active project was selected")
        exit()
    region = determine_region(prjt)

    # Query the IPS data
    dev_list, data_capture_list = ips.get_ips_settings(app, region, batch, called_function)

    logging.info(f"lst_of_devs: {dev_list}")

    # Update PowerFactory
    data_capture_list, updates = up.update_pf(app, dev_list, data_capture_list)
    logging.info(f"data_capture_list: {data_capture_list}")
    logging.info(f"updates: {updates}")

    # Create file to save script information
    save_file = create_save_file(app, prjt, called_function)
    if not save_file:
        return
    write_dict_list_to_csv(data_capture_list, save_file)
    if not batch:
        print_results(app, data_capture_list)

    timer.stop()
    stop_time = get_current_timestamp()
    app.PrintInfo(
        f"Script started at {start_time} and finished at {stop_time}"
    )
    if updates:
        app.PrintInfo("Of the devices selected there were updated settings")
    else:
        app.PrintInfo("Of the devices selected there were no updated settings")

    app.PrintPlain(f"Query Script run time: {timer.formatted}")

    return updates


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
        file_location = OUTPUT_BATCH_DIR
        main_file_name = select_main_file(
            app, file_name, file_location, called_function
        )
    else:
        file_location = OUTPUT_LOCAL_DIR
        main_file_name = select_main_file(
            app, file_name, file_location, called_function
        )
    return main_file_name


def select_main_file(app, file_name, location, called_function):
    """Check to see if a folder structure exists and create it if it doesn't.
    Create the csv file to publish all the data."""
    # Adjust path for Citrix environment
    location = get_citrix_adjusted_path(location)

    # Ensure directory exists
    ensure_directory_exists(location)

    set_file_name = os.path.join(location, f"{file_name}.csv")
    print(set_file_name)

    # Check if file was recently modified
    if called_function:
        # For batch mode, skip if file was modified in last 24 hours
        if is_file_recent(set_file_name, max_age_seconds=24 * 60 * 60):
            print("Project had already been studied")
            return None

    # Remove existing file if present
    safe_file_remove(set_file_name)

    return set_file_name


def print_results(app, data_capture_list):
    """This is to provide information to the user about the results of the
    script."""
    devices, device_object_dict = get_all_protection_devices(app)
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
    logging.basicConfig(
        filename=cl.getpath() / 'ips_to_pf_log.txt',
        level=logging.WARNING,
        format='%(asctime)s - %(levelname)s - %(message)s',
    )

    updates = main()
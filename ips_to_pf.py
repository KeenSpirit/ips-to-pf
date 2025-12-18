"""
IPS to PowerFactory Settings Transfer Script.

This script transfers protection device settings from the IPS database
to PowerFactory network models. It supports both interactive (single device
selection) and batch (all devices) update modes.

Usage:
    # In PowerFactory Python console:
    import ips_to_pf
    ips_to_pf.main()

    # For batch updates:
    ips_to_pf.main(batch=True)

    # Called from another script:
    ips_to_pf.main(app=pf_app, batch=True)
"""

import powerfactory as pf
import os
import csv
import time
from importlib import reload

import user_inputs
from ips_data import ips_settings as ips
import devices as dev
from update_powerfactory import update_powerfactory as up
from update_powerfactory.logging_utils import (
    get_logger,
    set_app,
    configure_logging,
    LogContext,
    timed_operation,
    log_performance,
)

# Reload modules during development (remove for production)
reload(user_inputs)
reload(ips)
reload(up)

logger = get_logger(__name__)


@log_performance(operation_name="IPS to PowerFactory Transfer")
def main(app=None, batch=False):
    """
    Main entry point for IPS to PowerFactory settings transfer.

    This function orchestrates the full transfer process:
    1. Determines the region (Energex/Ergon)
    2. Queries IPS database for protection settings
    3. Updates PowerFactory model with settings
    4. Creates output report file
    5. Prints results summary

    Args:
        app: PowerFactory application object (optional, will get if not provided)
        batch: True for batch update of all devices, False for interactive selection

    Returns:
        bool: True if any settings were updated, False otherwise
    """
    start_time = time.strftime("%H:%M:%S")

    # Get PowerFactory application
    if not app:
        called_function = False
        app = pf.GetApplication()
    else:
        called_function = True

    # Initialize logging with PowerFactory app
    set_app(app)
    app.ClearOutputWindow()

    logger.info(f"Script started at {start_time}")

    # Validate active project
    prjt = app.GetActiveProject()
    if prjt is None:
        logger.error("No active project selected. Activate a project to use this script")
        exit()

    project_name = prjt.GetAttribute("loc_name")

    with LogContext(operation="ips_transfer"):
        # Determine region
        region = determine_region(prjt)
        logger.info(f"Region determined: {region}")

        # Query IPS data
        with timed_operation("IPS Data Query"):
            dev_list, data_capture_list = ips.get_ips_settings(
                app, region, batch, called_function
            )

        logger.info(f"Retrieved settings for {len(dev_list)} devices")

        # Log device details (debug level)
        for dev_obj in dev_list:
            logger.debug(f"Device: {vars(dev_obj)}", pf_output=False)

        # Update PowerFactory
        with timed_operation("PowerFactory Update"):
            data_capture_list, updates = up.update_pf(app, dev_list, data_capture_list)

        logger.info(f"Update complete. Changes made: {updates}")

        # Create output file
        save_file = create_save_file(app, prjt, called_function)
        if save_file:
            write_data(app, data_capture_list, save_file)
            logger.info(f"Results saved to: {save_file}", pf_output=False)

        # Print results summary
        if not batch:
            print_results(app, data_capture_list)

    # Final summary
    stop_time = time.strftime("%H:%M:%S")
    logger.info(f"Script finished at {stop_time}")

    if updates:
        logger.info("Settings were updated for selected devices")
    else:
        logger.info("No setting changes were required")

    return updates


def format_time(seconds):
    """
    Format seconds into human-readable time string.

    Args:
        seconds: Number of seconds

    Returns:
        Formatted string like "2 hours 30 minutes 15 seconds"
    """
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


def create_save_file(app, prjt, called_function):
    """
    Create the output file path for saving results.

    Args:
        app: PowerFactory application object
        prjt: Active project object
        called_function: True if called from another script

    Returns:
        File path string, or None if file already exists (for batch)
    """
    project_name = prjt.GetAttribute("loc_name")
    current_user = app.GetCurrentUser()
    current_user_name = current_user.GetAttribute("loc_name")
    parent_folder = prjt.GetAttribute("fold_id")
    parent_folder_name = parent_folder.GetAttribute("loc_name")

    file_name = f"{current_user_name}_{parent_folder_name}_{project_name}".replace(
        "/", "_"
    )

    if called_function:
        file_location = r"\\ecasd01\WksMgmt\PowerFactory\ScriptsDEV\IPSDataTransferMastering\Script_Results"
    else:
        file_location = r"C:\LocalData\PowerFactory Output Folders\IPS Data Transfer"

    main_file_name = select_main_file(
        app, file_name, file_location, called_function
    )
    return main_file_name


def select_main_file(app, file_name, location, called_function):
    """
    Check folder structure and create output CSV file path.

    Args:
        app: PowerFactory application object
        file_name: Base file name
        location: Directory path
        called_function: True if called from another script

    Returns:
        Full file path, or None if file was recently created
    """
    # Handle Citrix environment
    citrix = os.path.isdir("\\\\Client\\C$\\localdata")
    if citrix and "C:" in location:
        location = "\\\\Client\\" + location.replace("C:", "C$")

    # Create directory if needed
    if not os.path.isdir(location):
        os.makedirs(location)
        logger.info(f"Created output directory: {location}", pf_output=False)

    set_file_name = os.path.join(location, f"{file_name}.csv")

    # Check for existing file
    try:
        last_mod_time = os.stat(set_file_name).st_mtime
        if called_function:
            check_time = time.time() - (24 * 60 * 60)
        else:
            check_time = last_mod_time

        if check_time < last_mod_time:
            logger.info("Project had already been studied recently", pf_output=False)
            return None

        os.remove(set_file_name)
    except FileNotFoundError:
        pass

    return set_file_name


def determine_region(prjt):
    """
    Determine the region (Energex/Ergon) based on project folder structure.

    Args:
        prjt: Active project object

    Returns:
        "Energex" or "Ergon"
    """
    base_prjt = prjt.der_baseproject
    if not base_prjt:
        base_prjt_fld = prjt.fold_id.loc_name
    else:
        base_prjt_fld = prjt.der_baseproject.fold_id.loc_name

    if base_prjt_fld == "SEQ Models":
        region = "Energex"
    else:
        region = "Ergon"

    return region


def write_data(app, update_info_list, main_file_name):
    """
    Write results to CSV file.

    Args:
        app: PowerFactory application object
        update_info_list: List of result dictionaries
        main_file_name: Output file path
    """
    # Collect all column headings
    col_headings = []
    for update_dict in update_info_list:
        for key in update_dict:
            if key not in col_headings:
                col_headings.append(key)

    # Write CSV
    with open(main_file_name, "a", newline="", encoding="UTF-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=col_headings)
        writer.writeheader()
        for data in update_info_list:
            writer.writerow(data)

    logger.debug(f"Wrote {len(update_info_list)} records to {main_file_name}", pf_output=False)


def print_results(app, data_capture_list):
    """
    Print results summary to PowerFactory output window.

    Args:
        app: PowerFactory application object
        data_capture_list: List of result dictionaries
    """
    # Get device dictionary for name lookup
    devices_list, device_object_dict = dev.prot_device(app)

    print_string = ""

    for i, info in enumerate(data_capture_list):
        # Batch print every 40 lines
        if i % 40 == 0 and print_string:
            logger.info(print_string)
            print_string = ""

        # Get device reference
        try:
            device = info["PLANT_NUMBER"]
            pf_device = device_object_dict[device][0]
        except KeyError:
            try:
                pf_device = info["CB_NAME"]
            except KeyError:
                pf_device = info.get("PLANT_NUMBER", "Unknown")

        # Get result
        result = info.get("RESULT", "Updated Successfully")

        print_string += f"\n{pf_device}    Result = {result}"

    # Print remaining
    if print_string:
        logger.info(print_string)


if __name__ == "__main__":
    # Optional: Configure file logging
    # configure_logging(
    #     log_file=r"C:\LocalData\logs\ips_transfer.log",
    #     level=logging.DEBUG
    # )

    updates = main()
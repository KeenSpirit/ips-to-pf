"""
Main orchestration module for IPS settings retrieval.

This module coordinates the retrieval of protection device settings from
the IPS database and their association with PowerFactory devices. It handles
both Energex (SEQ) and Ergon regional configurations.

The module uses SettingIndex for efficient O(1) lookups instead of
linear scans through raw setting lists.
"""

import logging
import sys
from typing import List, Tuple, Optional, Dict, Any, Union

# Import paths from config
from config.paths import RELAY_SKELETONS_PATH

sys.path.append(RELAY_SKELETONS_PATH)
import add_protection_relay_skeletons

from core import ProtectionDevice, UpdateResult
from ips_data import query_database as qd
from ips_data import ee_settings as ee
from ips_data import ex_settings as ex
from ips_data.setting_index import SettingIndex
from utils.pf_utils import get_all_protection_devices
from ui.device_selection import user_selection

logger = logging.getLogger(__name__)


def get_ips_settings(
    app,
    region: str,
    batch: bool,
    called_function: bool
) -> Tuple[List[ProtectionDevice], List[UpdateResult]]:
    """
    Retrieve IPS settings and create ProtectionDevice objects.

    This is the main entry point for getting IPS data. It:
    1. Creates an indexed lookup structure from IPS setting IDs
    2. Gets the devices to process (either user-selected or all)
    3. Loads detailed settings for each device
    4. Associates CT/VT settings

    Args:
        app: PowerFactory application object
        region: "Energex" or "Ergon"
        batch: True for batch update mode
        called_function: True if called from another script

    Returns:
        Tuple of (list_of_devices, data_capture_list) where:
        - list_of_devices: ProtectionDevice objects with settings
        - data_capture_list: UpdateResult objects for reporting
    """
    data_capture_list: List[UpdateResult] = []

    # Create indexed setting ID lookup (O(1) access)
    setting_index = qd.get_setting_ids(app, region)
    logger.info(f"Created setting index with {len(setting_index)} records")

    # Get selected devices and their setting IDs
    set_ids, device_list, data_capture_list = _get_selected_devices(
        app, batch, region, data_capture_list, setting_index, called_function
    )

    # Load detailed settings for all devices
    ips_settings, ips_it_settings = qd.batch_settings(
        app, region, called_function, set_ids
    )

    # Associate settings with each device
    _associate_device_settings(
        app, device_list, ips_settings, ips_it_settings,
        region, called_function
    )

    return device_list, data_capture_list


def _get_selected_devices(
    app,
    batch: bool,
    region: str,
    data_capture_list: List[UpdateResult],
    setting_index: SettingIndex,
    called_function: bool
) -> Tuple[List[str], List[ProtectionDevice], List[UpdateResult]]:
    """
    Get the list of devices to process based on mode and user selection.

    Args:
        app: PowerFactory application object
        batch: True for batch mode
        region: "Energex" or "Ergon"
        data_capture_list: List to append status records to
        setting_index: Indexed IPS settings
        called_function: True if called from another script

    Returns:
        Tuple of (setting_ids, device_list, data_capture_list)
    """
    failed_cbs: List = []
    set_ids: List[str] = []
    device_list: List[ProtectionDevice] = []

    if not batch:
        # Interactive mode - get user selection first
        result = _get_user_selected_devices(
            app, region, data_capture_list, setting_index
        )
        set_ids, device_list, data_capture_list = result

    if batch or set_ids == "Batch":
        # Batch mode - process all devices
        if region == "Energex":
            app.PrintInfo("Creating a list of Setting IDs for all Energex devices")
            device_list, failed_cbs, set_ids = ex.create_new_devices(
                app, setting_index, called_function
            )
        else:
            # Add relay skeletons for Ergon
            add_protection_relay_skeletons.main(app)
            app.ClearOutputWindow()
            app.PrintInfo("Creating a list of Setting IDs for all Ergon devices")
            set_ids, device_list, data_capture_list = ee.ergon_all_dev_list(
                app, data_capture_list, setting_index, called_function
            )

    # Record failed CBs using UpdateResult
    for cb in failed_cbs:
        data_capture_list.append(UpdateResult.failed_cb(cb))

    return set_ids, device_list, data_capture_list


def _get_user_selected_devices(
    app,
    region: str,
    data_capture_list: List[UpdateResult],
    setting_index: SettingIndex
) -> Tuple[Any, List[ProtectionDevice], List[UpdateResult]]:
    """
    Get devices based on user selection through GUI.

    Args:
        app: PowerFactory application object
        region: "Energex" or "Ergon"
        data_capture_list: List to append status records to
        setting_index: Indexed IPS settings

    Returns:
        Tuple of (setting_ids or "Batch", device_list, data_capture_list)
    """
    # Get all protection devices in the model
    devices, device_dict = get_all_protection_devices(app)

    # Show selection dialog
    selections = user_selection(app, device_dict)

    if not selections:
        message = "User has selected to exit the script"
        logger.info(message)
        qd.error_message(app, message)

    if selections == "Batch":
        return "Batch", [], data_capture_list

    # Process selections based on region
    if region == "Energex":
        setting_ids, device_list = ex.ex_device_list(
            app, selections, device_dict, setting_index
        )
    else:  # Ergon
        setting_ids, device_list, data_capture_list = ee.ee_device_list(
            app, selections, device_dict, setting_index, data_capture_list
        )

    return setting_ids, device_list, data_capture_list


def _associate_device_settings(
    app,
    device_list: List[ProtectionDevice],
    ips_settings: Dict[str, List[Dict]],
    ips_it_settings: List,
    region: str,
    called_function: bool
) -> None:
    """
    Associate detailed settings with each device.

    This includes relay settings and CT/VT instrument transformer settings.

    Args:
        app: PowerFactory application object
        device_list: List of ProtectionDevice objects
        ips_settings: Dictionary of relay settings by setting ID
        ips_it_settings: List of instrument transformer settings
        region: "Energex" or "Ergon"
        called_function: True if batch mode
    """
    total = len(device_list)

    for i, device_object in enumerate(device_list):
        if i % 10 == 0:
            app.PrintInfo(
                f"Device {i} of {total} has had its setting attributes assigned"
            )

        if not device_object.device:
            continue

        # Load relay settings for batch runs
        # (Non-batch runs already loaded settings during device creation)
        if called_function and ips_settings:
            device_object.associated_settings(ips_settings)

        # Load CT/VT settings
        if ips_it_settings:
            if region == "Energex":
                device_object.seq_instrument_attributes(ips_it_settings)
            else:
                device_object.reg_instrument_attributes(ips_it_settings)

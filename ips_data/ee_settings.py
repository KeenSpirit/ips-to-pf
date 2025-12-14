"""
Ergon (EE) regional settings processing for IPS to PowerFactory transfer.

This module handles the Ergon-specific logic for:
- Extracting plant numbers from device names
- Matching PowerFactory devices to IPS setting records
- Creating ProtectionDevice objects with associated settings

The module uses SettingIndex for efficient O(1) lookups instead of
linear scans through the settings list.
"""

import logging
from typing import Dict, List, Optional, Tuple, Any, Union

import devices as dev
from ips_data import query_database as qd
from ips_data.setting_index import SettingIndex, SettingRecord

logger = logging.getLogger(__name__)


def ee_device_list(
    app,
    selections: List[str],
    device_dict: Dict[str, List],
    setting_index: SettingIndex,
    data_capture_list: List[Dict]
) -> Tuple[List[str], List[dev.ProtectionDevice], List[Dict]]:
    """
    Create device list for user-selected Ergon devices.
    
    Processes the user's device selections and creates ProtectionDevice
    objects with their associated IPS settings.
    
    Args:
        app: PowerFactory application object
        selections: List of device names selected by user
        device_dict: Dictionary mapping device names to [pf_obj, class, phases, feeder, sub]
        setting_index: Indexed IPS settings for O(1) lookups
        data_capture_list: List to append status/error records to
        
    Returns:
        Tuple of (setting_ids, list_of_devices, data_capture_list)
    """
    list_of_devices: List[dev.ProtectionDevice] = []
    setting_ids: List[str] = []

    for i, device_name in enumerate(selections):
        if i % 10 == 0:
            app.PrintInfo(f"IPS is being checked for device {i} of {len(selections)}")
        
        plant_number = get_plant_number(device_name)
        pf_device = device_dict[device_name][0]
        
        if not plant_number:
            data_capture_list.append(_create_info_dict(pf_device, "Not a protection device"))
            continue
        
        # Handle non-relay devices (fuses)
        if device_dict[device_name][1] != "ElmRelay":
            fuse_result = _process_fuse_device(app, pf_device, list_of_devices)
            if fuse_result == "skip":
                continue
            elif fuse_result == "failed":
                data_capture_list.append(_create_info_dict(pf_device, "FAILED FUSE"))
                continue
            fuse_type, fuse_size = fuse_result
        else:
            fuse_type = None
            fuse_size = None
        
        # Look up setting in index and create device
        setting_ids, list_of_devices = _get_setting_id_indexed(
            app=app,
            plant_number=plant_number,
            list_of_devices=list_of_devices,
            setting_ids=setting_ids,
            pf_device=pf_device,
            fuse_type=fuse_type,
            fuse_size=fuse_size,
            setting_index=setting_index,
            called_function=False,
        )
    
    return setting_ids, list_of_devices, data_capture_list


def ergon_all_dev_list(
    app,
    data_capture_list: List[Dict],
    setting_index: SettingIndex,
    called_function: bool
) -> Tuple[List[str], List[dev.ProtectionDevice], List[Dict]]:
    """
    Process all protection devices in the active Ergon project.
    
    This is used for batch updates where all devices are processed
    rather than a user selection.
    
    Args:
        app: PowerFactory application object
        data_capture_list: List to append status/error records to
        setting_index: Indexed IPS settings for O(1) lookups
        called_function: True if called from batch update
        
    Returns:
        Tuple of (setting_ids, list_of_devices, data_capture_list)
    """
    prot_devices = get_all_protection_devices(app)
    list_of_devices: List[dev.ProtectionDevice] = []
    setting_ids: List[str] = []
    
    for i, pf_device in enumerate(prot_devices):
        if i % 10 == 0:
            app.PrintInfo(f"IPS is being checked for device {i} of {len(prot_devices)}")
        
        # Delete duplicate devices (names ending with parentheses)
        if pf_device.loc_name.endswith(")"):
            pf_device.Delete()
            continue
        
        plant_number = get_plant_number(pf_device.loc_name)
        
        if not plant_number:
            data_capture_list.append(_create_info_dict(pf_device, "Not a protection device"))
            continue
        
        # Handle non-relay devices (fuses)
        if pf_device.GetClassName() != "ElmRelay":
            fuse_result = _process_fuse_device(app, pf_device, list_of_devices)
            if fuse_result == "skip":
                continue
            elif fuse_result == "failed":
                data_capture_list.append(_create_info_dict(pf_device, "FAILED FUSE"))
                continue
            fuse_type, fuse_size = fuse_result
        else:
            fuse_type = None
            fuse_size = None
        
        # Look up setting in index and create device
        setting_ids, list_of_devices = _get_setting_id_indexed(
            app=app,
            plant_number=plant_number,
            list_of_devices=list_of_devices,
            setting_ids=setting_ids,
            pf_device=pf_device,
            fuse_type=fuse_type,
            fuse_size=fuse_size,
            setting_index=setting_index,
            called_function=called_function,
        )
    
    return setting_ids, list_of_devices, data_capture_list


def _process_fuse_device(
    app,
    pf_device,
    list_of_devices: List[dev.ProtectionDevice]
) -> Union[str, Tuple[str, str]]:
    """
    Process a fuse device and determine if it should be added to the list.
    
    Args:
        app: PowerFactory application object
        pf_device: The PowerFactory fuse object
        list_of_devices: List to potentially add device to
        
    Returns:
        "skip" if device should be skipped (Tx fuse added to list)
        "failed" if fuse type couldn't be determined
        (fuse_type, fuse_size) tuple otherwise
    """
    fuse_type, fuse_size = dev.determine_fuse_type(app, pf_device)
    
    if fuse_type == "Tx Fuse":
        prot_dev = dev.ProtectionDevice(
            app, fuse_type, pf_device.loc_name, None, None, pf_device, None
        )
        prot_dev.fuse_size = fuse_size
        prot_dev.fuse_type = fuse_type
        list_of_devices.append(prot_dev)
        return "skip"
    
    if not fuse_type:
        return "failed"
    
    return (fuse_type, fuse_size)


def get_plant_number(device_name: str) -> Optional[str]:
    """
    Extract plant number from a device name.
    
    Plant numbers have specific structures depending on device type:
    - Reclosers: RC-{Number} or RE-{Number}
    - Relays: {SUB}SS-{BAY}-{Device}
    - Fuses: DO-{Number}, FU-{Number}, or DL-{Number}
    
    Args:
        device_name: The full device name from PowerFactory
        
    Returns:
        The extracted plant number, or None if not a valid protection device name
    """
    # Check if name matches expected patterns
    valid_patterns = [
        device_name[4:7] == "SS-",  # Relay pattern
        device_name[:3] == "RC-",   # Recloser
        device_name[:3] == "RE-",   # Recloser
        device_name[:3] == "DO-",   # Dropout fuse
        device_name[:3] == "FU-",   # Fuse
        device_name[:3] == "DL-",   # Distribution line fuse
    ]
    
    if not any(valid_patterns):
        return None
    
    # Extract plant number (everything before first space)
    return device_name.split(" ")[0]


def get_all_protection_devices(app) -> List:
    """
    Get all active protection devices in the current project.
    
    Args:
        app: PowerFactory application object
        
    Returns:
        List of relay and fuse PowerFactory objects
    """
    net_mod = app.GetProjectFolder("netmod")
    
    # Get all relays that are in valid locations and active
    all_relays = net_mod.GetContents("*.ElmRelay", True)
    relays = [
        relay for relay in all_relays
        if relay.GetAttribute("cpGrid")
        and relay.cpGrid.IsCalcRelevant()
        and relay.GetParent().GetClassName() == "StaCubic"
    ]
    
    # Get all fuses that are active
    all_fuses = net_mod.GetContents("*.RelFuse", True)
    fuses = [
        fuse for fuse in all_fuses
        if fuse.GetAttribute("cpGrid")
        and fuse.cpGrid.IsCalcRelevant()
    ]
    
    return relays + fuses


def _get_setting_id_indexed(
    app,
    plant_number: str,
    list_of_devices: List[dev.ProtectionDevice],
    setting_ids: List[str],
    pf_device,
    fuse_type: Optional[str],
    fuse_size: Optional[str],
    setting_index: SettingIndex,
    called_function: bool,
) -> Tuple[List[str], List[dev.ProtectionDevice]]:
    """
    Find setting ID(s) for a device using the indexed lookup.
    
    This replaces the original reg_get_setting_id function with O(1) lookups
    instead of O(n) linear scans.
    
    Args:
        app: PowerFactory application object
        plant_number: The plant number to look up
        list_of_devices: List to append new devices to
        setting_ids: List to append found setting IDs to
        pf_device: The PowerFactory device object
        fuse_type: Type of fuse if applicable
        fuse_size: Size of fuse if applicable
        setting_index: The indexed settings for O(1) lookup
        called_function: True if called from batch update
        
    Returns:
        Tuple of (updated setting_ids, updated list_of_devices)
    """
    # First try exact match (O(1) lookup)
    exact_matches = setting_index.get_by_asset_exact(plant_number)
    
    if exact_matches:
        # Found exact match - use it
        for record in exact_matches:
            device = _create_device_from_record(
                app, record, pf_device, fuse_type, fuse_size, called_function
            )
            if device:
                list_of_devices.append(device)
                setting_ids.append(record.relaysettingid)
        return setting_ids, list_of_devices
    
    # Try partial match (device name contained in asset name)
    partial_matches = setting_index.get_by_asset_contains(plant_number)
    
    if partial_matches:
        # Handle multiple devices in a single cubicle
        pf_device_name = pf_device.loc_name
        
        for record in partial_matches:
            asset_name = record.assetname
            
            # Try to find or create the appropriate PF device
            target_device = _find_or_create_relay(
                pf_device, pf_device_name, asset_name
            )
            
            if target_device:
                device = _create_device_from_record(
                    app, record, target_device, fuse_type, fuse_size, called_function
                )
                if device:
                    list_of_devices.append(device)
                    setting_ids.append(record.relaysettingid)
        
        if partial_matches:
            return setting_ids, list_of_devices
    
    # No match found - create device without settings
    no_setting_device = dev.ProtectionDevice(
        app, None, None, None, None, pf_device, None
    )
    no_setting_device.fuse_type = fuse_type
    no_setting_device.fuse_size = fuse_size
    list_of_devices.append(no_setting_device)
    
    return setting_ids, list_of_devices


def _create_device_from_record(
    app,
    record: SettingRecord,
    pf_device,
    fuse_type: Optional[str],
    fuse_size: Optional[str],
    called_function: bool
) -> Optional[dev.ProtectionDevice]:
    """
    Create a ProtectionDevice from a SettingRecord.
    
    Args:
        app: PowerFactory application object
        record: The IPS setting record
        pf_device: The PowerFactory device object
        fuse_type: Type of fuse if applicable
        fuse_size: Size of fuse if applicable
        called_function: True if called from batch update
        
    Returns:
        ProtectionDevice object or None if creation failed
    """
    prot_dev = dev.ProtectionDevice(
        app,
        record.patternname,
        record.assetname,
        record.relaysettingid,
        record.datesetting,
        pf_device,
        None,
    )
    
    # Load settings if not a batch call
    if not called_function:
        ips_settings = qd.reg_get_ips_settings(app, record.relaysettingid)
        prot_dev.associated_settings(ips_settings)
    
    prot_dev.fuse_type = fuse_type
    prot_dev.fuse_size = fuse_size
    
    return prot_dev


def _find_or_create_relay(
    pf_device,
    pf_device_name: str,
    asset_name: str
):
    """
    Find an existing relay with the asset name or create/rename one.
    
    This handles cases where multiple relays exist in a single cubicle.
    
    Args:
        pf_device: The original PowerFactory device
        pf_device_name: Original device name
        asset_name: The IPS asset name to match
        
    Returns:
        The PowerFactory device to use (existing, renamed, or new)
    """
    cubicle = pf_device.fold_id
    
    # Check if a device with this name already exists
    for device in cubicle.GetContents("*.ElmRelay"):
        if device.loc_name == asset_name:
            return device
        elif device.loc_name == pf_device_name:
            # Rename the original device
            device.loc_name = asset_name
            return device
    
    # Create new device in the cubicle
    return cubicle.CreateObject("ElmRelay", asset_name)


def _create_info_dict(pf_device, result: str) -> Dict[str, str]:
    """
    Create a status/info dictionary for a device.
    
    Args:
        pf_device: The PowerFactory device object
        result: The result/status message
        
    Returns:
        Dictionary with substation, plant number, and result
    """
    return {
        "SUBSTATION": pf_device.GetAttribute("r:cpGrid:e:loc_name"),
        "PLANT_NUMBER": pf_device.loc_name,
        "RESULT": result,
    }


# =============================================================================
# Legacy compatibility functions
# =============================================================================

def reg_get_setting_id(
    app,
    device: str,
    list_of_devices: List,
    setting_ids: List[str],
    pf_device,
    fuse_type: Optional[str],
    fuse_size: Optional[str],
    ids_dict_list: List[Dict],
    called_function: bool,
) -> Tuple[List[str], List]:
    """
    Legacy function for backward compatibility.
    
    DEPRECATED: This function performs O(n) linear scans. Use 
    _get_setting_id_indexed() with a SettingIndex instead.
    
    Args:
        app: PowerFactory application object
        device: Device/plant number to look up
        list_of_devices: List to append new devices to
        setting_ids: List to append found setting IDs to
        pf_device: The PowerFactory device object
        fuse_type: Type of fuse if applicable
        fuse_size: Size of fuse if applicable
        ids_dict_list: Raw list of setting dictionaries
        called_function: True if called from batch update
        
    Returns:
        Tuple of (updated setting_ids, updated list_of_devices)
    """
    logger.warning(
        "reg_get_setting_id() is deprecated. "
        "Use _get_setting_id_indexed() with SettingIndex instead."
    )
    
    # Create temporary index for this call
    from ips_data.setting_index import create_setting_index
    temp_index = create_setting_index(ids_dict_list, "Ergon")
    
    return _get_setting_id_indexed(
        app=app,
        plant_number=device,
        list_of_devices=list_of_devices,
        setting_ids=setting_ids,
        pf_device=pf_device,
        fuse_type=fuse_type,
        fuse_size=fuse_size,
        setting_index=temp_index,
        called_function=called_function,
    )


def info_dict(pf_device, result: str) -> Dict[str, str]:
    """
    Legacy wrapper for _create_info_dict.
    
    DEPRECATED: Use _create_info_dict() instead.
    """
    return _create_info_dict(pf_device, result)

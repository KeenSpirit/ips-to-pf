"""
Energex (EX/SEQ) settings processing for IPS to PowerFactory transfer.

This module handles the Energex-specific logic for:
- Matching PowerFactory switches to IPS relay setting records
- Handling double cable box configurations
- Creating ProtectionDevice objects with associated settings

The module uses SettingIndex for efficient O(1) lookups instead of
linear scans through the settings list.
"""

import logging
from typing import Dict, List, Optional, Tuple, Set, Any

from ips_data import query_database as qd
from ips_data.cb_mapping import get_cb_alt_name_list
from ips_data.setting_index import SettingIndex, SettingRecord
from core import ProtectionDevice

logger = logging.getLogger(__name__)

def ex_device_list(
    app,
    selections: List[str],
    device_dict: Dict[str, List],
    setting_index: SettingIndex
) -> Tuple[List[str], List[ProtectionDevice]]:
    """
    Create device list for user-selected Energex devices.
    
    Converts protection device selections to their associated PowerFactory 
    switches, then maps switch names to IPS relay setting IDs.
    
    Args:
        app: PowerFactory application object
        selections: List of device names selected by user
        device_dict: Dictionary mapping device names to [pf_obj, class, phases, feeder, sub]
        setting_index: Indexed IPS settings for O(1) lookups
        
    Returns:
        Tuple of (setting_ids, list_of_devices)
    """
    prjt = app.GetActiveProject()
    raw_switches = prjt.GetContents("*.StaSwitch", True) + prjt.GetContents("*.ElmCoup", True)
    
    # Get unique switches for selected devices
    switches = _get_switches_for_selections(app, selections, device_dict, raw_switches)
    
    # Convert switches to setting IDs and devices
    cb_alt_name_list = get_cb_alt_name_list(app)
    list_of_devices: List[ProtectionDevice] = []
    setting_ids: List[str] = []
    
    for switch in switches:
        new_ids, list_of_devices = _get_setting_id_indexed(
            app=app,
            switch=switch,
            list_of_devices=list_of_devices,
            setting_index=setting_index,
            called_function=False,
            cb_alt_name_list=cb_alt_name_list,
        )
        setting_ids.extend(new_ids)
    
    # Filter to only include explicitly selected devices
    list_of_devices = _filter_to_selections(list_of_devices, selections, device_dict)
    
    return setting_ids, list_of_devices


def _get_switches_for_selections(
    app,
    selections: List[str],
    device_dict: Dict[str, List],
    raw_switches: List
) -> List:
    """
    Get unique switches associated with the selected devices.
    
    Args:
        app: PowerFactory application object
        selections: List of selected device names
        device_dict: Device information dictionary
        raw_switches: All switches in the project
        
    Returns:
        List of unique switch objects
    """
    switches = []
    
    for i, device in enumerate(selections):
        if i % 10 == 0:
            app.PrintInfo(f"Finding switch for device {i} of {len(selections)}")
        
        # Extract base device name (before underscore)
        device_name = device.split("_")[0]
        
        pf_device = device_dict[device][0]
        assoc_switch = _get_assoc_switch(pf_device, raw_switches)
        
        if assoc_switch and assoc_switch not in switches:
            switches.append(assoc_switch)
    
    return switches


def _filter_to_selections(
    list_of_devices: List[ProtectionDevice],
    selections: List[str],
    device_dict: Dict[str, List]
) -> List[ProtectionDevice]:
    """
    Filter device list to only include explicitly selected devices.
    
    Args:
        list_of_devices: All devices found
        selections: User's selections
        device_dict: Device information dictionary
        
    Returns:
        Filtered list of devices
    """
    filtered = []
    
    for device in list_of_devices:
        # Build possible name variations
        if device.device_id:
            name_v1 = f"{device.name}_{device.device_id}".rstrip()
            name_v2 = f"{device.name}_{device.device_id}_{device.seq_name}".rstrip()
        else:
            name_v1 = f"{device.name}_{device.seq_name}".rstrip()
            name_v2 = None
        
        # Check if any variation is in selections
        if name_v1 in selections:
            device.pf_obj = device_dict[name_v1][0]
            filtered.append(device)
        elif name_v2 and name_v2 in selections:
            device.pf_obj = device_dict[name_v2][0]
            filtered.append(device)
    
    logger.info(f"Filtered to {len(filtered)} devices from {len(list_of_devices)} found")
    return filtered


def create_new_devices(
    app,
    setting_index: SettingIndex,
    called_function: bool
) -> Tuple[List[ProtectionDevice], List, List[str]]:
    """
    Batch update for Energex (SEQ) models.
    
    Processes all switches in the active project, finding or creating
    protection devices based on IPS data.
    
    Args:
        app: PowerFactory application object
        setting_index: Indexed IPS settings for O(1) lookups
        called_function: True if called from batch update
        
    Returns:
        Tuple of (list_of_devices, failed_cbs, setting_ids)
    """
    prjt = app.GetActiveProject()
    cb_alt_name_list = get_cb_alt_name_list(app)
    
    # Get all valid switches
    switches = _get_valid_switches(prjt)
    
    failed_cbs: List = []
    setting_ids: List[str] = []
    list_of_devices: List[ProtectionDevice] = []
    
    for i, switch in enumerate(switches):
        if i % 10 == 0:
            app.PrintInfo(f"IPS is being checked for switch {i} of {len(switches)}")
        
        # Skip certain ElmCoup switches
        if not _should_process_switch(switch):
            continue
        
        initial_count = len(setting_ids)
        
        new_ids, list_of_devices = _get_setting_id_indexed(
            app=app,
            switch=switch,
            list_of_devices=list_of_devices,
            setting_index=setting_index,
            called_function=called_function,
            cb_alt_name_list=cb_alt_name_list,
        )
        setting_ids.extend(new_ids)
        
        # Handle switches with no IPS data found
        if len(setting_ids) == initial_count:
            _handle_unmatched_switch(switch, failed_cbs)
    
    # Create/assign PowerFactory objects for all devices
    list_of_devices = _assign_pf_objects(list_of_devices)
    
    return list_of_devices, failed_cbs, setting_ids


def _get_valid_switches(prjt) -> List:
    """
    Get all valid switches for processing.
    
    Args:
        prjt: Active PowerFactory project
        
    Returns:
        List of valid switch objects
    """
    raw_switches = prjt.GetContents("*.StaSwitch", True) + prjt.GetContents("*.ElmCoup", True)
    
    return [
        switch for switch in raw_switches
        if switch.GetAttribute("cpGrid")
        and not switch.IsOutOfService()
        and switch.IsCalcRelevant()
        and switch.IsEnergized()
    ]


def _should_process_switch(switch) -> bool:
    """
    Determine if a switch should be processed for protection devices.
    
    Args:
        switch: The switch object to check
        
    Returns:
        True if switch should be processed
    """
    try:
        # Skip ElmCoup switches with numeric third character (not feeder bays)
        int(switch.loc_name[2])
        if switch.GetClassName() != "StaSwitch":
            return False
    except (ValueError, IndexError):
        pass
    
    try:
        if switch.GetClassName() == "StaSwitch":
            if not switch.GetAttribute("r:fold_id:r:obj_id:e:loc_name"):
                return False
    except AttributeError:
        return False
    
    return True


def _handle_unmatched_switch(switch, failed_cbs: List) -> None:
    """
    Handle a switch that has no matching IPS protection devices.
    
    Deletes any existing protection devices and records the switch as failed.
    
    Args:
        switch: The unmatched switch
        failed_cbs: List to append failed CBs to
    """
    # Get contents to clean up
    if switch.GetClassName() == "StaSwitch":
        contents = switch.fold_id.GetContents()
    else:
        root_cub = switch.GetCubicle(0)
        contents = root_cub.GetContents() if root_cub else []
    
    # Delete existing protection devices
    for content in contents:
        if content.GetClassName() in ["ElmRelay", "RelFuse", "StaCt"]:
            content.Delete()
    
    # Record CB as failed if it's a circuit breaker
    if switch.GetClassName() == "ElmCoup" and switch.GetAttribute("e:aUsage") == "cbk":
        if switch not in failed_cbs:
            failed_cbs.append(switch)


def _assign_pf_objects(
    list_of_devices: List[ProtectionDevice]
) -> List[ProtectionDevice]:
    """
    Create or assign PowerFactory objects for all devices.
    
    Args:
        list_of_devices: List of devices needing PF objects
        
    Returns:
        Updated list with PF objects assigned
    """
    used_names: Set[str] = set()
    result: List[ProtectionDevice] = []
    
    for device in list_of_devices:
        device_name = _get_device_name(device, used_names)
        used_names.add(device_name)
        
        switch = device.switch
        pf_obj = _find_or_create_pf_device(switch, device_name)
        
        if pf_obj and pf_obj.loc_name == device_name:
            device.pf_obj = pf_obj
            result.append(device)
        elif pf_obj:
            pf_obj.Delete()
    
    return result


def _get_device_name(device: ProtectionDevice, used_names: Set[str]) -> str:
    """
    Generate the PowerFactory device name.
    
    Args:
        device: The protection device
        used_names: Set of already-used names
        
    Returns:
        The device name to use
    """
    if not device.device_id:
        return f"{device.name}_{device.seq_name}".rstrip()
    
    base_name = f"{device.name}_{device.device_id}".rstrip()
    
    if base_name in used_names:
        return f"{device.name}_{device.device_id}_{device.seq_name}".rstrip()
    
    return base_name


def _find_or_create_pf_device(switch, device_name: str):
    """
    Find existing or create new PowerFactory protection device.
    
    Args:
        switch: The associated switch object
        device_name: Name for the device
        
    Returns:
        The PowerFactory device object
    """
    if switch.GetClassName() == "StaSwitch":
        cubicle = switch.fold_id
    else:
        cubicle = switch.GetCubicle(0)
    
    if not cubicle:
        return None
    
    # Check for existing device
    contents = cubicle.GetContents(f"{device_name}.ElmRelay")
    contents += cubicle.GetContents(f"{device_name}.RelFuse")
    
    if contents:
        return contents[0]
    
    # Create new device
    return cubicle.CreateObject("ElmRelay", device_name)


def _get_assoc_switch(pf_device, raw_switches: List):
    """
    Find the switch associated with a protection device.
    
    Args:
        pf_device: The PowerFactory protection device
        raw_switches: List of all switches
        
    Returns:
        The associated switch object or None
    """
    for switch in raw_switches:
        try:
            if switch.GetClassName() == "StaSwitch":
                cub = switch.fold_id
                for obj in cub.GetContents():
                    if obj.loc_name == pf_device.loc_name:
                        return switch
            else:
                # Check both bus1 and bus2 for ElmCoup
                for bus_attr in ["bus1", "bus2"]:
                    cub = getattr(switch, bus_attr, None)
                    if cub:
                        for obj in cub.GetContents():
                            if obj == pf_device:
                                return switch
        except AttributeError:
            pass
    
    return None


def _get_setting_id_indexed(
    app,
    switch,
    list_of_devices: List[ProtectionDevice],
    setting_index: SettingIndex,
    called_function: bool,
    cb_alt_name_list: List[Dict],
) -> Tuple[List[str], List[ProtectionDevice]]:
    """
    Find setting IDs for a switch using indexed lookup.
    
    The index handles double cable box expansion (e.g., "NIP1A+B" is indexed
    under both "NIP1A" and "NIP1B"), so a simple lookup by switch_name will
    return all matching records including those from combined devices.
    
    Note: Devices with identical attributes but different switches are allowed
    by design. The same setting record may create multiple device objects if
    it protects multiple switches (e.g., "NIP1A+B" creates devices for both
    switch "NIP1A" and switch "NIP1B"). This is handled later in the
    update_powerfactory portion of the script.
    
    Args:
        app: PowerFactory application object
        switch: The switch to find settings for
        list_of_devices: List to append new devices to
        setting_index: Indexed IPS settings
        called_function: True if batch update
        cb_alt_name_list: CB name mapping list
        
    Returns:
        Tuple of (new_setting_ids, updated list_of_devices)
    """
    setting_ids: List[str] = []
    
    # Get switch name (potentially mapped)
    switch_name, sub_code = _get_switch_info(switch, cb_alt_name_list)
    
    if len(switch_name) < 4:
        return setting_ids, list_of_devices
    
    # Look up matching records (O(1) lookup)
    # The index already handles "A+B" expansion, so "NIP1A+B" is indexed under
    # both "NIP1A" and "NIP1B"
    records = setting_index.get_by_switch_name(switch_name, sub_code)
    
    # Create devices from matching records
    for record in records:
        device = _create_device_from_record(
            app, record, switch, called_function
        )
        
        if device:
            # Add to list - duplicates with different switches are allowed by design
            # Each setting ID that matches a switch creates a device object
            list_of_devices.append(device)
            setting_ids.append(record.relaysettingid)
    
    return setting_ids, list_of_devices


def _get_switch_info(switch, cb_alt_name_list: List[Dict]) -> Tuple[str, Optional[str]]:
    """
    Get switch name and substation code for lookup.
    
    Args:
        switch: The switch object
        cb_alt_name_list: CB name mapping list
        
    Returns:
        Tuple of (switch_name, substation_code)
    """
    # Check for name mapping
    for cb_dict in cb_alt_name_list:
        if (cb_dict["SUBSTATION"] == switch.fold_id.loc_name and 
            cb_dict["CB_NAME"] == switch.loc_name):
            pf_switch_name = cb_dict["NEW_NAME"]
            break
    else:
        pf_switch_name = switch.loc_name
    
    # Extract base name (before underscore)
    switch_name = pf_switch_name.split("_")[0]
    
    # Get substation code for ElmCoup switches
    sub_code = None
    if switch.GetClassName() == "ElmCoup":
        sub_code = switch.fold_id.loc_name
    
    return switch_name, sub_code


def _create_device_from_record(
    app,
    record: SettingRecord,
    switch,
    called_function: bool
) -> Optional[ProtectionDevice]:
    """
    Create a ProtectionDevice from a SettingRecord.
    
    Args:
        app: PowerFactory application object
        record: The IPS setting record
        switch: The associated switch
        called_function: True if batch update
        
    Returns:
        ProtectionDevice object or None
    """
    # Clean device ID
    device_id = record.deviceid
    if device_id:
        for char in ": /,":
            device_id = device_id.replace(char, "")
    
    prot_dev = ProtectionDevice(
        app,
        record.patternname,
        record.nameenu,
        record.relaysettingid,
        record.datesetting,
        None,  # pf_obj assigned later
        device_id,
    )
    prot_dev.switch = switch
    prot_dev.seq_name = record.assetname
    
    # Load settings if not batch
    if not called_function:
        ips_settings = qd.seq_get_ips_settings(app, record.relaysettingid)
        prot_dev.associated_settings(ips_settings)
    
    # Mark fuses
    if prot_dev.device and "fuse" in prot_dev.device.lower():
        prot_dev.fuse_type = "Line Fuse"
    
    return prot_dev


# =============================================================================
# Legacy compatibility functions
# =============================================================================

def get_assoc_switch(app, pf_device, prjt, raw_switches):
    """
    Legacy wrapper for _get_assoc_switch.
    
    DEPRECATED: Use _get_assoc_switch() instead.
    """
    return _get_assoc_switch(pf_device, raw_switches)


def seq_get_setting_id(
    app,
    device,
    switch,
    list_of_devices: List,
    ids_dict_list: List[Dict],
    called_function: bool,
    cb_alt_name_list: List[Dict],
) -> Tuple[List[str], List]:
    """
    Legacy function for backward compatibility.
    
    DEPRECATED: Use _get_setting_id_indexed() with SettingIndex instead.
    """
    logger.warning(
        "seq_get_setting_id() is deprecated. "
        "Use _get_setting_id_indexed() with SettingIndex instead."
    )
    
    from ips_data.setting_index import create_setting_index
    temp_index = create_setting_index(ids_dict_list, "Energex")
    
    return _get_setting_id_indexed(
        app=app,
        switch=switch,
        list_of_devices=list_of_devices,
        setting_index=temp_index,
        called_function=called_function,
        cb_alt_name_list=cb_alt_name_list,
    )


def match_switch_to_relays(
    sub_code: Optional[str],
    switch_name: str,
    ids_dict_list: List[Dict]
) -> List[Dict]:
    """
    Legacy function for backward compatibility.
    
    DEPRECATED: Use SettingIndex.get_by_switch_name() instead.
    """
    logger.warning(
        "match_switch_to_relays() is deprecated. "
        "Use SettingIndex.get_by_switch_name() instead."
    )
    
    from ips_data.setting_index import create_setting_index
    temp_index = create_setting_index(ids_dict_list, "Energex")
    
    records = temp_index.get_by_switch_name(switch_name, sub_code)
    return [r.to_dict() for r in records]

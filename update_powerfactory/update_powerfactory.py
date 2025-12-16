"""
PowerFactory device update orchestration.

This module coordinates the update of PowerFactory relay and fuse devices
with settings from the IPS database. It handles:
- Building type indexes for efficient lookups
- Iterating through devices and dispatching to appropriate handlers
- Collecting update results and error handling

Performance optimizations:
- RelayTypeIndex and FuseTypeIndex provide O(1) type lookups
- Write caching is enabled during batch updates
- Progress reporting every 10 devices

Usage:
    from update_powerfactory import update_powerfactory as up
    results, has_updates = up.update_pf(app, device_list, data_capture_list)
"""

import logging
from typing import List, Dict, Tuple, Any, Optional

from update_powerfactory import relay_settings as rs
from update_powerfactory import fuse_settings as fs
from update_powerfactory.type_index import RelayTypeIndex, FuseTypeIndex
import devices

logger = logging.getLogger(__name__)

# List of feeder disconnect relays to switch out of service
# These relay types do not have protection settings in IPS
RELAYS_OOS = [
    "7PG21 (SOLKOR-RF)",
    "7SG18 (SOLKOR-N)",
    "RED615 2.6 - 2.8",
    "SOLKOR-N_Energex",
    "SOLKOR-RF_Energex",
]


def update_pf(
        app,
        lst_of_devs: List[Any],
        data_capture_list: List[Dict[str, str]]
) -> Tuple[List[Dict[str, str]], bool]:
    """
    Update PowerFactory relays and fuses with data from IPS.

    This is the main entry point for updating protection devices.
    It builds type indexes once, then iterates through all devices,
    updating each based on its type and IPS settings.

    Args:
        app: PowerFactory application object
        lst_of_devs: List of ProtectionDevice objects to update
        data_capture_list: List to append update result records to

    Returns:
        Tuple of (updated data_capture_list, has_updates flag)
    """
    if not lst_of_devs:
        logger.warning("No devices to update")
        return data_capture_list, False

    # Build type indexes once for O(1) lookups
    app.PrintInfo("Creating indexed database of PowerFactory Fuse and Relay Types")
    relay_index = RelayTypeIndex.build(app)
    fuse_index = FuseTypeIndex.build(app)

    logger.info(
        f"Type indexes built: {len(relay_index)} relay types, "
        f"{len(fuse_index)} fuse types"
    )

    update_info: Dict[str, str] = {}
    updates = False

    # Enable write caching for better performance during batch updates
    app.SetWriteCacheEnabled(1)

    try:
        for i, device_object in enumerate(lst_of_devs):
            # Progress reporting
            if i % 10 == 0:
                app.PrintInfo(f"Device {i} of {len(lst_of_devs)} is being updated")

            # Skip devices without PowerFactory object
            if not device_object.pf_obj:
                continue

            # Handle devices not found in IPS
            if not device_object.setting_id and not device_object.fuse_type:
                update_info = _create_not_in_ips_record(device_object)
                data_capture_list.append(update_info)
                update_info = {}
                continue

            # Process device based on type
            try:
                update_info, updates = _process_device(
                    app,
                    device_object,
                    relay_index,
                    fuse_index,
                    updates
                )
            except Exception as e:
                update_info = _handle_device_error(app, device_object, e)

            data_capture_list.append(update_info)
            update_info = {}

            # Check if relay should be switched OOS
            _switch_relay_oos(RELAYS_OOS, device_object)

        # Commit all changes
        app.WriteChangesToDb()

    finally:
        # Always disable write cache when done
        app.SetWriteCacheEnabled(0)

    logger.info(f"Update complete: {len(data_capture_list)} devices processed")
    return data_capture_list, updates


def _process_device(
        app,
        device_object: Any,
        relay_index: RelayTypeIndex,
        fuse_index: FuseTypeIndex,
        updates: bool
) -> Tuple[Dict[str, str], bool]:
    """
    Process a single device based on its type.

    Dispatches to the appropriate settings handler based on whether
    the device is a relay or fuse.

    Args:
        app: PowerFactory application object
        device_object: The ProtectionDevice to process
        relay_index: Indexed relay types for O(1) lookup
        fuse_index: Indexed fuse types for O(1) lookup
        updates: Current updates flag

    Returns:
        Tuple of (update_info dict, updated updates flag)
    """
    if device_object.pf_obj.GetClassName() == "ElmRelay":
        return rs.relay_settings(
            app, device_object, relay_index, updates
        )
    else:
        update_info = fs.fuse_setting(app, device_object, fuse_index)
        return update_info, updates


def _create_not_in_ips_record(device_object: Any) -> Dict[str, str]:
    """
    Create an update record for a device not found in IPS.

    Args:
        device_object: The ProtectionDevice not found in IPS

    Returns:
        Dictionary with substation, plant number, and result
    """
    return {
        "SUBSTATION": device_object.pf_obj.GetAttribute("r:cpGrid:e:loc_name"),
        "PLANT_NUMBER": device_object.pf_obj.loc_name,
        "RESULT": "Not in IPS",
    }


def _handle_device_error(
        app,
        device_object: Any,
        error: Exception
) -> Dict[str, str]:
    """
    Handle an error during device processing.

    Logs the error, sets the device out of service, and creates
    an error record.

    Args:
        app: PowerFactory application object
        device_object: The device that failed
        error: The exception that occurred

    Returns:
        Dictionary with error information
    """
    logger.exception(
        f"{device_object.pf_obj.loc_name} Result = Script Failed: {error}"
    )
    devices.log_device_atts(device_object)

    try:
        substation = device_object.pf_obj.GetAttribute("r:cpGrid:e:loc_name")
    except AttributeError:
        substation = "UNKNOWN"

    # Set device out of service due to error
    try:
        device_object.pf_obj.SetAttribute("outserv", 1)
    except Exception:
        pass

    return {
        "SUBSTATION": substation,
        "PLANT_NUMBER": device_object.pf_obj.loc_name,
        "RELAY_PATTERN": getattr(device_object, 'device', 'Unknown'),
        "RESULT": "Script Failed",
    }


def _switch_relay_oos(relays_oos: List[str], device_object: Any) -> None:
    """
    Switch specific relay types out of service.

    Some relay types (e.g., SOLKOR) should be set OOS as they don't
    have protection settings in IPS.

    Args:
        relays_oos: List of relay pattern names to switch OOS
        device_object: The device to check and potentially switch OOS
    """
    # Check if device pattern is in OOS list
    if device_object.device in relays_oos:
        device_object.pf_obj.SetAttribute("outserv", 1)

    # Check if associated switch is off
    try:
        if device_object.switch.on_off == 0:
            device_object.pf_obj.SetAttribute("outserv", 1)
    except AttributeError:
        pass


# =============================================================================
# Legacy compatibility - keep old function signature working
# =============================================================================

def get_relay_types(app) -> RelayTypeIndex:
    """
    Build relay type index.

    Note: This now returns a RelayTypeIndex instead of a list.
    The index supports both O(1) lookups via .get(name) and
    list access via .get_all() for backward compatibility.

    Args:
        app: PowerFactory application object

    Returns:
        RelayTypeIndex with all relay types indexed
    """
    return RelayTypeIndex.build(app)


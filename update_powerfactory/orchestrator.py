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
from typing import List, Dict, Tuple, Any, Optional, Union

from update_powerfactory import relay_settings as rs
from update_powerfactory import fuse_settings as fs
from update_powerfactory.type_index import RelayTypeIndex, FuseTypeIndex
from core import UpdateResult
from config.relay_patterns import RELAYS_OOS
from logging_config.configure_logging import log_device_atts

logger = logging.getLogger(__name__)


def update_pf(
        app,
        lst_of_devs: List[Any],
        data_capture_list: List[Union[Dict[str, str], UpdateResult]]
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
        Tuple of (updated data_capture_list as dicts, has_updates flag)
    """
    if not lst_of_devs:
        logger.warning("No devices to update")
        return _convert_results_to_dicts(data_capture_list), False

    # Build type indexes once for O(1) lookups
    app.PrintInfo("Creating indexed database of PowerFactory Fuse and Relay Types")
    relay_index = RelayTypeIndex.build(app)
    fuse_index = FuseTypeIndex.build(app)

    logger.info(
        f"Type indexes built: {len(relay_index)} relay types, "
        f"{len(fuse_index)} fuse types"
    )

    updates = False
    results: List[UpdateResult] = []

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
                result = UpdateResult.not_in_ips(device_object)
                results.append(result)
                continue

            # Process device based on type
            try:
                result, updates = _process_device(
                    app,
                    device_object,
                    relay_index,
                    fuse_index,
                    updates
                )
            except Exception as e:
                result = _handle_device_error(app, device_object, e)

            results.append(result)

            # Check if relay should be switched OOS
            _switch_relay_oos(RELAYS_OOS, device_object)

        # Commit all changes
        app.WriteChangesToDb()

    finally:
        # Always disable write cache when done
        app.SetWriteCacheEnabled(0)

    logger.info(f"Update complete: {len(results)} devices processed")

    # Convert any existing dict entries and new results to dicts for output
    final_results = _convert_results_to_dicts(data_capture_list)
    final_results.extend([r.to_dict() for r in results])

    return final_results, updates


def _process_device(
        app,
        device_object: Any,
        relay_index: RelayTypeIndex,
        fuse_index: FuseTypeIndex,
        updates: bool
) -> Tuple[UpdateResult, bool]:
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
        Tuple of (UpdateResult, updated updates flag)
    """
    if device_object.pf_obj.GetClassName() == "ElmRelay":
        return rs.relay_settings(
            app, device_object, relay_index, updates
        )
    else:
        result = fs.fuse_setting(app, device_object, fuse_index)
        return result, updates


def _handle_device_error(
        app,
        device_object: Any,
        error: Exception
) -> UpdateResult:
    """
    Handle an error during device processing.

    Logs the error, sets the device out of service, and creates
    an error result.

    Args:
        app: PowerFactory application object
        device_object: The device that failed
        error: The exception that occurred

    Returns:
        UpdateResult with error information
    """
    logger.exception(
        f"{device_object.pf_obj.loc_name} Result = Script Failed: {error}"
    )
    log_device_atts(device_object)

    # Set device out of service due to error
    try:
        device_object.pf_obj.SetAttribute("outserv", 1)
    except Exception:
        pass

    return UpdateResult.script_failed(device_object, error)


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


def _convert_results_to_dicts(
    results: List[Union[Dict[str, str], UpdateResult]]
) -> List[Dict[str, str]]:
    """
    Convert a mixed list of results to dictionaries.

    Handles both UpdateResult objects and existing dictionaries
    for backward compatibility during migration.

    Args:
        results: List of UpdateResult objects or dictionaries

    Returns:
        List of dictionaries
    """
    converted = []
    for item in results:
        if isinstance(item, UpdateResult):
            converted.append(item.to_dict())
        elif isinstance(item, dict):
            converted.append(item)
        else:
            logger.warning(f"Unknown result type: {type(item)}")
    return converted


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

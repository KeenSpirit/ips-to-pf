"""
Database query functions for retrieving IPS protection device settings.

This module handles all interactions with the IPS database through the
NetDash API and corporate data caching layer. It provides functions for:
- Retrieving setting IDs for all devices in a region
- Fetching detailed settings for specific relay setting IDs
- Getting instrument transformer (CT/VT) details

The module uses the SettingIndex class for efficient O(1) lookups of
setting data instead of linear scans through lists.
"""

import sys
import time
import logging
from typing import Dict, List, Optional, Tuple, Any

sys.path.append(r"\\ecasd01\WksMgmt\PowerFactory\ScriptsLIB\NetDash-Reader")
from netdashread import get_json_data
from tenacity import retry, stop_after_attempt, wait_random_exponential

sys.path.append(r"\\Ecasd01\WksMgmt\PowerFactory\Scripts\AssetClasses")
import assetclasses
from assetclasses.corporate_data import get_cached_data

from ips_data.setting_index import SettingIndex, create_setting_index

logger = logging.getLogger(__name__)

# Cache for setting indexes to avoid rebuilding on repeated calls
_index_cache: Dict[str, SettingIndex] = {}


def get_setting_ids(app, region: str) -> SettingIndex:
    """
    Retrieve all protection device setting IDs for a region.
    
    This function fetches the setting ID data from the corporate cache
    and returns an indexed structure for efficient lookups. The index
    is cached to avoid repeated processing.
    
    Args:
        app: PowerFactory application object
        region: "Energex" or "Ergon"
        
    Returns:
        SettingIndex object providing O(1) lookups by various keys
        
    Raises:
        SystemExit: If unable to retrieve data after multiple attempts
    """
    app.PrintInfo("Creating the Setting ID Index")
    
    # Check cache first
    cache_key = f"setting_index_{region}"
    if cache_key in _index_cache:
        logger.info(f"Using cached SettingIndex for {region}")
        return _index_cache[cache_key]
    
    # Fetch raw data with retry logic
    ids_dict_list = _fetch_setting_ids_with_retry(app, region)
    
    # Build indexed structure
    index = create_setting_index(ids_dict_list, region)
    
    # Cache for future use
    _index_cache[cache_key] = index
    
    logger.info(f"Setting ID Index successfully created for {region}")
    return index


def _fetch_setting_ids_with_retry(app, region: str, max_attempts: int = 5) -> List[Dict]:
    """
    Fetch setting IDs with retry logic for concurrent access issues.
    
    Args:
        app: PowerFactory application object
        region: "Energex" or "Ergon"
        max_attempts: Maximum number of retry attempts
        
    Returns:
        List of setting ID dictionaries
        
    Raises:
        SystemExit: If unable to retrieve data after max_attempts
    """
    ids_dict_list = []
    attempts = 0
    
    while len(ids_dict_list) == 0 and attempts < max_attempts:
        if attempts > 0:
            # Wait before retry if not first attempt
            time.sleep(10)
            
        ids_dict_list = _create_ids_dict(region)
        attempts += 1
        
        if attempts > 1:
            logger.warning(f"Retry attempt {attempts} for setting IDs")
    
    if len(ids_dict_list) == 0:
        logger.error("Could not create the setting ID dictionary")
        error_message(
            app,
            "Unable to obtain data for Setting IDs, please contact the Protection SME",
        )
    
    return ids_dict_list


def _create_ids_dict(region: str) -> List[Dict]:
    """
    Fetch raw setting ID data from corporate cache.
    
    Args:
        region: "Energex" or "Ergon"
        
    Returns:
        List of dictionaries containing setting ID data
    """
    report_name = (
        "Report-Cache-ProtectionSettingIDs-EX" 
        if region == "Energex" 
        else "Report-Cache-ProtectionSettingIDs-EE"
    )
    
    rows = get_cached_data(report_name, max_age=3)
    
    ids_dict_list = []
    for row in rows:
        try:
            ids_dict_list.append(dict(row._asdict()))
        except AttributeError:
            continue
            
    return ids_dict_list


def get_setting_ids_legacy(app, region: str) -> List[Dict]:
    """
    Legacy function returning raw list format for backward compatibility.
    
    DEPRECATED: Use get_setting_ids() which returns a SettingIndex instead.
    This function is provided only for gradual migration of existing code.
    
    Args:
        app: PowerFactory application object
        region: "Energex" or "Ergon"
        
    Returns:
        List of setting ID dictionaries (raw format)
    """
    logger.warning(
        "get_setting_ids_legacy() is deprecated. "
        "Use get_setting_ids() returning SettingIndex instead."
    )
    return _fetch_setting_ids_with_retry(app, region)


def clear_index_cache() -> None:
    """
    Clear the cached setting indexes.
    
    Call this if you need to force a refresh of the data from the database.
    """
    global _index_cache
    _index_cache.clear()
    logger.info("Setting index cache cleared")


def error_message(app, message: str) -> None:
    """
    Display error message and terminate script.
    
    Args:
        app: PowerFactory application object
        message: Error message to display
    """
    app.PrintError(message)
    sys.exit(0)


def batch_settings(
    app, 
    region: str, 
    called_function: bool, 
    set_ids: List[str]
) -> Tuple[Dict[str, List[Dict]], List]:
    """
    Retrieve detailed settings for a batch of relay setting IDs.
    
    This function fetches the complete setting details for each setting ID
    and also retrieves associated instrument transformer settings.
    
    Args:
        app: PowerFactory application object
        region: "Energex" or "Ergon"
        called_function: True if called from batch update (loads all settings)
        set_ids: List of relay setting IDs to fetch
        
    Returns:
        Tuple of (ips_settings dict, ips_it_settings list)
        - ips_settings: Dict mapping setting ID to list of setting records
        - ips_it_settings: List of instrument transformer setting records
    """
    ips_settings: Dict[str, List[Dict]] = {}
    
    if region == "Energex":
        if called_function:
            ips_settings = _fetch_settings_in_batches(
                app, set_ids, seq_get_ips_settings, batch_size=900
            )
        ips_it_settings = seq_get_ips_it_details(app, set_ids)
    else:
        if called_function:
            ips_settings = _fetch_settings_in_batches(
                app, set_ids, reg_get_ips_settings, batch_size=900
            )
        ips_it_settings = reg_get_ips_it_details(app, set_ids)
    
    return ips_settings, ips_it_settings


def _fetch_settings_in_batches(
    app,
    set_ids: List[str],
    fetch_func,
    batch_size: int = 900
) -> Dict[str, List[Dict]]:
    """
    Fetch settings in batches to avoid overwhelming the API.
    
    Args:
        app: PowerFactory application object
        set_ids: List of setting IDs to fetch
        fetch_func: Function to call for each setting ID
        batch_size: Maximum IDs to process before yielding
        
    Returns:
        Combined dictionary of all settings
    """
    ips_settings: Dict[str, List[Dict]] = {}
    
    for i, set_id in enumerate(set_ids):
        if i > 0 and i % batch_size == 0:
            logger.info(f"Processed {i} of {len(set_ids)} settings")
        
        settings = fetch_func(app, set_id)
        ips_settings.update(settings)
    
    return ips_settings


def seq_get_ips_it_details(app, devices: List[str]) -> List:
    """
    Get instrument transformer details for Energex (SEQ) devices.
    
    The CT/VT ratios are configured based on the CT/VT setting nodes
    attached to each relay setting node.
    
    Args:
        app: PowerFactory application object
        devices: List of relay setting IDs
        
    Returns:
        List of IT setting records that match the given devices
    """
    device_set = set(devices)  # Convert to set for O(1) lookup
    
    it_set_db = get_cached_data("Report-Cache-ProtectionITSettings-EX", max_age=3)
    
    ips_settings = []
    if it_set_db:
        for setting in it_set_db:
            if setting.relaysettingid in device_set:
                ips_settings.append(setting)
    
    return ips_settings


def reg_get_ips_it_details(app, devices: List[str]) -> List:
    """
    Get instrument transformer details for Ergon (Regional) devices.
    
    The CT/VT ratios are configured based on the CT/VT setting nodes
    attached to each relay setting node.
    
    Args:
        app: PowerFactory application object
        devices: List of relay setting IDs
        
    Returns:
        List of IT setting records that match the given devices
    """
    device_set = set(devices)  # Convert to set for O(1) lookup
    
    it_set_db = get_cached_data("Report-Cache-ProtectionITSettings-EE", max_age=3)
    
    ips_settings = []
    if it_set_db:
        for setting in it_set_db:
            if setting.relaysettingid in device_set:
                ips_settings.append(setting)
    
    return ips_settings


def seq_get_ips_settings(app, set_id: str) -> Dict[str, List[Dict]]:
    """
    Get full setting file for an Energex relay from the database.
    
    Args:
        app: PowerFactory application object
        set_id: The relay setting ID
        
    Returns:
        Dictionary mapping setting ID to list of setting records:
        {relaysettingid: [{blockpathenu, paramnameenu, proposedsetting, unitenu}, ...]}
    """
    settings = get_data("Protection-SettingRelay-EX", "setting_id", set_id)
    
    return {set_id: list(settings)}


def reg_get_ips_settings(app, set_id: str) -> Dict[str, List[Dict]]:
    """
    Get full setting file for an Ergon relay from the database.
    
    Args:
        app: PowerFactory application object
        set_id: The relay setting ID
        
    Returns:
        Dictionary mapping setting ID to list of setting records:
        {relaysettingid: [{blockpathenu, paramnameenu, proposedsetting, unitenu}, ...]}
        
    Note:
        Records with empty proposedsetting are filtered out for Ergon.
    """
    settings = get_data("Protection-SettingRelay-EE", "setting_id", set_id)
    
    # Filter out records with no proposed setting
    filtered_settings = [s for s in settings if s.get("proposedsetting")]
    
    return {set_id: filtered_settings}


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_random_exponential(multiplier=1, max=5),
)
def get_data(data_report: str, parameter: str, variable: str) -> List[Dict]:
    """
    Query the IPS database via NetDash API.
    
    This function includes automatic retry logic with exponential backoff
    to handle transient failures.
    
    Args:
        data_report: Name of the NetDash report to query
        parameter: Query parameter name
        variable: Query parameter value
        
    Returns:
        List of dictionaries containing query results
    """
    data = get_json_data(
        report=data_report, 
        params={parameter: variable}, 
        timeout=120
    )
    
    if len(data) == 0:
        logger.warning(f"Query returned no data for {data_report} with {parameter}={variable}")
    
    return data

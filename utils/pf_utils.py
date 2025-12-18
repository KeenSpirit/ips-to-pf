"""
PowerFactory utility functions.

This module provides utility functions for working with PowerFactory
objects and data structures. These functions are used throughout
the application for common PowerFactory operations.

Functions:
    all_relevant_objects: Recursively get objects from folder hierarchy
    get_all_protection_devices: Get all relays and fuses from network model
    get_all_switches: Get all switches/CBs from network model
    get_active_feeders: Get all active feeders from network data
    determine_region: Determine Energex/Ergon from project structure
"""

import logging
from typing import List, Dict, Any, Tuple, Optional

logger = logging.getLogger(__name__)


def all_relevant_objects(
    app: Any,
    folders: List[Any],
    type_of_obj: str,
    objects: Optional[List[Any]] = None
) -> List[Any]:
    """
    Recursively retrieve all objects of a given type from folder hierarchy.
    
    This function performs a depth-first traversal of the folder structure,
    collecting all objects matching the specified type. It's faster than
    using GetContents with recursive=True on folders outside your own user.
    
    Args:
        app: PowerFactory application object
        folders: List of folder objects to search
        type_of_obj: Object type pattern (e.g., "*.ElmRelay", "*.RelFuse")
        objects: Accumulator for recursive calls (internal use)
        
    Returns:
        List of all matching PowerFactory objects
        
    Example:
        >>> net_mod = app.GetProjectFolder("netmod")
        >>> relays = all_relevant_objects(app, [net_mod], "*.ElmRelay")
    """
    if objects is None:
        objects = []
        
    for folder in folders:
        # Get objects at this level (non-recursive)
        folder_objects = folder.GetContents(type_of_obj, 0)
        objects.extend(folder_objects)
        
        # Get subfolders to recurse into
        sub_folders = folder.GetContents("*.IntFolder", 0)
        sub_folders += folder.GetContents("*.IntPrjfolder", 0)
        
        if sub_folders:
            all_relevant_objects(app, sub_folders, type_of_obj, objects)
            
    return objects


def get_all_protection_devices(app: Any) -> Tuple[List[Any], Dict[str, List]]:
    """
    Get all active protection devices (relays and fuses) from the network model.
    
    This function retrieves all relays and fuses that are:
    - Energized (connected terminal is energized)
    - In service
    - Calculation relevant
    - In a valid cubicle (relays) or line position (fuses)
    
    Args:
        app: PowerFactory application object
        
    Returns:
        Tuple of (devices_list, device_dict) where:
        - devices_list: List of relay and fuse objects
        - device_dict: Dictionary mapping device name to [object, class, phases, feeder, grid]
        
    Example:
        >>> devices, device_dict = get_all_protection_devices(app)
        >>> for device in devices:
        ...     print(device.loc_name)
    """
    net_mod = app.GetProjectFolder("netmod")
    
    # Get all relays
    all_relays = net_mod.GetContents("*.ElmRelay", True)
    relays = [
        relay for relay in all_relays
        if relay.HasAttribute("e:cpGrid")
        if relay.GetParent().GetClassName() == "StaCubic"
        if relay.fold_id.cterm.IsEnergized()
        if not relay.IsOutOfService()
        if relay.IsCalcRelevant()
    ]
    
    # Get all fuses
    all_fuses = net_mod.GetContents("*.RelFuse", True)
    fuses = [
        fuse for fuse in all_fuses
        if fuse.fold_id.HasAttribute("cterm")
        if fuse.fold_id.cterm.IsEnergized()
        if not fuse.IsOutOfService()
        if _is_line_fuse(fuse)
    ]
    
    devices = relays + fuses
    
    # Get active feeders for device classification
    net_data = app.GetProjectFolder("netdat")
    active_feeders = [
        feeder for feeder in net_data.GetContents("*.ElmFeeder", True)
        if not feeder.IsOutOfService()
    ]
    
    # Build device dictionary
    device_dict = {}
    for device in devices:
        term = device.cbranch
        
        # Find feeder containing this device
        feeder = [
            feeder.loc_name for feeder in active_feeders
            if term in feeder.GetAll()
        ]
        if not feeder:
            feeder = ["Not in a Feeder"]
            
        # Get number of phases
        try:
            num_phases = device.GetAttribute("r:cbranch:r:bus1:e:nphase")
        except AttributeError:
            num_phases = 3
            
        device_dict[device.loc_name] = [
            device,
            device.GetClassName(),
            num_phases,
            feeder[0],
            device.cpGrid.loc_name,
        ]
        
    return devices, device_dict


def _is_line_fuse(fuse: Any) -> bool:
    """
    Determine if a fuse is a line fuse (not a transformer or SWER isolator fuse).
    
    Args:
        fuse: PowerFactory fuse object
        
    Returns:
        True if the fuse is a line fuse
    """
    # Check if fuse has active location
    fuse_active = fuse.HasAttribute("r:fold_id:r:obj_id:e:loc_name")
    if not fuse_active:
        return True
        
    fuse_grid = fuse.cpGrid
    
    # Check if in a line cubicle
    try:
        term_folder = fuse.GetAttribute("r:fold_id:r:cterm:r:fold_id:e:loc_name")
        if term_folder == fuse_grid.loc_name:
            return True
    except AttributeError:
        pass
        
    # Check if fuse is in a switch object
    try:
        obj_name = fuse.GetAttribute("r:fold_id:r:obj_id:e:loc_name")
        if fuse.loc_name not in obj_name:
            return True
    except AttributeError:
        pass
        
    # Check if connected to a transformer
    try:
        secondary_sub = fuse.fold_id.cterm.fold_id
        contents = secondary_sub.GetContents()
        for content in contents:
            if content.GetClassName() == "ElmTr2":
                return False
    except AttributeError:
        pass
        
    return True


def get_all_switches(app: Any) -> List[Any]:
    """
    Get all switch/circuit breaker objects from the network model.
    
    Args:
        app: PowerFactory application object
        
    Returns:
        List of switch objects
    """
    net_mod = app.GetProjectFolder("netmod")
    return net_mod.GetContents("*.ElmCoup", True)


def get_active_feeders(app: Any) -> List[Any]:
    """
    Get all active (in-service) feeders from the network data.
    
    Args:
        app: PowerFactory application object
        
    Returns:
        List of active feeder objects
    """
    net_data = app.GetProjectFolder("netdat")
    all_feeders = net_data.GetContents("*.ElmFeeder", True)
    return [f for f in all_feeders if not f.IsOutOfService()]


def determine_region(prjt: Any) -> str:
    """
    Determine the region (Energex/Ergon) from project structure.
    
    The region is determined by examining the base project folder name.
    SEQ Models folder indicates Energex region.
    
    Args:
        prjt: PowerFactory project object
        
    Returns:
        "Energex" or "Ergon"
        
    Example:
        >>> prjt = app.GetActiveProject()
        >>> region = determine_region(prjt)
        >>> print(region)
        'Energex'
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
        
    logger.info(f"Determined region: {region}")
    return region


def get_relay_types(app: Any) -> List[Any]:
    """
    Get all relay types from the equipment type library.
    
    Args:
        app: PowerFactory application object
        
    Returns:
        List of relay type objects
    """
    equip_type_lib = app.GetProjectFolder("equip")
    folders = [equip_type_lib]
    return all_relevant_objects(app, folders, "*.TypRelay")


def get_fuse_types(app: Any) -> List[Any]:
    """
    Get all fuse types from the equipment type library.
    
    Args:
        app: PowerFactory application object
        
    Returns:
        List of fuse type objects
    """
    equip_type_lib = app.GetProjectFolder("equip")
    folders = [equip_type_lib]
    return all_relevant_objects(app, folders, "*.TypFuse")

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


def determine_fuse_role(app, fuse):
    """This function will observe the fuse location and determine if it is
    a Distribution transformer fuse, SWER isolating fuse or a line fuse"""
    # Create the fuse dictionary for sizes based on transformer data
    size_dict = create_fuse_dict()
    # First check is that if the fuse exists in a terminal that is in the
    # System Overiew then it will be a line fuse.
    fuse_active = fuse.HasAttribute("r:fold_id:r:obj_id:e:loc_name")
    if not fuse_active:
        return [None, None]
    fuse_grid = fuse.cpGrid
    if (
        fuse.GetAttribute("r:fold_id:r:cterm:r:fold_id:e:loc_name")
        == fuse_grid.loc_name
    ):
        # This would indicate it is in a line cubical
        return ["Line Fuse", None]
    if fuse.loc_name not in fuse.GetAttribute("r:fold_id:r:obj_id:e:loc_name"):
        # This indicates that the duse is not ina scitch object
        return ["Line Fuse", None]
    secondary_sub = fuse.fold_id.cterm.fold_id
    contents = secondary_sub.GetContents()
    for content in contents:
        if content.GetClassName() == "ElmTr2":
            break
    else:
        return ["Line Fuse", None]
    try:
        # Determine the type of transformer
        tx_type = content.typ_id
        tx_constr = tx_type.GetAttribute("e:nt2ph")
        if tx_constr == 3:
            # Three winding transformers are always going to be
            # distribution transformers
            hv_term_volt = int(tx_type.GetAttribute("e:utrn_h"))
            tx_rating = int(round(tx_type.GetAttribute("e:strn"), 4) * 1000)
            key = "{}{}{}".format(tx_constr, hv_term_volt, tx_rating)
            try:
                fuse_size = size_dict[key]
            except KeyError:
                # Set the fuse to the smallest available fuse.
                fuse_size = "3/10K"
            return ["Tx Fuse", fuse_size]
        if (
            tx_constr == 2
            and secondary_sub.GetAttribute("e:sType").lower() == "swer isolator"
        ):
            # These are SWER Isolator transformers
            term1_volt = int(tx_type.GetAttribute("e:utrn_h"))
            term2_volt = int(tx_type.GetAttribute("e:utrn_l"))
            tx_rating = int(float(tx_type.GetAttribute("e:strn")) * 1000)
            try:
                key = "{}{}{}".format(term1_volt, term2_volt, tx_rating)
                fuse_size = size_dict[key]
            except KeyError:
                key = "{}{}{}".format(term2_volt, term1_volt, tx_rating)
                try:
                    fuse_size = size_dict[key]
                except KeyError:
                    # Set the fuse to the smallest available fuse.
                    fuse_size = "3/10K"
            return ["Tx Fuse", fuse_size]
        elif tx_constr == 2 and content.bushv.cterm.GetAttribute("e:phtech") == 6:
            tx_constr = 1
            hv_term_volt = str(tx_type.GetAttribute("e:utrn_h"))[:4]
            tx_rating = int(float(tx_type.GetAttribute("e:strn")) * 1000)
            key = "{}{}{}".format(tx_constr, hv_term_volt, tx_rating)
            try:
                fuse_size = size_dict[key]
            except KeyError:
                # Set the fuse to the smallest available fuse.
                fuse_size = "3/10K"
            return ["Tx Fuse", fuse_size]
        else:
            hv_term_volt = int(tx_type.GetAttribute("e:utrn_h"))
            tx_rating = int(round(tx_type.GetAttribute("e:strn"), 4) * 1000)
            key = "{}{}{}".format(tx_constr, hv_term_volt, tx_rating)
            try:
                fuse_size = size_dict[key]
            except KeyError:
                # Set the fuse to the smallest available fuse.
                fuse_size = "3/10K"
            return ["Tx Fuse", fuse_size]
    except (AttributeError, ValueError, TypeError):
        fuse_size = "3/10K"
        return ["Tx Fuse", fuse_size]


def create_fuse_dict():
    """This has been developed based on STNW1001. The key will be
    pf attribute for transfomer type, Voltage level, rating"""
    fuse_dict = {
        "21110": "3/10K",
        "21115": "3/10K",
        "21125": "6/20K",
        "21150": "16K",
        "31115": "3/10K",
        "31125": "3/10K",
        "31150": "6/20K",
        "31163": "6/20K",
        "31175": "12K",
        "311100": "16K",
        "311150": "20K",
        "311200": "25K",
        "311250": "31K",
        "311300": "31K",
        "311315": "31K",
        "311500": "50K",
        "311750": "63K",
        "3111000": "80K",
        "3111500": "100K",
        "22210": "3/10K",
        "22215": "3/10K",
        "22225": "3/10K",
        "22250": "6/20K",
        "32215": "3/10K",
        "32225": "3/10K",
        "32250": "3/10K",
        "32263": "3/10K",
        "32275": "6/20K",
        "322100": "6/20K",
        "322150": "12K",
        "322200": "16K",
        "322250": "20K",
        "322300": "20K",
        "322315": "20K",
        "322500": "31K",
        "322750": "40K",
        "3221000": "50K",
        "3221500": "63K",
        "23310": "3/10K",
        "23325": "3/10K",
        "23350": "3/10K",
        "33325": "3/10K",
        "33350": "3/10K",
        "33363": "3/10K",
        "333100": "3/10K",
        "333200": "12K",
        "333300": "16K",
        "333315": "16K",
        "333500": "20K",
        "111125": "12K",
        "111150": "16K",
        "1111100": "25K",
        "1111150": "31K",
        "1111200": "40K",
        "1112.725": "12K",
        "1112.750": "16K",
        "1112.7100": "25K",
        "1112.7150": "31K",
        "1112.7200": "40K",
        "2212.725": "6/20K",
        "2212.750": "10K",
        "2212.7100": "20K",
        "2212.7150": "25K",
        "2212.7200": "31K",
        "3312.725": "6/20K",
        "3312.750": "6/20K",
        "3312.7100": "16K",
        "3312.7150": "20K",
        "3312.7200": "25K",
        "1119.125": "16K",
        "1119.150": "20K",
        "1119.1100": "31K",
        "1119.1150": "40K",
        "1119.1200": "50K",
        "2219.125": "6/20K",
        "2219.150": "6/20K",
        "2219.1100": "20K",
        "2219.1150": "25K",
        "2219.1200": "31K",
        "3319.125": "6/20K",
        "3319.150": "6/20K",
        "3319.1100": "16K",
        "3319.1150": "20K",
        "3319.1200": "25K",
        "1115": "3/10K",
        "11110": "3/10K",
        "11125": "6/20K",
        "11150": "10K",
        "11163": "10K",
        "112.75": "3/10K",
        "112.710": "3/10K",
        "112.725": "3/10K",
        "112.750": "10K",
        "112.763": "10K",
        "119.15": "3/10K",
        "119.110": "3/10K",
        "119.125": "3/10K",
        "119.150": "6/20K",
        "119.163": "6/20K",
    }
    return fuse_dict

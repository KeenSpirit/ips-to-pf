import sys
import re
from collections import defaultdict
sys.path.append(r"\\Ecasd01\WksMgmt\PowerFactory\Scripts\AssetClasses")
import assetclasses
from assetclasses.corporate_data import get_cached_data

import logging  # noqa

from ips_data import query_database as qd

logger = logging.getLogger(__name__)
DATA_SOURCE_STRING = "PRS"
GAS_SWITCH_STRING = "Gas Switch"


def add_relay_skeletons(app, project=None):
    """
    Get all the protection information from ellipse/gisep and process
    each switch within the model. Add the skeletons if they do not yet
    exist.

    Switches inside Substations that are not feeder CBs are ignored.
    """

    if project is None:
        project = app.GetActiveProject()
    if project is None:
        logger.error("No Active Project or passed project, Ending Script")
        return
    if project != app.GetActiveProject():
        logger.error(f"Passed project is not the active project. Ending Script")
        return

    logger.debug(f"Deleting PDS elements")
    remove_pds_elements(project)

    # Get information from GISEP/Ellipse
    logger.info(f"Getting Relay Information")
    relay_info = get_cached_data(
        report="List-RelayCBs", max_age=3,
    )
    logger.debug(f"Got Relays")
    logger.info(f"Getting Recloser Information")
    recloser_info = get_cached_data(
        report="List-Reclosers", max_age=3,
    )
    logger.debug(f"Got Reclosers")
    logger.info(f"Getting Fuse Information")
    fuses_info = get_cached_data(
        report="List-Fuses", max_age=3,
    )
    logger.debug(f"Got Fuses")
    logger.info(f"Getting Gas Switch Information")
    gas_switch_info = get_cached_data(
        report="List-GasSwitches", max_age=3,
    )
    logger.debug(f"Got Gas Switch")

    # Building Dictionaries
    logger.info(f"Building Relay Dictionary")
    relay_dict = produce_switch_based_dict(relay_info)
    logger.info(f"Building Recloser Dictionary")
    recloser_dict = produce_line_switch_based_dict(recloser_info)
    logger.info(f"Building Fuse Dictionary")
    fuse_dict = produce_line_switch_based_dict(fuses_info)
    logger.info(f"Building Gas Switch Dictionary")
    gas_switch = produce_line_switch_based_dict(gas_switch_info)
    logger.info(f"Dictionaries Built")

    # Produce list of Feeder CBs
    feeder_cbs = produce_list_of_model_feeder_cbs(project)
    logger.info(f"Feeder CBs Identified")

    # Process Existing switches.
    elm_coups = project.GetContents("*.ElmCoup", True)
    sta_switches = project.GetContents("*.StaSwitch", True)
    switches = elm_coups + sta_switches
    num_switches = len(switches)

    for i, elm in enumerate(switches):
        if i % 100 == 0:
            logger.info(f"Checking Switch {i+1}/{num_switches}")

        process_switch_for_relay_check(
            app, elm, relay_dict, fuse_dict, recloser_dict, gas_switch, feeder_cbs
        )


def remove_pds_elements(project):

    protection_elms = list()
    for class_name in [
        "ElmRelay",
        "RelFuse",
        "RelIoc",
        "RelLogdip",
        "RelLogic",
        "RelMeasure",
        "RelRecl",
        "RelToc",
        "StaCt",
    ]:
        objs = project.GetContents(f"*.{class_name}", True)
        protection_elms.extend(objs)

    deleted_elms = list()
    problem_classes = list()
    for obj in protection_elms:
        try:
            data_source = obj.GetAttribute("dat_src")
        except AttributeError:
            problem_classes.append(obj.GetClassName())
            logger.warning(f'{obj} has no attribute "dat_scr"')
            continue
        if data_source == "PDS":
            if not obj.IsDeleted():
                ef = obj.Delete()
                if ef:
                    logger.error(f"Unable to delete {obj}")
                else:
                    deleted_elms.append(obj)

    for problem_class in problem_classes:
        logger.warning(f"{problem_class} has no dat_scr attribute")

    logger.info(f"Deleted {len(deleted_elms)} PDS Objects.")


def produce_switch_based_dict(relay_info):
    """Produce a dictionary for the relays, ignores null CB rows"""
    d = defaultdict(list)
    nulls = list()
    for data in relay_info:
        # logger.debug(data)
        asset_id = data.cb_asset_id
        if not asset_id:
            nulls.append(data)
        else:
            d[str(asset_id)].append(data)

    logger.debug(
        f"There are {len(nulls)} relays with no CB associated"
        f" with the protection scheme. "
        f"These should be bus or tx protection schemes without local CBs."
    )

    return d


def produce_line_switch_based_dict(info):
    """Produce a dictionary for fuses and recloser information"""
    d = defaultdict(list)

    for data in info:
        asset_id = data.asset_id
        if not asset_id:
            logger.warning(f'Null asset_id: "{asset_id}" in {data}')
        else:
            d[str(asset_id)].append(data)

    return d


def produce_list_of_model_feeder_cbs(project):
    """Produce a list of CBs associated with feeders"""
    feeders = project.GetContents("*.ElmFeeder", True)

    feeder_cbs = list()

    for feeder in feeders:
        cub = feeder.GetAttribute("obj_id")
        if cub:
            switch = cub.GetAttribute("obj_id")
            if switch:
                feeder_cbs.append(switch)

    return feeder_cbs


def process_switch_for_relay_check(
    app, elm, relay_dict, fuse_dict, recloser_dict, gas_switch, feeder_cbs
):
    """
    Check if elm should have a relay, recloser or fuse.
    If it should ensure the appropriate rel object exists.

    Will also delete any objects that are in the wrong location
    from the ETL where the correct switch location is within the model
    """

    # Ignore Switches in the Substation that are not feeder CBs
    # not short-circuited so the error message can be more detailed
    parent = elm.GetParent()
    pot_feeder_cb = True
    if parent.GetClassName() == "ElmSubstat":
        if elm not in feeder_cbs:
            pot_feeder_cb = False

    # Get the expected foreign key (ellipse ID)
    foreign_key = elm.GetAttribute("for_name")
    ecorp_id = ellipse_ecorp_asset_id_extraction(foreign_key)

    if ecorp_id == "25268198":
        logger.debug(f"** {elm} should have multiple relays")

    # Now process each type of protection device sequentially for
    # information associated with the switch

    new_devices = list()

    # Relays
    try:
        relay_info = relay_dict[ecorp_id]
    except KeyError:
        # Elm does not have a relay associated with it,
        # check the other types
        pass
    else:
        if len(relay_info) > 1:
            logger.debug(f"Multiple Protection Relays found for {elm}")

        # Handle potential for multiple fuses on one recloser
        for relay_data in relay_info:
            # Relay associated, ensure it exists
            if pot_feeder_cb:
                logger.debug(
                    f"setting up relay {relay_data.plant_no} on {elm},"
                    f" {relay_data.ellipse_equip_no}"
                )
                new_relay = setup_relay(
                    app=app,
                    elm=elm,
                    asset_id=relay_data.asset_id,
                    plant_no=relay_data.plant_no,
                    ellipse_id=relay_data.ellipse_equip_no,
                    relay_class="ElmRelay",
                )
                new_devices.append(new_relay)
            else:
                logger.debug(
                    f"Skipping {elm} as it is not a feeder CB in a sub: "
                    f"Data: {relay_data} "
                )

    # Reclosers
    try:
        recloser_info = recloser_dict[ecorp_id]
    except KeyError:
        # Elm does not have a relay associated with it,
        # check the other types
        pass
    else:
        if len(recloser_info) > 1:
            logger.info(f"Multiple Reclosers found for {elm}")

        # Handle potential for multiple fuses on one recloser
        for recloser_data in recloser_info:
            # Relay associated, ensure it exists
            if pot_feeder_cb:
                new_recloser = setup_relay(
                    app=app,
                    elm=elm,
                    asset_id=recloser_data.asset_id,
                    plant_no=recloser_data.plant_no,
                    ellipse_id=recloser_data.equip_no,
                    relay_class="ElmRelay",
                )
                new_devices.append(new_recloser)
            else:
                logger.info(
                    f"Skipping {elm} as it is not a feeder CB in a sub: "
                    f"Data: {recloser_data} "
                )

    # Fuses
    try:
        fuse_info = fuse_dict[ecorp_id]
    except KeyError:
        # Elm does not have a fuse associated with it,
        # check the other types or do nothing
        pass
    else:
        if len(fuse_info) > 1:
            logger.info(f"Multiple Fuses found for {elm}")

        # Handle potential for multiple fuses on one switch
        for fuse_data in fuse_info:
            # Fuse associated, ensure it exists
            if pot_feeder_cb:
                new_fuse = setup_relay(
                    app=app,
                    elm=elm,
                    asset_id=fuse_data.asset_id,
                    plant_no=fuse_data.plant_no,
                    ellipse_id=fuse_data.equip_no,
                    relay_class="RelFuse",
                )
                new_devices.append(new_fuse)
            else:
                logger.info(
                    f"Skipping {elm} as it is not a feeder CB in a sub: "
                    f"Data: {fuse_data} "
                )
    # Gas Switches
    try:
        gas_switch_info = gas_switch[ecorp_id]
    except KeyError:
        # Elm does not have a Gas Switch associated with it,
        # check the other types or do nothing
        pass
    else:
        if len(gas_switch_info) > 1:
            logger.info(f"Multiple Gas Switches found for {elm}")

        # Handle potential for multiple Gas Switches on one switch
        for gas_switch_data in gas_switch_info:
            # Fuse associated, ensure it exists
            if pot_feeder_cb:
                new_gs = setup_relay(
                    app=app,
                    elm=elm,
                    asset_id=gas_switch_data.asset_id,
                    plant_no=gas_switch_data.plant_no,
                    ellipse_id=gas_switch_data.equip_no,
                    relay_class="ElmRelay",
                    gas_switch=True,
                )
                new_devices.append(new_gs)
            else:
                logger.info(
                    f"Skipping {elm} as it is not a feeder CB in a sub: "
                    f"Data: {gas_switch_data} "
                )

    return new_devices


def setup_relay(
    app,
    elm,
    asset_id,
    plant_no,
    ellipse_id,
    relay_class,
    gas_switch=False,
):
    """
    Find the existing relay or fuses,
    or create a new one with the minimum required parameters

    Delete incorrectly positioned relays
    """
    # Determine required skeleton params
    if not asset_id or not plant_no or not ellipse_id:
        logger.error(
            f"Do not have all of the required values: Planto_no: {plant_no} "
            f"asset_id: {asset_id}, ellipse: {ellipse_id}, relay_class: {relay_class}"
        )
        return
    try:
        plant_no = plant_no.strip()
    except AttributeError:
        plant_no = f"NoPlantNo_Ellipse_{ellipse_id}"
        logger.error(
            f"No Plant_no for {asset_id}, ellipse: {ellipse_id}, relay_class: {relay_class}"
        )
    if relay_class == "ElmRelay":
        expected_relay_foreign_key = f"ELMREL{int(ellipse_id)}"
    elif relay_class in ["ElmFuse", "RelFuse"]:
        expected_relay_foreign_key = f"RELFUS{int(ellipse_id)}"
    else:
        raise RuntimeError(
            f"Unhandled Class {relay_class} for "
            f"{elm}, {asset_id}, {ellipse_id}, {plant_no}"
        )

    # Check for an existing relay in the correct location
    root_cub, found_relays = determine_root_cub_relay_exists(
        elm,
        expected_relay_foreign_key=expected_relay_foreign_key,
        relay_class=relay_class,
    )
    if found_relays:
        relay_exists = False
        for relay in found_relays:
            # Delete any relay that does not match the new
            existing_name = relay.GetAttribute("loc_name")
            if plant_no not in existing_name:
                relay.Delete()
                continue
            try:
                int(existing_name.replace(plant_no, "")[0])
                relay.Delete()
            except (ValueError, IndexError):
                logger.debug(f"{relay} was found for {plant_no}")
                relay_exists = True
                found_relay = relay
        if relay_exists:
            return found_relay
    else:
        # Check for a relay associated somewhere else
        existing_relay = app.SearchObjectByForeignKey(expected_relay_foreign_key)
        if existing_relay:
            relay_parent = determine_existing_relay_switch(existing_relay)

            logger.warning(
                f"{existing_relay} was found based on "
                f"{expected_relay_foreign_key} with "
                f"{relay_parent}. \n"
                f"It was not associated with {elm}. "
                f"Deleting {existing_relay}"
            )
            ef = existing_relay.Delete()
            if ef:
                if not existing_relay.IsDeleted():
                    logger.error(f"Unable to delete {existing_relay}")
            else:
                logger.debug(f"Deleted {existing_relay}")
    if root_cub is None:
        logger.error(f"Unable to create a relay for {elm} as it has no cub0")
        return None
    # Build the new relay skeleton
    new_relay = root_cub.CreateObject(relay_class, plant_no)
    try:
        new_relay.SetAttribute("for_name", expected_relay_foreign_key)
    except AttributeError:
        # Handle a relay that already has a second foreign key
        existing_relay = app.SearchObjectByForeignKey(expected_relay_foreign_key)
        if existing_relay:
            existing_relay_parent = determine_existing_relay_switch(existing_relay)
            if not existing_relay_parent:
                logger.debug(
                    f"{existing_relay} is not associated with a switch, deleting it"
                )
                existing_relay.SetAttribute("for_name", "")
                ef = existing_relay.Delete()
                try:
                    new_relay.SetAttribute("for_name", expected_relay_foreign_key)
                except AttributeError:
                    logger.error(
                        f"Still unable to set {new_relay} foreign key to "
                        f"{expected_relay_foreign_key}"
                    )
        else:
            logger.error(
                f"Unable to set {new_relay} to foreign key "
                f"{expected_relay_foreign_key} however there is no relay named "
                f"after it. Manually fix relay foreign key."
            )
    new_relay.SetAttribute("dat_src", DATA_SOURCE_STRING)
    if gas_switch:
        new_relay.SetAttribute("chr_name", GAS_SWITCH_STRING)
    new_relay.SetAttribute("outserv", 1)

    logger.info(f"Added {new_relay} for {elm} based on {asset_id}")
    return new_relay


def determine_existing_relay_switch(existing_relay):
    """
    Determine the StaSwitch/ElmCoups associated with the existing relay
    Designed for debugging and will produce:
        a list of StaSwitches,
        or a single ElmCoup or StaSwitch
    """

    # Get the relay's cub
    parent_cub = existing_relay.GetParent()

    # Check for same level within cub StaSwitches
    sta_switches = parent_cub.GetContents("*.StaSwitch")
    if sta_switches:
        if len(sta_switches) == 1:
            return sta_switches[0]
        else:
            return sta_switches

    # Get the Connected Branch Cubicle.
    try:
        cub_obj = parent_cub.GetAttribute("obj_id")
    except AttributeError:
        cub_obj = None
    return cub_obj


def determine_root_cub_relay_exists(elm, expected_relay_foreign_key, relay_class):
    """
    Return the root Cubicle where the relay should be put and if
    the relay already exists associated with elm.
    """
    found_relay = None

    if elm.GetClassName() == "ElmCoup":
        # Get the 0ths cubicle for returning
        root_cub = elm.GetCubicle(0)
        # Check for an existing relay or fuse
        cubs = [elm.GetCubicle(i) for i in range(elm.GetConnectionCount())]
        cubs = [c for c in cubs if c]

        relays = list()
        for cub in cubs:
            cub_relays = cub.GetContents(f"*.{relay_class}")
            relays.extend(cub_relays)

    elif elm.GetClassName() == "StaSwitch":
        # Get the cubicle to put the relay in
        root_cub = elm.GetParent()
        # Check for an existing relay or fuse.
        relays = root_cub.GetContents(f"*.{relay_class}")

    else:
        raise RuntimeError(f"{elm} is not of a handled classname")

    return root_cub, relays


def ellipse_ecorp_asset_id_extraction(foreign_key: str):
    """
    Get the ellipse or ecorp asset id from the foreign key. takes a string and
    returns a string of 2 or more number in length or None

    Note that because the ellipse asset id is truncated it cannot get
    ellipse ids 000000000020 and below. This should not be an issue
    """
    # The remove list only needs to be those that end in a number

    remove_list = [
        "ELMTR2",
        "ELMTR3",
        "ELMTR4",
        "BNDTR2",
        "BNDTR3",
        "BNDTR4",
    ]

    if foreign_key is None:
        return None
    elif not isinstance(foreign_key, str):
        raise ValueError(
            "Unable to determine ecorp_id from the foreign key {} "
            "which is a {} not a string".format(foreign_key, type(foreign_key))
        )

    for delete_string in remove_list:
        foreign_key = foreign_key.replace(delete_string, "")

    p = re.compile(r"[\d]{2}[\d]*")

    s = p.search(foreign_key)
    if s:
        return s.group().rjust(12, "0")
    else:
        return None
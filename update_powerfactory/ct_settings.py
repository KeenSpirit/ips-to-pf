"""
Current Transformer (CT) settings configuration for PowerFactory.

This module handles the configuration of CT devices associated with
protection relays in PowerFactory using settings from the IPS database.

It includes:
- CT slot assignment and update
- CT type selection and creation
- Measurement element configuration
"""

import logging
from typing import Any, Optional

from utils.pf_utils import all_relevant_objects
from core import UpdateResult

logger = logging.getLogger(__name__)


def update_ct(
        app,
        device_object: Any,
        result: UpdateResult
) -> UpdateResult:
    """
    Update CT configuration for a protection device.

    Once the correct mapping table can be accessed in IPS then this function
    will be expanded. Initially it deals with the need to convert a SWER
    recloser from a 3phase to 1 phase CT.

    Args:
        app: PowerFactory application object
        device_object: The ProtectionDevice to configure
        result: UpdateResult to update with CT information

    Returns:
        Updated UpdateResult with CT configuration status
    """
    # At this point the script needs to update the appropriate primary and
    # secondary turns. This means that the type needs to contain the appropriate
    # attributes.
    ct_library = all_relevant_objects(
        app, [app.GetLocalLibrary()], "Current Transformers.IntFolder"
    )
    if not ct_library:
        ct_library = app.GetLocalLibrary().CreateObject(
            "IntFolder", "Current Transformers"
        )
    else:
        ct_library = ct_library[0]

    if device_object.pf_obj.typ_id.fold_id.loc_name == "Reclosers":
        current_trans = update_ct_slots(app, device_object)
        # Check the type
        ct_type = current_trans.GetAttribute("e:typ_id")
        if not ct_type:
            ct_type = select_ct_type(app, ct_library, 1, 1)
            current_trans.SetAttribute("e:typ_id", ct_type)
        if "swer_" in device_object.device:
            # Only need to reconfigure the CT if it was configured
            current_trans.SetAttribute("iphase", 1)

        ct_name = "{}_CT".format(device_object.pf_obj.loc_name)
        result.set_ct_info(ct_name, "Recloser CT was updated")
        return result

    # Check to see if the relay has a type and if it has available CT ratios
    primary = int(float(device_object.ct_primary))
    if primary == 1:
        # This indicates that there was not a CT linked in IPS
        # The following code clears the CT slot
        slot_objs = device_object.pf_obj.GetAttribute("pdiselm")
        for i, item in enumerate(device_object.pf_obj.GetAttribute("r:typ_id:e:pblk")):
            if item.GetAttribute("filtmod") == "StaCt*":
                slot_objs[i] = None
                break
        device_object.pf_obj.SetAttribute("pdiselm", slot_objs)
        result.ct_result = "No CT Linked"
        return result

    secondary = int(float(device_object.ct_secondary))
    current_trans = update_ct_slots(app, device_object)
    required_ct_type = select_ct_type(app, ct_library, primary, secondary)

    try:
        if required_ct_type.loc_name != current_trans.GetAttribute(
                "r:typ_id:e:loc_name"
        ):
            current_trans.SetAttribute("e:typ_id", required_ct_type)
    except AttributeError:
        # This means the CT does not have a type ID already
        current_trans.SetAttribute("e:typ_id", required_ct_type)

    current_trans.SetAttribute("e:ptapset", primary)
    current_trans.SetAttribute("e:stapset", secondary)

    if device_object.ct_op_id:
        current_trans.SetAttribute("e:sernum", device_object.ct_datesetting)

    result.set_ct_info(device_object.ct_op_id, "CT info updated")

    # Check that measuring devices have matching CT secondary
    check_update_measurement_elements(app, device_object.pf_obj, secondary)

    return result


def select_ct_type(
        app,
        ct_library: Any,
        primary: int,
        secondary: int
) -> Any:
    """
    Check the local library for a suitable CT type or create a new one.

    Args:
        app: PowerFactory application object
        ct_library: The CT library folder
        primary: Primary tap setting
        secondary: Secondary tap setting

    Returns:
        The PowerFactory TypCt object
    """
    ct_types = ct_library.GetContents("*.TypCt")

    for ct_type in ct_types:
        primary_taps = ct_type.GetAttribute("e:primtaps")
        secondary_taps = ct_type.GetAttribute("e:sectaps")
        if primary in primary_taps and secondary in secondary_taps:
            break
    else:
        ct_type = ct_library.CreateObject("TypCt", "{}/{}".format(primary, secondary))
        ct_type.SetAttribute("e:primtaps", [primary])
        ct_type.SetAttribute("e:sectaps", [secondary])

    return ct_type


def update_ct_slots(app, device_object: Any) -> Any:
    """
    Update the slot in the relay that the CT is assigned to.

    A setting slot is part of a list of elements. This function will
    ensure the correct CT is allocated to the correct CT slot.

    Args:
        app: PowerFactory application object
        device_object: The ProtectionDevice being configured

    Returns:
        The PowerFactory StaCt object
    """
    pf_device = device_object.pf_obj
    cubical = pf_device.fold_id
    slot_objs = pf_device.GetAttribute("pdiselm")
    remote_ct_slot_names = ["Ct-3P(remote)", "Winding 2 Ct"]

    if not device_object.ct_op_id:
        ct_name = "{}_CT".format(pf_device.loc_name)
    else:
        ct_name = device_object.ct_op_id

    current_trans = None

    for i, item in enumerate(pf_device.GetAttribute("typ_id").GetAttribute("pblk")):
        if not item:
            continue

        filtmod = item.GetAttribute("filtmod")
        if filtmod == "StaCt*" or filtmod == "StaCt*,StaCombi":
            if item.loc_name in remote_ct_slot_names:
                # Clear the remote CT slots. These get automatically populated
                slot_objs[i] = None
                continue

            ct_obj = pf_device.GetSlot(item.GetAttribute("loc_name"))
            if not ct_obj:
                ct_obj_name = "Not Configured"
            else:
                ct_obj_name = ct_obj.loc_name

            if ct_obj_name == ct_name:
                current_trans = ct_obj
            else:
                for obj in cubical.GetContents("*.StaCt"):
                    if not obj:
                        continue
                    obj_name = obj.loc_name

                    if obj_name == ct_name:
                        slot_objs[i] = obj
                        current_trans = obj
                        break

                    if (
                            obj.ptapset == device_object.ct_primary
                            and obj.stapset == device_object.ct_secondary
                            and not device_object.ct_op_id
                    ):
                        new_name = str()
                        for char in device_object.pf_obj.loc_name:
                            if char == "_":
                                break
                            new_name = new_name + char
                        obj.loc_name = f"{new_name}_CT"
                        slot_objs[i] = obj
                        current_trans = obj
                        break
                else:
                    current_trans = cubical.CreateObject("StaCt", ct_name)
                    slot_objs[i] = current_trans

    pf_device.SetAttribute("pdiselm", slot_objs)
    return current_trans


def check_update_measurement_elements(
        app,
        pf_device: Any,
        secondary: int
) -> None:
    """
    Update measurement elements with matching CT secondary rating.

    Not all setting files have a setting that can define the secondary
    rating of the CT. This function will use the CT secondary to configure
    this attribute.

    Args:
        app: PowerFactory application object
        pf_device: The PowerFactory relay object
        secondary: The CT secondary rating
    """
    measurement_elements = pf_device.GetContents("*.RelMeasure")

    for element in measurement_elements:
        try:
            element.SetAttribute("e:Inom", secondary)
        except AttributeError:
            pass

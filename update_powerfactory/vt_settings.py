from update_powerfactory import get_objects as go

def update_vt(app, device_object, update_info):
    """VT elements are used to provide the relay with vt signals. VT are not always
    located in the same bay as the relay. Due to limitations of scripting a
    VT that is associated with the relay will be plsaced into the same cubicle."""
    # If the Vt secondary is equal to 1 then it has been determined that no
    # VT is required.
    if device_object.vt_secondary == 1:
        slot_objs = device_object.pf_obj.GetAttribute("pdiselm")
        for i, item in enumerate(device_object.pf_obj.GetAttribute("r:typ_id:e:pblk")):
            if item.GetAttribute("filtmod") == "StaVt*":
                slot_objs[i] = None
                break
        device_object.pf_obj.SetAttribute("pdiselm", slot_objs)
        update_info["VT_RESULT"] = "No VT Linked"
        return update_info
    # VTs have a type, assign the library folder containing these types to a
    # variable.
    vt_library = go.all_relevant_objects(
        app, [app.GetLocalLibrary()], "Voltage Transformers.IntFolder"
    )
    if not vt_library:
        vt_library = app.GetLocalLibrary().CreateObject(
            "IntFolder", "Voltage Transformers"
        )
    else:
        vt_library = vt_library[0]
    # Set up variables with the correct VT winding settings
    primary = int(float(device_object.vt_primary))
    secondary = int(float(device_object.vt_secondary))
    volt_trans = update_vt_slots(app, device_object)
    required_vt_type = select_vt_type(app, vt_library, primary, secondary)
    try:
        if required_vt_type.loc_name != volt_trans.GetAttribute("r:typ_id:e:loc_name"):
            volt_trans.SetAttribute("e:typ_id", required_vt_type)
    except AttributeError:
        volt_trans.SetAttribute("e:typ_id", required_vt_type)
    volt_trans.SetAttribute("e:ptapset", primary)
    volt_trans.SetAttribute("e:stapset", secondary)
    if device_object.vt_op_id:
        volt_trans.SetAttribute("e:sernum", device_object.vt_datesetting)
    update_info["VT_NAME"] = device_object.vt_op_id
    update_info["VT_RESULT"] = "VT info updated"
    # check that measureing devices have matching VT secondary.
    check_update_vt_measurement_elements(app, device_object.pf_obj, secondary)
    return update_info


def update_vt_slots(app, device_object):
    """This function will update the slot in the relay that the VT is assigned
    too. This may already set if so then check or update."""
    pf_device = device_object.pf_obj
    cubical = pf_device.fold_id
    slot_objs = pf_device.GetAttribute("pdiselm")
    if not device_object.vt_op_id:
        vt_name = "{}_VT".format(pf_device.loc_name)
    else:
        vt_name = device_object.vt_op_id
    for i, item in enumerate(pf_device.GetAttribute("typ_id").GetAttribute("pblk")):
        if not item:
            continue
        if item.GetAttribute("filtmod") == "StaVt*":
            vt_obj = pf_device.GetSlot(item.GetAttribute("loc_name"))
            if not vt_obj:
                vt_obj_name = "Not Configured"
            else:
                vt_obj_name = vt_obj.loc_name
            if vt_obj_name == vt_name:
                # This indicates that the existing assigned VT object is correctly
                # assigned
                volt_trans = vt_obj
            else:
                # Search the cubicle for a VT with a matching name
                for obj in cubical.GetContents("*.StaVt"):
                    if not obj:
                        continue
                    obj_name = obj.loc_name
                    if obj_name == vt_name:
                        # This object matches the required VT name. Assign it to
                        # the appropriate slot
                        slot_objs[i] = obj
                        volt_trans = obj
                        break
                    if (
                        obj.ptapset == device_object.vt_primary
                        and obj.stapset == device_object.vt_secondary
                        and not device_object.ct_op_id
                    ):
                        # This deals with objects that have the correct tappings
                        new_name = str()
                        for char in device_object.pf_obj.loc_name:
                            if char == "_":
                                break
                            new_name = new_name + char
                        obj.loc_name = f"{new_name}_VT"
                        slot_objs[i] = obj
                        volt_trans = obj
                        break
                else:
                    volt_trans = cubical.CreateObject("StaVt", vt_name)
                    slot_objs[i] = volt_trans
    pf_device.SetAttribute("pdiselm", slot_objs)
    return volt_trans


def select_vt_type(app, vt_library, primary, secondary):
    """This function will check the local library to see if a suitable
    VT type is available. If not then it will create a new one."""
    vt_types = vt_library.GetContents("*.TypVt")
    for vt_type in vt_types:
        primary_taps = vt_type.GetAttribute("e:primtaps")
        if primary in primary_taps:
            break
    else:
        vt_type = vt_library.CreateObject("TypVt", "{}/{}".format(primary, secondary))
        vt_type.SetAttribute("e:primtaps", [primary])
        vt_type.SetAttribute("e:iopt_mod", 0)
    return vt_type


def check_update_vt_measurement_elements(app, pf_device, secondary):
    """Not all setting files have a setting that can define the secondary
    rating of the VT. This function will use the VT secondary to configure this
    attribute."""
    measurement_elements = pf_device.GetContents("*.RelMeasure")
    for element in measurement_elements:
        try:
            element.SetAttribute("e:Unom", secondary)
        except AttributeError:
            pass
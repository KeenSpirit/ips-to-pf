def fuse_setting(app, device_object, fuse_types):
    """Fuse can only be configured one way"""
    # Record the information of the conversion and display this in output window
    # or be recorded in a CSV if run as part of a batch.
    update_info = {}
    # Extract a plant number from the name of the device that the user has configured
    update_info["SUBSTATION"] = device_object.pf_obj.GetAttribute("r:cpGrid:e:loc_name")
    update_info["PLANT_NUMBER"] = device_object.pf_obj.loc_name
    curve_type = str()
    # If the device is a line fuse but does not have a matching setting
    if device_object.fuse_type == "Line Fuse" and not device_object.setting_id:
        update_info["RESULT"] = "Not in IPS"
        return update_info
    # Determine the device type and the setting id(this is an IPS attribute)
    if device_object.fuse_type == "Line Fuse":
        for setting in device_object.settings:
            # A setting has been found but the setting values are empty
            if len(setting) < 3:
                update_info["RESULT"] = "Not in IPS"
                return update_info
            if setting[1].lower() == "curve" and "Dual Rated" in setting[2]:
                curve_type = "K"
            elif setting[1].lower() == "curve":
                curve_type = setting[2]
            elif setting[1] == "MAX" and "Dual Rated" in setting[2]:
                rating = " {}/".format(setting[2])
            elif setting[1] in ["MAX", "In"]:
                rate_set = str()
                for char in setting[2]:
                    if char == "." or char == ",":
                        break
                    else:
                        rate_set = "{}{}".format(rate_set, char)
                rating = " {}A".format(rate_set)
    for fuse in fuse_types:
        if curve_type.lower() == fuse.loc_name[-1].lower() and rating in fuse.loc_name:
            break
        elif device_object.fuse_size:
            if (
                device_object.fuse_size[-1] == fuse.loc_name[-1]
                and device_object.fuse_size[:-1] in fuse.loc_name
            ):
                break
    else:
        update_info["RELAY_PATTERN"] = device_object.device
        update_info["USED_PATTERN"] = device_object.device
        update_info["RESULT"] = "Type Matching Error"
        return update_info
    # Set the relay with the information about which setting from IPS was used
    device_object.pf_obj.SetAttribute("e:chr_name", str(device_object.date))
    update_info["DATE_SETTING"] = device_object.date
    update_info["RELAY_PATTERN"] = device_object.device
    update_info["USED_PATTERN"] = device_object.device
    try:
        if device_object.pf_obj.typ_id.loc_name != fuse.loc_name:
            device_object.pf_obj.typ_id = fuse
        else:
            update_info["RESULT"] = "Type Correct"
    except AttributeError:
        device_object.pf_obj.typ_id = fuse
    device_object.pf_obj.SetAttribute("e:outserv", 0)
    return update_info
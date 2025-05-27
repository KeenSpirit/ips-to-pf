import logging

class ProtectionDevice:
    """Each protection device will have its own object. They will have
    IPS data attributed to them for use in configuring a device in PF."""

    def __init__(
        self, app, device, name, setting_id, date, pf_obj, device_id, *args, **kwargs
    ):
        self.app = app
        self.device = device
        self.device_id = device_id
        self.name = name
        self.setting_id = setting_id
        self.date = date
        self.pf_obj = pf_obj
        self.ct_primary = 1
        self.ct_secondary = 1
        self.vt_primary = 1
        self.vt_secondary = 1
        self.ct_op_id = str()
        self.vt_op_id = str()
        self.multiple = False
        self.fuse_type = None
        self.fuse_size = None

    # ips_settings = {relaysettingid: [setting, setting, setting...]}

    # [self.setting_id] = [setting, setting, setting...]

    # row = setting

    # setting = {blockpathenu: value, paramnameenu: value, proposedsetting: unitenu}


    def associated_settings(self, all_settings):
        """This function will go through the full list of settings and
        determine all settings associated with that protection device."""
        self.settings = []
        if not self.setting_id:
            return
        for row in all_settings[self.setting_id]:
            setting = []
            setting.append(row["blockpathenu"])
            setting.append(row["paramnameenu"])
            setting.append(row["proposedsetting"])
            setting.append(row["unitenu"])
            self.settings.append(setting)
            # based on settings determine CT ratios
            try:
                if str(row["paramnameenu"]) in ["0120", "Iprim", "0A07"]:
                    self.ct_primary = int(float(row["proposedsetting"]))
                elif str(row["paramnameenu"]) in ["0121", "In", "0A08"]:
                    self.ct_secondary = int(float(row["proposedsetting"]))
            except ValueError:
                pass

    def seq_instrument_attributes(self, all_settings):
        """This function will use the setting ID to assocaite a CT or VT to the
        particular relay"""
        for row in all_settings:
            if row.relaysettingid == self.setting_id:
                self.ct_settingid = row.relaysettingid
                if not row.actualvalue:
                    continue
                if "Iprim" in row.nameenu:
                    value = int(float(row.actualvalue))
                    if value > self.ct_primary:
                        self.ct_primary = value
                elif "Isec" in row.nameenu:
                    self.ct_secondary = int(float(row.actualvalue))
                elif "Vprim" in row.nameenu:
                    self.vt_primary = int(float(row.actualvalue))
                elif "Vsec" in row.nameenu:
                    self.vt_secondary = int(float(row.actualvalue))

    def reg_instrument_attributes(self, all_settings):
        """This function will use the setting ID to associate a CT or VT to the
        particular relay"""
        for row in all_settings:
            if row.relaysettingid == self.setting_id and row.setting:
                if not self.ct_op_id and "CT" in row.nameenu:
                    self.ct_op_id = row.propvalue
                    self.ct_settingid = row.itsettingid
                    self.ct_datesetting = row.datesetting
                if not self.vt_op_id and "VT" in row.nameenu:
                    self.vt_op_id = row.propvalue
                    self.vt_settingid = row.itsettingid
                    self.vt_datesetting = row.datesetting
                if "CT" in row.nameenu and "Primary" in row.paramnameenu:
                    self.ct_primary = int(float(row.setting))
                elif "CT" in row.nameenu and "Secondary" in row.paramnameenu:
                    self.ct_secondary = int(float(row.setting))
                elif "VT" in row.nameenu and "Primary" in row.paramnameenu:
                    self.vt_primary = int(float(row.setting))
                elif "VT" in row.nameenu and "Secondary" in row.paramnameenu:
                    self.vt_secondary = int(float(row.setting))

def prot_device(app):
    """Obtain all protection devices that currently existing in PowerFactory. """
    # Create a list of relays in the model
    # Relays belong in the network model project folder.
    net_mod = app.GetProjectFolder("netmod")
    # Filter for for relays under network model recursively.
    all_relays = net_mod.GetContents("*.ElmRelay", True)
    relays = [
        relay
        for relay in all_relays
        if relay.HasAttribute("e:cpGrid")
        if relay.GetParent().GetClassName() == "StaCubic"
        if relay.fold_id.cterm.IsEnergized()
        if not relay.IsOutOfService()
        if relay.IsCalcRelevant()
    ]
    # Create a list of active fuses
    all_fuses = net_mod.GetContents("*.RelFuse", True)
    fuses = [
        fuse
        for fuse in all_fuses
        if fuse.fold_id.HasAttribute("cterm")
        if fuse.fold_id.cterm.IsEnergized()
        if not fuse.IsOutOfService()
        if determine_line_fuse(fuse)
    ]
    devices = relays + fuses
    # Create a list of all the feeders
    net_data = app.GetProjectFolder("netdat")
    active_feeders = [
        feeder
        for feeder in net_data.GetContents("*.ElmFeeder", True)
        if not feeder.IsOutOfService()
    ]
    # Construct the dictionary of relays for use in the script
    device_object_dict = {}
    for device in devices:
        term = device.cbranch
        feeder = [
            feeder.loc_name for feeder in active_feeders if term in feeder.GetAll()
        ]
        if not feeder:
            feeder = ["Not in a Feeder"]
        try:
            num_of_phases = device.GetAttribute("r:cbranch:r:bus1:e:nphase")
        except AttributeError:
            num_of_phases = 3
        device_object_dict[device.loc_name] = [
            device,
            device.GetClassName(),
            num_of_phases,
            feeder[0],
            device.cpGrid.loc_name,
        ]
    return [devices, device_object_dict]


def determine_line_fuse(fuse):
    """This function will observe the fuse location and determine if it is
    a Distribution transformer fuse, SWER isolating fuse or a line fuse"""
    # First check is that if the fuse exists in a terminal that is in the
    # System Overiew then it will be a line fuse.
    fuse_active = fuse.HasAttribute("r:fold_id:r:obj_id:e:loc_name")
    if not fuse_active:
        return True
    fuse_grid = fuse.cpGrid
    if (
        fuse.GetAttribute("r:fold_id:r:cterm:r:fold_id:e:loc_name")
        == fuse_grid.loc_name
    ):  # noqa [E501]
        # This would indicate it is in a line cubical
        return True
    if fuse.loc_name not in fuse.GetAttribute("r:fold_id:r:obj_id:e:loc_name"):
        # This indicates that the fuse is not in a switch object
        return True
    secondary_sub = fuse.fold_id.cterm.fold_id
    contents = secondary_sub.GetContents()
    for content in contents:
        if content.GetClassName() == "ElmTr2":
            return False
    else:
        return True


def determine_fuse_type(app, fuse):
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
    except:  # noqa [E722]
        fuse_size = "3/10K"
        return ["Tx Fuse", fuse_size]


def create_fuse_dict():
    """This has been developed based on STNW1001. The key will be
    transfomer type, Voltage level, rating"""
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


def log_device_atts(prot_dev):
    """
    Log the device attributes.
    Settings attribute is logged as 'yes/no' to keep logged data to manageable levels
    Args:
        prot_dev:

    Returns:
    logged device attributes
    """

    logging.info(f"Attributes for protection device{prot_dev.device}:")
    attributes = dir(prot_dev)
    for attr in attributes:
        if not attr.startswith('__'):
            value = getattr(prot_dev, attr)
            if attr == 'settings':
                if len(value) > 0:
                    value = 'settings loaded'
                else:
                    value = 'no settings loaded'
            logging.info(f"{attr}: {value}")
import powerfactory as pf
import sys
import os
import csv
import tkinter as tk
from tkinter import *  # noqa [F403]
from tkinter import ttk
import time
import yaml

# Set up Oracle library for querying - commented out as installed in Citrix.
# os.environ["PATH"] = os.pathsep.join(
#    (
#        os.path.abspath(
#            "\\ecasd01\WksMgmt\PowerFactory\ScriptsDEV\IPSProtectionDeviceSettings\instantclient_11_2"  # noqa [E501]
#        ),
#        os.environ["PATH"],
#    )
# )
# import cx_Oracle

sys.path.append(
    r"\\ecasd01\WksMgmt\PowerFactory\ScriptsDEV\AddProtectionRelaySkeletons\addprotectionrelayskeletons"  # noqa [E501]
)
import add_protection_relay_skeletons

sys.path.append(r"\\ecasd01\WksMgmt\PowerFactory\ScriptsLIB\NetDash-Reader")
from netdashread import get_json_data
from tenacity import retry
from tenacity import stop_after_attempt, wait_random_exponential
from assetclasses.corporate_data import get_cached_data


def main(app=None, batch=False):
    """This Script Will be used to transfer Settings from IPS to PF. This
    script can be used for with region"""
    start_time = time.strftime("%H:%M:%S")
    # Record if the project has an setting updated
    updates = False
    if not app:
        # Change to True if you want to mimic a batch update
        called_function = False
        app = pf.GetApplication()
    else:
        called_function = True
    app.ClearOutputWindow()
    # Create file to save batch script information
    prjt = app.GetActiveProject()
    project_name = prjt.GetAttribute("loc_name")
    current_user = app.GetCurrentUser()
    current_user_name = current_user.GetAttribute("loc_name")
    parent_folder = prjt.GetAttribute("fold_id")
    parent_folder_name = parent_folder.GetAttribute("loc_name")
    file_name = f"{current_user_name}_{parent_folder_name}_{project_name}".replace(
        "/", "_"
    )
    if called_function:
        file_location = r"\\ecasd01\WksMgmt\PowerFactory\ScriptsDEV\IPSDataTransferMastering\Script_Results"  # noqa [E501]
        main_file_name = select_main_file(
            app, file_name, file_location, called_function
        )
    else:
        file_location = r"C:\LocalData\PowerFactory Output Folders\IPS Data Transfer"
        main_file_name = select_main_file(
            app, file_name, file_location, called_function
        )
    if not main_file_name:
        return
    # Determine which IPS data base is to be quiried
    region = determine_region(app, prjt)
    if not region:
        return
    if called_function:
        ips_db = determine_ips_db(app, region)
        # Set up a connection to the IPS Database
        ips_connection = connect_to_db(region, ips_db)
    # Create a list captureing all the update data.
    data_capture_list = []
    set_ids = None
    failed_cbs = []
    # Create a Dictionary for the setting ids
    app.PrintInfo("Creating the Setting ID Dictionary")
    ids_dict_list = create_ids_dict(app, region)
    attempts = 1
    while len(ids_dict_list) == 0:
        # If someone else has started the script at the exact same time
        # it prevents other users from accessing the cached data csv
        time.sleep(10)
        ids_dict_list = create_ids_dict(app, region)
        attempts += 1
        if attempts > 5 and len(ids_dict_list) == 0:
            error_message(
                app,
                "Unable to obtained data for Setting IDs,"
                " please contact the Protection SME",
            )
    # Get the selected Device
    if not batch:
        [set_ids, lst_of_devs, data_capture_list] = prot_dev_lst(
            app, region, data_capture_list, ids_dict_list
        )
    if batch or set_ids == "Batch":
        if region == "Energex":
            app.PrintInfo("Creating a list of Setting IDs")
            # Create a list of setting ids for each device in the network
            [lst_of_devs, failed_cbs, set_ids] = create_new_devices(
                app, ids_dict_list, called_function
            )
        else:
            add_protection_relay_skeletons.main(app)
            app.ClearOutputWindow()
            start_time = time.strftime("%H:%M:%S")
            app.PrintInfo("Creating a list of Setting IDs")
            [set_ids, lst_of_devs, data_capture_list] = ergon_all_dev_list(
                app, data_capture_list, ids_dict_list, called_function
            )
    # start_time = time.strftime("%H:%M:%S")
    if region == "Energex":
        if called_function:
            ips_settings = {}
            while len(set_ids) > 900:
                ids_1 = set_ids[:900]
                ips_settings.update(batch_seq_get_ips_settings(ips_connection, ids_1))
                set_ids = set_ids[900:]
            if len(set_ids) < 900:
                ips_settings.update(batch_seq_get_ips_settings(ips_connection, set_ids))
        ips_it_settings = seq_get_ips_it_details(app, set_ids)
    else:
        if called_function:
            ips_settings = {}
            while len(set_ids) > 900:
                ids_1 = set_ids[:900]
                ips_settings.update(batch_reg_get_ips_settings(ips_connection, ids_1))
                set_ids = set_ids[900:]
            if len(set_ids) < 900:
                ips_settings.update(batch_reg_get_ips_settings(ips_connection, set_ids))
        ips_it_settings = reg_get_ips_it_details(app, set_ids)
    # Get all associated settings and attirbutes from IPS
    for i, device_object in enumerate(lst_of_devs):
        if i % 10 == 0:
            app.ClearOutputWindow()
            app.PrintInfo(
                f"device number {i} of {len(lst_of_devs)} has had its"
                " setting attributes assigned"
            )
        if device_object.device:
            if called_function:
                device_object.associated_settings(ips_settings)
            if ips_it_settings:
                if region == "Energex":
                    device_object.seq_instrument_attributes(ips_it_settings)
                else:
                    device_object.reg_instrument_attributes(ips_it_settings)
    if called_function:
        # Close the IPS connection
        ips_connection.close()
    # Create a list of all the fuse types
    ergon_lib = app.GetGlobalLibrary()
    app.PrintInfo("Creating a database of PowerFactory Fuse and Relay Types")
    # fuse_folder = ergon_lib.SearchObject("Protection\\Fuses.IntFolder")
    fuse_folder = ergon_lib.SearchObject(r"\ErgonLibrary\Protection\Fuses.IntFolder")
    fuse_types = fuse_folder.GetContents("*.TypFuse", 0)
    # Create a list of relay types
    relay_types = get_relay_types(app)
    # Begin to update the PowerFactory relays with data from IPS
    update_info = {}
    app.SetWriteCacheEnabled(1)
    for i, device_object in enumerate(lst_of_devs):
        if i % 10 == 0:
            app.PrintInfo(f"Device {i} of {len(lst_of_devs)} is being updated")
        if not device_object.pf_obj:
            continue
        # Check to see if there is a setting for the device
        if not device_object.setting_id and not device_object.fuse_type:
            update_info["SUBSTATION"] = device_object.pf_obj.GetAttribute(
                "r:cpGrid:e:loc_name"
            )
            update_info["PLANT_NUMBER"] = device_object.pf_obj.loc_name
            update_info["RESULT"] = "Not in IPS"
            data_capture_list.append(update_info)
            update_info = {}
            continue
        try:
            # Start configuring the device
            if device_object.pf_obj.GetClassName() == "ElmRelay":
                [update_info, updates] = relay_settings(
                    app, device_object, relay_types, updates
                )
            else:
                update_info = fuse_setting(app, device_object, fuse_types)
        except:  # noqa [E722]
            try:
                update_info["SUBSTATION"] = device_object.pf_obj.GetAttribute(
                    "r:cpGrid:e:loc_name"
                )  # noqa [E122]
            except AttributeError:
                update_info["SUBSTATION"] = "UNKNOWN"
            update_info["PLANT_NUMBER"] = device_object.pf_obj.loc_name
            update_info["RELAY_PATTERN"] = device_object.device
            update_info["RESULT"] = "Script Failed"
            device_object.pf_obj.SetAttribute("outserv", 1)
        # At the moment feeder diff relays should out of service.
        if device_object.device in [
            "7PG21 (SOLKOR-RF)",
            "7SG18 (SOLKOR-N)",
            "RED615 2.6 - 2.8",
            "SOLKOR-N_Energex",
            "SOLKOR-RF_Energex",
        ]:
            device_object.pf_obj.SetAttribute("outserv", 1)
        try:
            if device_object.switch.on_off == 0:
                device_object.pf_obj.SetAttribute("outserv", 1)
        except:  # noqa [E722]
            pass
        data_capture_list.append(update_info)
        update_info = {}
    app.WriteChangesToDb()
    app.SetWriteCacheEnabled(0)
    update_info = {}
    for cb in failed_cbs:
        update_info["SUBSTATION"] = cb.GetAttribute("r:cpGrid:e:loc_name")
        update_info["CB_NAME"] = cb.loc_name
        update_info["RESULT"] = "Failed to find match"
        data_capture_list.append(update_info)
        update_info = {}
    write_data(app, data_capture_list, main_file_name)
    if not batch:
        print_results(app, data_capture_list)
    stop_time = time.strftime("%H:%M:%S")
    app.PrintInfo(
        "Script started at {} and finshed at {}".format(start_time, stop_time)
    )
    if updates:
        app.PrintInfo("Of the device selected there were updated settings")
    else:
        app.PrintInfo("Of the device selected there were no updated settings")
    return updates


def all_relevant_objects(app, folders, type_of_obj, objects=None):
    """When performing a GetContents on objects outside your own user, the function
    can take a significant amount of time. This is a quick function to perform
    a similar type function."""
    for folder in folders:
        if not objects:
            objects = folder.GetContents(type_of_obj, 0)
        else:
            objects += folder.GetContents(type_of_obj, 0)
        sub_folders = folder.GetContents("*.IntFolder", 0)
        sub_folders += folder.GetContents("*.IntPrjfolder", 0)
        if sub_folders:
            objects = all_relevant_objects(app, sub_folders, type_of_obj, objects)
    return objects


def apply_settings(app, device_object, mapping_file, setting_dict, updates):
    """This function will go through each line of the mapping file and
    apply the setting."""
    pf_device = device_object.pf_obj
    for mapped_set in mapping_file:
        # This function is not used to deal with and logic elements
        if (
            "_logic" in mapped_set[1]
            or "_dip" in mapped_set[1]
            or "_Trips" in mapped_set[1]
        ):
            continue
        # Get the PowerFactory object for the setting to be applied to
        element = find_element(app, pf_device, mapped_set)
        if not element:
            app.PrintError("Unable to find an element for {}".format(mapped_set))
            continue
        key = str().join(mapped_set[:3])
        try:
            setting = setting_dict[key]
        except KeyError:
            # This is to deal with the outserv attributes.
            if mapped_set[2] == "outserv":
                setting = None
            else:
                continue
        attribute = "e:{}".format(mapped_set[2])
        updates = set_attribute(
            app,
            mapped_set,
            setting,
            element,
            attribute,
            device_object,
            setting_dict,
            updates,
        )
    return updates


def batch_reg_get_ips_settings(connection, unique_ids):
    """Using the unique setting ID get the full setting file from the DB"""
    ips_cursor = connection.cursor()
    settings = ips_cursor.execute(
        """
        SELECT  relparblock.blockpathenu
                , RelParModel.ParamNameENU
                ,CASE
                    when RelParModel.DataType = 'Enum' then RelParEnumItem.TextENU
                    else RelayParam.Actual
                end as ProposedSetting
                , RelParModel.UnitENU
                , RelaySetting.RelaySettingID
        FROM    EDW_LDG_OWNER.IPS_RelParBlock  RelParBlock_2 INNER JOIN
                EDW_LDG_OWNER.IPS_RelParBlock  RelParBlock_1 ON
                RelParBlock_2.RelParBlockID = RelParBlock_1.ParentRowID RIGHT OUTER JOIN
                EDW_LDG_OWNER.IPS_RelayParam RelayParam INNER JOIN
                EDW_LDG_OWNER.IPS_RelayParamSet RelayParamSet ON
                RelayParam.RelayParamSetID = RelayParamSet.RelayParamSetID INNER JOIN
                EDW_LDG_OWNER.IPS_RelaySetting RelaySetting ON
                RelayParamSet.RelaySettingID = RelaySetting.RelaySettingID INNER JOIN
                EDW_LDG_OWNER.IPS_RelParModel RelParModel ON
                RelayParam.RelParModelID = RelParModel.RelParModelID INNER JOIN
                EDW_LDG_OWNER.IPS_RelParBlock RelParBlock ON
                RelParModel.RelParBlockID = RelParBlock.RelParBlockID INNER JOIN
                EDW_LDG_OWNER.IPS_MntAsset MntAsset ON
                RelaySetting.AssetID = MntAsset.AssetId LEFT OUTER JOIN
                EDW_LDG_OWNER.IPS_RelParEnumItem RelParEnumItem ON
                RelayParam.Actual = RelParEnumItem.RelParEnumItemID LEFT OUTER JOIN
                EDW_LDG_OWNER.IPS_RelParEnum RelParEnum ON
                RelParModel.RelParEnumID = RelParEnum.RelParEnumID ON
                RelParBlock_1.RelParBlockID = RelParBlock.ParentRowID
        WHERE   RelaySetting.RelaySettingID IN ("""
        + "'"
        + "','".join(unique_ids)
        + "'"
        + """)
        ORDER BY RelaySetting.AssetID
        """
    )
    setting_id_dict = {}
    for set_id in unique_ids:
        setting_id_dict[set_id] = []
    for setting in settings:
        if not setting[2]:
            continue
        setting_dict = {}
        col_names = [
            "blockpathenu",
            "paramnameenu",
            "proposedsetting",
            "unitenu",
            "relaysettingid",
        ]
        for i, col_name in enumerate(col_names):
            setting_dict[col_name] = setting[i]
        setting_id_dict[setting_dict["relaysettingid"]].append(setting_dict)
    return setting_id_dict


def batch_seq_get_ips_settings(connection, unique_ids):
    """Using the unique setting ID get the full setting file from the DB"""
    ips_cursor = connection.cursor()
    settings = ips_cursor.execute(
        """
        SELECT
            relparblock.blockpathenu,relparmodel.paramnameenu,
            CASE
                when relparmodel.datatype = 'Enum'
                then CAST (relparenumitem.textenu AS NVARCHAR2(2000))
                else CAST (relayparam.actual AS NVARCHAR2(2000))
            end as proposedsetting, relparmodel.unitenu, relaysetting.relaysettingid
            FROM
                edw_ldg_owner.ips_relparblock relparblock_2
                INNER JOIN edw_ldg_owner.ips_relparblock relparblock_1 ON
                relparblock_2.relparblockid = relparblock_1.parentrowid
                RIGHT OUTER JOIN (
                edw_ldg_owner.ips_relayparam relayparam
                INNER JOIN edw_ldg_owner.ips_relayparamset relayparamset ON
                relayparam.relayparamsetid = relayparamset.relayparamsetid
                INNER JOIN edw_ldg_owner.ips_relaysetting relaysetting ON
                relayparamset.relaysettingid = relaysetting.relaysettingid
                INNER JOIN edw_ldg_owner.ips_relparmodel relparmodel ON
                relayparam.relparmodelid = relparmodel.relparmodelid
                INNER JOIN edw_ldg_owner.ips_relparblock relparblock ON
                relparmodel.relparblockid = relparblock.relparblockid
                INNER JOIN edw_ldg_owner.ips_mntasset mntasset ON
                relaysetting.assetid = mntasset.assetid
                LEFT OUTER JOIN edw_ldg_owner.ips_relparenumitem relparenumitem ON
                relayparam.actual = relparenumitem.relparenumitemid
                LEFT OUTER JOIN edw_ldg_owner.ips_relparenum relparenum ON
                relparmodel.relparenumid = relparenum.relparenumid ) ON
                relparblock_1.relparblockid = relparblock.parentrowid
        WHERE   relaySetting.relaysettingid IN ("""
        + "'"
        + "','".join(unique_ids)
        + "'"
        + """)
                AND relayparam.actual IS NOT NULL
        ORDER BY relaysetting.assetid
        """
    )
    setting_id_dict = {}
    for set_id in unique_ids:
        setting_id_dict[set_id] = []
    for setting in settings:
        setting_dict = {}
        col_names = [
            "blockpathenu",
            "paramnameenu",
            "proposedsetting",
            "unitenu",
            "relaysettingid",
        ]
        for i, col_name in enumerate(col_names):
            setting_dict[col_name] = setting[i]
        setting_id_dict[setting_dict["relaysettingid"]].append(setting_dict)
    return setting_id_dict


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_random_exponential(multiplier=1, max=5),
)
def cached_data(report):
    """This retrieves the IPS data from NetDash"""
    # The csvs should be updated every 3 days.
    # Previous max age set to 129600
    rows = get_cached_data(report, max_age=3)
    return rows


def check_update_measurement_elements(app, pf_device, secondary):
    """Not all setting files have a setting that can define the secondary
    rating of the CT. This function will use the CT secondary to configure this
    attribute."""
    measurement_elements = pf_device.GetContents("*.RelMeasure")
    for element in measurement_elements:
        try:
            element.SetAttribute("e:Inom", secondary)
        except AttributeError:
            pass


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


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_random_exponential(multiplier=1, max=5),
)
def connect_to_db(region, ips_db):
    """The IPS data is mirrored into the Ergon ODS. This data base contains the information
    about the protection settings"""
    # Get the credientials to access the production database
    [username, password] = user_name_password(region)
    # tns = cx_Oracle.makedsn(ips_db[0], 1521, service_name=ips_db[1])
    # connection = cx_Oracle.connect(username, password, tns)
    connection = None
    return connection


def convert_binary(app, setting_value, line):
    """Some settings are provided in binary. These need to be converted to
    be properly configured in PF"""
    binary_val = str(bin(int(setting_value))).replace("0b", "")
    bits_of_int = [-int(num) for num in line[-2]]
    binary_val = "0000000000000" + binary_val
    new_setting_value = str()
    for bit_of_int in bits_of_int:
        new_setting_value += binary_val[bit_of_int]
    return new_setting_value


def convert_string_to_list(string):
    """This provides the user the ability to set an Off statement for the
    out of service attribute by multiple things"""
    new_list = []
    element = str()
    for char in string:
        if char in ["[", " "]:
            continue
        elif char == ",":
            new_list.append(element)
            element = str()
            continue
        elif char == "]":
            new_list.append(element)
            break
        element += char.lower()
    return new_list


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


def create_ids_dict(app, region):
    """This function will create a dictionary of setting ids based on the
    extracted IPS data."""
    if region == "Energex":
        rows = cached_data("Report-Cache-ProtectionSettingIDs-EX")
    else:
        rows = cached_data("Report-Cache-ProtectionSettingIDs-EE")
    ids_dict_list = []
    for row in rows:
        try:
            ids_dict_list.append(dict(row._asdict()))
        except:  # noqa [E722]
            continue
    return ids_dict_list


def create_new_devices(app, ids_dict_list, called_function):
    """This is for SEQ models. It uses switch names to search IPS to find
    a match. If a match is found then a device is added into the appropriate
    cubicle. This will also return the objects of each instance with the
    associated settings."""
    prjt = app.GetActiveProject()
    cb_alt_name_list = get_cb_alt_name_list(app)
    # Create a list of switches
    raw_switches = prjt.GetContents("*.StaSwitch", True) + prjt.GetContents(
        "*.ElmCoup", True
    )
    switches = [
        switch
        for switch in raw_switches
        if switch.GetAttribute("cpGrid")
        if not switch.IsOutOfService()
        if switch.IsCalcRelevant()
        if switch.IsEnergized()
    ]
    failed_cbs = []
    setting_ids = []
    list_of_devices = []
    for i, switch in enumerate(switches):
        num_of_devices = len(setting_ids)
        try:
            # Dealing with ElmCoup switches that are not feeder bay switches
            int(switch.loc_name[2])
            if switch.GetClassName() != "StaSwitch":
                continue
        except:  # noqa [E722]
            pass
        if i % 10 == 0:
            app.ClearOutputWindow()
            app.PrintInfo(f"IPS is being checked for switch {i} of {len(switches)}")
        try:
            if switch.GetClassName() == "StaSwitch" and not switch.GetAttribute(
                "r:fold_id:r:obj_id:e:loc_name"
            ):
                continue
        except AttributeError:
            continue
        [setting_ids, list_of_devices] = seq_get_setting_id(
            app,
            None,
            switch,
            setting_ids,
            list_of_devices,
            ids_dict_list,
            called_function,
            cb_alt_name_list,
        )
        if len(setting_ids) == num_of_devices:
            # This indicates that this switch does not have any a protection device
            # In this case delete an protection device that already exists
            if switch.GetClassName() == "StaSwitch":
                contents = switch.fold_id.GetContents()
            else:
                root_cub = switch.GetCubicle(0)
                contents = root_cub.GetContents()
            for content in contents:
                if content.GetClassName() in ["ElmRelay", "RelFuse", "StaCt"]:
                    content.Delete()
            if (
                switch.GetClassName() == "ElmCoup"
                and switch.GetAttribute("e:aUsage") == "cbk"
            ):  # noqa [E501]
                if switch not in failed_cbs:
                    failed_cbs.append(switch)
    used_names = []
    for device in list_of_devices:
        switch = device.switch
        if not device.device_id:
            device_name = f"{device.name}_{device.seq_name}".rstrip()
        else:
            device_name = f"{device.name}_{device.device_id}".rstrip()
            if device_name in used_names:
                # This will handle wher ethe same device ID has been used
                device_name = (
                    f"{device.name}_{device.device_id}_{device.seq_name}".rstrip()
                )  # noqa [E501]
        used_names.append(device_name)
        # Check to see if a PF object already exists
        if switch.GetClassName() == "StaSwitch":
            # This indicates that the relay would be in the same cubicle
            contents = switch.fold_id.GetContents(f"{device_name}.ElmRelay")
            contents += switch.fold_id.GetContents(f"{device_name}.RelFuse")
        else:
            root_cub = switch.GetCubicle(0)
            contents = root_cub.GetContents(f"{device_name}.ElmRelay")
            contents += root_cub.GetContents(f"{device_name}.RelFuse")
        if contents:
            # This deivice already exists
            device.pf_obj = contents[0]
            continue
        # If a setting was found for a switch that doesn't already have an
        # associated protection device
        if "fuse" in device.device.lower():
            if switch.GetClassName() == "StaSwitch":
                device_pf = switch.fold_id.CreateObject("RelFuse", device_name)
                if device_pf.loc_name != device_name:
                    device_pf.Delete()
                    list_of_devices.remove(device)
                else:
                    device.pf_obj = device_pf
            elif switch.GetClassName() == "ElmCoup":
                root_cub = switch.GetCubicle(0)
                if device_pf.loc_name != device_name:
                    device_pf.Delete()
                    list_of_devices.remove(device)
                else:
                    device.pf_obj = device_pf
        else:
            if switch.GetClassName() == "StaSwitch":
                device_pf = switch.fold_id.CreateObject("ElmRelay", device_name)
                if device_pf.loc_name != device_name:
                    device_pf.Delete()
                    list_of_devices.remove(device)
                else:
                    device.pf_obj = device_pf
            elif switch.GetClassName() == "ElmCoup":
                root_cub = switch.GetCubicle(0)
                device_pf = root_cub.CreateObject("ElmRelay", device_name)
                if device_pf.loc_name != device_name:
                    device_pf.Delete()
                    list_of_devices.remove(device)
                else:
                    device.pf_obj = device_pf
    return [list_of_devices, failed_cbs, setting_ids]


def create_setting_dictionary(app, settings, mapping_file, pf_device):
    """The settings will have an associated key that maps a setting value to
    an attribute in PF. This function will take the settings and create a
    dictionary"""
    setting_dictionary = {}
    for setting in settings:
        lines = mapping_file
        for i, value in enumerate(setting):
            prob_lines = []
            for line in lines:
                if line[3] in ["None", "ON", "On", "OFF", "Off"]:
                    # This setting is not required as part of this relay.
                    if len(line) < 5:
                        continue
                # Determine the index of the associated setting reference from the
                # line in the mapping file.
                index = i + 3  # This allows the index to be adjusted to start at
                # Column D in the mapping file.
                if line[index] == "use_setting":
                    key = str().join(line[:3])
                    if setting[-1] in ["mA", "ms"]:
                        setting[i] = float(setting[i]) / 1000
                    elif setting[-1] in ["kA"]:
                        setting[i] = float(setting[i]) * 1000
                    setting_dictionary[key] = setting[i]
                    continue
                elif (
                    str(line[index]) != str(value)
                    and "0{}".format(line[index]) != value
                ):
                    # Where the setting address is a number it has the ability
                    # to drop the front 0.
                    continue
                else:
                    # Multiple lines in the mapping file could have a couple of
                    # similar values until the full key is determined.
                    # app.PrintError(line)
                    prob_lines.append(line)
            if not prob_lines:
                break
            lines = prob_lines
    return setting_dictionary


def determine_ips_db(app, region):
    """This function relies on the file structure under the Publisher"""
    if region == "Energex":
        ips_db = [
            "cbnf1c02vm01-vip.au1.ocm.s7130879.oraclecloudatcustomer.com",
            "XEDWHPS1.au1.ocm.s7130879.oraclecloudatcustomer.com",
        ]
        return ips_db
    else:
        ips_db = [
            "cbns1c-scan1",
            "ERG_EDW_PROD.au2.ocm.s7134658.oraclecloudatcustomer.com",
        ]
        return ips_db


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


def determine_on_off(app, setting_value, disable_cond):
    """Each device can have different ways of enabling or disabling an element"""
    try:
        disable_cond = int(disable_cond)
    except (ValueError, TypeError):
        # The Disabled condition should be in a list format. Each entry should be
        # in lower case.
        disable_list = []
        if "[" in disable_cond and "]" in disable_cond:
            disable_list = convert_string_to_list(disable_cond)
        else:
            disable_list.append(disable_cond.lower())
    if not setting_value and disable_cond == "ON":
        return 0
    elif not setting_value and disable_cond == "OFF":
        return 1
    elif not setting_value:
        return 1
    elif type(disable_cond).__name__ == "int":
        setting_value = str(setting_value)
        new_setting_value = str()
        if "e" in setting_value:
            # Deal with exponential setting values
            setting_len = int(setting_value[-1]) + 1
        else:
            setting_len = len(setting_value)
        for char in setting_value:
            if char == "e":
                break
            if char == ".":
                continue
            new_setting_value = new_setting_value + char

        while len(new_setting_value) < setting_len:
            new_setting_value = new_setting_value + "0"
        for char in new_setting_value:
            if char not in ["0", "1"]:
                break
        else:
            try:
                bit_condition = new_setting_value[disable_cond]
            except IndexError:
                bit_condition = "0"
            if bit_condition == "1":
                return 0
            else:
                return 1
    elif setting_value.lower() in disable_list:
        return 1
    else:
        return 0


def determine_phase(app, device_object):
    """Single pole and phase specific relays need to be mapped correctly to
    the correct type. Keys can exist in different locations, this function
    is configured to map the keys and determine the correct relay type."""
    # If the relay is a two phase relay then these will have a unique type.
    multi_phase_list = [
        "I> 2Ph +IE>1Ph I in A + T in TMS_Energex",
        "I>+ I>> 2Ph +IE>+IE>> I in A + T in TMS_Energex",
        "CDG61",
    ]
    if device_object.device in multi_phase_list:
        return None
    try:
        name = device_object.seq_name
    except AttributeError:
        name = device_object.name
    # Check to see if it is an A-Phase Relay
    phase_dict = {
        "_A": 0,
        "A-A": 0,
        "-A": 0,
        "-R": 0,
        "_B": 1,
        "B-B": 1,
        "-B": 1,
        "-W": 1,
        "C-C": 2,
        "-C": 2,
        "_C": 2,
    }
    for string in phase_dict:
        if string in name[-6:]:
            return phase_dict[string]
    # Check to see if it is an EF Relay
    for string in ["N-E", "N", "EF-E", "E-E", "DEF", "-EF"]:
        if string in name[-6:]:
            device_object.device = f"{device_object.device}_Earth"
            return None
    if name[-1] == "E":
        device_object.device = f"{device_object.device}_Earth"
        return None
    # If all else fails set it as A Phase
    return 0


def determine_region(app, prjt):
    """This function relies on the file structure under the Publisher"""
    base_prjt = prjt.der_baseproject
    if not base_prjt:
        base_prjt_fld = prjt.fold_id.loc_name
    else:
        base_prjt_fld = prjt.der_baseproject.fold_id.loc_name
    if base_prjt_fld == "SEQ Models":
        return "Energex"
    else:
        return "Ergon"


class DeviceSelection(Tk):
    """This class is used to record the protection devices that the user wants
    to study"""

    def __init__(self, device_dict, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Define class attributes
        self.device_dict = device_dict
        self.variables_dict = {}
        self.device_ordered_list = []
        self.cancel = False
        self.selection = None
        self.batch = False
        # Build up the widget
        self.title("Select Protection Device/s")
        self.create_widgets()
        self.resizable(False, False)
        # Keep window on top
        self.wm_attributes("-topmost", 1)
        # Place the widget in the middle of the screen
        x = (self.winfo_screenwidth() - self.winfo_reqwidth()) / 2
        y = ((self.winfo_screenheight() - self.winfo_reqheight()) / 2) - 250
        self.geometry("+%d+%d" % (x, y))
        self.focus_force()
        self.mainloop()

    def create_widgets(self):
        """This function will build the user interface objects"""
        # Configure the frame to houses the check boxes. This is frame has a
        # vertical scroll bar
        self.frame = VerticalScrolledFrame(self)
        self.list_build()
        self.frame.pack(fill=BOTH)

        # Configure a frame that houses action buttons
        self.frame_1 = ttk.Frame(self)
        self.frame_1.pack()
        ttk.Button(self.frame_1, text="Select All", command=self.select_all).grid(
            column=1, row=2, stick=W + E, pady=5
        )
        ttk.Button(self.frame_1, text="Unselect All", command=self.unselect_all).grid(
            column=2, row=2, pady=5
        )
        ttk.Button(self.frame_1, text="OK", command=self.ok).grid(
            column=1, row=3, stick=W + E, pady=5
        )
        ttk.Button(self.frame_1, text="Cancel", command=self.cancel_script).grid(
            column=2, row=3, stick=W, pady=5
        )
        ttk.Button(
            self.frame_1, text="Complete Update", command=self.complete_update
        ).grid(column=1, row=4, stick=W + E, pady=5)
        self.bind("<Return>", self.ok)
        self.bind("<Escape>", self.cancel_script)

    def list_build(self):
        """This function will add text with no indent for the substation, one indent for feeder
        and then a check box for all active devices in that feeder."""
        self.sub_dict = {}
        self.feeder_dict = {}
        self.var = {}
        list_of_devices = [device for device in self.device_dict]
        for device in list_of_devices:
            # Check to see if there is an entrance for the substation
            sub = self.device_dict[device][4]
            if sub not in self.sub_dict:
                self.var[sub] = StringVar()
                self.option_check = ttk.Checkbutton(
                    self.frame.interior,
                    text="{}".format(sub),
                    variable=self.var[sub],
                    onvalue="On",
                    offvalue="Off",
                    command=lambda key=sub: self.select_feeders(key),
                ).pack(anchor=W, padx=0)
                self.sub_dict[sub] = self.var[sub]
                for device in list_of_devices:
                    # Record all the devices that belong to this subsation
                    if sub != self.device_dict[device][4]:
                        continue
                    feeder = self.device_dict[device][3]
                    if feeder not in self.feeder_dict:
                        self.var[feeder] = StringVar()
                        self.option_check = ttk.Checkbutton(
                            self.frame.interior,
                            text="{}".format(feeder),
                            variable=self.var[feeder],
                            onvalue="On",
                            offvalue="Off",
                            command=lambda key=feeder: self.select_devices(key),
                        ).pack(anchor=W, padx=30)
                        self.feeder_dict[feeder] = self.var[feeder]
                        for device in list_of_devices:
                            # Record all the devices that belong to this feeder
                            if feeder != self.device_dict[device][3]:
                                continue
                            if device not in self.variables_dict:
                                self.check = StringVar()
                                self.option_check = ttk.Checkbutton(
                                    self.frame.interior,
                                    text="{}".format(device),
                                    variable=self.check,
                                    onvalue="On",
                                    offvalue="Off",
                                ).pack(anchor=W, padx=90)
                                # Create a dictionary and an ordered list of
                                # tree structure for use later in the script.
                                self.variables_dict[device] = self.check
                                self.device_ordered_list += [device]

    def ok(self, event=None):
        self.destroy()

    def cancel_script(self, event=None):
        self.cancel = True
        self.unselect_all()
        self.destroy()

    def select_all(self):
        """This function is turn all checkboxes on"""
        for name in self.variables_dict:
            self.variables_dict[name].set("On")
        for name in self.sub_dict:
            self.sub_dict[name].set("On")
        for name in self.feeder_dict:
            self.feeder_dict[name].set("On")

    def unselect_all(self):
        """This function is turn all checkboxes off"""
        for name in self.variables_dict:
            self.variables_dict[name].set("Off")
        for name in self.sub_dict:
            self.sub_dict[name].set("Off")
        for name in self.feeder_dict:
            self.feeder_dict[name].set("Off")

    def complete_update(self):
        """This function is to exit the selection and begin to do a complete
        update of the model."""
        self.batch = True
        self.unselect_all()
        self.destroy()

    def select_feeders(self, key):
        """If the sub is ON then all of the feeders should be on as well"""
        state = self.var[key].get()
        if state == "On":
            for device in self.device_dict:
                if key == self.device_dict[device][4]:
                    self.variables_dict[device].set("On")
                    self.feeder_dict[self.device_dict[device][3]].set("On")
        else:
            for device in self.device_dict:
                if key == self.device_dict[device][4]:
                    self.variables_dict[device].set("Off")
                    self.feeder_dict[self.device_dict[device][3]].set("Off")

    def select_devices(self, key):
        """If the user selects a feeder all the devices below it will turned
        on. If the user unselects a feeder all device turns off"""
        state = self.var[key].get()
        if state == "On":
            for device in self.device_dict:
                if key == self.device_dict[device][3]:
                    self.variables_dict[device].set("On")
        else:
            for device in self.device_dict:
                if key == self.device_dict[device][3]:
                    self.variables_dict[device].set("Off")


def ergon_all_dev_list(app, data_capture_list, ids_dict_list, called_function):
    """This will go through every protection device in the network"""
    prot_devices = get_all_protection_devices(app)
    update_info = {}
    list_of_devices = []
    setting_ids = []
    for i, pf_device in enumerate(prot_devices):
        if i % 10 == 0:
            app.ClearOutputWindow()
            app.PrintInfo(f"IPS is being checked for device {i} of {len(prot_devices)}")
        if pf_device.loc_name[-1] == ")":
            pf_device.Delete()
            continue
        # Get all the setting IDs and create an object for each ID
        plant_number = get_plant_number(app, pf_device.loc_name)
        if not plant_number:
            update_info["SUBSTATION"] = pf_device.GetAttribute("r:cpGrid:e:loc_name")
            update_info["PLANT_NUMBER"] = pf_device.loc_name
            update_info["RESULT"] = "Not a protection device"
            data_capture_list.append(update_info)
            update_info = {}
            # app.PrintInfo('{} is not a protection device'.format(pf_device.loc_name))
            continue
        if pf_device.GetClassName() != "ElmRelay":
            [fuse_type, fuse_size] = determine_fuse_type(app, pf_device)
            if fuse_type == "Tx Fuse":
                prot_dev = ProtectionDevice(
                    app, fuse_type, pf_device.loc_name, None, None, pf_device, None
                )
                prot_dev.fuse_size = fuse_size
                prot_dev.fuse_type = fuse_type
                list_of_devices.append(prot_dev)
                continue
            if not fuse_type:
                update_info["SUBSTATION"] = pf_device.GetAttribute(
                    "r:cpGrid:e:loc_name"
                )
                update_info["PLANT_NUMBER"] = pf_device.loc_name
                update_info["RESULT"] = "FAILED FUSE"
                data_capture_list.append(update_info)
                update_info = {}
                continue
        else:
            fuse_type = None
            fuse_size = None
        [setting_ids, list_of_devices] = reg_get_setting_id(
            app,
            plant_number,
            list_of_devices,
            setting_ids,
            pf_device,
            fuse_type,
            fuse_size,
            ids_dict_list,
            called_function,
        )
    return [setting_ids, list_of_devices, data_capture_list]


def error_message(app, message):
    """Due to a certain condition the script needs to be cancelled"""
    app.ClearOutputWindow()
    app.PrintError(message)
    sys.exit(0)


def find_element(app, pf_object, line):
    """The setting is associated with an element. The line knows the
    element name and the folder name that it is located in. The element
    PowerFactory object is needed to apply the setting."""
    obj_contents = pf_object.GetContents(line[1], True)
    if not obj_contents:
        # Due to obj naming the get contents function does work all the time.
        # But it is the most efficent way so it is given priority.
        obj_contents = pf_object.GetContents()
        if not obj_contents:
            return None
        for obj in obj_contents:
            if obj.fold_id.loc_name == line[0] and obj.loc_name == line[1]:
                break
        else:
            for obj in obj_contents:
                obj = find_element(app, obj, line)
                if obj:
                    break
            else:
                return None
    else:
        for obj in obj_contents:
            if obj.fold_id.loc_name == line[0]:
                break
        else:
            obj = None
    return obj


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


def get_all_protection_devices(app):
    """Get all active protection devices"""
    net_mod = app.GetProjectFolder("netmod")
    all_devices = [
        relay
        for relay in net_mod.GetContents("*.ElmRelay", True)
        if relay.GetAttribute("cpGrid")
        if relay.cpGrid.IsCalcRelevant()
        if relay.GetParent().GetClassName() == "StaCubic"
    ]
    all_devices += [
        fuse
        for fuse in net_mod.GetContents("*.RelFuse", True)
        if fuse.GetAttribute("cpGrid")
        if fuse.cpGrid.IsCalcRelevant()
    ]
    return all_devices


def get_assoc_switch(app, pf_device, prjt, raw_switches):
    """To seach for a Setting ID the switch is needed. This function will
    return the switch that the relay is associated to."""
    for switch in raw_switches:
        try:
            if switch.GetClassName() == "StaSwitch":
                cub = switch.fold_id
                for obj in cub.GetContents():
                    if obj.loc_name == pf_device.loc_name:
                        return switch
            else:
                cub = switch.bus1
                for obj in cub.GetContents():
                    if obj == pf_device:
                        return switch
                cub = switch.bus1
                for obj in cub.GetContents():
                    if obj == pf_device:
                        return switch
        except AttributeError:
            pass
    return None


def get_cb_alt_name_list(app):
    """Due to project creation in the SEQ space some CBs have not got a name
    that maps to IPS. A csv contains the mappings for these CBs"""
    current_script = app.GetCurrentScript()
    if current_script:
        script_file_path = current_script.filePath.replace(f"\\ips_to_pf.py", "")
        csv_loc = f"{script_file_path}"
        try:
            csv_open = open(f"{csv_loc}\\CB_ALT_NAME.csv", "r")
        except:  # noqa [E722]
            csv_loc = "\\\\ecasd01\\WksMgmt\\PowerFactory\\ScriptsDEV\\IPSProtectionDeviceSettings"  # noqa [E501]
            csv_open = open(f"{csv_loc}\\CB_ALT_NAME.csv", "r")
    else:
        csv_loc = "\\\\ecasd01\\WksMgmt\\PowerFactory\\ScriptsDEV\\IPSProtectionDeviceSettings"  # noqa [E501]
        csv_open = open(f"{csv_loc}\\CB_ALT_NAME.csv", "r")
    cb_alt_name_list = []
    for row in csv_open.readlines():
        line_dict = {}
        line = row.split(",")
        line[-1] = line[-1].replace("\n", "")
        if line[0] == "PROJECT" or line[-1].lower() in [
            "not needed",
            "no active setting",
            "wrong sub name",
            "unknown",
        ]:
            continue
        for i, col in enumerate(
            ["PROJECT", "GRID", "SUBSTATION", "CB_NAME", "NEW_NAME"]
        ):
            line_dict[col] = line[i]
        cb_alt_name_list.append(line_dict)
    return cb_alt_name_list


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_random_exponential(multiplier=1, max=5),
)
def get_data(data_report, paramater, variable):
    """This will use NetDash to perform an acutal query of the IPS DB."""
    data = get_json_data(report=data_report, params={paramater: variable}, timeout=120)
    return data


def get_pf_curve(app, setting_value, element):
    """Curves are the one setting that requires another PF object to be assigned
    to the attribute."""
    idmt_type = element.typ_id
    curves = idmt_type.GetAttribute("e:pcharac")
    reduced_curves = []
    for curve in curves:
        if curve.loc_name == setting_value:
            return curve
        if setting_value in curve.loc_name or curve.loc_name in setting_value:
            reduced_curves.append(curve)
    for curve in reduced_curves:
        if setting_value in curve.loc_name:
            return curve
    for curve in reduced_curves:
        if curve.loc_name in setting_value:
            return curve
    # Import the mapping file for curves
    csv_loc = r"\\ecasd01\WksMgmt\PowerFactory\ScriptsDEV\IPSProtectionDeviceSettings"
    csv_open = open("{}\\{}.csv".format(csv_loc, "curve_mapping"), "r")
    for row in csv_open.readlines():
        element_line = row.split(",")
        element_line[-1] = element_line[-1].replace("\n", "")
        try:
            # If the setting is binary add zeros to the front to match the length
            int(element_line[1])
            while len(element_line[1]) < len(setting_value):
                element_line[1] = "0" + element_line[1]
        except ValueError:
            pass  # noqa [E117]
        if setting_value == element_line[1]:
            csv_open.close()
            for curve in curves:
                if curve.loc_name == element_line[2]:
                    return curve
    csv_open.close()
    for curve in curves:
        if "Extreme" in curve.loc_name and "Extreme" in setting_value:
            return curve
        elif "Standard" in curve.loc_name and "Standard" in setting_value:
            return curve
        elif "Very" in curve.loc_name and "Very" in setting_value:
            return curve
        elif "Definite" in curve.loc_name and "DT" in setting_value:
            return curve
        elif "Curve A" in curve.loc_name and "Curve A" in setting_value:
            return curve
        elif "Curve B" in curve.loc_name and "Curve B" in setting_value:
            return curve
        elif "Curve C" in curve.loc_name and "Curve C" in setting_value:
            return curve
        elif "Curve D" in curve.loc_name and "Curve D" in setting_value:
            return curve
    else:
        # By default if the curve can not be determined then set the curve to
        # Standard Inverse.
        for curve in curves:
            if "Standard" in curve.loc_name:
                return curve


def get_plant_number(app, device_name):
    """A plant number will be structured. These structures differ depending on the
    device.
    - Reclosers will have either RC-{Number} or RE-{Number}
    - Relays should have {SUB}SS-{BAY}-{Device}
    - Fuse will be either DO-{Number} or FU-{number} or DL-{Number}"""
    meets_cond = False
    if (
        device_name[4:7] == "SS-"
        or device_name[:3] == "RC-"
        or device_name[:3] == "RE-"
        or device_name[:3] == "DO-"
        or device_name[:3] == "FU-"
        or device_name[:3] == "DL-"
    ):
        meets_cond = True
    if meets_cond:
        plant_number = ""
        for char in device_name:
            if char == " ":
                break
            else:
                plant_number = plant_number + char
    else:
        plant_number = None
    return plant_number


def get_possible_locations(app):
    """Create a dictionary that associates a cubible to a switch name.
    If a relay already exists. Record that as an exiting device."""
    prjt = app.GetActiveProject()
    # Create a list of switches
    raw_switches = prjt.GetContents("*.StaSwitch", True) + prjt.GetContents(
        "*.ElmCoup", True
    )
    switches = [
        switch
        for switch in raw_switches
        if switch.GetAttribute("cpGrid")
        if not switch.IsOutOfService()
        if switch.IsCalcRelevant()
        if switch.IsEnergized()
    ]
    # If a protection device already exists record the device
    # if not then record the switch
    possible_loc = []
    existing_devs_dict = {}
    for switch in switches:
        if switch.GetClassName() == "StaSwitch":
            # This indicates that the relay would be in the same cubicle
            contents = switch.fold_id.GetContents()
        else:
            root_cub = switch.GetCubicle(0)
            contents = root_cub.GetContents()
        device_exist = False
        for content in contents:
            if content.GetClassName() in ["ElmRelay", "RelFuse"]:
                existing_devs_dict[content.loc_name] = [content, switch]
                device_exist = True
        if not device_exist:
            possible_loc.append(switch)
    return [possible_loc, existing_devs_dict]


def get_trip_num(app, mapping_file, setting_dictionary):
    """This will find the get the setting that is associated with
    the number of trips."""
    trips_to_lockout = 1
    for mapped_set in mapping_file:
        if "_TripstoLockout" not in mapped_set[1]:
            continue
        reclosing_key = mapped_set[-1]
        key = str().join(mapped_set[:3])
        setting = setting_dictionary[key]
        if setting == reclosing_key:
            trips_to_lockout += 1
    return trips_to_lockout


def get_relay_types(app):
    """This will create a list of relay types. It searches the ErgonLibrary,
    and DIgSILENT library to find these types. As a last resot it will also
    look in the active project."""
    global_library = app.GetGlobalLibrary()
    protection_lib = global_library.GetContents("Protection")
    relay_types = all_relevant_objects(app, protection_lib, "*.TypRelay", None)
    database = global_library.fold_id
    dig_lib = database.GetContents("Lib")[0]
    prot_lib = dig_lib.GetContents("Prot")[0]
    relay_lib = prot_lib.GetContents("ProtRelay")
    dig_relay_types = all_relevant_objects(app, relay_lib, "*.TypRelay", None)
    relay_types = relay_types + dig_relay_types
    current_user = app.GetCurrentUser()
    protection_folder = current_user.GetContents("Protection")
    local_relays = all_relevant_objects(app, protection_folder, "*.TypRelay", None)
    if local_relays:
        for local_relay in local_relays:
            for relay_type in relay_types:
                if local_relay.loc_name == relay_type.loc_name:
                    break
            else:
                relay_types.append(local_relay)
    app.PrintInfo("Finished Getting Relay types")
    return relay_types


def print_results(app, data_capture_list):
    """This is to provide information to the user about the results of the
    script."""
    [devices, device_object_dict] = prot_device(app)
    print_string = str()
    app.ClearOutputWindow()
    for i, info in enumerate(data_capture_list):
        if i % 40 == 0:
            app.PrintInfo(print_string)
            print_string = str()
        try:
            device = info["PLANT_NUMBER"]
            pf_device = device_object_dict[device][0]
        except KeyError:
            try:
                pf_device = info["CB_NAME"]
            except KeyError:
                pf_device = info["PLANT_NUMBER"]
        try:
            result = info["RESULT"]
        except KeyError:
            result = "Updated Successfully"
        print_string = print_string + "\n" + f"{pf_device}    Result = {result}"
    app.PrintInfo(print_string)


def prot_device(app):
    """Protection devices are the main point of a study. Get active relays
    and fuses. """
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


def prot_dev_lst(app, region, data_capture_list, ids_dict_list):
    """The model configuration differs between the regional and SEQ models.
    This function is used to create a list of devices to update"""
    # User selection should be the same
    # Set up a database of the active devices in the model
    [devices, device_dict] = prot_device(app)
    # Ask the user to select which protection devices they want to study
    selections = user_selection(app, device_dict)
    list_of_devices = []
    setting_ids = []
    if not selections:
        message = "User has selected to exit the script"
        error_message(app, message)
    elif selections == "Batch":
        return ["Batch", None, data_capture_list]
    if region == "Energex":
        cb_alt_name_list = get_cb_alt_name_list(app)
        # The setting id query required the switch
        prjt = app.GetActiveProject()
        raw_switches = prjt.GetContents("*.StaSwitch", True) + prjt.GetContents(
            "*.ElmCoup", True
        )
        switches = []
        for i, device in enumerate(selections):
            if i % 10 == 0:
                app.ClearOutputWindow()
                app.PrintInfo(
                    f"IPS is being checked for switch {i} of {len(selections)}"
                )
            # Need to remove the device id from the name
            device_name = str()
            for char in device:
                if char == "_":
                    break
                device_name = device_name + char
            assoc_switch = get_assoc_switch(
                app, device_dict[device][0], prjt, raw_switches
            )
            for switch in switches:
                if switch == assoc_switch:
                    break
            else:
                switches.append(assoc_switch)
        for switch in switches:
            [setting_ids, list_of_devices] = seq_get_setting_id(
                app,
                None,
                switch,
                setting_ids,
                list_of_devices,
                ids_dict_list,
                False,
                cb_alt_name_list,
            )
        temp_list = []
        for device in list_of_devices:
            temp_list.append(device)
        for device in temp_list:
            app.PrintInfo(f"{device.name}_{device.device_id}_{device.seq_name}")
            # Only have device that were selected in the list of devices
            if device.device_id:
                name = f"{device.name}_{device.device_id}".rstrip()
                if name not in selections:
                    name = (
                        f"{device.name}_{device.device_id}_{device.seq_name}".rstrip()
                    )  # noqa [E501]
                    if name not in selections:
                        list_of_devices.remove(device)
                    else:
                        device.pf_obj = device_dict[name][0]
                else:
                    device.pf_obj = device_dict[name][0]
            else:
                name = f"{device.name}_{device.seq_name}".rstrip()
                if name not in selections:
                    list_of_devices.remove(device)
                else:
                    device.pf_obj = device_dict[name][0]
    elif region == "Ergon":
        update_info = {}
        for i, device in enumerate(selections):
            # Go through each device and see if there is a setting ID.
            if i % 10 == 0:
                app.ClearOutputWindow()
                app.PrintInfo(
                    f"IPS is being checked for device {i} of {len(selections)}"
                )
            plant_number = get_plant_number(app, device)
            pf_device = device_dict[device][0]
            if not plant_number:
                update_info["SUBSTATION"] = pf_device.GetAttribute(
                    "r:cpGrid:e:loc_name"
                )
                update_info["PLANT_NUMBER"] = pf_device.loc_name
                update_info["RESULT"] = "Not a protection device"
                data_capture_list.append(update_info)
                update_info = {}
                continue
            if device_dict[device][1] != "ElmRelay":
                [fuse_type, fuse_size] = determine_fuse_type(app, pf_device)
                if fuse_type == "Tx Fuse":
                    prot_dev = ProtectionDevice(
                        app, fuse_type, pf_device.loc_name, None, None, pf_device, None
                    )
                    prot_dev.fuse_size = fuse_size
                    prot_dev.fuse_type = fuse_type
                    list_of_devices.append(prot_dev)
                    continue
                if not fuse_type:
                    update_info["SUBSTATION"] = pf_device.GetAttribute(
                        "r:cpGrid:e:loc_name"
                    )
                    update_info["PLANT_NUMBER"] = pf_device.loc_name
                    update_info["RESULT"] = "FAILED FUSE"
                    data_capture_list.append(update_info)
                    update_info = {}
                    continue
            else:
                fuse_type = None
                fuse_size = None
            [setting_ids, list_of_devices] = reg_get_setting_id(
                app,
                plant_number,
                list_of_devices,
                setting_ids,
                pf_device,
                fuse_type,
                fuse_size,
                ids_dict_list,
                False,
            )
    return [setting_ids, list_of_devices, data_capture_list]


class ProtectionDevice:
    """Each protection device will have its own instance. They will have
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
        """This function will use the setting ID to assocaite a CT or VT to the
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


def read_mapping_file(app, rel_pattern, pf_device):
    """Each line of the mapping csv will be bought in as an a list."""
    current_script = app.GetCurrentScript()
    if current_script:
        script_file_path = current_script.filePath.replace(f"\\ips_to_pf.py", "")
        csv_loc = f"{script_file_path}\\mapping"
        try:
            csv_open = open(f"{csv_loc}\\type_mapping.csv", "r")
        except:  # noqa [E722]
            csv_loc = "\\\\ecasd01\\WksMgmt\\PowerFactory\\ScriptsDEV\\IPSProtectionDeviceSettings\\mapping"  # noqa [E501]
            csv_open = open(f"{csv_loc}\\type_mapping.csv", "r")
    else:
        csv_loc = "\\\\ecasd01\\WksMgmt\\PowerFactory\\ScriptsDEV\\IPSProtectionDeviceSettings\\mapping"  # noqa [E501]
        csv_open = open(f"{csv_loc}\\type_mapping.csv", "r")
    # Determine the line that has the associated mapping details for the
    # Relay pattern from IPS
    for row in csv_open.readlines():
        line = row.split(",")
        line[-1] = line[-1].replace("\n", "")
        if line[0] == rel_pattern:
            csv_open.close()
            break
    else:
        # The script is unable to match the Relay pattern to a mapping file
        csv_open.close()
        return [None, None]
    try:
        mapping_csv_open = open(f"{csv_loc}\\{line[1]}.csv", "r")
    except FileNotFoundError:
        # This relay pattern is mapped to a file that does not exist
        return [None, None]
    mapping_file = []
    for row in list(csv.reader(mapping_csv_open, skipinitialspace=True)):
        if "FOLDER" in row[0] and "ELEMENT" in row[1]:
            continue
        if row[3] == "None" and "_dip" not in row[1]:
            if len(row) > 4:
                if not row[4]:
                    continue
            else:
                continue
        if row[0] in ["Relay Model", "Default", "default"]:
            row[0] = pf_device.loc_name
        # Remove elements from the line that are empty. This deals with rows with
        # less columns of information.
        element_line = [element for element in row if element]
        mapping_file.append(element_line)
    mapping_csv_open.close()
    # Return the mapping file and the relay type
    return [mapping_file, line[2]]


def reg_get_ips_it_details(app, devices):
    """The CT Ratio will be configure based on the CT setting node that is
    attached to the relay setting node."""
    ips_settings = []
    it_set_db = cached_data("Report-Cache-ProtectionITSettings-EE")
    for setting in it_set_db:
        if setting.relaysettingid in devices:
            ips_settings.append(setting)
    return ips_settings


def reg_get_ips_settings(app, set_id):
    """Using the unique setting ID get the full setting file from the DB"""
    ips_settings = {}
    ips_settings[set_id] = []
    settings = get_data("Protection-SettingRelay-EE", "setting_id", set_id)
    for setting in settings:
        if not setting["proposedsetting"]:
            continue
        ips_settings[set_id].append(setting)
    return ips_settings


def reg_get_setting_id(
    app,
    device,
    list_of_devices,
    setting_ids,
    pf_device,
    fuse_type,
    fuse_size,
    ids_dict_list,
    called_function,
):
    """Each device has a unique setting ID. This ID is to be used in another SQL
    query on the DB to extract settings."""
    setting_found = False
    # Need to deal with the wild card getting settings that may not be correct
    wild_card_issue = False
    new_rows = []
    for row in ids_dict_list:
        # This is becuase not all rows are needed
        if (
            "RTU" in row["patternname"]
            or device not in row["assetname"]
            or not row["active"]
            or "CMGR12" in row["patternname"]
        ):
            continue
        if row["assetname"] == device:
            # If the device name is an exact match to a name in IPS
            setting_ids.append(row["relaysettingid"])
            prot_dev = ProtectionDevice(
                app,
                row["patternname"],
                row["assetname"],
                row["relaysettingid"],
                row["datesetting"],
                pf_device,
                None,
            )
            if not called_function:
                ips_settings = reg_get_ips_settings(app, row["relaysettingid"])
                prot_dev.associated_settings(ips_settings)
            prot_dev.fuse_type = fuse_type
            prot_dev.fuse_size = fuse_size
            list_of_devices.append(prot_dev)
            wild_card_issue = True
            break
        if device in row["assetname"]:
            new_rows.append(row)
    if wild_card_issue:
        return [setting_ids, list_of_devices]
    pf_device_name = pf_device.loc_name
    for row in new_rows:
        # Rename or create a new devices with the name. This deals with multiple
        # devices in a single cubicle
        name = row["assetname"]
        for device in pf_device.fold_id.GetContents("*.ElmRelay"):
            if device.loc_name == name:
                # This finds another device in the cubicle with the same name
                break
            elif device.loc_name == pf_device_name:
                # Rename this device if it is the correct one to rename
                device.loc_name = name
                pf_device = device
                break
        else:
            cubicle = pf_device.fold_id
            pf_device = cubicle.CreateObject("ElmRelay", name)
        setting_ids.append(row["relaysettingid"])
        prot_dev = ProtectionDevice(
            app,
            row["patternname"],
            row["assetname"],
            row["relaysettingid"],
            row["datesetting"],
            pf_device,
            None,
        )
        if not called_function:
            ips_settings = reg_get_ips_settings(app, row["relaysettingid"])
            prot_dev.associated_settings(ips_settings)
        prot_dev.fuse_type = fuse_type
        prot_dev.fuse_size = fuse_size
        list_of_devices.append(prot_dev)
        setting_found = True
    if not setting_found:
        list_of_devices.append(
            ProtectionDevice(app, None, None, None, None, pf_device, None)
        )
        list_of_devices[-1].fuse_type = fuse_type
        list_of_devices[-1].fuse_size = fuse_size
    return [setting_ids, list_of_devices]


def relay_settings(app, device_object, relay_types, updates):
    """This function can either use the settings from IPS."""
    # Record the information of the conversion and display this in output window
    # or be recorded in a CSV if run as part of a batch.
    update_info = {}
    try:
        # This tests if the user has set the type, or if the relay had previously
        # been configured.
        exist_relay_type = device_object.pf_obj.GetAttribute("r:typ_id:e:loc_name")
        # Determine if the existing type has been replaced and therefore the
        # the existing type would be a recycle bin
        type_is_deleted = device_object.pf_obj.typ_id.IsDeleted()
    except AttributeError:
        exist_relay_type = "None"
        type_is_deleted = 0
    update_info["SUBSTATION"] = device_object.pf_obj.GetAttribute("r:cpGrid:e:loc_name")
    update_info["PLANT_NUMBER"] = device_object.pf_obj.loc_name
    update_info["RELAY_PATTERN"] = device_object.device
    # Due to limitation of IPS certain relay patterns can have two relay
    # types in PF.
    try:
        num_of_phases = device_object.pf_obj.GetAttribute("r:fold_id:e:nphase")
    except AttributeError:
        num_of_phases = 3
    if num_of_phases < 3:
        device_object.device = f"swer_{device_object.device}"
    # Manage single pole and phase specific relays.
    phase = None
    if device_object.device in [
        "I>+ I>> 1Ph I in % + T in TMS_Energex",
        "I> 1Ph I in A + I>> in xIs + T in %_Energex",
        "I> 2Ph I in A + T in TMS_Energex",
        "MCGG22",
        "MCGG21",
        "RXIDF",
        "I> 1Ph I in A + I>> in xIs + T in %_Energex",
    ]:
        phase = determine_phase(app, device_object)
    if not device_object.settings and device_object.device not in ["SOLKOR-RF_Energex"]:
        # This indicates that there is no protection settings. This typically
        # means that the device is a switch
        device_object.device = f"switch_{device_object.device}"
    else:
        # Determine if the device is a secitonaliser
        for setting in device_object.settings:
            if setting[1] in ["Sectionaliser"]:
                if setting[2].lower() in ["on", "auto"]:
                    device_object.device = f"sect_{device_object.device}"
                break
            if setting[1] in ["Detection"]:
                if setting[2].lower() == "on":
                    device_object.device = f"switch_{device_object.device}"
    update_info["USED_PATTERN"] = device_object.device
    [mapping_file, mapping_type] = read_mapping_file(
        app, device_object.device, device_object.pf_obj
    )
    if mapping_file:
        setting_dict = create_setting_dictionary(
            app, device_object.settings, mapping_file, device_object.pf_obj
        )
        # Set the relay with the information about which setting from IPS was used
        update_info["DATE_SETTING"] = device_object.date
        device_object.pf_obj.SetAttribute("e:sernum", str(device_object.date))
    else:
        update_info["RESULT"] = "Not been mapped"
        device_object.pf_obj.SetAttribute("outserv", 1)
        return [update_info, updates]
    if exist_relay_type != mapping_type or type_is_deleted == 1:
        # Before applying settings the relay type needs to be correct
        updated = update_relay_type(
            app, device_object.pf_obj, mapping_type, relay_types
        )
        if not updated:
            update_info["RESULT"] = "Unable to find the appropriate type"
            device_object.pf_obj.SetAttribute("e:outserv", 1)
            return [update_info, updates]
        else:
            # Found a type and turn the relay in service.
            device_object.pf_obj.SetAttribute("e:outserv", 0)
    else:
        device_object.pf_obj.SetAttribute("e:outserv", 0)
    updates = apply_settings(app, device_object, mapping_file, setting_dict, updates)
    update_reclosing_logic(app, device_object, mapping_file, setting_dict)
    update_logic_elements(app, device_object.pf_obj, mapping_file, setting_dict)
    update_info = update_ct(app, device_object, update_info)
    update_info = update_vt(app, device_object, update_info)
    if phase:
        meas_obj = device_object.pf_obj.GetContents("*.RelMeasure")[0]
        meas_obj.SetAttribute("e:iphase", phase)
    return [update_info, updates]


def select_ct_type(app, ct_library, primary, secondary):
    """This function will check the local library to see if a suitable
    CT type is available. If not then it will create a new one."""
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


def select_main_file(app, file_name, location, called_function):
    """Check to see if a folder structure exists and create it if it doesn't.
    Create the csv file to publish all the data."""
    citrix = os.path.isdir("\\\\Client\\C$\\localdata")
    if citrix and "C:" in location:
        location = "\\\\Client\\" + location.replace("C:", "C$")
    protection_folder_check = os.path.isdir(location)
    if not protection_folder_check:
        os.makedirs(location)
    set_file_name = location + "\\{}.csv".format(file_name)
    print(set_file_name)
    # Open the files
    try:
        last_mod_time = os.stat(set_file_name).st_mtime
        if called_function:
            check_time = time.time() - (24 * 60 * 60)
        else:
            check_time = last_mod_time
        if check_time < last_mod_time:
            print("Project had already been studied")
            return None
        os.remove(set_file_name)
    except FileNotFoundError:
        pass
    return set_file_name


def seq_get_ips_it_details(app, devices):
    """The CT Ratio will be configure based on the CT setting node that is
    attached to the relay setting node."""
    ips_settings = []
    it_set_db = cached_data("Report-Cache-ProtectionITSettings-EX")
    for setting in it_set_db:
        if setting.relaysettingid in devices:
            ips_settings.append(setting)
    return ips_settings


def seq_get_ips_settings(app, set_id):
    """Using the unique setting ID get the full setting file from the DB"""
    ips_settings = {}
    ips_settings[set_id] = []
    settings = get_data("Protection-SettingRelay-EX", "setting_id", set_id)
    for setting in settings:
        ips_settings[set_id].append(setting)
    return ips_settings


def seq_get_setting_id(
    app,
    device,
    switch,
    setting_ids,
    list_of_devices,
    ids_dict_list,
    called_function,
    cb_alt_name_list,
):
    """This will seach the Setting ID DB for the relevant setting ID for
    that device."""
    for cb_dict in cb_alt_name_list:
        cb_name = cb_dict["CB_NAME"]
        elmnet_name = cb_dict["SUBSTATION"]
        if elmnet_name == switch.fold_id.loc_name and cb_name == switch.loc_name:
            pf_switch_name = cb_dict["NEW_NAME"]
            break
    else:
        pf_switch_name = switch.loc_name
    switch_name = str()
    # Due to same named CB in different locations. Determine the substation
    # that the CB belongs to.
    if switch.GetClassName() == "ElmCoup":
        sub_code = switch.fold_id.loc_name
    else:
        sub_code = None
    for char in pf_switch_name:
        if char == "_":
            break
        switch_name = switch_name + char
    if len(switch_name) < 4:
        return [setting_ids, list_of_devices]
    list_of_types = [
        "SEL2505_Energex",
        "GenericRelayWithoutSetting_Energex",
        "SEL-2505",
        "GenericRelayWithoutSetting",
        "T> in TMS no Current_Energex",
        "I>> 3Ph no Time I>> in A_Energex",
        "I> 1Ph no Time I in A_Energex",
        "I> 1Ph no Time I in %_Energex",
    ]
    possible_bays = []
    rows = []
    for row in ids_dict_list:
        row_sub = row["locationpathenu"].split("/")[2]
        for char in row_sub:
            # Some relays belong to a bulk supply that does not follow the
            # conventional naming convention
            try:
                int(char)
                row_sub = None
                break
            except ValueError:
                continue
        if sub_code and row_sub:
            if sub_code != row_sub:
                continue
        if row["nameenu"] != switch_name:
            check_str = row["nameenu"]
            if switch_name not in check_str:
                continue
            # Need to ensure that the string the start of the name
            descision = False
            for i, char in enumerate(switch_name):
                if check_str[i] != char:
                    descision = True
            if descision:
                continue
            check_str = check_str.replace(switch_name, "")
            try:
                int(check_str[0])
                continue
            except ValueError:
                possible_bays.append(row)
        else:
            rows.append(row)
    if not rows:
        rows = possible_bays
    for row in rows:
        if row["patternname"] in list_of_types:
            continue
        try:
            device_id = row["deviceid"]
            for char in ": /,":
                device_id = device_id.replace(char, "")
        except AttributeError:
            device_id = row["deviceid"]
        setting_ids.append(row["relaysettingid"])
        prot_dev = ProtectionDevice(
            app,
            row["patternname"],
            row["nameenu"],
            row["relaysettingid"],
            row["datesetting"],
            device,
            device_id,
        )
        prot_dev.switch = switch
        prot_dev.seq_name = row["assetname"]
        already_added = False
        for chk_device in list_of_devices:
            if chk_device.pf_obj == device and device:
                already_added = True
                break
        else:
            list_of_devices.append(prot_dev)
        if already_added:
            continue
        if not called_function:
            ips_settings = seq_get_ips_settings(app, row["relaysettingid"])
            prot_dev.associated_settings(ips_settings)
        if "fuse" in list_of_devices[-1].device.lower():
            list_of_devices[-1].fuse_type = "Line Fuse"
    return [setting_ids, list_of_devices]


def set_attribute(
    app,
    line,
    setting_value,
    element,
    attribute,
    device_object,
    setting_dictionary,
    updates,
):
    """Using the setting and attribute this will set the attribute."""
    if line[2] == "pcharac":
        # A curve setting requires an actual PF object to update the
        # setting
        if line[-1] == "binary":
            setting_value = convert_binary(app, setting_value, line)
        setting_value = get_pf_curve(app, setting_value, element)
        existing_setting = element.GetAttribute(attribute)
        if setting_value != existing_setting:
            element.SetAttribute(attribute, setting_value)
        return True
    elif line[2] == "outserv":
        # This setting is used to set the element out of service. This
        # requires further anylsis of the setting to determine how to
        # set PowerFactory
        if line[-1] == "binary":
            setting_value = convert_binary(app, setting_value, line)
            if setting_value == "1":
                setting_value = "OFF"
                line[-1] = "OFF"
            else:
                setting_value = "ON"
                line[-1] = "NF"
        setting_value = determine_on_off(app, setting_value, line[-1])
        element.SetAttribute(attribute, setting_value)
        return updates
    if line[6] == "None":
        # The final entry in the line determines if the setting needs
        # adjusting. If this is none then the setting can be directly applied.
        existing_setting = element.GetAttribute(attribute)
        try:
            # Due to the variable type this might not be correct to go directly
            # into PowerFactory.
            if setting_value != existing_setting:
                element.SetAttribute(attribute, setting_value)
                return True
        except TypeError:
            # Generally all settings will be a string.
            try:
                # Converting it to float is the first option as it maintains
                # the decimal numbers.
                setting_value = float(setting_value)
                if setting_value != round(existing_setting, 3):
                    element.SetAttribute(attribute, setting_value)
                    return True
            except (ValueError, TypeError):
                # The setting might be a legit string. This is typically used
                # to indicate that the element is not used.
                try:
                    # This try will convert the setting to an integer.
                    setting_value = int(setting_value)
                    if setting_value != existing_setting:
                        element.SetAttribute(attribute, setting_value)
                        return True
                except ValueError:
                    # As a last resort this will set the element to its maximum
                    element.SetAttribute(attribute, 9999)
                    return updates
    else:
        # This will adjust the setting based on the mapping file.
        setting_value = setting_adjustment(app, line, setting_dictionary, device_object)
        if not setting_value:
            return updates
        existing_setting = element.GetAttribute(attribute)
        try:
            if setting_value != existing_setting:
                element.SetAttribute(attribute, setting_value)
                return True
        except TypeError:
            setting_value = int(setting_value)
            if setting_value != existing_setting:
                element.SetAttribute(attribute, setting_value)
                return True
    return updates


def setting_adjustment(app, line, setting_dictionary, device_object):
    """If a setting needs to be adjusted to allow correct application from
    setting to what is required in Powerfactory."""
    key = str().join(line[:3])
    try:
        setting = float(setting_dictionary[key])
    except:  # noqa [E722]
        try:
            setting_value = determine_on_off(app, setting_dictionary[key], line[6])
            return setting_value
        except:  # noqa [E722]
            setting = 0
    if line[-1] == "primary":
        primary = device_object.ct_primary
        setting_value = setting / primary
    elif line[-1] == "ctr":
        primary = device_object.ct_primary
        secondary = device_object.ct_secondary
        setting_value = setting * secondary / primary
    elif line[-1] == "secondary":
        secondary = device_object.ct_secondary
        setting_value = setting / secondary
    elif line[-1] == "perc_pu":
        secondary = device_object.ct_secondary
        setting_value = (setting / 100) * secondary
    else:
        math_sym = line[6]
        manipulator_value = float(line[7])
        if math_sym == "+":
            setting_value = setting + manipulator_value
        elif math_sym == "-":
            setting_value = setting - manipulator_value
        elif math_sym == "/":
            try:
                setting_value = setting / manipulator_value
            except ZeroDivisionError:
                setting_value = 0
        elif math_sym == "*":
            setting_value = setting * manipulator_value
    return setting_value


def update_ct(app, device_object, update_info):
    """Once the correct mapping table can be accessed in IPS then this function
    will be expanded. Initially it deals with the need to convert a SWER
    recloser from a 3phase to 1 phase CT"""
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
        update_info["CT_NAME"] = "{}_CT".format(device_object.pf_obj.loc_name)
        update_info["CT_RESULT"] = "Recloser CT was updated"
        return update_info
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
        update_info["CT_RESULT"] = "No CT Linked"
        return update_info
    secondary = int(float(device_object.ct_secondary))
    current_trans = update_ct_slots(app, device_object)
    required_ct_type = select_ct_type(app, ct_library, primary, secondary)
    try:
        if required_ct_type.loc_name != current_trans.GetAttribute(
            "r:typ_id:e:loc_name"
        ):
            current_trans.SetAttribute("e:typ_id", required_ct_type)
    except AttributeError:
        # This means the CT soes not have a type ID already
        current_trans.SetAttribute("e:typ_id", required_ct_type)
    current_trans.SetAttribute("e:ptapset", primary)
    current_trans.SetAttribute("e:stapset", secondary)
    if device_object.ct_op_id:
        current_trans.SetAttribute("e:sernum", device_object.ct_datesetting)
    update_info["CT_NAME"] = device_object.ct_op_id
    update_info["CT_RESULT"] = "CT info updated"
    # check that measureing devices have matching CT secondary.
    check_update_measurement_elements(app, device_object.pf_obj, secondary)
    return update_info


def update_ct_slots(app, device_object):
    """A setting slot is part of a list or elements. This function will
    ensure the correct CT is allocate to the correct CT slot."""
    pf_device = device_object.pf_obj
    cubical = pf_device.fold_id
    slot_objs = pf_device.GetAttribute("pdiselm")
    remote_ct_slot_names = ["Ct-3P(remote)", "Winding 2 Ct"]
    if not device_object.ct_op_id:
        ct_name = "{}_CT".format(pf_device.loc_name)
    else:
        ct_name = device_object.ct_op_id
    for i, item in enumerate(pf_device.GetAttribute("typ_id").GetAttribute("pblk")):
        if not item:
            continue
        if item.GetAttribute("filtmod") == "StaCt*":
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


def update_vt(app, device_object, update_info):
    """VT elements are used to provide the relay with vt signals. VT are not always
    located in the same bay as the relay. Due to limitations of scripting a
    VT that is associated with the relay will be plsacedinto the same cubicle."""
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
    vt_library = all_relevant_objects(
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


def update_logic_elements(app, pf_device, mapping_file, setting_dict):
    """Some relays will require logic elements with dip switches configured
    to control the functionality of the elements in a relay"""
    # There could be multiple elements that are logic. Make a list of all
    # Element names that contain logic
    element_list = []
    for line in mapping_file:
        if "_dip" in line[1]:
            element_name = line[1]
            if element_name not in element_list:
                element_list.append(element_name)
    if not element_list:
        # Not all relays will have logic
        return
    for element in element_list:
        element_mapping = []
        pf_element = None
        # Obtain the PF object for the element and determine all lines in the
        # mapping file associated with this element
        for line in mapping_file:
            if element not in line[1]:
                # This line is not associated with this element
                continue
            element_mapping.append(line)
            if not pf_element:
                line[1] = line[1].replace("_dip", "")
                pf_element = find_element(app, pf_device, line)
                line[1] = line[1] + "_dip"
                if pf_element.GetClassName() != "RelLogdip":
                    # This function is only used to setting reclosing logic
                    element = None
                    continue
            if not pf_element:
                app.PrintError("Element - {} could not be found".format(element))
                continue
        # Reset the dip switches to be all OFF
        existing_dip_set = pf_element.GetAttribute("e:aDipset")
        if len(existing_dip_set) != len(element_mapping):
            # This indicates that there is not a match for all dip settings in
            # the mapping file for what is in the actual element
            continue
        existing_dip_set.replace("1", "0")
        dip_names = pf_element.GetAttribute("r:typ_id:e:sInput")[0].split(",")
        for line in element_mapping:
            dip_set_name = line[2]
            key = str().join(line[:3])
            try:
                setting = setting_dict[key]
            except KeyError:
                setting = 0
            dip_name_index = [
                i for i, dip_set in enumerate(dip_names) if dip_set_name == dip_set
            ]
            try:
                setting = int(setting)
            except ValueError:
                pass
            if setting == 1:
                # Returned setting is high
                logic_value = "1"
            elif setting == 0:
                logic_value = "0"
            elif line[-1] in setting:
                # The logic key is found in the setting value string
                logic_value = "1"
            elif "32" in setting:
                logic_value = "1"
            else:
                # All else is disabled
                logic_value = "0"
            new_dip_set = list(existing_dip_set)
            new_dip_set[dip_name_index[0]] = logic_value
            existing_dip_set = "".join(new_dip_set)
        pf_element.SetAttribute("e:aDipset", existing_dip_set)


def update_reclosing_logic(app, device_object, mapping_file, setting_dictionary):
    """The reclosing element has logic that controls the output to elements
    depending on the trip number. Using the following logic and the mapped
    settings update each row with either Reclosing, Lockout or Disable."""
    pf_device = device_object.pf_obj
    device_type = device_object.device
    # RC01 do not have a specific number of trips to lockout setting
    setting = None
    if "RC01" in device_type:
        trip_setting = get_trip_num(app, mapping_file, setting_dictionary)
        element = find_element(
            app, pf_device, [pf_device.loc_name, "Reclosing Element"]
        )
        element.SetAttribute("e:oplockout", trip_setting)
    row_dict = {}
    element = None
    for mapped_set in mapping_file:
        if "_logic" not in mapped_set[1]:
            continue
        if not element:
            mapped_set[1] = mapped_set[1].replace("_logic", "")
            element = find_element(app, pf_device, mapped_set)
            mapped_set[1] = mapped_set[1] + "_logic"
            if element.GetClassName() != "RelRecl":
                # This function is only used to setting reclosing logic
                element = None
                continue
            op_to_lockout = element.GetAttribute("e:oplockout")
        if element.loc_name not in mapped_set[1]:
            # This means this line is not associated with a reclosing element
            continue
        row_name = mapped_set[2]
        try:
            trip_num = int(mapped_set[-3])
        except ValueError:
            trip_num = mapped_set[-3]
        on_off_key = mapped_set[-2]
        recl = mapped_set[-1]
        key = str().join(mapped_set[:3])
        try:
            setting = setting_dictionary[key]
        except KeyError:
            setting = mapped_set[-2]
        try:
            if mapped_set[6] != "None":
                setting = setting_adjustment(
                    app, mapped_set, setting_dictionary, device_object
                )
        except:  # noqa [E722]
            if mapped_set[3] == "ON":
                trip_num = "ALL"
                setting = trip_setting
            else:
                setting = "off"
                recl = "N"
                trip_num = "ALL"
                on_off_key = "off"
        logic_str = []
        # The first check is to see if the element allows reclosing
        if recl == "N":
            # Determine if the element is to be on
            if setting.lower() == on_off_key.lower():
                set_log = 0.0
            else:
                set_log = 2.0
            for i in range(0, op_to_lockout):
                if trip_num == "ALL":
                    logic_str.append(set_log)
                elif i + 1 == trip_num:
                    logic_str.append(set_log)
                else:
                    logic_str.append(0.0)
            row_dict[row_name] = logic_str
            continue
        # Check to see if it is not an indvidual trip
        if trip_num == "ALL":
            # Some IPS data might be missing. Therefore if this is the case then
            # The setting will be set to 1 trip to lockout
            if setting == "None":
                setting = 1
            for i in range(0, op_to_lockout):
                if i + 1 < op_to_lockout and i + 1 < float(setting):
                    logic_str.append(1.0)
                elif i + 1 == op_to_lockout or i + 1 == float(setting):
                    logic_str.append(2.0)
                elif i + 1 > float(setting):
                    logic_str.append(0.0)
            row_dict[row_name] = logic_str
            continue
        # The only other option now is that the row is associated with a
        # Specific trip
        for i in range(0, op_to_lockout):
            if i + 1 != trip_num:
                logic_str.append(0.0)
            elif i + 1 == trip_num and trip_num < op_to_lockout:
                logic_str.append(1.0)
            elif i + 1 == trip_num and trip_num == op_to_lockout:
                logic_str.append(2.0)
        row_dict[row_name] = logic_str
    if not element:
        return
    block_ids = element.GetAttribute("r:typ_id:e:blockid")
    for row in row_dict:
        block_ids = [row_dict[row] if x == row else x for x in block_ids]
    element.SetAttribute("e:ilogic", block_ids)
    if element.GetAttribute("e:reclnotactive"):
        element.SetAttribute("e:oplockout", 1)


def update_relay_type(app, pf_device, mapping_type, relay_types):
    """Update the type if the exsting type does not match the mapping type"""
    # Initially the new types do not exist in the ErgonLibrry
    # The Ergon created relays will be located in the ErgonLibrary
    for relay_type in relay_types:
        if relay_type.loc_name == mapping_type:
            break
    else:
        relay_type = None
    if not relay_type:
        return False
    pf_device.SetAttribute("e:typ_id", relay_type)
    pf_device.SlotUpdate()
    return True


def user_selection(app, device_dict):
    """Present the user with a structure to select the relays that they
    would like to study. Return the list of selected devices."""
    selection = DeviceSelection(device_dict)
    if selection.cancel:
        return None
    if selection.batch:
        return "Batch"
    # Get a list of devices that have been selected
    selected_devices = []
    for element in selection.device_ordered_list:
        state = selection.variables_dict[element].get()
        if state == "On":
            selected_devices += [element]
    return selected_devices


def user_name_password(region):
    """For batch updates the script will use a direct connection to IPS for the
    settings. This function retrieves the username and password."""
    try:
        yaml_ini_file = r"C:\LocalData\BatchStudy\sql_login_details.yaml"
        with open(yaml_ini_file) as yaml_f:
            d = yaml.load(yaml_f)
    except:  # noqa [E722]
        yaml_ini_file = "\\\\Client\\C$\\localdata\\BatchStudy\\sql_login_details.yaml"
        with open(yaml_ini_file) as yaml_f:
            d = yaml.load(yaml_f)
    if region == "Energex":
        username = d["seq_user"]
        password = d["seq_password"]
    else:
        username = d["reg_user"]
        password = d["reg_password"]
    return [username, password]


class VerticalScrolledFrame(ttk.Frame):
    """A pure Tkinter scrollable frame that actually works!
    * Use the 'interior' attribute to place widgets inside the scrollable frame
    * Construct and pack/place/grid normally
    * This frame only allows vertical scrolling
    """

    def __init__(self, parent, *args, **kw):
        Frame.__init__(self, parent, *args, **kw)
        # create a canvas object and a vertical scrollbar for scrolling it
        vscrollbar = ttk.Scrollbar(self, orient=VERTICAL)
        vscrollbar.pack(fill=Y, side=RIGHT, expand=FALSE)
        canvas = Canvas(
            self, bd=0, highlightthickness=0, yscrollcommand=vscrollbar.set, height=600
        )
        canvas.pack(side=LEFT, fill=BOTH, expand=TRUE)
        vscrollbar.config(command=canvas.yview)
        # reset the view
        canvas.xview_moveto(0)
        canvas.yview_moveto(0)
        # create a frame inside the canvas which will be scrolled with it
        self.interior = interior = ttk.Frame(canvas)
        interior_id = canvas.create_window(0, 0, window=interior, anchor=NW)

        def _configure_interior(event):
            # update the scrollbars to match the size of the inner frame
            size = (interior.winfo_reqwidth(), interior.winfo_reqheight())
            canvas.config(scrollregion="0 0 %s %s" % size)
            if interior.winfo_reqwidth() != canvas.winfo_width():
                # update the canvas's width to fit the inner frame
                canvas.config(width=interior.winfo_reqwidth())

        interior.bind("<Configure>", _configure_interior)

        def _configure_canvas(event):
            if interior.winfo_reqwidth() != canvas.winfo_width():
                # update the inner frame's width to fill the canvas
                canvas.itemconfigure(interior_id, width=canvas.winfo_width())
                canvas.bind("<Configure>", _configure_canvas)
                return


def write_data(app, update_info_list, main_file_name):
    """This function records the results of the IPS to PF transfer."""
    # Get Column names
    col_headings = []
    for update_dict in update_info_list:
        for key in update_dict:
            if key in col_headings:
                continue
            else:
                col_headings.append(key)
    # Open the CSV
    with open(main_file_name, "a", newline="", encoding="UTF-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=col_headings)
        writer.writeheader()
        for data in update_info_list:
            writer.writerow(data)


def database_warning():
    """Advise user that the Database query is currently undergoing maintenance."""

    root = tk.Tk()
    root.title("IPStoPF Script")
    root.geometry("+800+200")

    ttk.Label(root, text="WARNING", font='Helvetica 14 bold').\
        grid(columnspan=3, sticky="n", padx=5, pady=5)
    ttk.Label(root, text="The IPS database connection for this script is currently being repaired.").\
        grid(row=2, column=0, sticky="w", padx=30, pady=5)
    ttk.Label(root, text="PowerFactory will be updated in accordance the last successful query (22 April, 2024).").\
        grid(row=3, column=0, sticky="w", padx=30, pady=5)
    ttk.Label(root, text="Any changes to protection devices occuring after this date must be manually added to the PowerFactory model.").\
        grid(row=4, column=0, sticky="w", padx=30, pady=5)
    ttk.Button(root, text='Okay', command=lambda: root.destroy()) \
            .grid(row=5, column=0, sticky="s", padx=5, pady=5)

    # Run the interface
    root.mainloop()

    return


if __name__ == "__main__":
    updates = main()
    # except:  # noqa [E722]
    #     raise

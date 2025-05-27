import sys
import time
import logging

sys.path.append(r"\\ecasd01\WksMgmt\PowerFactory\ScriptsLIB\NetDash-Reader")
from netdashread import get_json_data
from tenacity import retry
from tenacity import stop_after_attempt, wait_random_exponential
sys.path.append(r"\\Ecasd01\WksMgmt\PowerFactory\Scripts\AssetClasses")
import assetclasses
from assetclasses.corporate_data import get_cached_data


def get_setting_ids(app, region):
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
            logging.error(f"Could not create the setting ID dictionary")
            error_message(
                app,
                "Unable to obtained data for Setting IDs,"
                " please contact the Protection SME",
            )
    logging.info(f"Setting ID Dictionary sucessfully created.")
    return ids_dict_list


def create_ids_dict(app, region):
    """This function will create a dictionary of setting ids based on the
    extracted IPS data."""
    if region == "Energex":
        rows = get_cached_data("Report-Cache-ProtectionSettingIDs-EX", max_age=3)
    else:
        rows = get_cached_data("Report-Cache-ProtectionSettingIDs-EE", max_age=3)
    ids_dict_list = []
    for row in rows:
        try:
            ids_dict_list.append(dict(row._asdict()))
        except:  # noqa [E722]
            continue
    return ids_dict_list


def error_message(app, message):
    """Due to a certain condition the script needs to be cancelled"""
    # app.ClearOutputWindow()
    app.PrintError(message)
    sys.exit(0)


def batch_settings(app, region, called_function, set_ids):
    """
    Fpr all the given setting ids get the device settings from IPS
    Args:
        app:
        region:
        called_function:
        set_ids:

    Returns:

    """
    ips_settings = {}
    if region == "Energex":
        if called_function:
            while len(set_ids) > 900:
                ids_1 = set_ids[:900]
                for id_n in ids_1:
                    ips_settings.update(seq_get_ips_settings(app, id_n))
                set_ids = set_ids[900:]
            if len(set_ids) < 900:
                for id_n in set_ids:
                    ips_settings.update(seq_get_ips_settings(app, id_n))
        ips_it_settings = seq_get_ips_it_details(app, set_ids)
    else:
        if called_function:
            while len(set_ids) > 900:
                ids_1 = set_ids[:900]
                for id_n in ids_1:
                    ips_settings.update(reg_get_ips_settings(app, id_n))
                set_ids = set_ids[900:]
            if len(set_ids) < 900:
                for id_n in set_ids:
                    ips_settings.update(reg_get_ips_settings(app, id_n))
        ips_it_settings = reg_get_ips_it_details(app, set_ids)
    return ips_settings, ips_it_settings


def seq_get_ips_it_details(app, devices):
    """The CT Ratio will be configure based on the CT setting node that is
    attached to the relay setting node."""
    ips_settings = []
    it_set_db = get_cached_data("Report-Cache-ProtectionITSettings-EX", max_age=3)
    if it_set_db:
        for setting in it_set_db:
            if setting.relaysettingid in devices:
                ips_settings.append(setting)
    return ips_settings


def reg_get_ips_it_details(app, devices):
    """The CT Ratio will be configure based on the CT setting node that is
    attached to the relay setting node."""
    ips_settings = []
    it_set_db = get_cached_data("Report-Cache-ProtectionITSettings-EE", max_age=3)
    if it_set_db:
        for setting in it_set_db:
            if setting.relaysettingid in devices:
                ips_settings.append(setting)
    return ips_settings


def seq_get_ips_settings(app, set_id: str):
    """
    Using the relay setting ID get the full setting file from the DB
    Args:
        app:
        set_id:

    Returns:
    ips_settings = dict{list[dict]}
    ips_settings = {relaysettingid: [setting, setting, setting...]}
    setting = {blockpathenu: value, paramnameenu: value, proposedsetting: unitenu}
    """
    ips_settings = {}
    ips_settings[set_id] = []
    settings = get_data("Protection-SettingRelay-EX", "setting_id", set_id)
    for setting in settings:
        ips_settings[set_id].append(setting)
    return ips_settings



def reg_get_ips_settings(app, set_id: str):
    """
    Using the relay setting ID get the full setting file from the DB
    Args:
        app:
        set_id:

    Returns:
    ips_settings = dict{list[dict]}
    ips_settings = {relaysettingid: [setting, setting, setting...]}
    setting = {blockpathenu: value, paramnameenu: value, proposedsetting: unitenu}
    """
    ips_settings = {}
    ips_settings[set_id] = []
    settings = get_data("Protection-SettingRelay-EE", "setting_id", set_id)
    for setting in settings:
        if not setting["proposedsetting"]:
            continue
        ips_settings[set_id].append(setting)
    return ips_settings


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_random_exponential(multiplier=1, max=5),
)
def get_data(data_report, paramater, variable):
    """This will use NetDash to perform an acutal query of the IPS DB."""
    data = get_json_data(report=data_report, params={paramater: variable}, timeout=120)
    if len(data) == 0:
        logging.error("The query returned no data")
    return data

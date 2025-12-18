"""
This module stores external variables that are subject to maintenance.
They must be kept up to date for the script to function as intended.
"""

from typing import Set, Dict


def sub_mapping() -> Dict:
    """
    PowerFactory stores all SEQ sub names as three character alpha strings.
    Some SEQ sub names include numerics. In order for switches at these subs
    to be processed correctly, a mapping must be provided between the two
    naming conventions.
    Used in setting_index.py module
    :return: sub_map
    """

    sub_map = {
        "H22": "LGL",
        "H31": "MRD",
        "H38": "GNA",
        "H4": "MGB",
        "T108": "BLH",
        "T11": "CBT",
        "T124": None,
        "T128": "RBA",
        "T136": "ABM",
        "T142": "TSN",
        "T16": "NBR",
        "T160": "SMR",
        "T161": "AGT",
        "T162": "BDB",
        "T187": "RLD",
        "T24": "RBS",
        "T29": "PRG",
        "T30": "AGW",
        "T70": "CRY",
        "T75": "NRG",
        "T78": "LRE",
        "T8": "GYM",
        "T80": "RPN",
        "T81": "CCY",
    }
    return sub_map


# Store SEQ IPS relay patterns with no protection settings.
# These are filtered out during lookups.
# Used in setting_index.py module
EXCLUDED_PATTERNS: Set[str] = {
    "RTU",
    "CMGR12",
    "SEL2505_Energex",
    "GenericRelayWithoutSetting_Energex",
    "SEL-2505",
    "GenericRelayWithoutSetting",
    "T> in TMS no Current_Energex",
    "I>> 3Ph no Time I>> in A_Energex",
    "I> 1Ph no Time I in A_Energex",
    "I> 1Ph no Time I in %_Energex",
}

# Define the IPS name of all single phase and 2 phase relays
# so that they can be placed on the correct phase in the PowerFactory model.
# Used in relay_settings.py module

SINGLE_PHASE_RELAYS = [
    "I>+ I>> 1Ph I in % + T in TMS_Energex",
    "I> 1Ph I in A + I>> in xIs + T in %_Energex",
    "I> 2Ph I in A + T in TMS_Energex",
    "MCGG22",
    "MCGG21",
    "RXIDF",
    "I> 1Ph I in A + I>> in xIs + T in %_Energex",
]

MULTI_PHASE_RELAYS = [
    "I> 2Ph +IE>1Ph I in A + T in TMS_Energex",
    "I>+ I>> 2Ph +IE>+IE>> I in A + T in TMS_Energex",
    "CDG61",
]

# List of feeder disconnect relays to switch out of service
# in the Powerfactory model.
# These relay types do not have TOC protection settings in IPS.
# Used in update_powerfactory.py module
RELAYS_OOS = [
    "7PG21 (SOLKOR-RF)",
    "7SG18 (SOLKOR-N)",
    "RED615 2.6 - 2.8",
    "SOLKOR-N_Energex",
    "SOLKOR-RF_Energex",
]

# Names of IPS relays that protect double cable boxes must be matched to the
# switch name of each cable box.
# Used in setting_index.py module
# Order matters - check longer suffixes first
suffix_expansions = [
    ("A+B+C", ["A", "B", "C"]),
    ("A+B+CP11", ["A", "B", "CP11"]),
    ("A+B+CP12", ["A", "B", "CP12"]),
    ("A+B", ["A", "B"]),
]
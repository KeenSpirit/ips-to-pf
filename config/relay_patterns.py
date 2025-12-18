"""
Relay pattern classification constants.

This module contains lists and sets used to classify relay patterns
by their characteristics (single phase, multi-phase, etc.) and to
identify patterns that should be excluded or handled specially.

These constants are used by:
- relay_settings.py: To determine phase configuration
- setting_index.py: To filter excluded patterns
- update_powerfactory.py: To identify relays to set out of service

Maintenance Notes:
    These lists must be kept up to date as new relay patterns are
    added to the IPS database. When a new relay pattern is added,
    determine its characteristics and add it to the appropriate list.
"""

from typing import Set, List, FrozenSet


# =============================================================================
# Phase Classification
# =============================================================================

# IPS relay patterns that protect single phase or 2-phase configurations.
# Used to place relays on the correct phase in the PowerFactory model.
SINGLE_PHASE_RELAYS: List[str] = [
    "I>+ I>> 1Ph I in % + T in TMS_Energex",
    "I> 1Ph I in A + I>> in xIs + T in %_Energex",
    "I> 2Ph I in A + T in TMS_Energex",
    "MCGG22",
    "MCGG21",
    "RXIDF",
    "I> 1Ph I in A + I>> in xIs + T in %_Energex",
]

# IPS relay patterns that protect multiple phases with earth fault.
# These require special handling for phase assignment.
MULTI_PHASE_RELAYS: List[str] = [
    "I> 2Ph +IE>1Ph I in A + T in TMS_Energex",
    "I>+ I>> 2Ph +IE>+IE>> I in A + T in TMS_Energex",
    "CDG61",
]


# =============================================================================
# Out of Service Relays
# =============================================================================

# Relay types that should be set out of service in PowerFactory.
# These are feeder disconnect relays that do not have TOC protection
# settings in IPS.
RELAYS_OOS: List[str] = [
    "7PG21 (SOLKOR-RF)",
    "7SG18 (SOLKOR-N)",
    "RED615 2.6 - 2.8",
    "SOLKOR-N_Energex",
    "SOLKOR-RF_Energex",
]


# =============================================================================
# Excluded Patterns
# =============================================================================

# IPS relay patterns that have no protection settings and should be
# filtered out during lookups. These patterns exist in IPS but don't
# contain configurable protection settings.
EXCLUDED_PATTERNS: FrozenSet[str] = frozenset({
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
})


# =============================================================================
# Helper Functions
# =============================================================================

def is_single_phase_relay(pattern_name: str) -> bool:
    """
    Check if a relay pattern is single phase.
    
    Args:
        pattern_name: The IPS relay pattern name
        
    Returns:
        True if the pattern is in SINGLE_PHASE_RELAYS
    """
    return pattern_name in SINGLE_PHASE_RELAYS


def is_multi_phase_relay(pattern_name: str) -> bool:
    """
    Check if a relay pattern is multi-phase.
    
    Args:
        pattern_name: The IPS relay pattern name
        
    Returns:
        True if the pattern is in MULTI_PHASE_RELAYS
    """
    return pattern_name in MULTI_PHASE_RELAYS


def should_set_out_of_service(relay_type: str) -> bool:
    """
    Check if a relay type should be set out of service.
    
    Args:
        relay_type: The relay type name
        
    Returns:
        True if the relay should be set out of service
    """
    return relay_type in RELAYS_OOS


def is_excluded_pattern(pattern_name: str) -> bool:
    """
    Check if a pattern should be excluded from processing.
    
    This checks if any of the excluded pattern strings appear
    within the pattern name (substring match).
    
    Args:
        pattern_name: The IPS relay pattern name
        
    Returns:
        True if the pattern should be excluded
    """
    if not pattern_name:
        return False
    
    for excluded in EXCLUDED_PATTERNS:
        if excluded in pattern_name:
            return True
    
    return False

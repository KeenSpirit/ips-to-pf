"""
Fuse settings configuration for PowerFactory.

This module handles the configuration of fuse devices in PowerFactory
using settings from the IPS database. It supports:
- Line fuse configuration
- Transformer fuse configuration
- Automatic fuse type matching by curve and rating

Performance optimizations:
- Uses FuseTypeIndex for O(1) fuse type lookups
"""

from logging_config.logging_utils import get_logger
from typing import Dict, List, Optional, Any, Union, Tuple

from update_powerfactory.type_index import FuseTypeIndex
from core import UpdateResult

logger = get_logger(__name__)


def fuse_setting(
    app,
    device_object: Any,
    fuse_index: Union[FuseTypeIndex, List]
) -> UpdateResult:
    """
    Configure a fuse device with settings from IPS.

    Fuses can only be configured one way - by matching the curve type
    and rating from IPS to a PowerFactory fuse type.

    Args:
        app: PowerFactory application object
        device_object: The ProtectionDevice to configure
        fuse_index: FuseTypeIndex for O(1) lookups, or list for backward compatibility

    Returns:
        UpdateResult with update status
    """
    # Create result from device
    result = UpdateResult.from_device(device_object)

    # Initialize variables for fuse matching
    curve_type = ""
    rating = ""

    # If device is a line fuse but has no matching setting
    if device_object.fuse_type == "Line Fuse" and not device_object.setting_id:
        result.result = "Not in IPS"
        return result

    # Extract curve type and rating from IPS settings
    if device_object.fuse_type == "Line Fuse":
        curve_type, rating, extraction_failed = _extract_fuse_parameters(
            device_object.settings
        )
        if extraction_failed:
            result.result = "Not in IPS"
            return result

    # Find matching fuse type
    fuse = _find_matching_fuse(
        fuse_index, curve_type, rating, device_object.fuse_size
    )

    if not fuse:
        result.relay_pattern = device_object.device
        result.used_pattern = device_object.device
        result.result = "Type Matching Error"
        return result

    # Apply fuse type and settings
    _apply_fuse_type(device_object, fuse, result)

    return result


def _extract_fuse_parameters(
    settings: List[List]
) -> Tuple[str, str, bool]:
    """
    Extract curve type and rating from IPS settings.

    Args:
        settings: List of IPS setting rows

    Returns:
        Tuple of (curve_type, rating, extraction_failed)
    """
    curve_type = ""
    rating = ""

    for setting in settings:
        # Check if setting has sufficient data
        if len(setting) < 3:
            return "", "", True

        setting_name = setting[1].lower()
        setting_value = setting[2]

        # Determine curve type
        if setting_name == "curve":
            if "Dual Rated" in setting_value:
                curve_type = "K"
            else:
                curve_type = setting_value

        # Determine rating
        elif setting[1] == "MAX" and "Dual Rated" in setting_value:
            rating = f" {setting_value}/"
        elif setting[1] in ["MAX", "In"]:
            # Extract numeric portion of rating
            rate_set = ""
            for char in setting_value:
                if char in [".", ","]:
                    break
                rate_set += char
            rating = f" {rate_set}A"

    return curve_type, rating, False


def _find_matching_fuse(
    fuse_index: Union[FuseTypeIndex, List],
    curve_type: str,
    rating: str,
    fuse_size: Optional[str]
) -> Optional[Any]:
    """
    Find a matching fuse type using available criteria.

    Uses O(1) indexed lookup if fuse_index is a FuseTypeIndex,
    otherwise falls back to O(n) linear search for backward compatibility.

    Args:
        fuse_index: FuseTypeIndex for O(1) lookups, or list for compatibility
        curve_type: The curve type letter (e.g., "K", "T")
        rating: The rating string (e.g., " 100A")
        fuse_size: Optional fuse size for Tx fuses (e.g., "100K")

    Returns:
        The matching PowerFactory TypFuse object, or None if not found
    """
    # Use indexed lookup if available (O(1))
    if isinstance(fuse_index, FuseTypeIndex):
        # Try curve + rating first
        if curve_type and rating:
            fuse = fuse_index.get_by_curve_and_rating(curve_type, rating)
            if fuse:
                return fuse

        # Fall back to fuse size
        if fuse_size:
            fuse = fuse_index.get_by_fuse_size(fuse_size)
            if fuse:
                return fuse

        return None

    # Fall back to linear search for backward compatibility (O(n))
    for fuse in fuse_index:
        fuse_name = fuse.loc_name
        fuse_curve = fuse_name[-1].lower()

        # Match by curve type and rating
        if curve_type and rating:
            if curve_type.lower() == fuse_curve and rating in fuse_name:
                return fuse

        # Match by fuse size (for Tx fuses)
        if fuse_size:
            size_curve = fuse_size[-1]
            size_rating = fuse_size[:-1]
            if size_curve == fuse_name[-1] and size_rating in fuse_name:
                return fuse

    return None


def _apply_fuse_type(
    device_object: Any,
    fuse: Any,
    result: UpdateResult
) -> None:
    """
    Apply the fuse type to the PowerFactory device.

    Args:
        device_object: The ProtectionDevice to update
        fuse: The PowerFactory TypFuse to apply
        result: UpdateResult to update with status
    """
    pf_device = device_object.pf_obj

    # Set the relay with the information about which setting from IPS was used
    pf_device.SetAttribute("e:chr_name", str(device_object.date))
    result.date_setting = device_object.date
    result.relay_pattern = device_object.device
    result.used_pattern = device_object.device

    try:
        existing_type = pf_device.typ_id.loc_name
        if existing_type != fuse.loc_name:
            pf_device.typ_id = fuse
        else:
            result.result = "Type Correct"
    except AttributeError:
        # No existing type assigned
        pf_device.typ_id = fuse

    # Ensure fuse is in service
    pf_device.SetAttribute("e:outserv", 0)

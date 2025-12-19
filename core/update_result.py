"""
Update result/status class for PowerFactory device updates.

This module provides the UpdateResult dataclass which replaces the
dictionary-based update_info pattern used throughout the update_powerfactory
module. Benefits include:
- Type safety and IDE support
- Clear documentation of available fields
- Consistent field naming
- Easy conversion to dictionary for CSV output

Usage:
    result = UpdateResult.from_device(device_object)
    result.result = "Updated Successfully"
    result.ct_result = "CT info updated"

    # Convert to dict for CSV writing
    data_capture_list.append(result.to_dict())
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any
from logging_config.logging_utils import get_logger

logger = get_logger(__name__)


@dataclass
class UpdateResult:
    """
    Represents the result of updating a protection device in PowerFactory.

    This dataclass captures all relevant information about a device update
    operation, including success/failure status, CT/VT configuration results,
    and any error information.

    Attributes:
        substation: Name of the substation containing the device
        plant_number: Device plant number/name in PowerFactory
        relay_pattern: The IPS relay pattern name
        used_pattern: The actual pattern used (may differ from relay_pattern)
        date_setting: Date stamp of the IPS setting used
        result: Overall result message (e.g., "Updated Successfully", "Not in IPS")
        ct_name: Name of the CT assigned to the device
        ct_result: Result of CT configuration
        vt_name: Name of the VT assigned to the device
        vt_result: Result of VT configuration
        cb_name: Circuit breaker name (for failed CB records)
        error_detail: Detailed error message if processing failed

    Example:
        >>> result = UpdateResult(
        ...     substation="SUBSTATION_A",
        ...     plant_number="RC-12345",
        ...     relay_pattern="RC01_Recloser",
        ...     result="Updated Successfully"
        ... )
        >>> result.to_dict()
        {'SUBSTATION': 'SUBSTATION_A', 'PLANT_NUMBER': 'RC-12345', ...}
    """

    # Core identification fields
    substation: str = ""
    plant_number: str = ""

    # Relay/fuse pattern information
    relay_pattern: Optional[str] = None
    used_pattern: Optional[str] = None
    date_setting: Optional[str] = None

    # Overall result
    result: str = ""

    # CT configuration results
    ct_name: Optional[str] = None
    ct_result: Optional[str] = None

    # VT configuration results
    vt_name: Optional[str] = None
    vt_result: Optional[str] = None

    # CB information (for failed CB records in batch mode)
    cb_name: Optional[str] = None

    # Error handling
    error_detail: Optional[str] = None

    @classmethod
    def from_device(cls, device_object: Any, app: Any = None) -> 'UpdateResult':
        """
        Create an UpdateResult from a ProtectionDevice object.

        This is the primary factory method for creating results. It extracts
        common information from the device object to initialise the result.

        Args:
            device_object: The ProtectionDevice being processed
            app: Optional PowerFactory application object (for logging)

        Returns:
            UpdateResult instance with device information populated

        Example:
            >>> result = UpdateResult.from_device(device_object)
            >>> result.result = "Updated Successfully"
        """
        substation = ""
        plant_number = ""

        try:
            if device_object.pf_obj:
                substation = device_object.pf_obj.GetAttribute("r:cpGrid:e:loc_name") or ""
                plant_number = device_object.pf_obj.loc_name or ""
        except AttributeError:
            if app:
                logger.warning("Could not extract substation/plant_number from device")

        return cls(
            substation=substation,
            plant_number=plant_number,
            relay_pattern=getattr(device_object, 'device', None),
            used_pattern=getattr(device_object, 'device', None),
            date_setting=getattr(device_object, 'date', None),
        )

    @classmethod
    def not_in_ips(cls, device_object: Any) -> 'UpdateResult':
        """
        Create a result for a device not found in IPS.

        Args:
            device_object: The ProtectionDevice not found in IPS

        Returns:
            UpdateResult with "Not in IPS" result
        """
        result = cls.from_device(device_object)
        result.result = "Not in IPS"
        return result

    @classmethod
    def script_failed(
            cls,
            device_object: Any,
            error: Optional[Exception] = None
    ) -> 'UpdateResult':
        """
        Create a result for a device that failed during processing.

        Args:
            device_object: The ProtectionDevice that failed
            error: Optional exception that caused the failure

        Returns:
            UpdateResult with "Script Failed" result
        """
        result = cls.from_device(device_object)
        result.result = "Script Failed"

        if error:
            result.error_detail = str(error)

        return result

    @classmethod
    def failed_cb(cls, cb_object: Any) -> 'UpdateResult':
        """
        Create a result for a failed circuit breaker match.

        Used in batch mode when a CB cannot be matched to IPS data.

        Args:
            cb_object: The PowerFactory CB object that failed to match

        Returns:
            UpdateResult with CB failure information
        """
        try:
            substation = cb_object.GetAttribute("r:cpGrid:e:loc_name") or ""
        except AttributeError:
            substation = "UNKNOWN"

        return cls(
            substation=substation,
            cb_name=getattr(cb_object, 'loc_name', 'Unknown'),
            result="Failed to find match"
        )

    @classmethod
    def info_record(cls, pf_device: Any, result_message: str) -> 'UpdateResult':
        """
        Create an informational result record.

        Used for devices that are skipped or have informational status
        (e.g., "Not a protection device", "FAILED FUSE").

        Args:
            pf_device: The PowerFactory device object
            result_message: The status/result message

        Returns:
            UpdateResult with the specified message
        """
        try:
            substation = pf_device.GetAttribute("r:cpGrid:e:loc_name") or ""
            plant_number = pf_device.loc_name or ""
        except AttributeError:
            substation = ""
            plant_number = ""

        return cls(
            substation=substation,
            plant_number=plant_number,
            result=result_message
        )

    def to_dict(self) -> Dict[str, str]:
        """
        Convert the result to a dictionary for CSV output.

        The dictionary uses uppercase keys to match the existing CSV
        format used by the script. Only non-None values are included.

        Returns:
            Dictionary with uppercase keys and string values

        Example:
            >>> result = UpdateResult(substation="SUB_A", result="OK")
            >>> result.to_dict()
            {'SUBSTATION': 'SUB_A', 'RESULT': 'OK'}
        """
        # Field name to CSV column name mapping
        field_mapping = {
            'substation': 'SUBSTATION',
            'plant_number': 'PLANT_NUMBER',
            'relay_pattern': 'RELAY_PATTERN',
            'used_pattern': 'USED_PATTERN',
            'date_setting': 'DATE_SETTING',
            'result': 'RESULT',
            'ct_name': 'CT_NAME',
            'ct_result': 'CT_RESULT',
            'vt_name': 'VT_NAME',
            'vt_result': 'VT_RESULT',
            'cb_name': 'CB_NAME',
            'error_detail': 'ERROR_DETAIL',
        }

        result_dict = {}
        for field_name, csv_name in field_mapping.items():
            value = getattr(self, field_name)
            if value is not None and value != "":
                result_dict[csv_name] = str(value)

        return result_dict

    def set_ct_info(self, name: Optional[str], result: str) -> 'UpdateResult':
        """
        Set CT configuration results.

        Convenience method for setting both CT fields at once.
        Returns self for method chaining.

        Args:
            name: CT name/identifier
            result: CT configuration result message

        Returns:
            Self for method chaining
        """
        self.ct_name = name
        self.ct_result = result
        return self

    def set_vt_info(self, name: Optional[str], result: str) -> 'UpdateResult':
        """
        Set VT configuration results.

        Convenience method for setting both VT fields at once.
        Returns self for method chaining.

        Args:
            name: VT name/identifier
            result: VT configuration result message

        Returns:
            Self for method chaining
        """
        self.vt_name = name
        self.vt_result = result
        return self

    def mark_success(self, message: str = "Updated Successfully") -> 'UpdateResult':
        """
        Mark the update as successful.

        Args:
            message: Success message (default: "Updated Successfully")

        Returns:
            Self for method chaining
        """
        self.result = message
        return self

    def mark_failure(self, message: str, error: Optional[Exception] = None) -> 'UpdateResult':
        """
        Mark the update as failed.

        Args:
            message: Failure message
            error: Optional exception that caused the failure

        Returns:
            Self for method chaining
        """
        self.result = message
        if error:
            self.error_detail = str(error)
        return self

    def __str__(self) -> str:
        """String representation for logging."""
        return f"UpdateResult({self.plant_number}: {self.result})"

    def __repr__(self) -> str:
        """Detailed representation for debugging."""
        return (
            f"UpdateResult(substation={self.substation!r}, "
            f"plant_number={self.plant_number!r}, "
            f"result={self.result!r})"
        )


# =============================================================================
# Helper functions for backward compatibility
# =============================================================================

def dict_to_result(update_info: Dict[str, str]) -> UpdateResult:
    """
    Convert an old-style update_info dictionary to UpdateResult.

    Provided for gradual migration of existing code.

    Args:
        update_info: Dictionary with uppercase keys

    Returns:
        UpdateResult instance
    """
    return UpdateResult(
        substation=update_info.get('SUBSTATION', ''),
        plant_number=update_info.get('PLANT_NUMBER', ''),
        relay_pattern=update_info.get('RELAY_PATTERN'),
        used_pattern=update_info.get('USED_PATTERN'),
        date_setting=update_info.get('DATE_SETTING'),
        result=update_info.get('RESULT', ''),
        ct_name=update_info.get('CT_NAME'),
        ct_result=update_info.get('CT_RESULT'),
        vt_name=update_info.get('VT_NAME'),
        vt_result=update_info.get('VT_RESULT'),
        cb_name=update_info.get('CB_NAME'),
    )


def result_to_dict(result: UpdateResult) -> Dict[str, str]:
    """
    Convert UpdateResult to dictionary.

    Alias for result.to_dict() for backward compatibility.

    Args:
        result: UpdateResult instance

    Returns:
        Dictionary with uppercase keys
    """
    return result.to_dict()

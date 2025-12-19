"""
Core domain objects for IPS to PowerFactory settings transfer.

This package contains shared domain objects used by both the ips_data
and update_powerfactory packages. By centralizing these objects here,
we eliminate circular dependencies between the data retrieval and
data application layers.

Classes:
    UpdateResult: Represents the result of updating a device
    ProtectionDevice: Represents a protection relay or fuse with its settings
    SettingRecord: Represents a single setting record from IPS

Usage:
    from core import UpdateResult, ProtectionDevice, SettingRecord
    
    # Create result from device
    result = UpdateResult.from_device(device_object)
    result.result = "Updated Successfully"
    
    # Create protection device
    device = ProtectionDevice(app, "CAPM4", "RC-001", "SET123", "2024-01-01", pf_obj, "DEV001")
    
    # Create setting record
    record = SettingRecord.from_dict({"relaysettingid": "123", "assetname": "RC-001"})
"""

from core.update_result import (
    UpdateResult
)

from core.protection_device import ProtectionDevice

from core.setting_record import SettingRecord

__all__ = [
    "UpdateResult",
    "ProtectionDevice",
    "SettingRecord",
]

"""
Setting record domain model.

This module contains the SettingRecord dataclass which represents a
single setting record from the IPS database.

The SettingRecord provides named access to setting attributes instead
of dictionary key lookups, improving code readability and enabling
IDE support for attribute access.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class SettingRecord:
    """
    Represents a single setting record from IPS.
    
    This dataclass provides named access to setting attributes instead of
    dictionary key lookups, improving code readability and enabling IDE
    support for attribute access.
    
    Attributes:
        relaysettingid: Unique identifier for the relay setting
        assetname: Name of the asset in IPS
        patternname: The relay pattern/type name
        datesetting: Date the setting was created/modified
        active: Whether the setting is currently active (Ergon only)
        nameenu: Switch/CB name (Energex only)
        locationpathenu: Full location path (Energex only)
        deviceid: Device identifier (Energex only)
        raw_data: Original dictionary for accessing any additional fields
        
    Example:
        >>> data = {"relaysettingid": "123", "assetname": "RC-001", "patternname": "CAPM4"}
        >>> record = SettingRecord.from_dict(data)
        >>> print(record.assetname)
        'RC-001'
    """
    relaysettingid: str
    assetname: str
    patternname: str
    datesetting: Optional[str] = None
    active: Optional[bool] = None
    nameenu: Optional[str] = None
    locationpathenu: Optional[str] = None
    deviceid: Optional[str] = None
    raw_data: Dict[str, Any] = field(default_factory=dict, repr=False)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SettingRecord':
        """
        Create a SettingRecord from a raw dictionary.
        
        Args:
            data: Dictionary containing setting data from IPS query
            
        Returns:
            SettingRecord instance with mapped attributes
            
        Example:
            >>> data = {"relaysettingid": "123", "assetname": "RC-001"}
            >>> record = SettingRecord.from_dict(data)
        """
        return cls(
            relaysettingid=data.get('relaysettingid', ''),
            assetname=data.get('assetname', ''),
            patternname=data.get('patternname', ''),
            datesetting=data.get('datesetting'),
            active=data.get('active'),
            nameenu=data.get('nameenu'),
            locationpathenu=data.get('locationpathenu'),
            deviceid=data.get('deviceid'),
            raw_data=data
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the record back to a dictionary.
        
        Returns:
            Dictionary representation of the record
        """
        return {
            'relaysettingid': self.relaysettingid,
            'assetname': self.assetname,
            'patternname': self.patternname,
            'datesetting': self.datesetting,
            'active': self.active,
            'nameenu': self.nameenu,
            'locationpathenu': self.locationpathenu,
            'deviceid': self.deviceid,
        }
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a value from the raw data dictionary.
        
        Provides dictionary-like access for fields not explicitly
        defined as attributes.
        
        Args:
            key: The key to look up
            default: Default value if key not found
            
        Returns:
            The value or default
        """
        return self.raw_data.get(key, default)
    
    @property
    def is_active(self) -> bool:
        """Check if the setting is active (defaults to True if not specified)."""
        return self.active is True or self.active is None
    
    @property
    def has_location(self) -> bool:
        """Check if the record has location information."""
        return bool(self.locationpathenu)
    
    @property
    def has_switch_name(self) -> bool:
        """Check if the record has a switch/CB name."""
        return bool(self.nameenu)

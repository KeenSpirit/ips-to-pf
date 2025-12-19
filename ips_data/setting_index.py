"""
Indexed data structures for efficient IPS setting lookups.

This module provides the SettingIndex class which pre-processes the raw
IPS setting ID data into indexed dictionaries for O(1) lookups by various
keys (asset name, switch name, etc.).

The raw data from IPS comes as a list of dictionaries that would otherwise
require O(n) linear scans for each lookup. With thousands of settings and
hundreds of devices, this optimization reduces lookup complexity from
O(n*m) to O(n+m).
"""

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Any
import logging

from core import SettingRecord
from config.relay_patterns import EXCLUDED_PATTERNS
from config.region_config import get_substation_mapping, SUFFIX_EXPANSIONS

logger = logging.getLogger(__name__)

class SettingIndex:
    """
    Indexed container for IPS setting records providing O(1) lookups.
    
    This class pre-processes a list of setting dictionaries into multiple
    index structures optimized for different lookup patterns:
    
    - by_asset_exact: Exact match on asset name
    - by_asset_prefix: Prefix match for partial asset name lookups  
    - by_switch_name: Lookup by switch/CB name (Energex)
    - by_setting_id: Direct lookup by relay setting ID
    
    Example usage:
        >>> index = SettingIndex(ids_dict_list, region="Energex")
        >>> records = index.get_by_switch_name("CB01")
        >>> exact_match = index.get_by_asset_exact("RC-12345")
    
    Attributes:
        region: The region this index is configured for ("Energex" or "Ergon")
        records: List of all SettingRecord objects
    """

    def __init__(self, ids_dict_list: List[Dict[str, Any]], region: str):
        """
        Initialize the index from a list of setting dictionaries.
        
        Args:
            ids_dict_list: List of dictionaries from IPS query
            region: "Energex" or "Ergon" - affects which indexes are built
        """
        self.region = region
        self.records: List[SettingRecord] = []
        
        # Primary indexes
        self._by_asset_exact: Dict[str, List[SettingRecord]] = defaultdict(list)
        self._by_asset_prefix: Dict[str, List[SettingRecord]] = defaultdict(list)
        self._by_setting_id: Dict[str, SettingRecord] = {}
        
        # Energex-specific indexes
        self._by_switch_name: Dict[str, List[SettingRecord]] = defaultdict(list)
        self._by_substation_and_switch: Dict[str, Dict[str, List[SettingRecord]]] = defaultdict(lambda: defaultdict(list))
        
        # Build indexes
        self._build_indexes(ids_dict_list)
        
        logger.info(
            f"SettingIndex built for {region}: "
            f"{len(self.records)} records, "
            f"{len(self._by_asset_exact)} unique assets, "
            f"{len(self._by_setting_id)} setting IDs"
        )
    
    def _build_indexes(self, ids_dict_list: List[Dict[str, Any]]) -> None:
        """
        Build all index structures from the raw data.
        
        Args:
            ids_dict_list: List of dictionaries from IPS query
        """
        for data in ids_dict_list:
            record = SettingRecord.from_dict(data)
            
            # Skip records that should be filtered
            if self._should_skip_record(record):
                continue
                
            self.records.append(record)
            
            # Index by setting ID (unique)
            if record.relaysettingid:
                self._by_setting_id[record.relaysettingid] = record
            
            # Index by exact asset name
            if record.assetname:
                self._by_asset_exact[record.assetname].append(record)
                
                # Also index by prefix (for partial matching)
                # This handles cases like "RC-12345" matching "RC-12345 Phase A"
                self._index_by_prefixes(record)
            
            # Energex-specific indexing
            if self.region == "Energex" and record.nameenu:
                self._build_energex_indexes(record)
    
    def _should_skip_record(self, record: SettingRecord) -> bool:
        """
        Determine if a record should be excluded from indexes.
        
        Args:
            record: The setting record to check
            
        Returns:
            True if record should be skipped, False otherwise
        """
        if not record.patternname:
            return False
            
        # Check for excluded pattern substrings
        for excluded in EXCLUDED_PATTERNS:
            if excluded in record.patternname:
                return True
        
        # Ergon: skip inactive records
        if self.region == "Ergon" and record.active is False:
            return True
            
        return False
    
    def _index_by_prefixes(self, record: SettingRecord) -> None:
        """
        Index a record by progressively longer prefixes of its asset name.
        
        This enables efficient prefix matching for cases where device names
        in PowerFactory are substrings of asset names in IPS.
        
        Args:
            record: The setting record to index
        """
        asset = record.assetname
        # Index by meaningful prefixes (at least 4 chars to avoid too many collisions)
        for length in range(4, len(asset) + 1):
            prefix = asset[:length]
            self._by_asset_prefix[prefix].append(record)
    
    def _build_energex_indexes(self, record: SettingRecord) -> None:
        """
        Build Energex-specific indexes for switch name lookups.
        
        Energex uses switch names (nameenu) and location paths for matching,
        unlike Ergon which uses asset names directly.
        
        For double cable box configurations (names ending in "A+B"), we index
        the record under BOTH individual switch names. For example, a record
        with nameenu "NIP1A+B" is indexed under both "NIP1A" and "NIP1B".
        
        Args:
            record: The setting record to index
        """
        nameenu = record.nameenu
        
        # Extract base switch name (part before underscore)
        base_name = nameenu.split('_')[0] if '_' in nameenu else nameenu
        
        # Check if this is a double cable box configuration (ends with "A+B")
        expanded_names = self._expand_double_cable_box_name(base_name)
        
        # Get substation for substation-filtered lookups
        substation = None
        if record.locationpathenu:
            parts = record.locationpathenu.split('/')
            if len(parts) > 2:
                sub = parts[2]
                # May only use if substation is alphabetic
                if sub.isalpha():
                    substation = sub
                else:
                    sub_map = get_substation_mapping()
                    if sub in sub_map:
                        substation = sub_map[sub]

        # Index under each expanded name (or just the original if no expansion)
        for switch_name in expanded_names:
            self._by_switch_name[switch_name].append(record)
            
            # Also index by substation + switch for disambiguating same-named switches
            if substation:
                self._by_substation_and_switch[substation][switch_name].append(record)
        
        # Also index by full nameenu for exact matches (if different from base)
        if nameenu != base_name and nameenu not in expanded_names:
            self._by_switch_name[nameenu].append(record)
    
    def _expand_double_cable_box_name(self, name: str) -> List[str]:
        """
        Expand a double cable box name into individual switch names.
        
        If the name ends with "A+B", returns the individual switch names.
        Otherwise, returns the original name unchanged.
        
        Examples:
            "NIP1A+B" -> ["NIP1A", "NIP1B"]
            "CB01A+B+C" -> ["CB01A", "CB01B", "CB01C"]
            "NIP1A" -> ["NIP1A"]
        
        Args:
            name: The switch/device name to expand
            
        Returns:
            List of individual switch names
        """

        for suffix, components in SUFFIX_EXPANSIONS:
            if name.endswith(suffix):
                base = name[:-len(suffix)]
                return [base + comp for comp in components]
        
        # No expansion needed - return original name
        return [name]
    
    def get_by_asset_exact(self, asset_name: str) -> List[SettingRecord]:
        """
        Get all records matching an exact asset name.
        
        Args:
            asset_name: The exact asset name to look up
            
        Returns:
            List of matching SettingRecord objects (empty if no match)
        """
        return self._by_asset_exact.get(asset_name, [])
    
    def get_by_asset_contains(self, device_name: str) -> List[SettingRecord]:
        """
        Get all records where the asset name contains the device name.
        
        This is used for Ergon matching where device names from PowerFactory
        may be substrings of IPS asset names.
        
        Args:
            device_name: The device name to search for
            
        Returns:
            List of matching SettingRecord objects
        """
        # First try exact match
        exact = self._by_asset_exact.get(device_name, [])
        if exact:
            return exact
        
        # Then try prefix match
        prefix_matches = self._by_asset_prefix.get(device_name, [])
        if prefix_matches:
            return prefix_matches
        
        # Fall back to substring search (slower but necessary for some cases)
        results = []
        for asset_name, records in self._by_asset_exact.items():
            if device_name in asset_name:
                results.extend(records)
        return results
    
    def get_by_switch_name(
        self, 
        switch_name: str, 
        substation_code: Optional[str] = None
    ) -> List[SettingRecord]:
        """
        Get all records matching a switch name (Energex).
        
        Args:
            switch_name: The switch/CB name to look up
            substation_code: Optional substation code to filter results
            
        Returns:
            List of matching SettingRecord objects
        """
        if substation_code and substation_code in self._by_substation_and_switch:
            sub_index = self._by_substation_and_switch[substation_code]
            if switch_name in sub_index:
                return sub_index[switch_name]
        
        return self._by_switch_name.get(switch_name, [])
    
    def get_by_setting_id(self, setting_id: str) -> Optional[SettingRecord]:
        """
        Get a single record by its relay setting ID.
        
        Args:
            setting_id: The relay setting ID
            
        Returns:
            The matching SettingRecord or None if not found
        """
        return self._by_setting_id.get(setting_id)
    
    def get_all_setting_ids(self) -> List[str]:
        """
        Get all relay setting IDs in the index.
        
        Returns:
            List of all setting ID strings
        """
        return list(self._by_setting_id.keys())
    
    def __len__(self) -> int:
        """Return the number of records in the index."""
        return len(self.records)
    
    def __iter__(self):
        """Iterate over all records."""
        return iter(self.records)


def create_setting_index(ids_dict_list: List[Dict[str, Any]], region: str) -> SettingIndex:
    """
    Factory function to create a SettingIndex.
    
    This is the primary entry point for creating an index from raw IPS data.
    
    Args:
        ids_dict_list: List of dictionaries from IPS query
        region: "Energex" or "Ergon"
        
    Returns:
        Configured SettingIndex instance
        
    Example:
        >>> ids_dict_list = query_database.create_ids_dict(app, region)
        >>> index = create_setting_index(ids_dict_list, region)
        >>> records = index.get_by_asset_exact("RC-12345")
    """
    return SettingIndex(ids_dict_list, region)

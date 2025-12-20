"""
Type indexing for PowerFactory relay and fuse types.

This module provides indexed lookups for relay and fuse types,
replacing O(n) linear scans with O(1) dictionary lookups.

The TypeIndex classes are designed to be built once at the start of
processing and reused for all device updates, providing significant
performance improvements when processing large numbers of devices.

Usage:
    # Build indexes once
    relay_index = RelayTypeIndex.build(app)
    fuse_index = FuseTypeIndex.build(app)
    
    # O(1) lookups
    relay_type = relay_index.get("Generic SEL351 Relay")
    fuse_type = fuse_index.get_by_curve_and_rating("K", "100A")
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple

from utils.pf_utils import all_relevant_objects


@dataclass
class RelayTypeIndex:
    """
    Indexed collection of PowerFactory relay types for O(1) lookup.

    Provides direct name-based lookup instead of iterating through
    a list of relay types for each device update.

    Attributes:
        _by_name: Dictionary mapping relay type name to PF object
        _all_types: List of all relay type objects (for compatibility)
    """
    _by_name: Dict[str, Any] = field(default_factory=dict)
    _all_types: List[Any] = field(default_factory=list)

    @classmethod
    def build(cls, app) -> 'RelayTypeIndex':
        """
        Build the relay type index from PowerFactory libraries.

        Searches for relay types in:
        1. ErgonLibrary Protection folder
        2. DIgSILENT global library
        3. Current user's Protection folder (local relays)

        Local relay types take precedence if they have the same name
        as library types.

        Args:
            app: PowerFactory application object

        Returns:
            RelayTypeIndex with all relay types indexed by name
        """
        index = cls()

        # 1. Get relay types from ErgonLibrary
        global_library = app.GetGlobalLibrary()
        protection_lib = global_library.GetContents("Protection")
        ergon_types = all_relevant_objects(app, protection_lib, "*.TypRelay", None)

        for relay_type in ergon_types or []:
            name = relay_type.loc_name
            index._by_name[name] = relay_type
            index._all_types.append(relay_type)

        # 2. Get relay types from DIgSILENT library
        try:
            database = global_library.fold_id
            dig_lib = database.GetContents("Lib")[0]
            prot_lib = dig_lib.GetContents("Prot")[0]
            relay_lib = prot_lib.GetContents("ProtRelay")
            dig_types = all_relevant_objects(app, relay_lib, "*.TypRelay", None)

            for relay_type in dig_types or []:
                name = relay_type.loc_name
                if name not in index._by_name:
                    index._by_name[name] = relay_type
                    index._all_types.append(relay_type)
        except (IndexError, AttributeError):
            pass

        # 3. Get local relay types (these take precedence)
        current_user = app.GetCurrentUser()
        protection_folder = current_user.GetContents("Protection")
        local_types = all_relevant_objects(app, protection_folder, "*.TypRelay", None)

        if local_types:
            for relay_type in local_types:
                name = relay_type.loc_name
                if name not in index._by_name:
                    # New type not in libraries
                    index._by_name[name] = relay_type
                    index._all_types.append(relay_type)
                else:
                    # Local type overrides library type
                    index._by_name[name] = relay_type

        return index

    def get(self, name: str) -> Optional[Any]:
        """
        Get a relay type by exact name match.

        Args:
            name: The relay type name (e.g., "Generic SEL351 Relay")

        Returns:
            The PowerFactory TypRelay object, or None if not found
        """
        return self._by_name.get(name)

    def get_all(self) -> List[Any]:
        """
        Get all relay types as a list.

        Provided for backward compatibility with code expecting a list.

        Returns:
            List of all relay type objects
        """
        return self._all_types

    def __len__(self) -> int:
        """Return the number of indexed relay types."""
        return len(self._by_name)

    def __contains__(self, name: str) -> bool:
        """Check if a relay type name exists in the index."""
        return name in self._by_name


@dataclass
class FuseTypeIndex:
    """
    Indexed collection of PowerFactory fuse types for O(1) lookup.

    Fuse types are matched by curve type (K, T, etc.) and rating (e.g., "100A").
    This class provides multiple lookup strategies:
    - Exact name match
    - Curve + rating match
    - Fuse size match (for Tx fuses)

    Attributes:
        _by_name: Dictionary mapping fuse type name to PF object
        _by_curve: Dictionary mapping curve letter to list of fuse types
        _all_types: List of all fuse type objects (for compatibility)
    """
    _by_name: Dict[str, Any] = field(default_factory=dict)
    _by_curve: Dict[str, List[Any]] = field(default_factory=dict)
    _all_types: List[Any] = field(default_factory=list)

    # Pattern to extract rating from fuse name (e.g., " 100A" from "HRC 100A K")
    _RATING_PATTERN = re.compile(r'\s+(\d+)A')

    @classmethod
    def build(cls, app) -> 'FuseTypeIndex':
        """
        Build the fuse type index from PowerFactory ErgonLibrary.

        Args:
            app: PowerFactory application object

        Returns:
            FuseTypeIndex with all fuse types indexed
        """
        index = cls()

        try:
            ergon_lib = app.GetGlobalLibrary()
            fuse_folder = ergon_lib.SearchObject(
                r"\ErgonLibrary\Protection\Fuses.IntFolder"
            )

            if not fuse_folder:
                app.PrintWarn("Fuse folder not found in ErgonLibrary")
                return index

            fuse_types = fuse_folder.GetContents("*.TypFuse", 0)

            for fuse_type in fuse_types or []:
                name = fuse_type.loc_name
                index._by_name[name] = fuse_type
                index._all_types.append(fuse_type)

                # Index by curve type (last character of name)
                curve = name[-1].upper()
                if curve not in index._by_curve:
                    index._by_curve[curve] = []
                index._by_curve[curve].append(fuse_type)

        except AttributeError:
            pass

        return index

    def get(self, name: str) -> Optional[Any]:
        """
        Get a fuse type by exact name match.

        Args:
            name: The fuse type name

        Returns:
            The PowerFactory TypFuse object, or None if not found
        """
        return self._by_name.get(name)

    def get_by_curve_and_rating(
        self,
        curve_type: str,
        rating: str
    ) -> Optional[Any]:
        """
        Find a fuse type matching the curve type and rating.

        This is the primary lookup method for line fuses, matching
        the logic previously in fuse_settings.fuse_setting().

        Args:
            curve_type: The curve type letter (e.g., "K", "T")
            rating: The rating string (e.g., "100A", " 100/")

        Returns:
            The matching PowerFactory TypFuse object, or None if not found
        """
        curve_upper = curve_type.upper()

        # Get all fuses with this curve type
        candidates = self._by_curve.get(curve_upper, [])

        for fuse in candidates:
            if rating in fuse.loc_name:
                return fuse

        return None

    def get_by_fuse_size(self, fuse_size: str) -> Optional[Any]:
        """
        Find a fuse type matching the fuse size specification.

        Used for Tx fuses where the size is determined by transformer rating.

        Args:
            fuse_size: The fuse size string (e.g., "100K", "50T")
                      Last character is curve type, rest is rating

        Returns:
            The matching PowerFactory TypFuse object, or None if not found
        """
        if not fuse_size or len(fuse_size) < 2:
            return None

        curve = fuse_size[-1].upper()
        rating_prefix = fuse_size[:-1]

        candidates = self._by_curve.get(curve, [])

        for fuse in candidates:
            if rating_prefix in fuse.loc_name:
                return fuse

        return None

    def find_matching_fuse(
        self,
        curve_type: Optional[str] = None,
        rating: Optional[str] = None,
        fuse_size: Optional[str] = None
    ) -> Optional[Any]:
        """
        Find a matching fuse type using available criteria.

        This is a convenience method that tries multiple matching strategies:
        1. If curve_type and rating are provided, use get_by_curve_and_rating
        2. If fuse_size is provided, use get_by_fuse_size

        Args:
            curve_type: The curve type letter (optional)
            rating: The rating string (optional)
            fuse_size: The fuse size specification (optional)

        Returns:
            The matching PowerFactory TypFuse object, or None if not found
        """
        # Try curve + rating first
        if curve_type and rating:
            result = self.get_by_curve_and_rating(curve_type, rating)
            if result:
                return result

        # Fall back to fuse size
        if fuse_size:
            return self.get_by_fuse_size(fuse_size)

        return None

    def get_all(self) -> List[Any]:
        """
        Get all fuse types as a list.

        Provided for backward compatibility with code expecting a list.

        Returns:
            List of all fuse type objects
        """
        return self._all_types

    def __len__(self) -> int:
        """Return the number of indexed fuse types."""
        return len(self._by_name)

    def __contains__(self, name: str) -> bool:
        """Check if a fuse type name exists in the index."""
        return name in self._by_name


# =============================================================================
# Factory functions for convenience
# =============================================================================

def build_type_indexes(app) -> Tuple[RelayTypeIndex, FuseTypeIndex]:
    """
    Build both relay and fuse type indexes.

    Convenience function to build both indexes at once.

    Args:
        app: PowerFactory application object

    Returns:
        Tuple of (RelayTypeIndex, FuseTypeIndex)
    """
    relay_index = RelayTypeIndex.build(app)
    fuse_index = FuseTypeIndex.build(app)
    return relay_index, fuse_index
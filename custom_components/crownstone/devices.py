"""Base classes for Crownstone devices."""
from typing import Any, Dict, Optional

from .const import CROWNSTONE_TYPES, DOMAIN


class CrownstoneDevice:
    """Representation of a Crownstone device."""

    def __init__(self, crownstone) -> None:
        """Initialize the device."""
        self.crownstone = crownstone

    @property
    def cloud_id(self) -> str:
        """Return the cloud id of this crownstone."""
        return self.crownstone.cloud_id

    @property
    def device_info(self) -> Optional[Dict[str, Any]]:
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self.crownstone.unique_id)},
            "name": self.crownstone.name,
            "manufacturer": "Crownstone",
            "model": CROWNSTONE_TYPES[self.crownstone.type],
            "sw_version": self.crownstone.sw_version,
        }


class PresenceDevice:
    """Representation of a Crownstone Presence device."""

    def __init__(self, location, description) -> None:
        """Initialize the location device."""
        self.location = location
        self.description = description

    @property
    def cloud_id(self) -> str:
        """Return the cloud id of this presence holder."""
        return self.location.cloud_id

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, self.location.unique_id)},
            "name": f"{self.location.name} presence",
            "manufacturer": "Crownstone",
            "model": self.description,
        }

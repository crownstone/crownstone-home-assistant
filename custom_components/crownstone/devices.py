"""Base classes for Crownstone devices."""
from __future__ import annotations

from crownstone_cloud.cloud_models.crownstones import Crownstone
from crownstone_cloud.cloud_models.locations import Location

from homeassistant.const import (
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_NAME,
    ATTR_SW_VERSION,
)
from homeassistant.helpers.entity import DeviceInfo

from .const import CROWNSTONE_INCLUDE_TYPES, DOMAIN


class CrownstoneDevice:
    """Representation of a Crownstone device."""

    def __init__(self, device: Crownstone) -> None:
        """Initialize the device."""
        self.device = device

    @property
    def cloud_id(self) -> str:
        """
        Return the unique identifier for this device.

        Used as device ID and to generate unique entity ID's.
        """
        return str(self.device.cloud_id)

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return {
            ATTR_IDENTIFIERS: {(DOMAIN, self.cloud_id)},
            ATTR_NAME: self.device.name,
            ATTR_MANUFACTURER: "Crownstone",
            ATTR_MODEL: CROWNSTONE_INCLUDE_TYPES[self.device.type],
            ATTR_SW_VERSION: self.device.sw_version,
        }


class PresenceDevice:
    """Representation of a Crownstone Presence device."""

    def __init__(self, location: Location, model: str) -> None:
        """Initialize the location device."""
        self.location = location
        self.model = model

    @property
    def cloud_id(self) -> str:
        """
        Return the unique identifier for this device.

        Used as device ID and to generate unique entity ID's.
        """
        return str(self.location.cloud_id)

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return {
            ATTR_IDENTIFIERS: {(DOMAIN, self.cloud_id)},
            ATTR_NAME: self.location.name,
            ATTR_MANUFACTURER: "Crownstone",
            ATTR_MODEL: self.model,
        }

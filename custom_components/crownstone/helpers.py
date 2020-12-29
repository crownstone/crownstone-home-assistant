"""Helper functions/classes for Crownstone."""
import asyncio
import threading

from crownstone_uart import CrownstoneUart

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry

from .const import ADDED_ITEMS, DOMAIN, REMOVED_ITEMS


class UartManager(threading.Thread):
    """Uart manager that manages usb connections."""

    def __init__(self) -> None:
        """Init with new event loop and instance."""
        self.loop = asyncio.new_event_loop()
        self.uart_instance = CrownstoneUart(self.loop)

        threading.Thread.__init__(self)

    def run(self) -> None:
        """Run this function in the thread."""
        self.loop.run_until_complete(self.initialize_usb())

    async def initialize_usb(self) -> None:
        """
        Manage USB connections.

        This function runs until Home Assistant is stopped.
        """
        await self.uart_instance.initialize_usb()

    def stop(self) -> None:
        """Stop the uart manager."""
        self.uart_instance.stop()


def set_to_dict(input_set: set):
    """Convert a set to a dictionary."""
    return {key: key for key in input_set}


def check_items(old_data: dict, new_data: dict) -> dict:
    """Compare local data to new data from the cloud."""
    changed_items = {}
    changed_items[ADDED_ITEMS] = []
    changed_items[REMOVED_ITEMS] = []

    for device_id in new_data:
        # check for existing devices
        if device_id in old_data:
            continue

        # new data contains an id that's not in the current data, add it
        changed_items[ADDED_ITEMS].append(new_data.get(device_id))

    # check for removed items
    for device_id in old_data:
        if device_id not in new_data:
            changed_items[REMOVED_ITEMS].append(old_data.get(device_id))

    return changed_items


async def async_remove_devices(
    hass: HomeAssistant, entry: ConfigEntry, devices: list
) -> None:
    """Remove devices from HA when they were removed from the Crownstone cloud."""
    device_reg = await device_registry.async_get_registry(hass)

    for removed_device in devices:
        # remove the device from HA.
        # this also removes all entities of that device.
        device = device_reg.async_get_device(
            identifiers={(DOMAIN, removed_device.cloud_id)}, connections=set()
        )
        if device is not None:
            device_reg.async_update_device(
                device.id, remove_config_entry_id=entry.entry_id
            )

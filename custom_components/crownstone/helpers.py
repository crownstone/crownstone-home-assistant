"""Helper functions/classes for Crownstone."""
import asyncio
from datetime import datetime, timezone
import threading
from typing import Any

from crownstone_uart import CrownstoneUart
from tzlocal import get_localzone

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


class EnergyData:
    """Data class that holds energy measurements."""

    def __init__(self, accumulated_energy: int, utc_timestamp: Any) -> None:
        """Initialize the object."""
        # new value obtained from UART
        self.energy_usage = accumulated_energy
        # the new energy usage value (after adding the offset or previous value)
        self.corrected_energy_usage = 0
        # timestamp of the measurement in UTC
        self.timestamp = utc_timestamp
        # flag for being a first node in the energy data chain
        self.first_measurement = False
        # flag for a restored state from previous session
        self.restored_state = False


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


def create_utc_timestamp(cs_timestamp: int):
    """Create a UTC timestamp from a localzone Crownstone timestamp."""
    # get the timezone of this computer
    tz = get_localzone()
    date = datetime.fromtimestamp(cs_timestamp, tz)
    # calculate the offset
    utc_offset = date.utcoffset().total_seconds()
    # utc is the positive east, calculate timestamp
    return cs_timestamp - utc_offset


def process_energy_update(
    next_data_point: EnergyData, previous_data_point: EnergyData
) -> None:
    """
    Process an update for the energy usage.

    It's possible for devices to reboot (power loss, sw update, crash).
    After a reboot the saved value for energy goes back to zero.
    A check is done to prevent the value in HA from resetting as well.
    """
    next_value = next_data_point.energy_usage
    next_timestamp = next_data_point.timestamp
    previous_raw_value = previous_data_point.energy_usage
    previous_value = previous_data_point.corrected_energy_usage
    previous_timestamp = previous_data_point.timestamp

    # create data objects from timestamps
    # check if a month or year is past
    # we set the energy usage back to 0 each month
    if previous_timestamp is not None:
        next_date = datetime.fromtimestamp(next_timestamp, timezone.utc)
        previous_date = datetime.fromtimestamp(previous_timestamp, timezone.utc)

        if next_date.year > previous_date.year or next_date.month > previous_date.month:
            next_data_point.corrected_energy_usage = 0
            next_data_point.first_measurement = True
            return

    # initial HA value, make sure we start at 0 in HA
    # set first measurement flag to save the start date
    if previous_raw_value == 0 and previous_timestamp is None:
        next_value = 0
        next_data_point.first_measurement = True

    # restored data point, set new measurement to saved value
    elif previous_data_point.restored_state:
        next_value = previous_value

    else:
        # calculate offset value
        offset_value = previous_value - previous_raw_value

        # if the new value is greater than the offset value, accept measurement
        # if it is smaller, add the new value to the offsetvalue
        # check if the new value is below the old value, but just a little, since it can increase fast
        if next_value < previous_raw_value * 0.9:
            next_value += previous_value
        else:
            next_value += offset_value

        # ignore change if next value is still smaller, energy decrease unsupported
        if next_value < previous_value:
            next_value = previous_value

    # set new value
    next_data_point.corrected_energy_usage = next_value

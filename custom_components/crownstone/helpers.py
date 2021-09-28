"""Helper functions for the Crownstone integration."""
from __future__ import annotations

import os

from crownstone_cloud.cloud_models.crownstones import Crownstone
from crownstone_cloud.cloud_models.locations import Location
from serial.tools.list_ports_common import ListPortInfo

from homeassistant.components import usb
from homeassistant.components.binary_sensor import DEVICE_CLASS_CONNECTIVITY
from homeassistant.const import DEVICE_CLASS_ENERGY, DEVICE_CLASS_POWER
from homeassistant.core import HomeAssistant, T, callback
from homeassistant.helpers import device_registry, entity_registry

from .const import (
    CONNECTION_NAME_SUFFIX,
    DOMAIN,
    DONT_USE_USB,
    ENERGY_USAGE_NAME_SUFFIX,
    MANUAL_PATH,
    POWER_USAGE_NAME_SUFFIX,
    REFRESH_LIST,
)


def list_ports_as_str(
    serial_ports: list[ListPortInfo], no_usb_option: bool = True
) -> list[str]:
    """
    Represent currently available serial ports as string.

    Adds option to not use usb on top of the list,
    option to use manual path or refresh list at the end.
    """
    ports_as_string: list[str] = []

    if no_usb_option:
        ports_as_string.append(DONT_USE_USB)

    for port in serial_ports:
        ports_as_string.append(
            usb.human_readable_device_name(
                port.device,
                port.serial_number,
                port.manufacturer,
                port.description,
                f"{hex(port.vid)[2:]:0>4}".upper(),
                f"{hex(port.pid)[2:]:0>4}".upper(),
            )
        )
    ports_as_string.append(MANUAL_PATH)
    ports_as_string.append(REFRESH_LIST)

    return ports_as_string


def get_port(dev_path: str) -> str | None:
    """Get the port that the by-id link points to."""
    # not a by-id link, but just given path
    by_id = "/dev/serial/by-id"
    if by_id not in dev_path:
        return dev_path

    try:
        return f"/dev/{os.path.basename(os.readlink(dev_path))}"
    except FileNotFoundError:
        return None


def map_from_to(val: int, in_min: int, in_max: int, out_min: int, out_max: int) -> int:
    """Map a value from a range to another."""
    return int((val - in_min) * (out_max - out_min) / (in_max - in_min) + out_min)


def get_removed_items(old_data: dict[str, T], new_data: dict[str, T]) -> list[T]:
    """Return a list with removed items from a dict."""
    return [old_data[dev_id] for dev_id in old_data if dev_id not in new_data]


def get_added_items(old_data: dict[str, T], new_data: dict[str, T]) -> list[T]:
    """Return a list with added items from a dict."""
    return [new_data[dev_id] for dev_id in new_data if dev_id not in old_data]


@callback
def async_update_devices(
    hass: HomeAssistant, new_data: dict[str, Crownstone | Location]
) -> None:
    """Update device info when data is updated."""
    dev_reg = device_registry.async_get(hass)
    ent_reg = entity_registry.async_get(hass)

    for crownstone_device in new_data.values():
        ha_device = dev_reg.async_get_device({(DOMAIN, crownstone_device.cloud_id)})
        if ha_device is None:
            continue

        if ha_device.name != crownstone_device.name:
            dev_reg.async_update_device(ha_device.id, name=crownstone_device.name)

        if (
            isinstance(crownstone_device, Crownstone)
            and ha_device.sw_version != crownstone_device.sw_version
        ):
            dev_reg.async_update_device(
                ha_device.id, sw_version=crownstone_device.sw_version
            )

        entries = entity_registry.async_entries_for_device(ent_reg, ha_device.id, True)
        for entry in entries:
            if entry.name == crownstone_device.name:
                continue

            new_name = crownstone_device.name
            if entry.device_class == DEVICE_CLASS_CONNECTIVITY:
                new_name = f"{new_name} {CONNECTION_NAME_SUFFIX}"
            if entry.device_class == DEVICE_CLASS_POWER:
                new_name = f"{new_name} {POWER_USAGE_NAME_SUFFIX}"
            if entry.device_class == DEVICE_CLASS_ENERGY:
                new_name = f"{new_name} {ENERGY_USAGE_NAME_SUFFIX}"

            ent_reg.async_update_entity(entry.entity_id, name=new_name)


@callback
def async_remove_devices(
    hass: HomeAssistant, entry_id: str, removed_devices: list[Crownstone]
) -> None:
    """Remove devices from HA if they were removed from the Crownstone cloud."""
    dev_reg = device_registry.async_get(hass)

    for removed_device in removed_devices:
        device = dev_reg.async_get_device({(DOMAIN, removed_device.cloud_id)})
        if device is None:
            continue

        dev_reg.async_update_device(device.id, remove_config_entry_id=entry_id)

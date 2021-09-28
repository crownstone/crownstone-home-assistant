"""Integration for Crownstone."""
from __future__ import annotations

import logging

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .entry_manager import CrownstoneEntryManager

_LOGGER = logging.getLogger(__name__)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    _LOGGER.debug("Migrating from version %s", entry.version)

    hass.async_create_task(hass.config_entries.async_remove(entry.entry_id))

    current_flows = hass.config_entries.flow.async_progress()
    if not [flow for flow in current_flows if flow["handler"] == DOMAIN]:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}
            )
        )

    return False


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Initiate setup for a Crownstone config entry."""
    manager = CrownstoneEntryManager(hass, entry)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = manager

    return await manager.async_setup()


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok: bool = await hass.data[DOMAIN][entry.entry_id].async_unload()
    if len(hass.data[DOMAIN]) == 0:
        hass.data.pop(DOMAIN)
    return unload_ok

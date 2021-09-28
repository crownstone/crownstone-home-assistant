"""Support for Crownstone devices."""
from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING, Any

from crownstone_cloud.cloud_models.crownstones import Crownstone, CrownstoneAbility
from crownstone_cloud.const import (
    DIMMING_ABILITY,
    SWITCHCRAFT_ABILITY,
    TAP_TO_TOGGLE_ABILITY,
)
from crownstone_cloud.exceptions import CrownstoneAbilityError
from crownstone_uart import CrownstoneUart

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    SUPPORT_BRIGHTNESS,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ABILITY,
    CROWNSTONE_INCLUDE_TYPES,
    CROWNSTONE_SUFFIX,
    DOMAIN,
    SIG_ADD_CROWNSTONE_DEVICES,
    SIG_CROWNSTONE_STATE_UPDATE,
)
from .devices import CrownstoneBaseEntity
from .helpers import map_from_to

if TYPE_CHECKING:
    from .entry_manager import CrownstoneEntryManager


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up crownstones from a config entry."""
    manager: CrownstoneEntryManager = hass.data[DOMAIN][config_entry.entry_id]

    entities: list[CrownstoneEntity] = []

    # Add Crownstone entities that support switching/dimming
    for sphere in manager.cloud.cloud_data:
        for crownstone in sphere.crownstones:
            if crownstone.type not in CROWNSTONE_INCLUDE_TYPES:
                continue
            if manager.uart and sphere.cloud_id == manager.usb_sphere_id:
                entities.append(CrownstoneEntity(crownstone, manager.uart))
            else:
                entities.append(CrownstoneEntity(crownstone))

    # add callback for new devices
    manager.config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            SIG_ADD_CROWNSTONE_DEVICES,
            partial(async_add_crownstone_entities, async_add_entities, manager),
        )
    )

    async_add_entities(entities)


def crownstone_state_to_hass(value: int) -> int:
    """Crownstone 0..100 to hass 0..255."""
    return map_from_to(value, 0, 100, 0, 255)


def hass_to_crownstone_state(value: int) -> int:
    """Hass 0..255 to Crownstone 0..100."""
    return map_from_to(value, 0, 255, 0, 100)


@callback
def async_add_crownstone_entities(
    async_add_entities: AddEntitiesCallback,
    manager: CrownstoneEntryManager,
    crownstones: list[Crownstone],
    sphere_id: str,
) -> None:
    """Add a new Crownstone device to HA."""
    entities: list[CrownstoneEntity] = []

    for crownstone in crownstones:
        if crownstone.type not in CROWNSTONE_INCLUDE_TYPES:
            continue
        # adding a Crownstone is done in 2 steps
        # these parameters have to be added for initialization
        crownstone.abilities = {
            DIMMING_ABILITY: CrownstoneAbility(ABILITY),
            TAP_TO_TOGGLE_ABILITY: CrownstoneAbility(ABILITY),
            SWITCHCRAFT_ABILITY: CrownstoneAbility(ABILITY),
        }
        crownstone.data["currentSwitchState"] = {"switchState": 100}

        if manager.uart and sphere_id == manager.usb_sphere_id:
            entities.append(CrownstoneEntity(crownstone, manager.uart))
        else:
            entities.append(CrownstoneEntity(crownstone))

    async_add_entities(entities)


class CrownstoneEntity(CrownstoneBaseEntity, LightEntity):
    """
    Representation of a crownstone.

    Light platform is used to support dimming.
    """

    _attr_icon = "mdi:power-socket-de"

    def __init__(
        self, crownstone_data: Crownstone, usb: CrownstoneUart | None = None
    ) -> None:
        """Initialize the crownstone."""
        super().__init__(crownstone_data)
        self.usb = usb
        # Entity class attributes
        self._attr_name = str(self.device.name)
        self._attr_unique_id = f"{self.cloud_id}-{CROWNSTONE_SUFFIX}"

    @property
    def brightness(self) -> int | None:
        """Return the brightness if dimming enabled."""
        return crownstone_state_to_hass(self.device.state)

    @property
    def is_on(self) -> bool:
        """Return if the device is on."""
        return crownstone_state_to_hass(self.device.state) > 0

    @property
    def supported_features(self) -> int:
        """Return the supported features of this Crownstone."""
        dimming = self.device.abilities.get(DIMMING_ABILITY)
        if dimming and dimming.is_enabled:
            return SUPPORT_BRIGHTNESS
        return 0

    async def async_added_to_hass(self) -> None:
        """Set up a listener when this entity is added to HA."""
        # new state received
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIG_CROWNSTONE_STATE_UPDATE, self.async_write_ha_state
            )
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on this light via dongle or cloud."""
        if ATTR_BRIGHTNESS in kwargs:
            if self.usb is not None and self.usb.is_ready():
                await self.hass.async_add_executor_job(
                    partial(
                        self.usb.dim_crownstone,
                        self.device.unique_id,
                        hass_to_crownstone_state(kwargs[ATTR_BRIGHTNESS]),
                    )
                )
            else:
                try:
                    await self.device.async_set_brightness(
                        hass_to_crownstone_state(kwargs[ATTR_BRIGHTNESS])
                    )
                except CrownstoneAbilityError as ability_error:
                    raise HomeAssistantError(ability_error) from ability_error

            # assume brightness is set on device
            self.device.state = hass_to_crownstone_state(kwargs[ATTR_BRIGHTNESS])
            self.async_write_ha_state()

        elif self.usb is not None and self.usb.is_ready():
            await self.hass.async_add_executor_job(
                partial(self.usb.switch_crownstone, self.device.unique_id, on=True)
            )
            self.device.state = 100
            self.async_write_ha_state()

        else:
            await self.device.async_turn_on()
            self.device.state = 100
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off this device via dongle or cloud."""
        if self.usb is not None and self.usb.is_ready():
            await self.hass.async_add_executor_job(
                partial(self.usb.switch_crownstone, self.device.unique_id, on=False)
            )

        else:
            await self.device.async_turn_off()

        self.device.state = 0
        self.async_write_ha_state()

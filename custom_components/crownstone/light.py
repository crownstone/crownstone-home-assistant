"""Support for Crownstone devices."""
from functools import partial
import logging
from typing import Any, Dict, Optional

from crownstone_cloud.cloud_models.crownstones import CrownstoneAbility
from crownstone_cloud.const import (
    DIMMING_ABILITY,
    SWITCHCRAFT_ABILITY,
    TAP_TO_TOGGLE_ABILITY,
)
from crownstone_cloud.exceptions import CrownstoneAbilityError
import numpy

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    SUPPORT_BRIGHTNESS,
    LightEntity,
)
from homeassistant.core import callback
from homeassistant.helpers.device_registry import async_get_registry as get_device_reg
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_registry import async_get_registry as get_entity_reg

from .const import (
    ABILITY,
    ABILITY_STATE,
    CROWNSTONE_EXCLUDE,
    CROWNSTONE_SUFFIX,
    DOMAIN,
    SIG_ADD_CROWNSTONE_DEVICES,
    SIG_CROWNSTONE_STATE_UPDATE,
    SIG_CROWNSTONE_UPDATE,
    SIG_UART_READY,
)
from .devices import CrownstoneDevice

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up crownstones from a config entry."""
    crownstone_hub = hass.data[DOMAIN][config_entry.entry_id]

    entities = []

    for crownstone in crownstone_hub.sphere.crownstones:
        # some don't support light features
        if crownstone.type not in CROWNSTONE_EXCLUDE:
            entities.append(
                Crownstone(crownstone, crownstone_hub.uart_manager.uart_instance)
            )

    # subscribe to Crownstone add signals
    async_dispatcher_connect(
        hass,
        SIG_ADD_CROWNSTONE_DEVICES,
        partial(add_crownstone_entities, async_add_entities, crownstone_hub),
    )

    async_add_entities(entities)


@callback
async def add_crownstone_entities(async_add_entities, crownstone_hub, crownstones):
    """Add a new Crownstone device to HA."""
    entities = []

    for crownstone in crownstones:
        # adding a Crownstone is done in 2 steps
        # these parameters have to be added for initialization
        crownstone.abilities = {
            DIMMING_ABILITY: CrownstoneAbility(ABILITY),
            TAP_TO_TOGGLE_ABILITY: CrownstoneAbility(ABILITY),
            SWITCHCRAFT_ABILITY: CrownstoneAbility(ABILITY),
        }
        crownstone.data["currentSwitchState"] = {"switchState": 100}

        entities.append(
            Crownstone(crownstone, crownstone_hub.uart_manager.uart_instance)
        )

    async_add_entities(entities)


def crownstone_state_to_hass(value: float):
    """Crownstone 0..100 to hass 0..255."""
    return numpy.interp(value, [0, 100], [0, 255])


def hass_to_crownstone_state(value: float):
    """Hass 0..255 to Crownstone 0..1."""
    return numpy.interp(value, [0, 255], [0, 100])


class Crownstone(CrownstoneDevice, LightEntity):
    """
    Representation of a crownstone.

    Light platform is used to support dimming.
    """

    def __init__(self, crownstone, uart):
        """Initialize the crownstone."""
        super().__init__(crownstone)
        self.uart = uart

    @property
    def name(self) -> str:
        """Return the name of this presence holder."""
        return self.crownstone.name

    @property
    def unique_id(self) -> Optional[str]:
        """Return the unique id of this entity."""
        return f"{self.cloud_id}-{CROWNSTONE_SUFFIX}"

    @property
    def icon(self) -> Optional[str]:
        """Return the icon."""
        return "mdi:power-socket-de"

    @property
    def brightness(self) -> float:
        """Return the brightness if dimming enabled."""
        return crownstone_state_to_hass(self.crownstone.state)

    @property
    def is_on(self) -> bool:
        """Return if the device is on."""
        return crownstone_state_to_hass(self.crownstone.state) > 0

    @property
    def supported_features(self) -> int:
        """Return the supported features of this Crownstone."""
        if self.crownstone.abilities.get(DIMMING_ABILITY).is_enabled:
            return SUPPORT_BRIGHTNESS
        return 0

    @property
    def should_poll(self) -> bool:
        """Return if polling is required after switching."""
        return False

    async def async_added_to_hass(self) -> None:
        """Set up a listener when this entity is added to HA."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIG_CROWNSTONE_STATE_UPDATE, self.async_write_ha_state
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIG_CROWNSTONE_UPDATE, self.async_update_entity_and_device
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIG_UART_READY, self.async_write_ha_state
            )
        )

    @property
    def device_state_attributes(self) -> Optional[Dict[str, Any]]:
        """State attributes for Crownstone devices."""
        attributes = {}
        # switch method
        if self.uart.is_ready():
            attributes["Switch Method"] = "Crownstone USB Dongle"
        else:
            attributes["Switch Method"] = "Crownstone Cloud"

        # crownstone abilities
        attributes["Dimming"] = ABILITY_STATE.get(
            self.crownstone.abilities.get(DIMMING_ABILITY).is_enabled
        )
        attributes["Tap To Toggle"] = ABILITY_STATE.get(
            self.crownstone.abilities.get(TAP_TO_TOGGLE_ABILITY).is_enabled
        )
        attributes["Switchcraft"] = ABILITY_STATE.get(
            self.crownstone.abilities.get(SWITCHCRAFT_ABILITY).is_enabled
        )

        return attributes

    @callback
    async def async_update_entity_and_device(self, crownstone_id: str) -> None:
        """
        Update the entity and device information after data was updated.

        Entity & device name for Crownstones should be the same.
        """
        if crownstone_id == self.cloud_id:
            device_reg = await get_device_reg(self.hass)
            entity_reg = await get_entity_reg(self.hass)

            # get device
            device = device_reg.async_get_device(
                identifiers={(DOMAIN, self.cloud_id)}, connections=set()
            )
            if device is not None:
                # check if update is necessary
                if not device.name == self.name:
                    device_reg.async_update_device(
                        device.id, name=self.name, name_by_user=self.name
                    )
                if not device.sw_version == self.crownstone.sw_version:
                    device_reg.async_update_device(
                        device.id, sw_version=self.crownstone.sw_version
                    )

            # check if entity update is necessary
            if not self.registry_entry.name == self.name:
                entity_reg.async_update_entity(self.entity_id, name=self.name)

        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on this light via dongle or cloud."""
        if ATTR_BRIGHTNESS in kwargs:
            try:
                if self.uart.is_ready():
                    self.uart.dim_crownstone(
                        self.crownstone.unique_id,
                        # UART is still 0..1 until new release
                        (hass_to_crownstone_state(kwargs[ATTR_BRIGHTNESS]) / 100),
                    )
                else:
                    await self.crownstone.async_set_brightness(
                        hass_to_crownstone_state(kwargs[ATTR_BRIGHTNESS])
                    )
                # set brightness
                self.crownstone.state = hass_to_crownstone_state(
                    kwargs[ATTR_BRIGHTNESS]
                )
                self.async_write_ha_state()
            except CrownstoneAbilityError as ability_error:
                _LOGGER.error(ability_error)
        elif self.uart.is_ready():
            self.uart.switch_crownstone(self.crownstone.unique_id, on=True)
            # set state (in case the updates never comes in)
            self.crownstone.state = 100
            self.async_write_ha_state()
        else:
            await self.crownstone.async_turn_on()
            # set state (in case the updates never comes in)
            self.crownstone.state = 100
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off this device via dongle or cloud."""
        if self.uart.is_ready():
            # switch using crownstone usb dongle
            self.uart.switch_crownstone(self.crownstone.unique_id, on=False)
        else:
            # switch remotely using the cloud
            await self.crownstone.async_turn_off()

        # set state (in case the updates never comes in)
        self.crownstone.state = 0
        self.async_write_ha_state()

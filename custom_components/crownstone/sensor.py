"""Support for Crownstone sensor entities."""
from __future__ import annotations

from collections.abc import Mapping
from functools import partial
from typing import TYPE_CHECKING, Any

from crownstone_cloud.cloud_models.crownstones import Crownstone
from crownstone_cloud.cloud_models.locations import Location
from crownstone_cloud.cloud_models.spheres import Sphere
from crownstone_uart import CrownstoneUart

from homeassistant.components.sensor import (
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL_INCREASING,
    SensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_POWER,
    ENERGY_KILO_WATT_HOUR,
    POWER_WATT,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import StateType

from .const import (
    CROWNSTONE_INCLUDE_TYPES,
    DOMAIN,
    ENERGY_USAGE_NAME_SUFFIX,
    ENERGY_USAGE_SUFFIX,
    JOULE_TO_KWH,
    POWER_USAGE_NAME_SUFFIX,
    POWER_USAGE_SUFFIX,
    PRESENCE_LOCATION,
    PRESENCE_LOCATION_ICON,
    PRESENCE_SPHERE,
    PRESENCE_SPHERE_ICON,
    PRESENCE_SUFFIX,
    SIG_ADD_CROWNSTONE_DEVICES,
    SIG_ADD_PRESENCE_DEVICES,
    SIG_ENERGY_STATE_UPDATE,
    SIG_POWER_STATE_UPDATE,
    SIG_PRESENCE_STATE_UPDATE,
    SIG_SSE_STATE_CHANGE,
    SIG_UART_STATE_CHANGE,
)
from .devices import CrownstoneDevice, PresenceDevice

if TYPE_CHECKING:
    from .entry_manager import CrownstoneEntryManager


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors from a config entry."""
    manager: CrownstoneEntryManager = hass.data[DOMAIN][config_entry.entry_id]

    entities: list[Presence | PowerUsage | EnergyUsage] = []

    # Add sphere & location presence entities
    for sphere in manager.cloud.cloud_data:
        entities.append(
            Presence(
                manager,
                sphere,
                PRESENCE_SPHERE,
                PRESENCE_SPHERE_ICON,
                sphere.cloud_id,
            )
        )
        for location in sphere.locations:
            entities.append(
                Presence(
                    manager,
                    location,
                    PRESENCE_LOCATION,
                    PRESENCE_LOCATION_ICON,
                    sphere.cloud_id,
                )
            )

    # add power usage & energy usage entities
    for sphere in manager.cloud.cloud_data:
        for crownstone in sphere.crownstones:
            if crownstone.type not in CROWNSTONE_INCLUDE_TYPES:
                continue
            if sphere.cloud_id == manager.usb_sphere_id:
                entities.append(PowerUsage(crownstone, manager.uart))
                entities.append(EnergyUsage(crownstone, manager.uart))

    # add callbacks for new devices
    manager.config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            SIG_ADD_CROWNSTONE_DEVICES,
            partial(async_add_power_and_energy_entities, async_add_entities, manager),
        )
    )
    manager.config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            SIG_ADD_PRESENCE_DEVICES,
            partial(async_add_presence_location_entities, async_add_entities, manager),
        )
    )

    async_add_entities(entities)


@callback
def async_add_power_and_energy_entities(
    async_add_entities: AddEntitiesCallback,
    manager: CrownstoneEntryManager,
    crownstones: list[Crownstone],
    sphere_id: str,
) -> None:
    """Add power and energy usage entities to a new Crownstone device."""
    entities: list[PowerUsage | EnergyUsage] = []

    for crownstone in crownstones:
        if crownstone.type not in CROWNSTONE_INCLUDE_TYPES:
            continue
        if sphere_id == manager.usb_sphere_id:
            entities.append(PowerUsage(crownstone, manager.uart))
            entities.append(EnergyUsage(crownstone, manager.uart))

    async_add_entities(entities)


@callback
def async_add_presence_location_entities(
    async_add_entities: AddEntitiesCallback,
    manager: CrownstoneEntryManager,
    locations: list[Location],
    sphere_id: str,
) -> None:
    """Add presence entity to a new Location device."""
    entities: list[Presence] = []

    for location in locations:
        entities.append(
            Presence(
                manager,
                location,
                PRESENCE_LOCATION,
                PRESENCE_LOCATION_ICON,
                sphere_id,
            )
        )

    async_add_entities(entities)


class PowerUsage(CrownstoneDevice, SensorEntity):
    """
    Representation of a power usage sensor.

    The state of this sensor is updated using local push events from a Crownstone USB.
    """

    _attr_device_class = DEVICE_CLASS_POWER
    _attr_native_unit_of_measurement = POWER_WATT
    _attr_state_class = STATE_CLASS_MEASUREMENT
    _attr_should_poll = False

    def __init__(self, crownstone_data: Crownstone, usb: CrownstoneUart) -> None:
        """Initialize the power usage entity."""
        super().__init__(crownstone_data)
        self.usb = usb
        # Entity class attributes
        self._attr_name = f"{self.device.name} {POWER_USAGE_NAME_SUFFIX}"
        self._attr_unique_id = f"{self.cloud_id}-{POWER_USAGE_SUFFIX}"

    @property
    def available(self) -> bool:
        """Return if there is an active connection with a Crownstone USB."""
        return self.usb is not None and self.usb.is_ready()

    @property
    def native_value(self) -> StateType:
        """Return the current value of power usage for this device."""
        return int(self.device.power_usage)

    async def async_added_to_hass(self) -> None:
        """Set up listeners when this entity is added to HA."""
        # new state received
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIG_POWER_STATE_UPDATE, self.async_write_ha_state
            )
        )
        # updates state attributes when usb connects/disconnects
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIG_UART_STATE_CHANGE, self.async_write_ha_state
            )
        )


class EnergyUsage(CrownstoneDevice, SensorEntity, RestoreEntity):
    """
    Representation of an energy usage sensor.

    The state of this sensor is updated using local push events from a Crownstone USB.
    """

    _attr_device_class = DEVICE_CLASS_ENERGY
    _attr_native_unit_of_measurement = ENERGY_KILO_WATT_HOUR
    _attr_state_class = STATE_CLASS_TOTAL_INCREASING
    _attr_should_poll = False

    def __init__(self, crownstone_data: Crownstone, usb: CrownstoneUart) -> None:
        """Initialize the energy usage entity."""
        super().__init__(crownstone_data)
        self.usb = usb
        # Entity class attributes
        self._attr_name = f"{self.device.name} {ENERGY_USAGE_NAME_SUFFIX}"
        self._attr_unique_id = f"{self.cloud_id}-{ENERGY_USAGE_SUFFIX}"

    @property
    def available(self) -> bool:
        """Return if there is an active connection with a Crownstone USB."""
        return self.usb is not None and self.usb.is_ready()

    @property
    def native_value(self) -> StateType:
        """Return the current value of accumulated energy."""
        # calculate energy usage in kilowatt per hour
        energy_joule = self.device.energy_usage
        energy_wh: float = energy_joule / JOULE_TO_KWH

        return round(energy_wh, 2)

    async def async_added_to_hass(self) -> None:
        """Set up listeners when this entity is added to HA."""
        # Restore last state immediately otherwise the state will be 0
        # until the USB dongle sends an update which can take a minute.
        last_state = await self.async_get_last_state()
        if last_state is not None and last_state.state != STATE_UNAVAILABLE:
            self.device.energy_usage = int(float(last_state.state) * JOULE_TO_KWH)

        # new state received
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIG_ENERGY_STATE_UPDATE, self.async_write_ha_state
            )
        )
        # updates state attributes when usb connects/disconnects
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIG_UART_STATE_CHANGE, self.async_write_ha_state
            )
        )


class Presence(PresenceDevice, Entity):
    """
    Representation of an indoor presence sensor.

    The state of this updated using the Crownstone SSE client via push events.
    """

    _attr_should_poll = False

    def __init__(
        self,
        entry_manager: CrownstoneEntryManager,
        location_or_sphere_data: Location | Sphere,
        model: str,
        icon: str,
        sphere_id: str,
    ) -> None:
        """Initialize the indoor presence entity."""
        super().__init__(location_or_sphere_data, model)
        self.manager = entry_manager
        self.location_or_sphere = location_or_sphere_data
        self.sphere_id = sphere_id
        # Entity class attributes
        self._attr_name = location_or_sphere_data.name
        self._attr_icon = icon
        self._attr_unique_id = f"{self.cloud_id}-{PRESENCE_SUFFIX}"

    @property
    def available(self) -> bool:
        """Return if the connection to sse server is still open."""
        return bool(self.manager.sse.is_available)

    @property
    def state(self) -> StateType:
        """Return the state of the presence sensor."""
        present_people: list[str] = []
        # Get the first name of the people present on location
        for user_id in self.location_or_sphere.present_people:
            sphere = self.manager.cloud.cloud_data.find_by_id(self.sphere_id)
            user = sphere.users.find_by_id(user_id)
            present_people.append(user.first_name)

        return ", ".join(present_people)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return extra info for the people present on location."""
        attributes: dict[str, Any] = {}
        # Get the last name and role of the people present on location
        for user_id in self.location_or_sphere.present_people:
            sphere = self.manager.cloud.cloud_data.find_by_id(self.sphere_id)
            user = sphere.users.find_by_id(user_id)
            attributes[user.first_name] = (user.last_name, user.role)

        return attributes

    async def async_added_to_hass(self) -> None:
        """Set up listeners when this entity is added to HA."""
        # new state received
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIG_PRESENCE_STATE_UPDATE, self.async_write_ha_state
            )
        )
        # updates availability on sse state change
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIG_SSE_STATE_CHANGE, self.async_write_ha_state
            )
        )

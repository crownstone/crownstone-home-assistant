"""Support for Crownstone sensor entities."""
from __future__ import annotations

from collections.abc import Mapping
from functools import partial
from typing import TYPE_CHECKING, Any

from crownstone_cloud.cloud_models.crownstones import Crownstone
from crownstone_cloud.cloud_models.locations import Location
from crownstone_cloud.cloud_models.spheres import Sphere
from crownstone_uart import CrownstoneUart

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ENERGY_KILO_WATT_HOUR, POWER_WATT
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import (
    CONNECTION_NAME_SUFFIX,
    CONNECTION_SUFFIX,
    CONNECTIONS,
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
from .devices import CrownstoneBaseEntity, PresenceBaseEntity

if TYPE_CHECKING:
    from .entry_manager import CrownstoneEntryManager


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors from a config entry."""
    manager: CrownstoneEntryManager = hass.data[DOMAIN][config_entry.entry_id]

    entities: list[Connection | Presence | PowerUsage | EnergyUsage] = []

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
            if manager.uart and sphere.cloud_id == manager.usb_sphere_id:
                entities.append(Connection(crownstone, manager.uart))
                entities.append(PowerUsage(crownstone, manager.uart))
                entities.append(EnergyUsage(crownstone, manager.uart))
            else:
                entities.append(Connection(crownstone))

    # add callbacks for new devices
    manager.config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            SIG_ADD_CROWNSTONE_DEVICES,
            partial(async_add_conn_power_energy_entities, async_add_entities, manager),
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
def async_add_conn_power_energy_entities(
    async_add_entities: AddEntitiesCallback,
    manager: CrownstoneEntryManager,
    crownstones: list[Crownstone],
    sphere_id: str,
) -> None:
    """Add connection, power and energy usage entities to a new Crownstone device."""
    entities: list[Connection | PowerUsage | EnergyUsage] = []

    for crownstone in crownstones:
        if crownstone.type not in CROWNSTONE_INCLUDE_TYPES:
            continue
        if sphere_id == manager.usb_sphere_id:
            entities.append(Connection(crownstone, manager.uart))
            entities.append(PowerUsage(crownstone, manager.uart))
            entities.append(EnergyUsage(crownstone, manager.uart))
        else:
            entities.append(Connection(crownstone))

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


class PowerUsage(CrownstoneBaseEntity, SensorEntity):
    """
    Representation of a power usage sensor.

    The state of this sensor is updated using local push events from a Crownstone USB.
    """

    _attr_device_class = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement = POWER_WATT
    _attr_state_class = SensorStateClass.MEASUREMENT

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
        # updates availability when usb connects/disconnects
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIG_UART_STATE_CHANGE, self.async_write_ha_state
            )
        )


class EnergyUsage(CrownstoneBaseEntity, SensorEntity):
    """
    Representation of an energy usage sensor.

    The state of this sensor is updated using local push events from a Crownstone USB.
    """

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement = ENERGY_KILO_WATT_HOUR
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

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
        # new state received
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIG_ENERGY_STATE_UPDATE, self.async_write_ha_state
            )
        )
        # updates availability when usb connects/disconnects
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIG_UART_STATE_CHANGE, self.async_write_ha_state
            )
        )


class Presence(PresenceBaseEntity):
    """
    Representation of an indoor presence sensor.

    The state of this updated using the Crownstone SSE client via push events.
    """

    _attr_device_class = BinarySensorDeviceClass.PRESENCE

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


class Connection(CrownstoneBaseEntity):
    """Representation of a switch method entity."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_icon = "mdi:signal-variant"

    def __init__(
        self, crownstone_data: Crownstone, usb: CrownstoneUart | None = None
    ) -> None:
        """Initialize connection entity."""
        super().__init__(crownstone_data)
        self.usb = usb
        # Entity class attributes
        self._attr_name = f"{self.device.name} {CONNECTION_NAME_SUFFIX}"
        self._attr_unique_id = f"{self.cloud_id}-{CONNECTION_SUFFIX}"

    @property
    def state(self) -> StateType:
        """Return if the binary sensor is on."""
        return CONNECTIONS[self.usb is not None and self.usb.is_ready()]

    async def async_added_to_hass(self) -> None:
        """Set up listeners when this entity is added to HA."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIG_UART_STATE_CHANGE, self.async_write_ha_state
            )
        )

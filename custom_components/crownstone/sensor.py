"""Support for presence detection of Crownstone."""
from datetime import datetime
from functools import partial
from typing import Any, Dict, Optional

from sigfig import round

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_ENTITY_ID,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_POWER,
    ENERGY_WATT_HOUR,
    POWER_WATT,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import async_get_registry as get_device_reg
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_registry import async_get_registry as get_entity_reg
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    CONF_USER,
    CROWNSTONE_EXCLUDE,
    DOMAIN,
    ENERGY_USAGE_SUFFIX,
    EVENT_USER_ENTERED,
    EVENT_USER_LEFT,
    JOULE_TO_WH,
    LAST_UPDATE,
    MEASUREMENT_START,
    POWER_USAGE_SUFFIX,
    PRESENCE_LOCATION,
    PRESENCE_SPHERE,
    PRESENCE_SUFFIX,
    SIG_ADD_CROWNSTONE_DEVICES,
    SIG_ADD_PRESENCE_DEVICES,
    SIG_ENERGY_STATE_UPDATE,
    SIG_ENERGY_UPDATE,
    SIG_POWER_STATE_UPDATE,
    SIG_POWER_UPDATE,
    SIG_PRESENCE_STATE_UPDATE,
    SIG_PRESENCE_UPDATE,
    SIG_TRIGGER_EVENT,
    SIG_UART_READY,
)
from .devices import CrownstoneDevice, PresenceDevice
from .helpers import EnergyData


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up the sensor platform."""
    crownstone_hub = hass.data[DOMAIN][entry.entry_id]

    entities = [
        Presence(
            crownstone_hub,
            crownstone_hub.sphere,
            PRESENCE_SPHERE["description"],
            PRESENCE_SPHERE["icon"],
        )
    ]

    # add location presence entities
    for location in crownstone_hub.sphere.locations:
        entities.append(
            Presence(
                crownstone_hub,
                location,
                PRESENCE_LOCATION["description"],
                PRESENCE_LOCATION["icon"],
            )
        )

    # add power usage & energy usage entities to Crownstones
    for crownstone in crownstone_hub.sphere.crownstones:
        # some don't support power and energy usage features
        if crownstone.type not in CROWNSTONE_EXCLUDE:
            # initialize energy usage data object
            crownstone.energy_usage = EnergyData(0, None)

            entities.append(
                PowerUsage(crownstone, crownstone_hub.uart_manager.uart_instance)
            )
            entities.append(
                EnergyUsage(crownstone, crownstone_hub.uart_manager.uart_instance)
            )

    # subscribe to Crownstone add signals
    async_dispatcher_connect(
        hass,
        SIG_ADD_CROWNSTONE_DEVICES,
        partial(add_power_and_energy_entities, async_add_entities, crownstone_hub),
    )

    # subscribe to Location device add signals
    async_dispatcher_connect(
        hass,
        SIG_ADD_PRESENCE_DEVICES,
        partial(add_presence_entities, async_add_entities, crownstone_hub),
    )

    async_add_entities(entities)


@callback
async def add_power_and_energy_entities(
    async_add_entities, crownstone_hub, crownstones
):
    """Add power and energy usage entities to a new Crownstone device."""
    entities = []

    for crownstone in crownstones:
        # initialize energy usage data object
        crownstone.energy_usage = EnergyData(0, None)

        entities.append(
            PowerUsage(crownstone, crownstone_hub.uart_manager.uart_instance)
        )
        entities.append(
            EnergyUsage(crownstone, crownstone_hub.uart_manager.uart_instance)
        )

    async_add_entities(entities)


@callback
async def add_presence_entities(async_add_entities, crownstone_hub, locations):
    """Add presence entity to a new Location device."""
    entities = []

    for location in locations:
        entities.append(
            Presence(
                crownstone_hub,
                location,
                PRESENCE_LOCATION["description"],
                PRESENCE_LOCATION["icon"],
            )
        )

    async_add_entities(entities)


class PowerUsage(CrownstoneDevice, Entity):
    """
    Representation of a Power Usage Sensor.

    The state of this sensor is updated using local push events from the Crownstone USB.
    """

    def __init__(self, crownstone, uart):
        """Initialize the power usage entity."""
        super().__init__(crownstone)
        self.uart = uart

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self.crownstone.name} Power Usage"

    @property
    def unique_id(self) -> Optional[str]:
        """Return the unique id for this entity."""
        return f"{self.cloud_id}-{POWER_USAGE_SUFFIX}"

    @property
    def state(self) -> int:
        """Return the current value of the sensor."""
        return self.crownstone.power_usage

    @property
    def device_class(self) -> Optional[str]:
        """Return the class of the sensor."""
        return DEVICE_CLASS_POWER

    @property
    def unit_of_measurement(self) -> Optional[str]:
        """Return the unit of measurement of the sensor."""
        return POWER_WATT

    @property
    def icon(self) -> Optional[str]:
        """Return the icon for the sensor."""
        return "mdi:lightning-bolt"

    @property
    def available(self) -> bool:
        """Return whether the sensor is available or not."""
        return self.uart.is_ready()

    @property
    def should_poll(self) -> bool:
        """Return if new states have to be polled."""
        return False

    async def async_added_to_hass(self) -> None:
        """Set up a listener when this entity is added to HA."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIG_POWER_STATE_UPDATE, self.async_write_ha_state
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIG_POWER_UPDATE, self.async_update_entity
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIG_UART_READY, self.async_write_ha_state
            )
        )

    @callback
    async def async_update_entity(self, crownstone_id: str) -> None:
        """Update the entity information after data was updated."""
        if crownstone_id == self.cloud_id:
            entity_reg = await get_entity_reg(self.hass)

            # check if entity update is necessary
            if not self.registry_entry.name == self.name:
                entity_reg.async_update_entity(self.entity_id, name=self.name)

        self.async_write_ha_state()


class EnergyUsage(CrownstoneDevice, RestoreEntity):
    """
    Representation of an Energy Sensor.

    The state of this sensor is updated using local push events from the Crownstone USB.
    """

    def __init__(self, crownstone, uart) -> None:
        """Initialize the energy usage entity."""
        super().__init__(crownstone)
        self.uart = uart
        # flag for appearance of first energy measurement
        self.energy_start_time = None
        # flag for saving a restored state
        self.restored_energy_state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self.crownstone.name} Energy Usage"

    @property
    def unique_id(self) -> Optional[str]:
        """Return the unique id for this entity."""
        return f"{self.cloud_id}-{ENERGY_USAGE_SUFFIX}"

    @property
    def state(self) -> float:
        """Return the current value of the sensor."""
        # restore previous energy data point
        if self.restored_energy_state is not None:
            self.crownstone.energy_usage = self.restored_energy_state
            # set flag back to None once processed
            self.restored_energy_state = None

        energy_joule = self.crownstone.energy_usage.corrected_energy_usage
        energy_wh: float = energy_joule / JOULE_TO_WH

        if energy_wh == 0:
            return 0
        return round(energy_wh, decimals=1)

    @property
    def device_state_attributes(self) -> Optional[Dict[str, Any]]:
        """State attributes for Crownstone devices."""
        attributes = {}

        # flag is set by energy usage update method
        if self.crownstone.energy_usage.first_measurement:
            self.energy_start_time = datetime.now()

        # appears after first measurement
        if self.energy_start_time is not None:
            attributes[MEASUREMENT_START] = self.energy_start_time.strftime(
                "%Y-%m-%d %H:%M:%S"
            )

        # appears after first measurement or after state restore
        if self.crownstone.energy_usage.timestamp is not None:
            attributes[LAST_UPDATE] = datetime.fromtimestamp(
                self.crownstone.energy_usage.timestamp
            ).strftime("%Y-%m-%d %H:%M:%S")

        return attributes

    @property
    def device_class(self) -> Optional[str]:
        """Return the class of the sensor."""
        return DEVICE_CLASS_ENERGY

    @property
    def unit_of_measurement(self) -> Optional[str]:
        """Return the unit of measurement of the sensor."""
        return ENERGY_WATT_HOUR

    @property
    def icon(self) -> Optional[str]:
        """Return the icon for the sensor."""
        return "mdi:timer-outline"

    @property
    def available(self) -> bool:
        """Return whether the sensor is available or not."""
        return self.uart.is_ready()

    @property
    def should_poll(self) -> bool:
        """Return if new states have to be polled."""
        return False

    async def async_added_to_hass(self) -> None:
        """Set up a listeners when this entity is added to HA."""
        # get last state
        state_object = await self.async_get_last_state()

        # restore states
        if state_object is not None:
            # recreate EnergyData
            last_update_timestamp_str = state_object.attributes.get(LAST_UPDATE)
            if last_update_timestamp_str is not None:
                # timestamp in UTC
                utc_timestamp = int(
                    datetime.strptime(
                        last_update_timestamp_str, "%Y-%m-%d %H:%M:%S"
                    ).timestamp()
                )
                # set to 0, offset will make sure we count from the previous value
                self.restored_energy_state = EnergyData(0, utc_timestamp)
                self.restored_energy_state.corrected_energy_usage = int(
                    float(state_object.state) * JOULE_TO_WH
                )
                self.restored_energy_state.restored_state = True

            # restore state attributes
            measurement_timestamp_str = state_object.attributes.get(MEASUREMENT_START)
            if measurement_timestamp_str is not None:
                start_timestamp = datetime.strptime(
                    measurement_timestamp_str, "%Y-%m-%d %H:%M:%S"
                )
                self.energy_start_time = start_timestamp

        # set up listeners
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIG_ENERGY_STATE_UPDATE, self.async_write_ha_state
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIG_ENERGY_UPDATE, self.async_update_entity
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIG_UART_READY, self.async_write_ha_state
            )
        )

    @callback
    async def async_update_entity(self, crownstone_id: str) -> None:
        """Update the entity information after data was updated."""
        if crownstone_id == self.cloud_id:
            entity_reg = await get_entity_reg(self.hass)

            # check if entity update is necessary
            if not self.registry_entry.name == self.name:
                entity_reg.async_update_entity(self.entity_id, name=self.name)

        self.async_write_ha_state()


class Presence(PresenceDevice, Entity):
    """
    Representation of a Presence Sensor.

    The state of this sensor is updated using the Crownstone SSE client running in the background.
    """

    def __init__(self, hub, presence_holder, description, icon):
        """Initialize the presence detector."""
        super().__init__(presence_holder, description)
        self.hub = hub
        self.presence_holder = presence_holder
        self.description = description
        self.last_state = []
        self._icon = icon

    @property
    def name(self) -> str:
        """Return the name of this presence holder."""
        return self.presence_holder.name

    @property
    def unique_id(self) -> Optional[str]:
        """Return the unique id for this entity."""
        return f"{self.cloud_id}-{PRESENCE_SUFFIX}"

    @property
    def icon(self) -> Optional[str]:
        """Return the icon."""
        return self._icon

    @property
    def state(self) -> str:
        """
        Return a friendly state of the presence detector.

        Save the last state as list for comparison to the updated state.
        This state is a list of the first names represented as string.
        """
        presence_list = []
        self.last_state = []
        for user_id in self.presence_holder.present_people:
            user = self.hub.sphere.users.find_by_id(user_id)
            presence_list.append(user.first_name)
            self.last_state.append(user_id)

        return ", ".join(presence_list)

    @property
    def device_state_attributes(self) -> Optional[Dict[str, Any]]:
        """
        State attributes for presence sensor.

        Contains more detailed information about the state.
        Currently it displays last name and role.
        """
        attributes = {}
        for user_id in self.presence_holder.present_people:
            user = self.hub.sphere.users.find_by_id(user_id)
            attributes[user.first_name] = (user.last_name, user.role)
        return attributes

    @property
    def should_poll(self) -> bool:
        """Return if a new state has to be polled."""
        return False

    @property
    def available(self) -> bool:
        """Return if the presence sensor is available."""
        return self.hub.sse.is_available

    async def async_added_to_hass(self) -> None:
        """Set up a listener when this entity is added to HA."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIG_PRESENCE_STATE_UPDATE, self.async_write_ha_state
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIG_PRESENCE_UPDATE, self.async_update_entity_and_device
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIG_TRIGGER_EVENT, self.async_fire_trigger_event
            )
        )

    @callback
    async def async_fire_trigger_event(self, altered_user: str):
        """
        Fire event based on the state change.

        This method is called to provide the correct entity id to the event,
        to know which entity was updated.

        This method is called before the new state is written to the state machine,
        to compare the current state to the updated state.
        """
        event_data = {CONF_ENTITY_ID: self.entity_id, CONF_USER: altered_user}
        # compare the last state to the updated state.
        # this is for an extra check, rather than just taking the SSE event type.
        if len(self.presence_holder.present_people) > len(self.last_state):
            self.hass.bus.async_fire(EVENT_USER_ENTERED, event_data)
        elif len(self.presence_holder.present_people) < len(self.last_state):
            self.hass.bus.async_fire(EVENT_USER_LEFT, event_data)
        else:
            # state is unchanged, don't fire an event.
            return

    @callback
    async def async_update_entity_and_device(self, location_id: str) -> None:
        """
        Update the entity and device information after data was updated.

        Entity & device name for Locations should be the same.
        """
        if location_id == self.cloud_id:
            device_reg = await get_device_reg(self.hass)
            entity_reg = await get_entity_reg(self.hass)

            # get device
            device = device_reg.async_get_device(
                identifiers={(DOMAIN, self.cloud_id)},
                connections=set(),
            )
            if device is not None:
                # check if update is necessary
                if not device.name == f"{self.name} presence":
                    device_reg.async_update_device(
                        device.id,
                        name=f"{self.name} presence",
                        name_by_user=f"{self.name} presence",
                    )

            # check if update is necessary
            if not self.registry_entry.name == self.name:
                entity_reg.async_update_entity(self.entity_id, name=self.name)

        self.async_write_ha_state()

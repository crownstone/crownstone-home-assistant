"""Support for presence detection of Crownstone."""
from functools import partial
from typing import Any, Dict, Optional

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ENTITY_ID, DEVICE_CLASS_ENERGY, POWER_WATT
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import async_get_registry as get_device_reg
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_registry import async_get_registry as get_entity_reg
from homeassistant.util import ensure_unique_string

from .const import (
    CONF_USER,
    CROWNSTONE_EXCLUDE,
    DOMAIN,
    EVENT_USER_ENTERED,
    EVENT_USER_LEFT,
    POWER_USAGE_PREFIX,
    PRESENCE_LOCATION,
    PRESENCE_PREFIX,
    PRESENCE_SPHERE,
    SIG_ADD_CROWNSTONE_DEVICES,
    SIG_ADD_PRESENCE_DEVICES,
    SIG_POWER_STATE_UPDATE,
    SIG_POWER_UPDATE,
    SIG_PRESENCE_STATE_UPDATE,
    SIG_PRESENCE_UPDATE,
    SIG_TRIGGER_EVENT,
    SIG_UART_READY,
)
from .devices import CrownstoneDevice, PresenceDevice
from .helpers import async_get_unique_ids


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up the sensor platform."""
    crownstone_hub = hass.data[DOMAIN][entry.entry_id]

    unique_presence_ids = []
    unique_power_usage_ids = []

    # add sphere presence entity (will only ever be 1 of these)
    unique_sphere_id = ensure_unique_string(PRESENCE_PREFIX, unique_presence_ids)
    entities = [
        Presence(
            unique_sphere_id,
            crownstone_hub,
            crownstone_hub.sphere,
            PRESENCE_SPHERE["description"],
            PRESENCE_SPHERE["icon"],
        )
    ]
    unique_presence_ids.append(unique_sphere_id)

    # add location presence entities
    for location in crownstone_hub.sphere.locations:
        # create a unique ID
        unique_location_id = ensure_unique_string(PRESENCE_PREFIX, unique_presence_ids)
        unique_presence_ids.append(unique_location_id)

        entities.append(
            Presence(
                unique_location_id,
                crownstone_hub,
                location,
                PRESENCE_LOCATION["description"],
                PRESENCE_LOCATION["icon"],
            )
        )

    # add power usage entities to crownstones
    for crownstone in crownstone_hub.sphere.crownstones:
        # some don't support power usage features
        if crownstone.type not in CROWNSTONE_EXCLUDE:
            # create a unique ID
            unique_power_id = ensure_unique_string(
                POWER_USAGE_PREFIX, unique_power_usage_ids
            )
            unique_power_usage_ids.append(unique_power_id)

            entities.append(
                PowerUsage(
                    unique_power_id,
                    crownstone,
                    crownstone_hub.uart_manager.uart_instance,
                )
            )

    # subscribe to Crownstone add signals
    async_dispatcher_connect(
        hass,
        SIG_ADD_CROWNSTONE_DEVICES,
        partial(add_power_usage_entities, async_add_entities, crownstone_hub),
    )

    # subscribe to Location device add signals
    async_dispatcher_connect(
        hass,
        SIG_ADD_PRESENCE_DEVICES,
        partial(add_presence_entities, async_add_entities, crownstone_hub),
    )

    async_add_entities(entities)


@callback
async def add_power_usage_entities(async_add_entities, crownstone_hub, crownstones):
    """Add a new Crownstone devices to HA."""
    entities = []
    # get list of existing unique ids for entities in config entry
    unique_ids = await async_get_unique_ids(
        crownstone_hub.hass, crownstone_hub.config_entry
    )

    for crownstone in crownstones:
        # create a unique ID
        unique_id = ensure_unique_string(POWER_USAGE_PREFIX, unique_ids)
        unique_ids.append(unique_id)

        entities.append(
            PowerUsage(unique_id, crownstone, crownstone_hub.uart_manager.uart_instance)
        )

    async_add_entities(entities)


@callback
async def add_presence_entities(async_add_entities, crownstone_hub, locations):
    """Add a new Presence devices to HA."""
    entities = []
    # get list of existing unique ids for entities in config entry
    unique_ids = await async_get_unique_ids(
        crownstone_hub.hass, crownstone_hub.config_entry
    )

    for location in locations:
        # create a unique ID
        unique_id = ensure_unique_string(PRESENCE_PREFIX, unique_ids)
        unique_ids.append(unique_id)

        entities.append(
            Presence(
                unique_id,
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

    def __init__(self, unique_id, crownstone, uart):
        """Initialize the power usage entity."""
        super().__init__(crownstone)
        self.uart = uart
        self._unique_id = unique_id

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self.crownstone.name} Power Usage"

    @property
    def unique_id(self) -> Optional[str]:
        """Return the unique id for this entity."""
        return self._unique_id

    @property
    def state(self) -> int:
        """Return the current value of the sensor."""
        return self.crownstone.power_usage

    @property
    def device_class(self) -> Optional[str]:
        """Return the class of the sensor."""
        return DEVICE_CLASS_ENERGY

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

            # get entity
            entity = entity_reg.async_get(self.entity_id)
            if entity is not None:
                # check for update
                if not entity.name == self.name:
                    entity_reg.async_update_entity(self.entity_id, name=self.name)

        self.async_write_ha_state()


class Presence(PresenceDevice, Entity):
    """
    Representation of a Presence Sensor.

    The state of this sensor is updated using the Crownstone SSE client running in the background.
    """

    def __init__(self, unique_id, hub, presence_holder, description, icon):
        """Initialize the presence detector."""
        super().__init__(presence_holder, description)
        self.hub = hub
        self._unique_id = unique_id
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
        return self._unique_id

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
                identifiers={(DOMAIN, self.presence_holder.unique_id)},
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

            # get entity
            entity = entity_reg.async_get(self.entity_id)
            if entity is not None:
                # check if update is necessary
                if not entity.name == self.name:
                    entity_reg.async_update_entity(self.entity_id, name=self.name)

        self.async_write_ha_state()

"""Support for presence detection of Crownstone."""
import logging
from typing import Any, Dict, Optional

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ENTITY_ID
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import (
    CONF_USER,
    DOMAIN,
    EVENT_USER_ENTERED,
    EVENT_USER_LEFT,
    PRESENCE_LOCATION,
    PRESENCE_SPHERE,
    SIG_STATE_UPDATE,
    SIG_TRIGGER_EVENT,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up the sensor platform."""
    crownstone_hub = hass.data[DOMAIN][entry.entry_id]

    # add sphere presence entity
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

    async_add_entities(entities, True)


class Presence(Entity):
    """
    Representation of a Presence Sensor.

    The state for this sensor is updated using the Crownstone SSE client running in the background.
    """

    def __init__(self, hub, presence_holder, description, icon):
        """Initialize the presence detector."""
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
    def icon(self) -> Optional[str]:
        """Return the icon."""
        return self._icon

    @property
    def unique_id(self) -> str:
        """Return the unique ID."""
        return self.presence_holder.unique_id

    @property
    def cloud_id(self) -> str:
        """Return the cloud id of this presence holder."""
        return self.presence_holder.cloud_id

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

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            "name": f"{self.name} presence",
            "manufacturer": "Crownstone",
            "model": self.description,
        }

    async def async_added_to_hass(self) -> None:
        """Set up a listener when this entity is added to HA."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIG_STATE_UPDATE, self.async_write_ha_state
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

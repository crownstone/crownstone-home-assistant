"""Code to set up all communications with Crownstones."""
import asyncio
import logging
from typing import Optional

from crownstone_cloud import CrownstoneCloud
from crownstone_cloud.exceptions import (
    CrownstoneAuthenticationError,
    CrownstoneUnknownError,
)
from crownstone_cloud.lib.cloudModels.spheres import Sphere
from crownstone_sse import CrownstoneSSE
from crownstone_sse.const import (
    EVENT_ABILITY_CHANGE_DIMMING,
    EVENT_ABILITY_CHANGE_SWITCHCRAFT,
    EVENT_ABILITY_CHANGE_TAP_TO_TOGGLE,
    EVENT_PRESENCE_ENTER_LOCATION,
    EVENT_PRESENCE_ENTER_SPHERE,
    EVENT_PRESENCE_EXIT_SPHERE,
    EVENT_SYSTEM_STREAM_START,
)
from crownstone_sse.events.AbilityChangeEvent import AbilityChangeEvent
from crownstone_sse.events.PresenceEvent import PresenceEvent
from crownstone_sse.events.SystemEvent import SystemEvent

from homeassistant.config_entries import ConfigEntry, ConfigEntryNotReady
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    CONF_SPHERE,
    LIGHT_PLATFORM,
    SENSOR_PLATFORM,
    SIG_STATE_UPDATE,
    SIG_TRIGGER_EVENT,
)
from .helpers import UartManager

_LOGGER = logging.getLogger(__name__)


class CrownstoneHub:
    """Manage all Crownstone IO."""

    def __init__(self, hass, config_entry) -> None:
        """Initialize the hub."""
        self.sphere: Optional[Sphere] = None
        self.config_entry: ConfigEntry = config_entry
        self.hass: HomeAssistant = hass
        self.cloud: Optional[CrownstoneCloud] = None
        self.uart_manager: Optional[UartManager] = None
        self.sse: Optional[CrownstoneSSE] = None

    async def async_setup(self) -> bool:
        """
        Set up the Crownstone hub.

        The hub is a combination of Crownstone cloud, Crownstone SSE and Crownstone uart.
        Returns True if the setup was successful.
        """
        # Setup email and password gained from config flow
        customer_email = self.config_entry.data[CONF_EMAIL]
        customer_password = self.config_entry.data[CONF_PASSWORD]

        # Create cloud instance
        self.cloud = CrownstoneCloud(
            email=customer_email,
            password=customer_password,
            websession=aiohttp_client.async_get_clientsession(self.hass),
        )
        # Login
        try:
            await self.cloud.async_initialize()
        except CrownstoneAuthenticationError as auth_err:
            _LOGGER.error(
                "Auth error during login with type: %s and message: %s",
                auth_err.type,
                auth_err.message,
            )
            return False
        except CrownstoneUnknownError:
            _LOGGER.error("Unknown error during login")
            raise ConfigEntryNotReady

        # set the sphere we chose to setup in the flow
        self.sphere = self.cloud.spheres.find(self.config_entry.data[CONF_SPHERE])

        # Create uart manager to manage usb connections
        # uart.is_ready() returns whether the usb is ready or not.
        self.uart_manager = UartManager()
        self.uart_manager.start()

        # Create SSE instance
        self.sse = CrownstoneSSE(customer_email, customer_password)
        self.sse.set_access_token(self.cloud.get_access_token())
        self.sse.start()

        # subscribe to SSE start update
        self.sse.add_event_listener(EVENT_SYSTEM_STREAM_START, self.sse_start)

        # subscribe to user presence updates
        self.sse.add_event_listener(EVENT_PRESENCE_ENTER_SPHERE, self.update_presence)
        self.sse.add_event_listener(EVENT_PRESENCE_ENTER_LOCATION, self.update_presence)
        self.sse.add_event_listener(EVENT_PRESENCE_EXIT_SPHERE, self.update_presence)

        # subscribe to Crownstone ability updates
        self.sse.add_event_listener(EVENT_ABILITY_CHANGE_DIMMING, self.update_ability)
        self.sse.add_event_listener(
            EVENT_ABILITY_CHANGE_SWITCHCRAFT, self.update_ability
        )
        self.sse.add_event_listener(
            EVENT_ABILITY_CHANGE_TAP_TO_TOGGLE, self.update_ability
        )

        # create listener for when home assistant is stopped
        self.hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP, self.async_stop)

        # register presence entities
        self.hass.async_create_task(
            self.hass.config_entries.async_forward_entry_setup(
                self.config_entry, SENSOR_PLATFORM
            )
        )

        # register crownstone entities
        self.hass.async_create_task(
            self.hass.config_entries.async_forward_entry_setup(
                self.config_entry, LIGHT_PLATFORM
            )
        )

        return True

    async def async_reset(self) -> bool:
        """
        Reset the hub after entry removal.

        Config flow will ensure the right email and password are provided.
        If an authentication error still occurs, return.

        If the setup was successful, unload forwarded entry.
        """
        # stop services
        self.cloud.reset()
        self.uart_manager.stop()
        await self.sse.async_stop()

        # authentication failed
        if self.cloud.spheres is None:
            return True

        # unload all platform entities
        results = await asyncio.gather(
            self.hass.config_entries.async_forward_entry_unload(
                self.config_entry, SENSOR_PLATFORM
            ),
            self.hass.config_entries.async_forward_entry_unload(
                self.config_entry, LIGHT_PLATFORM
            ),
        )

        return False not in results

    @callback
    def sse_start(self, system_event: SystemEvent) -> None:
        """Notify sensor entities that the SSE client has started."""
        _LOGGER.debug(system_event.message)
        async_dispatcher_send(self.hass, SIG_STATE_UPDATE)

    @callback
    def update_presence(self, presence_event: PresenceEvent) -> None:
        """Update the presence in a location or in the sphere."""
        update_sphere = self.cloud.spheres.find_by_id(presence_event.sphere_id)
        if update_sphere.cloud_id == self.sphere.cloud_id:
            user = self.sphere.users.find_by_id(presence_event.user_id)
            altered_user = f"{user.first_name} {user.last_name}"

            if presence_event.type == EVENT_PRESENCE_ENTER_LOCATION:
                # remove the user from all locations
                # a user can only be in one location at the time, so make sure there are no duplicates.
                # we only have to listen for enter location, to see a data change.
                for location in self.sphere.locations:
                    if user.cloud_id in location.present_people:
                        location.present_people.remove(user.cloud_id)
                # add the user in the entered location
                location_entered = self.sphere.locations.find_by_id(
                    presence_event.location_id
                )
                location_entered.present_people.append(user.cloud_id)

            if presence_event.type == EVENT_PRESENCE_ENTER_SPHERE:
                # check if the user id is already in the sphere.
                if user.cloud_id in self.sphere.present_people:
                    # do nothing
                    pass
                else:
                    # add user to the present people
                    self.sphere.present_people.append(user.cloud_id)

            if presence_event.type == EVENT_PRESENCE_EXIT_SPHERE:
                # user has left the sphere.
                # remove the user from the present people.
                self.sphere.present_people.remove(user.cloud_id)

            # send signal for trigger event
            async_dispatcher_send(self.hass, SIG_TRIGGER_EVENT, altered_user)

        # send signal for state update
        async_dispatcher_send(self.hass, SIG_STATE_UPDATE)

    @callback
    def update_ability(self, ability_event: AbilityChangeEvent) -> None:
        """Update the ability information."""
        # make sure the sphere matches current.
        update_sphere = self.cloud.spheres.find_by_id(ability_event.sphere_id)
        if update_sphere.cloud_id == self.sphere.cloud_id:
            update_crownstone = self.sphere.crownstones.find_by_uid(
                ability_event.unique_id
            )
            if update_crownstone is not None:
                # write the change to the crownstone entity.
                update_crownstone.abilities[
                    ability_event.ability_type
                ].is_enabled = ability_event.ability_enabled
                # reload the config entry to process the change in supported features
                self.hass.async_create_task(
                    self.hass.config_entries.async_reload(self.config_entry.entry_id)
                )

    @callback
    async def async_stop(self, event: Event) -> None:
        """Close SSE client (thread) and uart bridge."""
        _LOGGER.debug(event.data)
        await self.sse.async_stop()
        self.uart_manager.stop()

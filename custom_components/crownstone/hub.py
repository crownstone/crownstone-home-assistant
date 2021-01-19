"""Code to set up all communications with Crownstones."""
import asyncio
import logging
from typing import Optional

from crownstone_cloud import CrownstoneCloud
from crownstone_cloud.cloud_models.spheres import Sphere
from crownstone_cloud.exceptions import (
    CrownstoneAuthenticationError,
    CrownstoneUnknownError,
)
from crownstone_sse import CrownstoneSSE

from homeassistant.config_entries import ConfigEntry, ConfigEntryNotReady
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import aiohttp_client

from .const import CONF_SPHERE, LIGHT_PLATFORM, SENSOR_PLATFORM
from .data_updater import UpdateCoordinator
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
            clientsession=aiohttp_client.async_get_clientsession(self.hass),
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
        except CrownstoneUnknownError as unknown_err:
            _LOGGER.error("Unknown error during login")
            raise ConfigEntryNotReady from unknown_err

        # set the sphere we chose to setup in the flow
        self.sphere = self.cloud.cloud_data.find(self.config_entry.data[CONF_SPHERE])

        # Create uart manager to manage usb connections
        # uart.is_ready() returns whether the usb is ready or not.
        self.uart_manager = UartManager()
        self.uart_manager.start()

        # Create SSE instance
        self.sse = CrownstoneSSE(
            customer_email, customer_password, asyncio.get_running_loop()
        )
        self.sse.set_access_token(self.cloud.access_token)
        self.sse.start()

        # Create data updater (adds all event listeners)
        UpdateCoordinator(self.hass, self.config_entry, self.sphere, self.sse)

        # create listener for when home assistant is stopped
        self.hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP, self.async_stop)

        # register crownstone entities
        self.hass.async_create_task(
            self.hass.config_entries.async_forward_entry_setup(
                self.config_entry, LIGHT_PLATFORM
            )
        )

        # register presence entities
        self.hass.async_create_task(
            self.hass.config_entries.async_forward_entry_setup(
                self.config_entry, SENSOR_PLATFORM
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
        self.uart_manager.stop()
        await self.sse.async_stop()

        # authentication failed
        if self.cloud.cloud_data is None:
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
    async def async_stop(self, event: Event) -> None:
        """Close SSE client (thread) and uart bridge."""
        _LOGGER.debug(event.data)
        await self.sse.async_stop()
        self.uart_manager.stop()

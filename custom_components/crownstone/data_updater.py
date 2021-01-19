"""
Data updater class for the Crownstone integration.

Crownstone only uses Cloud Polling to initialize the integration.
For data updates, Cloud Push is used in form of an SSE server that sends out events.
For fast device switching and power usage streaming Local Push is used in form of UART USB with Bluetooth.
"""
import logging

from crownstone_cloud.cloud_models.spheres import Sphere
from crownstone_sse import CrownstoneSSE
from crownstone_sse.const import (
    EVENT_ABILITY_CHANGE_DIMMING,
    EVENT_DATA_CHANGE_CROWNSTONE,
    EVENT_DATA_CHANGE_LOCATIONS,
    EVENT_DATA_CHANGE_USERS,
    EVENT_PRESENCE_ENTER_LOCATION,
    EVENT_PRESENCE_ENTER_SPHERE,
    EVENT_PRESENCE_EXIT_SPHERE,
    EVENT_SWITCH_STATE_UPDATE,
    EVENT_SYSTEM_STREAM_START,
    OPERATION_CREATE,
    OPERATION_DELETE,
    OPERATION_UPDATE,
    ability_change_events,
    data_change_events,
    presence_events,
)
from crownstone_sse.events.ability_change_event import AbilityChangeEvent
from crownstone_sse.events.data_change_event import DataChangeEvent
from crownstone_sse.events.presence_event import PresenceEvent
from crownstone_sse.events.switch_state_update_event import SwitchStateUpdateEvent
from crownstone_sse.events.system_event import SystemEvent
from crownstone_uart import UartEventBus, UartTopics
from crownstone_uart.topics.SystemTopics import SystemTopics

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    ADDED_ITEMS,
    REMOVED_ITEMS,
    SIG_ADD_CROWNSTONE_DEVICES,
    SIG_ADD_PRESENCE_DEVICES,
    SIG_CROWNSTONE_STATE_UPDATE,
    SIG_CROWNSTONE_UPDATE,
    SIG_ENERGY_STATE_UPDATE,
    SIG_ENERGY_UPDATE,
    SIG_POWER_STATE_UPDATE,
    SIG_POWER_UPDATE,
    SIG_PRESENCE_STATE_UPDATE,
    SIG_PRESENCE_UPDATE,
    SIG_TRIGGER_EVENT,
    SIG_UART_READY,
)
from .helpers import (
    EnergyData,
    async_remove_devices,
    check_items,
    create_utc_timestamp,
    process_energy_update,
)

_LOGGER = logging.getLogger(__name__)


class UpdateCoordinator:
    """Process Local and Cloud push events."""

    def __init__(self, hass, entry, user_data, sse):
        """Initialize the data updater class."""
        self.hass: HomeAssistant = hass
        self.entry: ConfigEntry = entry
        self.user_data: Sphere = user_data
        self.sse: CrownstoneSSE = sse

        # add SSE listeners
        self.sse.add_event_listener(EVENT_SYSTEM_STREAM_START, self.sse_start)
        self.sse.add_event_listener(
            EVENT_SWITCH_STATE_UPDATE, self.update_crwn_state_sse
        )

        for ability_event in ability_change_events:
            self.sse.add_event_listener(ability_event, self.update_ability)

        for presence_event in presence_events:
            self.sse.add_event_listener(presence_event, self.update_presence)

        for data_change_event in data_change_events:
            self.sse.add_event_listener(data_change_event, self.update_data)

        # add UART listeners
        UartEventBus.subscribe(
            SystemTopics.connectionEstablished, self.update_uart_state
        )
        UartEventBus.subscribe(SystemTopics.connectionClosed, self.update_uart_state)
        UartEventBus.subscribe(UartTopics.newDataAvailable, self.update_crwn_state_uart)
        UartEventBus.subscribe(UartTopics.newDataAvailable, self.update_power_usage)
        UartEventBus.subscribe(UartTopics.newDataAvailable, self.update_energy_usage)

    # SSE UPDATES

    def sse_start(self, system_event: SystemEvent) -> None:
        """Notify sensor entities that the SSE client has started."""
        _LOGGER.debug(system_event.message)
        # update availablility of presence entities.
        async_dispatcher_send(self.hass, SIG_PRESENCE_STATE_UPDATE)

    def update_crwn_state_sse(self, switch_state_event: SwitchStateUpdateEvent) -> None:
        """Update the state of a Crownstone when switched from the Crownstone app."""
        if switch_state_event.sphere_id == self.user_data.cloud_id:
            update_crownstone = self.user_data.crownstones.find_by_uid(
                switch_state_event.unique_id
            )
            if update_crownstone is not None:
                # only update on change.
                # HA sets the state manually when switching for more speed, only update when necessary.
                if not update_crownstone.state == switch_state_event.switch_state:
                    update_crownstone.state = switch_state_event.switch_state

                    # update the entity state
                    async_dispatcher_send(self.hass, SIG_CROWNSTONE_STATE_UPDATE)

    def update_presence(self, presence_event: PresenceEvent) -> None:
        """Update the presence in a location or in the sphere."""
        if presence_event.sphere_id == self.user_data.cloud_id:
            user = self.user_data.users.find_by_id(presence_event.user_id)
            altered_user = f"{user.first_name} {user.last_name}"

            if presence_event.type == EVENT_PRESENCE_ENTER_LOCATION:
                # remove the user from all locations
                # a user can only be in one location at the time, so make sure there are no duplicates.
                # we only have to listen for enter location, to see a data change.
                for location in self.user_data.locations:
                    if user.cloud_id in location.present_people:
                        location.present_people.remove(user.cloud_id)
                # add the user in the entered location
                location_entered = self.user_data.locations.find_by_id(
                    presence_event.location_id
                )
                location_entered.present_people.append(user.cloud_id)

            if presence_event.type == EVENT_PRESENCE_ENTER_SPHERE:
                # check if the user id is already in the sphere.
                if user.cloud_id in self.user_data.present_people:
                    # do nothing
                    pass
                else:
                    # add user to the present people
                    self.user_data.present_people.append(user.cloud_id)

            if presence_event.type == EVENT_PRESENCE_EXIT_SPHERE:
                # user has left the sphere.
                # remove the user from the present people.
                self.user_data.present_people.remove(user.cloud_id)
                # remove the user from all other locations.
                for location in self.user_data.locations:
                    if user.cloud_id in location.present_people:
                        location.present_people.remove(user.cloud_id)

            # send signal for trigger event
            async_dispatcher_send(self.hass, SIG_TRIGGER_EVENT, altered_user)
            # send signal for state update
            async_dispatcher_send(self.hass, SIG_PRESENCE_STATE_UPDATE)

    def update_ability(self, ability_event: AbilityChangeEvent) -> None:
        """
        Update the ability information.

        This update triggers an entry reload so the entity is re-created with the new data.
        This is because the change in supported features cannot be done during runtime.
        """
        # make sure the sphere matches current.
        if ability_event.sphere_id == self.user_data.cloud_id:
            update_crownstone = self.user_data.crownstones.find_by_uid(
                ability_event.unique_id
            )
            if update_crownstone is not None:
                # only update on a change in state
                if (
                    not update_crownstone.abilities[
                        ability_event.ability_type
                    ].is_enabled
                    == ability_event.ability_enabled
                ):
                    # write the change to the crownstone entity.
                    update_crownstone.abilities[
                        ability_event.ability_type
                    ].is_enabled = ability_event.ability_enabled
                    if ability_event.type == EVENT_ABILITY_CHANGE_DIMMING:
                        # reload the config entry because dimming is part of supported features
                        self.hass.async_create_task(
                            self.hass.config_entries.async_reload(self.entry.entry_id)
                        )
                    else:
                        # notify entity about change in state attributes
                        async_dispatcher_send(self.hass, SIG_CROWNSTONE_STATE_UPDATE)

    async def update_data(self, data_event: DataChangeEvent) -> None:
        """
        Update integration base data.

        This includes:
        - Names (Crownstone, location or user)
        - Firmware version update
        - Crownstone added / removed
        - Location added / removed

        The goal is to update this data without having to reload.
        """
        # for this sphere only
        if data_event.sphere_id == self.user_data.cloud_id:
            if data_event.type == EVENT_DATA_CHANGE_CROWNSTONE:
                # save old data for comparison (create copy)
                old_crownstone_data: dict = (
                    self.user_data.crownstones.crownstones.copy()
                )
                # fetch new data & update current Crownstones
                await self.user_data.crownstones.async_update_crownstone_data()

                # updated data
                if data_event.operation == OPERATION_UPDATE:
                    # update Crownstone entity & device info (name, fw update)
                    async_dispatcher_send(
                        self.hass, SIG_CROWNSTONE_UPDATE, data_event.changed_item_id
                    )
                    # update power usage entity (name)
                    async_dispatcher_send(
                        self.hass, SIG_POWER_UPDATE, data_event.changed_item_id
                    )
                    # update energy usage entity (name)
                    async_dispatcher_send(
                        self.hass, SIG_ENERGY_UPDATE, data_event.changed_item_id
                    )

                # additions or deletions
                if data_event.operation in (OPERATION_CREATE, OPERATION_DELETE):
                    items = dict(
                        check_items(
                            old_crownstone_data, self.user_data.crownstones.crownstones
                        )
                    )

                    # add or delete items, if any
                    if items[ADDED_ITEMS]:
                        async_dispatcher_send(
                            self.hass, SIG_ADD_CROWNSTONE_DEVICES, items[ADDED_ITEMS]
                        )

                    if items[REMOVED_ITEMS]:
                        await async_remove_devices(
                            self.hass, self.entry, items[REMOVED_ITEMS]
                        )

            if data_event.type == EVENT_DATA_CHANGE_LOCATIONS:
                # save old data for comparison (create copy)
                old_location_data: dict = self.user_data.locations.locations.copy()
                # fetch new data & update current presence devices
                await self.user_data.locations.async_update_location_data()
                # now fetch the presence for the locations
                await self.user_data.locations.async_update_location_presence()

                # updated data
                if data_event.operation == OPERATION_UPDATE:
                    # update entity & device info (name)
                    async_dispatcher_send(
                        self.hass, SIG_PRESENCE_UPDATE, data_event.changed_item_id
                    )

                # additions or deletions
                if data_event.operation in (OPERATION_CREATE, OPERATION_DELETE):
                    items = dict(
                        check_items(
                            old_location_data, self.user_data.locations.locations
                        )
                    )

                    # add or delete items, if any
                    if items[ADDED_ITEMS]:
                        async_dispatcher_send(
                            self.hass, SIG_ADD_PRESENCE_DEVICES, items[ADDED_ITEMS]
                        )

                    if items[REMOVED_ITEMS]:
                        await async_remove_devices(
                            self.hass, self.entry, items[REMOVED_ITEMS]
                        )

            if data_event.type == EVENT_DATA_CHANGE_USERS:
                # users have no entities, so only update data.
                await self.user_data.users.async_update_user_data()

    # UART UPDATES

    def update_uart_state(self, data=None) -> None:
        """Update the UART ready state for the power usage."""
        # update availability of power usage entities.
        async_dispatcher_send(self.hass, SIG_UART_READY)

    def update_crwn_state_uart(self, data) -> None:
        """Update the state of a Crownstone when switched from the Crownstone app."""
        update_crownstone = self.user_data.crownstones.find_by_uid(data["id"])
        if update_crownstone is not None:
            # only update on change
            # HA sets the state manually when switching for more speed, only update when necessary.
            if not update_crownstone.state == data["switchState"]:
                update_crownstone.state = (
                    100 if data["switchState"] > 100 else data["switchState"]
                )

                # update HA state
                async_dispatcher_send(self.hass, SIG_CROWNSTONE_STATE_UPDATE)

    def update_power_usage(self, data) -> None:
        """Update the power usage of a Crownstone when a Crownstone USB is available."""
        update_crownstone = self.user_data.crownstones.find_by_uid(data["id"])
        if update_crownstone is not None:
            if data["powerUsageReal"] < 0:
                update_crownstone.power_usage = 0
            else:
                update_crownstone.power_usage = int(data["powerUsageReal"])

            # update HA state
            async_dispatcher_send(self.hass, SIG_POWER_STATE_UPDATE)

    def update_energy_usage(self, data) -> None:
        """Update the energy usage of a Crownstone when a Crownstone USB is available."""
        update_crownstone = self.user_data.crownstones.find_by_uid(data["id"])
        if update_crownstone is not None:
            # create object that holds energy usage variables
            new_energy_usage = EnergyData(
                data["accumulatedEnergy"], create_utc_timestamp(data["timestamp"])
            )

            # compare new values to existing ones
            process_energy_update(new_energy_usage, update_crownstone.energy_usage)

            # set new data point
            update_crownstone.energy_usage = new_energy_usage

            # update HA state
            async_dispatcher_send(self.hass, SIG_ENERGY_STATE_UPDATE)

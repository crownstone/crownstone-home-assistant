"""
Listeners for updating data in the Crownstone integration.

For data updates, Cloud Push is used in form of an SSE server that sends out events.
For fast device switching Local Push is used in form of a USB dongle that hooks into a BLE mesh.
"""
from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING, cast

from crownstone_cloud.exceptions import CrownstoneNotFoundError
from crownstone_core.packets.serviceDataParsers.containers.AdvExternalCrownstoneState import (
    AdvExternalCrownstoneState,
)
from crownstone_core.packets.serviceDataParsers.containers.elements.AdvTypes import (
    AdvType,
)
from crownstone_core.protocol.SwitchState import SwitchState
from crownstone_sse.const import (
    EVENT_ABILITY_CHANGE,
    EVENT_ABILITY_CHANGE_DIMMING,
    EVENT_DATA_CHANGE,
    EVENT_DATA_CHANGE_CROWNSTONE,
    EVENT_DATA_CHANGE_LOCATIONS,
    EVENT_DATA_CHANGE_SPHERES,
    EVENT_DATA_CHANGE_USERS,
    EVENT_PRESENCE,
    EVENT_PRESENCE_ENTER_LOCATION,
    EVENT_PRESENCE_ENTER_SPHERE,
    EVENT_PRESENCE_EXIT_SPHERE,
    EVENT_SWITCH_STATE_UPDATE,
    EVENT_SYSTEM,
    EVENT_SYSTEM_STREAM_START,
    OPERATION_CREATE,
    OPERATION_DELETE,
    OPERATION_UPDATE,
)
from crownstone_sse.events import (
    AbilityChangeEvent,
    DataChangeEvent,
    PresenceEvent,
    SwitchStateUpdateEvent,
    SystemEvent,
)
from crownstone_uart import UartEventBus, UartTopics
from crownstone_uart.topics.SystemTopics import SystemTopics

from homeassistant.core import Event, callback
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
    dispatcher_send,
)

from .const import (
    DOMAIN,
    SIG_ADD_CROWNSTONE_DEVICES,
    SIG_ADD_PRESENCE_DEVICES,
    SIG_CROWNSTONE_STATE_UPDATE,
    SIG_ENERGY_STATE_UPDATE,
    SIG_POWER_STATE_UPDATE,
    SIG_PRESENCE_STATE_UPDATE,
    SIG_SSE_STATE_CHANGE,
    SIG_UART_STATE_CHANGE,
    SSE_LISTENERS,
    UART_LISTENERS,
)
from .helpers import (
    async_remove_devices,
    async_update_devices,
    get_added_items,
    get_removed_items,
)

if TYPE_CHECKING:
    from .entry_manager import CrownstoneEntryManager


@callback
def async_update_sse_state(
    manager: CrownstoneEntryManager, system_event: SystemEvent
) -> None:
    """Update the state of the SSE client for entities that use it."""
    if system_event.sub_type == EVENT_SYSTEM_STREAM_START:
        async_dispatcher_send(manager.hass, SIG_SSE_STATE_CHANGE)


@callback
def async_update_crwn_state_sse(
    manager: CrownstoneEntryManager, switch_event: SwitchStateUpdateEvent
) -> None:
    """Update the state of a Crownstone when switched externally."""
    try:
        updated_crownstone = manager.cloud.get_crownstone_by_id(switch_event.cloud_id)
    except CrownstoneNotFoundError:
        return

    # only update on change.
    if updated_crownstone.state != switch_event.switch_state:
        updated_crownstone.state = switch_event.switch_state
        async_dispatcher_send(manager.hass, SIG_CROWNSTONE_STATE_UPDATE)


@callback
def async_update_crwn_ability(
    manager: CrownstoneEntryManager, ability_event: AbilityChangeEvent
) -> None:
    """Update the ability information of a Crownstone."""
    try:
        updated_crownstone = manager.cloud.get_crownstone_by_id(ability_event.cloud_id)
    except CrownstoneNotFoundError:
        return

    ability_type = ability_event.ability_type
    ability_enabled = ability_event.ability_enabled
    # only update on a change in state
    if updated_crownstone.abilities[ability_type].is_enabled == ability_enabled:
        return

    # write the change to the crownstone entity.
    updated_crownstone.abilities[ability_type].is_enabled = ability_enabled

    if ability_event.sub_type == EVENT_ABILITY_CHANGE_DIMMING:
        # reload the config entry because dimming is part of supported features
        manager.hass.async_create_task(
            manager.hass.config_entries.async_reload(manager.config_entry.entry_id)
        )
    else:
        async_dispatcher_send(manager.hass, SIG_CROWNSTONE_STATE_UPDATE)


@callback
def async_update_presence(manager: CrownstoneEntryManager, ha_event: Event) -> None:
    """Update the presence in a Location or in a Sphere."""
    presence_event = PresenceEvent(ha_event.data)

    sphere = manager.cloud.cloud_data.find_by_id(presence_event.sphere_id)
    if sphere is None:
        return

    user = sphere.users.find_by_id(presence_event.user_id)
    if user is None:
        return

    if presence_event.sub_type == EVENT_PRESENCE_ENTER_LOCATION:
        # remove the user from all locations, we only listen for enter events
        for location in sphere.locations:
            if user.cloud_id in location.present_people:
                location.present_people.remove(user.cloud_id)

        location_entered = sphere.locations.find_by_id(presence_event.location_id)
        if location_entered is None:
            return
        location_entered.present_people.append(user.cloud_id)
    elif presence_event.sub_type == EVENT_PRESENCE_ENTER_SPHERE:
        if user.cloud_id in sphere.present_people:
            pass
        else:
            sphere.present_people.append(user.cloud_id)
    elif presence_event.sub_type == EVENT_PRESENCE_EXIT_SPHERE:
        if user.cloud_id in sphere.present_people:
            sphere.present_people.remove(user.cloud_id)
        # remove the user from all other locations, if still present
        for location in sphere.locations:
            if user.cloud_id in location.present_people:
                location.present_people.remove(user.cloud_id)
    else:
        return

    async_dispatcher_send(manager.hass, SIG_PRESENCE_STATE_UPDATE)


async def async_update_data(
    manager: CrownstoneEntryManager, data_change_event: DataChangeEvent
) -> None:
    """Update user data and remove or add new devices when detected."""
    sphere = manager.cloud.cloud_data.find_by_id(data_change_event.sphere_id)
    if sphere is None:
        return

    if data_change_event.sub_type == EVENT_DATA_CHANGE_CROWNSTONE:
        old_data = sphere.crownstones.data.copy()
        await sphere.crownstones.async_update_crownstone_data()

        if data_change_event.operation == OPERATION_UPDATE:
            async_update_devices(manager.hass, sphere.crownstones.data)
        if data_change_event.operation == OPERATION_CREATE:
            async_dispatcher_send(
                manager.hass,
                SIG_ADD_CROWNSTONE_DEVICES,
                get_added_items(old_data, sphere.crownstones.data),
                sphere.cloud_id,
            )
        if data_change_event.operation == OPERATION_DELETE:
            async_remove_devices(
                manager.hass,
                manager.config_entry.entry_id,
                get_removed_items(old_data, sphere.crownstones.data),
            )

    if data_change_event.sub_type == EVENT_DATA_CHANGE_LOCATIONS:
        old_data = sphere.locations.data.copy()
        await sphere.locations.async_update_location_data()

        if data_change_event.operation == OPERATION_UPDATE:
            async_update_devices(manager.hass, sphere.locations.data)
        if data_change_event.operation == OPERATION_CREATE:
            async_dispatcher_send(
                manager.hass,
                SIG_ADD_PRESENCE_DEVICES,
                get_added_items(old_data, sphere.locations.data),
                sphere.cloud_id,
            )
        if data_change_event.operation == OPERATION_DELETE:
            async_remove_devices(
                manager.hass,
                manager.config_entry.entry_id,
                get_removed_items(old_data, sphere.locations.data),
            )

    if data_change_event.sub_type == EVENT_DATA_CHANGE_USERS:
        await sphere.users.async_update_user_data()

    if data_change_event.sub_type == EVENT_DATA_CHANGE_SPHERES:
        # spheres can include an entire new stack of devices
        manager.hass.async_create_task(
            manager.hass.config_entries.async_reload(manager.config_entry.entry_id)
        )


def update_uart_state(manager: CrownstoneEntryManager, _: bool | None) -> None:
    """Update the uart ready state for entities that use USB."""
    # update availability of power usage entities.
    dispatcher_send(manager.hass, SIG_UART_STATE_CHANGE)


def update_crwn_state_uart(
    manager: CrownstoneEntryManager, data: AdvExternalCrownstoneState
) -> None:
    """Update the state of a Crownstone when switched externally."""
    if data.type != AdvType.EXTERNAL_STATE:
        return
    try:
        updated_crownstone = manager.cloud.get_crownstone_by_uid(
            data.crownstoneId, manager.usb_sphere_id
        )
    except CrownstoneNotFoundError:
        return

    if data.switchState is None:
        return
    # update on change
    updated_state = cast(SwitchState, data.switchState)
    if updated_crownstone.state != updated_state.intensity:
        updated_crownstone.state = updated_state.intensity

        dispatcher_send(manager.hass, SIG_CROWNSTONE_STATE_UPDATE)


def update_power_usage(
    manager: CrownstoneEntryManager, data: AdvExternalCrownstoneState
) -> None:
    """Update the power usage of a Crownstone."""
    if data.type != AdvType.EXTERNAL_STATE:
        return
    try:
        updated_crownstone = manager.cloud.get_crownstone_by_uid(
            data.crownstoneId, manager.usb_sphere_id
        )
    except CrownstoneNotFoundError:
        return

    if int(data.powerUsageReal) < 0:
        updated_crownstone.power_usage = 0
    else:
        updated_crownstone.power_usage = int(data.powerUsageReal)

    dispatcher_send(manager.hass, SIG_POWER_STATE_UPDATE)


def update_energy_usage(
    manager: CrownstoneEntryManager, data: AdvExternalCrownstoneState
) -> None:
    """Update the energy usage of a Crownstone."""
    if data.type != AdvType.EXTERNAL_STATE:
        return
    try:
        updated_crownstone = manager.cloud.get_crownstone_by_uid(
            data.crownstoneId, manager.usb_sphere_id
        )
    except CrownstoneNotFoundError:
        return

    updated_crownstone.energy_usage = int(data.accumulatedEnergy)

    dispatcher_send(manager.hass, SIG_ENERGY_STATE_UPDATE)


def setup_sse_listeners(manager: CrownstoneEntryManager) -> None:
    """Set up SSE listeners."""
    # save unsub function for when entry removed
    manager.listeners[SSE_LISTENERS] = [
        async_dispatcher_connect(
            manager.hass,
            f"{DOMAIN}_{EVENT_SYSTEM}",
            partial(async_update_sse_state, manager),
        ),
        async_dispatcher_connect(
            manager.hass,
            f"{DOMAIN}_{EVENT_SWITCH_STATE_UPDATE}",
            partial(async_update_crwn_state_sse, manager),
        ),
        async_dispatcher_connect(
            manager.hass,
            f"{DOMAIN}_{EVENT_ABILITY_CHANGE}",
            partial(async_update_crwn_ability, manager),
        ),
        async_dispatcher_connect(
            manager.hass,
            f"{DOMAIN}_{EVENT_DATA_CHANGE}",
            partial(async_update_data, manager),
        ),
        manager.hass.bus.async_listen(
            f"{DOMAIN}_{EVENT_PRESENCE}",
            partial(async_update_presence, manager),
        ),
    ]


def setup_uart_listeners(manager: CrownstoneEntryManager) -> None:
    """Set up UART listeners."""
    # save subscription id to unsub
    manager.listeners[UART_LISTENERS] = [
        UartEventBus.subscribe(
            SystemTopics.connectionEstablished,
            partial(update_uart_state, manager),
        ),
        UartEventBus.subscribe(
            SystemTopics.connectionClosed,
            partial(update_uart_state, manager),
        ),
        UartEventBus.subscribe(
            UartTopics.newDataAvailable,
            partial(update_crwn_state_uart, manager),
        ),
        UartEventBus.subscribe(
            UartTopics.newDataAvailable,
            partial(update_power_usage, manager),
        ),
        UartEventBus.subscribe(
            UartTopics.newDataAvailable,
            partial(update_energy_usage, manager),
        ),
    ]

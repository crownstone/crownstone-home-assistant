"""Provides device automation for Crownstone presence sensors."""
from typing import List

import voluptuous as vol

from homeassistant.components.automation import AutomationActionType
from homeassistant.components.crownstone.const import (
    ALL_USERS_ENTERED,
    ALL_USERS_LEFT,
    CONF_USER,
    CONF_USERS,
    DOMAIN,
    EVENT_USER_ENTERED,
    EVENT_USER_LEFT,
    MULTIPLE_USERS_ENTERED,
    MULTIPLE_USERS_LEFT,
    SENSOR_PLATFORM,
    USER_ENTERED,
    USER_LEFT,
)
from homeassistant.components.crownstone.helpers import set_to_dict
from homeassistant.components.device_automation import TRIGGER_BASE_SCHEMA
from homeassistant.components.device_automation.exceptions import (
    InvalidDeviceAutomationConfig,
)
from homeassistant.components.homeassistant.triggers import event as event_trigger
from homeassistant.const import (
    CONF_DEVICE,
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_ENTITY_ID,
    CONF_EVENT,
    CONF_PLATFORM,
    CONF_TYPE,
)
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, entity_registry
from homeassistant.helpers.typing import ConfigType

TRIGGER_TYPES = {
    USER_ENTERED,
    USER_LEFT,
    MULTIPLE_USERS_ENTERED,
    MULTIPLE_USERS_LEFT,
    ALL_USERS_ENTERED,
    ALL_USERS_LEFT,
}

TRIGGER_SCHEMA = TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Required(CONF_TYPE): vol.In(TRIGGER_TYPES),
    },
    extra=vol.ALLOW_EXTRA,
)


async def get_crownstone_users(hass: HomeAssistant, entity_id: str) -> set:
    """Fetch the users for the Crownstone config entry."""
    registry = await entity_registry.async_get_registry(hass)
    entity = registry.async_get(entity_id)

    crownstone_users = set()
    crownstone_hub = hass.data[DOMAIN][entity.config_entry_id]
    for user in crownstone_hub.sphere.users:
        crownstone_users.add(f"{user.first_name} {user.last_name}")

    return crownstone_users


async def async_validate_trigger_config(
    hass: HomeAssistant, config: ConfigType
) -> ConfigType:
    """Validate config."""
    # no entry data available yet, run this coroutine again after the rest of the tasks are completed
    if hass.data[DOMAIN] == {}:
        await hass.async_create_task(async_validate_trigger_config(hass, config))

    config = TRIGGER_SCHEMA(config)

    # get set of crownstone users
    crownstone_users = await get_crownstone_users(hass, config[CONF_ENTITY_ID])

    if config[CONF_TYPE] in (USER_ENTERED, USER_LEFT):
        user = config[CONF_USER]
        if not user or user not in crownstone_users:
            raise InvalidDeviceAutomationConfig
    elif config[CONF_TYPE] in (MULTIPLE_USERS_ENTERED, MULTIPLE_USERS_LEFT):
        users = set(config[CONF_USERS])
        if not users or not users.issubset(crownstone_users):
            raise InvalidDeviceAutomationConfig

    return config


async def async_get_triggers(hass: HomeAssistant, device_id: str) -> List[dict]:
    """List device triggers for Crownstone devices."""
    registry = await entity_registry.async_get_registry(hass)
    triggers = []

    # Get all the integrations entities for all sensor devices from Crownstone and add triggers
    for entry in entity_registry.async_entries_for_device(registry, device_id):
        if entry.domain == SENSOR_PLATFORM:

            for trigger in TRIGGER_TYPES:
                triggers.append(
                    {
                        CONF_PLATFORM: CONF_DEVICE,
                        CONF_DEVICE_ID: device_id,
                        CONF_DOMAIN: DOMAIN,
                        CONF_ENTITY_ID: entry.entity_id,
                        CONF_TYPE: trigger,
                    }
                )

    return triggers


async def async_get_trigger_capabilities(hass: HomeAssistant, config: dict) -> dict:
    """List trigger capabilities based on trigger type."""
    crownstone_users = await get_crownstone_users(hass, config[CONF_ENTITY_ID])

    if config[CONF_TYPE] in (USER_ENTERED, USER_LEFT):
        return {
            "extra_fields": vol.Schema(
                {vol.Required(CONF_USER): vol.In(crownstone_users)}
            )
        }
    if config[CONF_TYPE] in (MULTIPLE_USERS_ENTERED, MULTIPLE_USERS_LEFT):
        return {
            "extra_fields": vol.Schema(
                {
                    vol.Required(CONF_USERS): cv.multi_select(
                        set_to_dict(crownstone_users)
                    )
                }
            )
        }
    return {}


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: AutomationActionType,
    automation_info: dict,
) -> CALLBACK_TYPE:
    """Attach a trigger."""
    config = TRIGGER_SCHEMA(config)
    crownstone_users = await get_crownstone_users(hass, config[CONF_ENTITY_ID])

    if config[CONF_TYPE] in (USER_ENTERED, USER_LEFT):
        # match the entity_id of the entity which fired a state change
        # match the username of the person entered or left
        event_type = None
        if config[CONF_TYPE] == USER_ENTERED:
            event_type = EVENT_USER_ENTERED
        elif config[CONF_TYPE] == USER_LEFT:
            event_type = EVENT_USER_LEFT

        event_config = {
            event_trigger.CONF_PLATFORM: CONF_EVENT,
            event_trigger.CONF_EVENT_TYPE: event_type,
            event_trigger.CONF_EVENT_DATA: {
                CONF_ENTITY_ID: config[CONF_ENTITY_ID],
                CONF_USER: config[CONF_USER],
            },
        }

        event_config = event_trigger.TRIGGER_SCHEMA(event_config)
        return await event_trigger.async_attach_trigger(
            hass, event_config, action, automation_info, platform_type=CONF_DEVICE
        )
    elif config[CONF_TYPE] in (
        MULTIPLE_USERS_ENTERED,
        MULTIPLE_USERS_LEFT,
        ALL_USERS_ENTERED,
        ALL_USERS_LEFT,
    ):
        # match the entity_id of the entity which fired a state change
        # cache incoming events based on the amount of users in config
        # the action will be executed when there is an event received for all user names.
        event_registry = []

        # create a registry with the events that need to be matched
        def fill_registry(users: list):
            """Fill the event registry with users."""
            for user in users:
                event_registry.append(
                    {CONF_ENTITY_ID: config[CONF_ENTITY_ID], CONF_USER: user}
                )

        if config[CONF_TYPE] in (MULTIPLE_USERS_ENTERED, MULTIPLE_USERS_LEFT):
            fill_registry(config[CONF_USERS])
        if config[CONF_TYPE] in (ALL_USERS_ENTERED, ALL_USERS_LEFT):
            fill_registry(list(crownstone_users))

        @callback
        def handle_presence_events(event: Event):
            if event.data in event_registry:
                # event received that's in the registry, remove it from the list
                event_registry.remove(event.data)

            # all events for the users have been received, execute the action
            if not event_registry:
                hass.async_run_job(
                    action,
                    {"trigger": {"platform": CONF_DEVICE, "event": event}},
                    event.context,
                )
                # restore the registry
                if config[CONF_TYPE] in (MULTIPLE_USERS_ENTERED, MULTIPLE_USERS_LEFT):
                    fill_registry(config[CONF_USERS])
                if config[CONF_TYPE] in (ALL_USERS_ENTERED, ALL_USERS_LEFT):
                    fill_registry(list(crownstone_users))

        # listen for either entered or left events
        if config[CONF_TYPE] in (MULTIPLE_USERS_ENTERED, ALL_USERS_ENTERED):
            return hass.bus.async_listen(EVENT_USER_ENTERED, handle_presence_events)
        elif config[CONF_TYPE] in (MULTIPLE_USERS_LEFT, ALL_USERS_LEFT):
            return hass.bus.async_listen(EVENT_USER_LEFT, handle_presence_events)

"""Provides device automation for Crownstone presence sensors."""
from typing import List

import voluptuous as vol

from homeassistant.components.automation import AutomationActionType
from homeassistant.components.device_automation import TRIGGER_BASE_SCHEMA
from homeassistant.components.device_automation.exceptions import (
    InvalidDeviceAutomationConfig,
)
from homeassistant.const import (
    CONF_DEVICE,
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_ENTITY_ID,
    CONF_PLATFORM,
    CONF_TYPE,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_POWER,
)
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, entity_registry
from homeassistant.helpers.typing import ConfigType

from .const import (
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
from .helpers import set_to_dict

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
    config = TRIGGER_SCHEMA(config)

    user_schema = vol.Schema(
        {vol.Required(CONF_USER): cv.string}, extra=vol.ALLOW_EXTRA
    )
    users_schema = vol.Schema(
        {vol.Required(CONF_USERS): cv.ensure_list}, extra=vol.ALLOW_EXTRA
    )

    if config[CONF_TYPE] in (USER_ENTERED, USER_LEFT):
        try:
            user_schema(config)
        except vol.Invalid:
            raise InvalidDeviceAutomationConfig(
                "User name not provided, or user name not of type string."
            )
    elif config[CONF_TYPE] in (MULTIPLE_USERS_ENTERED, MULTIPLE_USERS_LEFT):
        try:
            users_schema(config)
        except vol.Invalid:
            raise InvalidDeviceAutomationConfig(
                "User names not provided, or user names not of type list."
            )

    return config


async def async_get_triggers(hass: HomeAssistant, device_id: str) -> List[dict]:
    """List device triggers for Crownstone devices."""
    registry = await entity_registry.async_get_registry(hass)
    triggers = []

    # loop through all entities for device
    for entry in entity_registry.async_entries_for_device(registry, device_id):
        # make sure to only add custom triggers to presence sensor entities
        if (
            entry.domain != SENSOR_PLATFORM
            or entry.device_class == DEVICE_CLASS_ENERGY
            or entry.device_class == DEVICE_CLASS_POWER
        ):
            continue

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
        # Check if the username exists in the Crownstone data
        if config[CONF_USER] not in crownstone_users:
            raise InvalidDeviceAutomationConfig(
                f"Invalid username '{config[CONF_USER]}'. Make sure you are using the full name, case sensitive."
            )

        # match the entity_id of the entity which fired a state change
        # match the username of the person entered or left
        event_data = {
            CONF_ENTITY_ID: config[CONF_ENTITY_ID],
            CONF_USER: config[CONF_USER],
        }

        @callback
        def handle_presence_event(event: Event):
            """Listen for events and call action when the required event is received."""
            if event.data == event_data:
                hass.async_run_job(
                    action,
                    {
                        "trigger": {
                            "platform": CONF_DEVICE,
                            "event": event,
                            "description": f"event '{event.event_type}'",
                        }
                    },
                    event.context,
                )

        # listen for either left or enter event
        if config[CONF_TYPE] == USER_ENTERED:
            return hass.bus.async_listen(EVENT_USER_ENTERED, handle_presence_event)
        elif config[CONF_TYPE] == USER_LEFT:
            return hass.bus.async_listen(EVENT_USER_LEFT, handle_presence_event)

    elif config[CONF_TYPE] in (
        MULTIPLE_USERS_ENTERED,
        MULTIPLE_USERS_LEFT,
        ALL_USERS_ENTERED,
        ALL_USERS_LEFT,
    ):
        # check if the usernames exist in the Crownstone data
        if config[CONF_TYPE] in (MULTIPLE_USERS_ENTERED, MULTIPLE_USERS_LEFT):
            config_users = set(config[CONF_USERS])
            if not config_users.issubset(crownstone_users):
                raise InvalidDeviceAutomationConfig(
                    f"Invalid user names in '{config_users}'. Makes sure you are using the full names, case sensitive."
                )

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
            """Listen for events and calls action when all required events are received."""
            if event.data in event_registry:
                # event received that's in the registry, remove it from the list
                event_registry.remove(event.data)

            # all events for the users have been received, execute the action
            if not event_registry:
                hass.async_run_job(
                    action,
                    {
                        "trigger": {
                            "platform": CONF_DEVICE,
                            "event": event,
                            "description": f"event '{event.event_type}'",
                        }
                    },
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

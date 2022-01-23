"""Provide device triggers for Crownstone presence sensors."""
from __future__ import annotations

from typing import Any, Final

from crownstone_sse.const import (
    EVENT_PRESENCE,
    EVENT_PRESENCE_ENTER_LOCATION,
    EVENT_PRESENCE_ENTER_SPHERE,
    EVENT_PRESENCE_EXIT_LOCATION,
    EVENT_PRESENCE_EXIT_SPHERE,
)
import voluptuous as vol

from homeassistant.components.automation import (
    AutomationActionType,
    AutomationTriggerInfo,
)
from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.components.device_automation.exceptions import (
    InvalidDeviceAutomationConfig,
)
from homeassistant.components.homeassistant.triggers.event import (
    CONF_EVENT_TYPE,
    TRIGGER_SCHEMA as EVENT_TRIGGER_SCHEMA,
    async_attach_trigger as async_attach_event_trigger,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import (
    CONF_DEVICE,
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_ENTITY_ID,
    CONF_EVENT_DATA,
    CONF_ID,
    CONF_NAME,
    CONF_PLATFORM,
    CONF_TYPE,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    config_validation as cv,
    device_registry,
    entity_registry,
)
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_ANY_USER_ENTERED,
    CONF_ANY_USER_LEFT,
    CONF_LOCATION,
    CONF_SPHERE,
    CONF_SUBTYPE,
    CONF_USER,
    CONF_USER_ENTERED,
    CONF_USER_LEFT,
    CONF_USERS,
    DOMAIN,
    PRESENCE_LOCATION,
    PRESENCE_SPHERE,
    PRESENCE_SUFFIX,
)
from .entry_manager import CrownstoneEntryManager

SUPPORTED_DEVICES: Final[set[str]] = {PRESENCE_LOCATION, PRESENCE_SPHERE}

EVENT_SUBTYPES: Final[dict[str, dict[str, str]]] = {
    CONF_SPHERE: {
        CONF_USER_ENTERED: EVENT_PRESENCE_ENTER_SPHERE,
        CONF_ANY_USER_ENTERED: EVENT_PRESENCE_ENTER_SPHERE,
        CONF_USER_LEFT: EVENT_PRESENCE_EXIT_SPHERE,
        CONF_ANY_USER_LEFT: EVENT_PRESENCE_EXIT_SPHERE,
    },
    CONF_LOCATION: {
        CONF_USER_ENTERED: EVENT_PRESENCE_ENTER_LOCATION,
        CONF_ANY_USER_ENTERED: EVENT_PRESENCE_ENTER_LOCATION,
        CONF_USER_LEFT: EVENT_PRESENCE_EXIT_LOCATION,
        CONF_ANY_USER_LEFT: EVENT_PRESENCE_EXIT_LOCATION,
    },
}

TRIGGER_TYPES: Final[set[str]] = {
    CONF_USER_ENTERED,
    CONF_USER_LEFT,
    CONF_ANY_USER_ENTERED,
    CONF_ANY_USER_LEFT,
}

TRIGGER_SCHEMA: Final = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Required(CONF_TYPE): vol.In(TRIGGER_TYPES),
    },
    extra=vol.ALLOW_EXTRA,
)


@callback
def _async_get_trigger_data(
    hass: HomeAssistant, entity_id: str
) -> dict[str, Any] | None:
    """Get the Crownstone users and information about the selected device."""
    event_data: dict[str, Any] = {}

    registry = entity_registry.async_get(hass)
    entity = registry.async_get(entity_id)
    if entity is None:
        return None

    crownstone_device_id = entity.unique_id[: -(len(PRESENCE_SUFFIX) + 1)]
    manager: CrownstoneEntryManager = hass.data[DOMAIN][entity.config_entry_id]

    event_data[CONF_ID] = crownstone_device_id
    # selected device can be sphere or location
    for sphere in manager.cloud.cloud_data:
        if (
            sphere.cloud_id == crownstone_device_id
            or crownstone_device_id in sphere.locations.data
        ):
            event_data[CONF_SPHERE] = sphere.cloud_id
            event_data[CONF_USERS] = {
                f"{user.first_name} {user.last_name}" for user in sphere.users
            }

        # specific device type
        if sphere.cloud_id == crownstone_device_id:
            event_data[CONF_DEVICE] = CONF_SPHERE
        elif crownstone_device_id in sphere.locations.data:
            event_data[CONF_DEVICE] = CONF_LOCATION
        else:
            continue

    return event_data


async def async_validate_trigger_config(
    hass: HomeAssistant, config: ConfigType
) -> ConfigType:
    """Validate config."""
    validated_config: ConfigType = TRIGGER_SCHEMA(config)

    if config[CONF_TYPE] in (CONF_USER_ENTERED, CONF_USER_LEFT):
        user_schema = TRIGGER_SCHEMA.extend(
            {vol.Required(CONF_USER): cv.string},
        )
        validated_config = user_schema(config)

    registry = device_registry.async_get(hass)
    device = registry.async_get(validated_config[CONF_DEVICE_ID])

    if device is None:
        raise InvalidDeviceAutomationConfig(
            f"Device with ID {validated_config[CONF_DEVICE_ID]} not found."
        )

    if device.model not in SUPPORTED_DEVICES:
        raise InvalidDeviceAutomationConfig(
            f"Crownstone device triggers are not available for device "
            f"{device.name} ({validated_config[CONF_DEVICE_ID]}). "
            f"Select a Crownstone presence device to use device triggers."
        )

    return validated_config


async def async_get_triggers(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, str]]:
    """List device triggers for Crownstone presence devices."""
    registry = entity_registry.async_get(hass)
    triggers: list[dict[str, str]] = []

    for entry in entity_registry.async_entries_for_device(registry, device_id):
        # only support presence sensors
        if (
            entry.domain != SENSOR_DOMAIN
            or entry.original_device_class != BinarySensorDeviceClass.PRESENCE
        ):
            continue

        base_trigger = {
            CONF_PLATFORM: CONF_DEVICE,
            CONF_DEVICE_ID: device_id,
            CONF_DOMAIN: DOMAIN,
            CONF_ENTITY_ID: entry.entity_id,
        }

        triggers += [{**base_trigger, CONF_TYPE: trigger} for trigger in TRIGGER_TYPES]

    return triggers


async def async_get_trigger_capabilities(
    hass: HomeAssistant, config: ConfigType
) -> dict[str, vol.Schema]:
    """List trigger capabilities for specific trigger types."""
    trigger_data = _async_get_trigger_data(hass, config[CONF_ENTITY_ID])
    if trigger_data is None:
        raise HomeAssistantError(
            f"Could not get trigger data for entity {config[CONF_ENTITY_ID]}"
        )

    if config[CONF_TYPE] in (CONF_USER_ENTERED, CONF_USER_LEFT):
        return {
            "extra_fields": vol.Schema(
                {vol.Required(CONF_USER): vol.In(trigger_data[CONF_USERS])}
            )
        }

    return {}


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: AutomationActionType,
    automation_info: AutomationTriggerInfo,
) -> CALLBACK_TYPE:
    """Attach triggers to Crownstone presence events."""
    trigger_data = _async_get_trigger_data(hass, config[CONF_ENTITY_ID])
    if trigger_data is None:
        raise HomeAssistantError(
            f"Could not get trigger data for entity {config[CONF_ENTITY_ID]}"
        )

    presence_event: dict[str, Any] = {
        CONF_TYPE: EVENT_PRESENCE,
        CONF_SUBTYPE: EVENT_SUBTYPES[trigger_data[CONF_DEVICE]][config[CONF_TYPE]],
        CONF_SPHERE: {CONF_ID: trigger_data[CONF_SPHERE]},
    }

    if config[CONF_TYPE] in (CONF_USER_ENTERED, CONF_USER_LEFT):
        if config[CONF_USER] not in trigger_data[CONF_USERS]:
            raise InvalidDeviceAutomationConfig(
                f"Invalid username '{config[CONF_USER]}'. "
                f"Make sure you are using the full name, case sensitive."
            )

        presence_event[CONF_USER] = {CONF_NAME: config[CONF_USER]}

    # this data is only necessary for a location device
    if trigger_data[CONF_DEVICE] == CONF_LOCATION:
        presence_event[CONF_LOCATION] = {CONF_ID: trigger_data[CONF_ID]}

    event_config = {
        CONF_PLATFORM: "event",
        CONF_EVENT_TYPE: f"{DOMAIN}_{EVENT_PRESENCE}",
        CONF_EVENT_DATA: presence_event,
    }
    event_config = EVENT_TRIGGER_SCHEMA(event_config)

    return await async_attach_event_trigger(
        hass, event_config, action, automation_info, platform_type=CONF_DEVICE
    )

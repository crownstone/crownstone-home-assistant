"""Provide device conditions for Crownstone presence sensors."""
from __future__ import annotations

from typing import Final

import voluptuous as vol
from voluptuous.validators import Any

from homeassistant.components.device_automation.exceptions import (
    InvalidDeviceAutomationConfig,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import (
    CONF_CONDITION,
    CONF_DEVICE,
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_ENTITY_ID,
    CONF_TYPE,
)
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    condition,
    config_validation as cv,
    device_registry,
    entity_registry,
)
from homeassistant.helpers.config_validation import DEVICE_CONDITION_BASE_SCHEMA
from homeassistant.helpers.typing import ConfigType, TemplateVarsType

from .const import (
    CONF_ANY_USER_PRESENT,
    CONF_USERS,
    CONF_USERS_NOT_PRESENT,
    CONF_USERS_PRESENT,
    DOMAIN,
    PRESENCE_LOCATION,
    PRESENCE_SPHERE,
    PRESENCE_SUFFIX,
)
from .entry_manager import CrownstoneEntryManager

SUPPORTED_DEVICES: Final[set[str]] = {PRESENCE_LOCATION, PRESENCE_SPHERE}

CONDITION_TYPES: Final[set[str]] = {
    CONF_USERS_PRESENT,
    CONF_USERS_NOT_PRESENT,
    CONF_ANY_USER_PRESENT,
}

CONDITION_SCHEMA = DEVICE_CONDITION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Required(CONF_TYPE): vol.In(CONDITION_TYPES),
    },
    extra=vol.ALLOW_EXTRA,
)


@callback
def _async_get_condition_data(
    hass: HomeAssistant, entity_id: str
) -> dict[str, str] | None:
    """Get the Crownstone users for the sphere."""
    crownstone_users: dict[str, str] = {}

    registry = entity_registry.async_get(hass)
    entity = registry.async_get(entity_id)
    if entity is None:
        return None

    crownstone_device_id = entity.unique_id[: -(len(PRESENCE_SUFFIX) + 1)]
    manager: CrownstoneEntryManager = hass.data[DOMAIN][entity.config_entry_id]

    for sphere in manager.cloud.cloud_data:
        if (
            sphere.cloud_id == crownstone_device_id
            or crownstone_device_id in sphere.locations.locations
        ):
            crownstone_users = {
                f"{user.first_name} {user.last_name}": f"{user.first_name} {user.last_name}"
                for user in sphere.users
            }

    return crownstone_users


@callback
def _async_get_state(hass: HomeAssistant, entity_id: str) -> State:
    """Get the state for an entity id. Raise error if it returns None."""
    state: State | None = hass.states.get(entity_id)
    if state is None:
        raise HomeAssistantError(f"State for entity {entity_id} returned None")

    return state


async def async_validate_condition_config(
    hass: HomeAssistant, config: ConfigType
) -> ConfigType:
    """Validate config."""
    validated_config: ConfigType = CONDITION_SCHEMA(config)

    if config[CONF_TYPE] in (CONF_USERS_PRESENT, CONF_USERS_NOT_PRESENT):
        user_schema = CONDITION_SCHEMA.extend(
            {vol.Required(CONF_USERS): vol.All(cv.ensure_list, [str])}
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


async def async_get_conditions(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, str]]:
    """List device conditions for Crownstone presence devices."""
    registry = entity_registry.async_get(hass)
    conditions: list[dict[str, str]] = []

    for entry in entity_registry.async_entries_for_device(registry, device_id):
        # only support presence sensors, which have no device class
        if entry.domain != SENSOR_DOMAIN or entry.device_class is not None:
            continue

        base_condition = {
            CONF_CONDITION: CONF_DEVICE,
            CONF_DEVICE_ID: device_id,
            CONF_DOMAIN: DOMAIN,
            CONF_ENTITY_ID: entry.entity_id,
        }

        conditions += [{**base_condition, CONF_TYPE: cond} for cond in CONDITION_TYPES]

    return conditions


@callback
async def async_get_condition_capabilities(
    hass: HomeAssistant, config: ConfigType
) -> dict[str, vol.Schema]:
    """List condition capabilities."""
    condition_data = _async_get_condition_data(hass, config[CONF_ENTITY_ID])
    if condition_data is None:
        raise HomeAssistantError(
            f"Could not get condition data for entity {config[CONF_ENTITY_ID]}"
        )

    if config[CONF_TYPE] in (CONF_USERS_PRESENT, CONF_USERS_NOT_PRESENT):
        return {
            "extra_fields": vol.Schema(
                {vol.Required(CONF_USERS): cv.multi_select(condition_data)}
            )
        }

    return {}


@callback
def async_condition_from_config(
    config: ConfigType, config_validation: bool
) -> condition.ConditionCheckerType:
    """Create a function to test a device condition."""
    if config_validation:
        config = CONDITION_SCHEMA(config)

    condition_type = config[CONF_TYPE]
    entity_id = config[CONF_ENTITY_ID]

    @callback
    def test_any_in_state(hass: HomeAssistant, variables: TemplateVarsType) -> bool:
        """Tests if there is any user in the state."""
        state_obj = _async_get_state(hass, entity_id)
        return bool(state_obj.state.strip())

    if condition_type == CONF_ANY_USER_PRESENT:
        return test_any_in_state

    users: list[str] = config[CONF_USERS]
    given_users_set: set[tuple[str, ...]] = {
        tuple(user_name.split()) for user_name in users
    }

    @callback
    def test_in_state(hass: HomeAssistant, variables: TemplateVarsType) -> bool:
        """Tests if the given users exists in the state."""
        state_obj = _async_get_state(hass, entity_id)
        state_attr_set: set[tuple[str, Any]] = {
            (first_name, attr[0])
            for first_name, attr in state_obj.attributes.items()
            if isinstance(attr, tuple)
        }
        return bool(state_attr_set.issuperset(given_users_set))

    if condition_type == CONF_USERS_PRESENT:
        return test_in_state

    @callback
    def test_not_in_state(hass: HomeAssistant, variables: TemplateVarsType) -> bool:
        """Tests if the given users don't exist in the state."""
        state_obj = _async_get_state(hass, entity_id)
        state_attr_set: set[tuple[str, Any]] = {
            (first_name, attr[0])
            for first_name, attr in state_obj.attributes.items()
            if isinstance(attr, tuple)
        }
        return bool(state_attr_set.isdisjoint(given_users_set))

    if condition_type == CONF_USERS_NOT_PRESENT:
        return test_not_in_state

    raise HomeAssistantError(f"Unhandled condition type {condition_type}")

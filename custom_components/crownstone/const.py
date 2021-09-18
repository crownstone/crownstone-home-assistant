"""Constants for the crownstone integration."""
from __future__ import annotations

from typing import Any, Final

# Platforms
DOMAIN: Final = "crownstone"
PLATFORMS: Final[list[str]] = ["light", "sensor"]

# Listeners
SSE_LISTENERS: Final = "sse_listeners"
UART_LISTENERS: Final = "uart_listeners"

# Unique ID suffixes
CROWNSTONE_SUFFIX: Final = "crownstone"
POWER_USAGE_SUFFIX: Final = "power_usage"
ENERGY_USAGE_SUFFIX: Final = "energy_usage"
PRESENCE_SUFFIX: Final = "presence"

# Entity name suffixes
POWER_USAGE_NAME_SUFFIX: Final = "Power"
ENERGY_USAGE_NAME_SUFFIX: Final = "Energy"

# Signals (within integration)
SIG_CROWNSTONE_STATE_UPDATE: Final = "crownstone.crownstone_state_update"
SIG_PRESENCE_STATE_UPDATE: Final = "crownstone.presence_state_update"
SIG_POWER_STATE_UPDATE: Final = "crownstone.power_state_update"
SIG_ENERGY_STATE_UPDATE: Final = "crownstone.energy_state_update"
SIG_UART_STATE_CHANGE: Final = "crownstone.uart_state_change"
SIG_SSE_STATE_CHANGE: Final = "crownstone.sse_state_change"
SIG_ADD_CROWNSTONE_DEVICES: Final = "crownstone.add_crownstone_device"
SIG_ADD_PRESENCE_DEVICES: Final = "crownstone.add_presence_device"

# Abilities
ABILITY_STATE: Final[dict[bool, str]] = {True: "Enabled", False: "Disabled"}
ABILITY: Final[dict[str, Any]] = {"enabled": False, "properties": {}}

# Config flow
CONF_USB_PATH: Final = "usb_path"
CONF_USB_MANUAL_PATH: Final = "usb_manual_path"
CONF_USB_SPHERE: Final = "usb_sphere"
# Options flow
CONF_USE_USB_OPTION: Final = "use_usb_option"
CONF_USB_SPHERE_OPTION: Final = "usb_sphere_option"
# USB config list entries
DONT_USE_USB: Final = "Don't use USB"
REFRESH_LIST: Final = "Refresh list"
MANUAL_PATH: Final = "Enter manually"

# Crownstone entity
CROWNSTONE_INCLUDE_TYPES: Final[dict[str, str]] = {
    "PLUG": "Plug",
    "BUILTIN": "Built-in",
    "BUILTIN_ONE": "Built-in One",
}

# Presence entity
PRESENCE_SPHERE: Final = "Sphere Presence"
PRESENCE_SPHERE_ICON: Final = "mdi:earth"
PRESENCE_LOCATION: Final = "Location Presence"
PRESENCE_LOCATION_ICON: Final = "mdi:map-marker-radius"

# Energy usage constant
JOULE_TO_KWH: Final = 3600000

# Device automation

# Automation data
CONF_USERS: Final = "users"
CONF_SUBTYPE: Final = "subType"
CONF_SPHERE: Final = "sphere"
CONF_USER: Final = "user"
CONF_LOCATION: Final = "location"

# Triggers
CONF_USER_ENTERED: Final = "user_entered"
CONF_USER_LEFT: Final = "user_left"
CONF_ANY_USER_ENTERED: Final = "any_user_entered"
CONF_ANY_USER_LEFT: Final = "any_user_left"

# Conditions
CONF_USERS_PRESENT: Final = "users_present"
CONF_USERS_NOT_PRESENT: Final = "users_not_present"
CONF_ANY_USER_PRESENT: Final = "any_user_present"

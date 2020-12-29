"""Constants for the crownstone integration."""

# Integrations
DOMAIN = "crownstone"
SENSOR_PLATFORM = "sensor"
LIGHT_PLATFORM = "light"

# Unique ID suffixes
CROWNSTONE_SUFFIX = "relay_and_dimmer"
POWER_USAGE_SUFFIX = "power_usage"
PRESENCE_SUFFIX = "presence"

# Signals (within integration)
SIG_PRESENCE_STATE_UPDATE = "crownstone.presence_state_update"
SIG_PRESENCE_UPDATE = "crownstone.presence_update"
SIG_CROWNSTONE_STATE_UPDATE = "crownstone.crownstone_state_update"
SIG_CROWNSTONE_UPDATE = "crownstone.crownstone_update"
SIG_POWER_STATE_UPDATE = "crownstone.power_state_update"
SIG_POWER_UPDATE = "crownstone.power_update"
SIG_TRIGGER_EVENT = "crownstone.trigger_event"
SIG_ADD_CROWNSTONE_DEVICES = "crownstone.add_crownstone_device"
SIG_ADD_PRESENCE_DEVICES = "crownstone.add_presence_device"
SIG_UART_READY = "crownstone.uart_ready"

# Added/deleted device or entities
ADDED_ITEMS = "added_items"
REMOVED_ITEMS = "removed_items"
ABILITY = {"enabled": False, "properties": {}}

# Abilities state
ABILITY_STATE = {True: "Enabled", False: "Disabled"}

# Config flow
CONF_SPHERE = "sphere"

# Crownstone entity
CROWNSTONE_TYPES = {
    "PLUG": "Plug",
    "CROWNSTONE_USB": "USB Dongle",
    "BUILTIN": "Built-in",
    "BUILTIN_ONE": "Built-in One",
    "GUIDESTONE": "Guidestone",
}
CROWNSTONE_EXCLUDE = ["CROWNSTONE_USB", "GUIDESTONE"]

# Presence entity
PRESENCE_SPHERE = {"icon": "mdi:earth", "description": "Sphere Presence"}
PRESENCE_LOCATION = {
    "icon": "mdi:map-marker-radius",
    "description": "Location Presence",
}

# Device automation

# Config
CONF_USER = "user"
CONF_USERS = "users"

# Triggers
USER_ENTERED = "user_entered"
USER_LEFT = "user_left"
MULTIPLE_USERS_ENTERED = "multiple_entered"
MULTIPLE_USERS_LEFT = "multiple_left"
ALL_USERS_ENTERED = "all_entered"
ALL_USERS_LEFT = "all_left"

# Trigger events (these are fired in the bus, and available to the user)
EVENT_USER_ENTERED = "crownstone.user_entered"
EVENT_USER_LEFT = "crownstone.user_left"

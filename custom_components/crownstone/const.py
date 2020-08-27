"""Constants for the crownstone integration."""

# Integrations
DOMAIN = "crownstone"
SENSOR_PLATFORM = "sensor"
LIGHT_PLATFORM = "light"

# Signals
SIG_STATE_UPDATE = "crownstone.state_update"
SIG_TRIGGER_EVENT = "crownstone.trigger_event"

# Config flow
CONF_SPHERE = "sphere"

# Crownstone entity
CROWNSTONE_TYPES = {
    "PLUG": "Crownstone plug",
    "CROWNSTONE_USB": "Crownstone USB",
    "BUILTIN": "Crownstone built-in",
    "BUILTIN_ONE": "Crownstone built-in one",
    "GUIDESTONE": "Crownstone guidestone",
}
CROWNSTONE_EXCLUDE = ["CROWNSTONE_USB", "GUIDESTONE"]

# Presence entity
PRESENCE_SPHERE = {"icon": "mdi:earth", "description": "Sphere presence"}
PRESENCE_LOCATION = {
    "icon": "mdi:map-marker-radius",
    "description": "Location presence",
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

# Trigger events
EVENT_USER_ENTERED = "crownstone.user_entered"
EVENT_USER_LEFT = "crownstone.user_left"

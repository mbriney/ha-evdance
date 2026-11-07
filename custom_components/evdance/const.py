"""Constants for the EVDANCE EV Charger integration."""
from __future__ import annotations

DOMAIN = "evdance"

# config keys
CONF_MODE = "mode"
CONF_SERIAL = "serial"
CONF_MODEL = "model"
CONF_HOST = "host"
CONF_PORT = "port"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"

# modes
MODE_LOCAL = "local"
MODE_CLOUD = "cloud"

# defaults
DEFAULT_MODEL = "ACT4002UA2"
DEFAULT_HOST = "mqtt.evdances.com"
DEFAULT_PORT = 1883
DEFAULT_USERNAME = "yccsmart"
MANUFACTURER = "EVDANCE"

MIN_CURRENT = 6
MAX_CURRENT = 40

STATUS_IDLE = 1
STATUS_CONNECTED = 2
STATUS_CHARGING = 3

STATUS_MAP = {
    STATUS_IDLE: "idle",
    STATUS_CONNECTED: "connected",
    STATUS_CHARGING: "charging",
}


def base_topic(model: str, serial: str) -> str:
    """Return the device's base MQTT topic, e.g. ycc/ACT4002UA2/<serial>."""
    return f"ycc/{model}/{serial}"


def signal_update(serial: str) -> str:
    """Dispatcher signal fired when new state arrives for a charger."""
    return f"{DOMAIN}_{serial}_update"

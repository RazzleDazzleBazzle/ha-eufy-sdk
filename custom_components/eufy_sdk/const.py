"""Constants for eufy_sdk."""

from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

DOMAIN = "eufy_sdk"
ATTRIBUTION = "Data provided by the eufy cloud via ha-eufy-sdk-bridge"

# Config-entry keys: the address of the ha-eufy-sdk-bridge WebSocket.
CONF_HOST = "host"
CONF_PORT = "port"
DEFAULT_PORT = 3000

# Options: how often the bridge polls the cloud for device state (minutes).
# Drives both the bridge's cloud poll (config.set) and how often HA reads it.
# Most real state changes (arming mode, motion, switches) arrive instantly over the
# push channel regardless of this value — see _IMMEDIATE_REFRESH_EVENTS in
# __init__.py — so this poll is a reconciliation sweep, not the primary way state
# reaches HA. Raised from 10: the device fleet itself is effectively static, and a
# longer gap means fewer chances per day for one slow cloud response to (briefly)
# mark every entity unavailable.
CONF_POLL_INTERVAL = "poll_interval_minutes"
DEFAULT_POLL_INTERVAL_MIN = 20

# Schema version this integration targets (the bridge sends its own in `hello`/`ready`).
SUPPORTED_SCHEMA = 1

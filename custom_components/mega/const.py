"""Constants for the mega integration."""

DOMAIN = "mega"
CONF_MEGA_ID = "mega_id"
CONF_DIMMER = "dimmer"
CONF_SWITCH = "switch"
CONF_KEY = 'key'
TEMP = 'temp'
HUM = 'hum'
W1 = 'w1'
W1BUS = 'w1bus'
CONF_PORT_TO_SCAN = 'port_to_scan'
CONF_RELOAD = 'reload'
CONF_INVERT = 'invert'
CONF_PORTS = 'ports'
CONF_CUSTOM = '__custom'
CONF_SKIP = 'skip'
PLATFORMS = [
    "light",
    "switch",
    "binary_sensor",
    "sensor",
]
EVENT_BINARY_SENSOR = f'{DOMAIN}.sensor'
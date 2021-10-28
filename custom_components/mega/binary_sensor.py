"""Platform for light integration."""
import logging

import voluptuous as vol

from homeassistant.components.binary_sensor import (
    PLATFORM_SCHEMA as SENSOR_SCHEMA,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_NAME,
    CONF_PORT,
    CONF_UNIQUE_ID,
    CONF_ID,
    CONF_ENTITY_ID,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.template import Template
from .const import EVENT_BINARY_SENSOR, DOMAIN, CONF_CUSTOM, CONF_SKIP, CONF_INVERT, CONF_RESPONSE_TEMPLATE
from .entities import  MegaPushEntity
from .hub import MegaD
from .tools import int_ignore

lg = logging.getLogger(__name__)


# Validation of the user's configuration
_EXTENDED = {
    vol.Required(CONF_PORT): int,
    vol.Optional(CONF_NAME): str,
    vol.Optional(CONF_UNIQUE_ID): str,
}
_ITEM = vol.Any(int, _EXTENDED)
PLATFORM_SCHEMA = SENSOR_SCHEMA.extend(
    {
        vol.Optional(str, description="mega id"): [_ITEM]
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup_platform(hass, config, add_entities, discovery_info=None):
    lg.warning('mega integration does not support yaml for binary_sensors, please use UI configuration')
    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_devices):
    mid = config_entry.data[CONF_ID]
    hub: MegaD = hass.data['mega'][mid]
    devices = []
    customize = hass.data.get(DOMAIN, {}).get(CONF_CUSTOM, {})
    for port, cfg in config_entry.data.get('binary_sensor', {}).items():
        port = int_ignore(port)
        c = customize.get(mid, {}).get(port, {})
        if c.get(CONF_SKIP, False):
            continue
        hub.lg.debug(f'add binary_sensor on port %s', port)
        sensor = MegaBinarySensor(mega=hub, port=port, config_entry=config_entry)
        if '<' in sensor.name:
            continue
        devices.append(sensor)
    async_add_devices(devices)


class MegaBinarySensor(BinarySensorEntity, MegaPushEntity):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mega.binary_sensors.append(self.port)
        self._is_on = None
        self._attrs = None
        self._click_task = None

    async def _click(self):
        await self.customize.get

    @property
    def state_attributes(self):
        return self._attrs

    @property
    def invert(self):
        return self.customize.get(CONF_INVERT, False)

    @property
    def is_on(self) -> bool:
        val = self.mega.values.get(self.port, {})
        if isinstance(val, dict):
            val = val.get("value", val.get('m'))
        if val is None and self._state is not None:
            return self._state == 'ON'
        elif val is not None:
            if val in ['ON', 'OFF', '1', '0']:
                return val in ['ON', '1'] if not self.invert else val in ['OFF', '0']
            elif isinstance(val, int):
                return val != 1 if not self.invert else val == 1

    def _update(self, payload: dict):
        self.mega.values[self.port] = payload


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
from .const import EVENT_BINARY_SENSOR, DOMAIN, CONF_CUSTOM, CONF_SKIP
from .entities import  MegaPushEntity
from .hub import MegaD


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
        port = int(port)
        c = customize.get(mid, {}).get(port, {})
        if c.get(CONF_SKIP, False):
            continue
        hub.lg.debug(f'add binary_sensor on port %s', port)
        sensor = MegaBinarySensor(mega=hub, port=port, config_entry=config_entry)
        devices.append(sensor)
    async_add_devices(devices)


class MegaBinarySensor(BinarySensorEntity, MegaPushEntity):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._is_on = None
        self._attrs = None

    @property
    def state_attributes(self):
        return self._attrs

    @property
    def is_on(self) -> bool:
        if self._is_on is not None:
            return self._is_on
        return self._state == 'ON'

    def _update(self, payload: dict):
        data = {CONF_ENTITY_ID: self.entity_id}
        payload = payload.copy()
        payload.pop(CONF_PORT)
        data.update(payload)
        if not self.is_first_update:
            self.hass.bus.async_fire(
                EVENT_BINARY_SENSOR,
                data,
            )
        val = payload.get("value")
        self._is_on = val == 'ON'
        self._attrs = data

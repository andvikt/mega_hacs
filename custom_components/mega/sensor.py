"""Platform for light integration."""
import logging

import typing
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_SCHEMA,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_HUMIDITY
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_NAME,
    CONF_PLATFORM,
    CONF_PORT,
    CONF_UNIQUE_ID,
    CONF_ID,
    CONF_TYPE,
)
from homeassistant.core import HomeAssistant
from .entities import BaseMegaEntity
from .const import CONF_KEY, TEMP, HUM, W1, W1BUS
from .hub import MegaD
import re

lg = logging.getLogger(__name__)
TEMP_PATT = re.compile(r'temp:([01234567890\.]+)')
HUM_PATT = re.compile(r'hum:([01234567890\.]+)')
PATTERNS = {
    TEMP: TEMP_PATT,
    HUM: HUM_PATT,
}

UNITS = {
    TEMP: '°C',
    HUM: '%'
}
CLASSES = {
    TEMP: DEVICE_CLASS_TEMPERATURE,
    HUM: DEVICE_CLASS_HUMIDITY
}
# Validation of the user's configuration
_ITEM = {
    vol.Required(CONF_PORT): int,
    vol.Optional(CONF_NAME): str,
    vol.Optional(CONF_UNIQUE_ID): str,
    vol.Required(CONF_TYPE): vol.Any(
        W1,
        W1BUS,
    ),
    vol.Optional(CONF_KEY, default=''): str,
}
PLATFORM_SCHEMA = SENSOR_SCHEMA.extend(
    {
        vol.Optional(str, description="mega id"): [_ITEM]
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup_platform(hass, config, add_entities, discovery_info=None):
    config.pop(CONF_PLATFORM)
    ents = []
    for mid, _config in config.items():
        for x in _config:
            ent = _make_entity(mid, **x)
            ents.append(ent)
    add_entities(ents)
    return True


def _make_entity(mid: str, port: int, conf: dict):
    key = conf[CONF_KEY]
    return Mega1WSensor(
        key=key,
        mega_id=mid,
        port=port,
        patt=PATTERNS.get(key),
        unit_of_measurement=UNITS.get(key, UNITS[TEMP]),  # TODO: make other units, make options in config flow
        device_class=CLASSES.get(key, CLASSES[TEMP]),
        id_suffix=key
    )


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_devices):
    mid = config_entry.data[CONF_ID]
    hub: MegaD = hass.data['mega'][mid]
    devices = []
    async for port, pty, m in hub.scan_ports():
        if pty == "3":
            values = await hub.get_port(port, get_value=True)
            lg.debug(f'values: %s', values)
            if values is None:
                continue
            if not isinstance(values, dict):
                values = {None: values}
            for key in values:
                hub.lg.debug(f'add sensor {W1}:{key}')
                sensor = _make_entity(
                    mid=mid,
                    port=port,
                    conf={
                        CONF_TYPE: W1,
                        CONF_KEY: key,
                    })
                devices.append(sensor)

    async_add_devices(devices)


class Mega1WSensor(BaseMegaEntity):

    def __init__(
            self,
            unit_of_measurement,
            device_class,
            patt=None,
            key=None,
            *args,
            **kwargs
    ):
        """
        1-wire sensor entity

        :param key: key to get value from mega's json
        :param patt: pattern to extract value, must have at least one group that will contain parsed value
        """
        super().__init__(*args, **kwargs)
        self._value = None
        self.key = key
        self.patt = patt
        self._device_class = device_class
        self._unit_of_measurement = unit_of_measurement

    async def async_added_to_hass(self) -> None:

        await super(Mega1WSensor, self).async_added_to_hass()
        self.mega.sensors.append(self)

    @property
    def unit_of_measurement(self):
        return self._unit_of_measurement

    @property
    def unique_id(self):
        if self.key:
            return super().unique_id + f'_{self.key}'
        else:
            return super(Mega1WSensor, self).unique_id

    @property
    def device_class(self):
        return self._device_class

    @property
    def should_poll(self):
        return False

    @property
    def state(self):
        if self._value is None and self._state is not None:
            return self._state.state
        return self._value

    def _update(self, payload: dict):
        val = payload.get('value', '')
        if isinstance(val, str):
            val = self.patt.findall(val)
            if val:
                self._value = val[0]
            else:
                self.lg.warning(f'could not parse: {payload}')
        elif isinstance(val, dict) and self.key is not None:
            self._value = val.get(self.key)
        elif isinstance(val, (float, int)):
            self._value = val
        else:
            self.lg.warning(f'could not parse: {payload}')

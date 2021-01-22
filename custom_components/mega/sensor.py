"""Platform for light integration."""
import logging
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_SCHEMA,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_HUMIDITY
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_NAME,
    CONF_PORT,
    CONF_UNIQUE_ID,
    CONF_ID,
    CONF_TYPE, CONF_UNIT_OF_MEASUREMENT,
)
from homeassistant.core import HomeAssistant
from .entities import MegaPushEntity
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
    lg.warning('mega integration does not support yaml for sensors, please use UI configuration')
    return True


def _make_entity(config_entry, mid: str, port: int, conf: dict):
    key = conf[CONF_KEY]
    return Mega1WSensor(
        key=key,
        mega_id=mid,
        port=port,
        patt=PATTERNS.get(key),
        unit_of_measurement=UNITS.get(key, UNITS[TEMP]),  # TODO: make other units, make options in config flow
        device_class=CLASSES.get(key, CLASSES[TEMP]),
        id_suffix=key,
        config_entry=config_entry
    )


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_devices):
    mid = config_entry.data[CONF_ID]
    hub: MegaD = hass.data['mega'][mid]
    devices = []
    for port, cfg in config_entry.data.get('sensor', {}).items():
        port = int(port)
        for data in cfg:
            hub.lg.debug(f'add sensor on port %s with data %s', port, data)
            sensor = Mega1WSensor(
                mega=hub,
                port=port,
                config_entry=config_entry,
                **data,
            )
            devices.append(sensor)

    async_add_devices(devices)


class Mega1WSensor(MegaPushEntity):

    def __init__(
            self,
            unit_of_measurement,
            device_class,
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
        self.mega.sensors.append(self)
        self._value = None
        self.key = key
        self._device_class = device_class
        self._unit_of_measurement = unit_of_measurement
        if self.port not in self.mega.sensors:
            self.mega.sensors.append(self.port)

    @property
    def unit_of_measurement(self):
        _u = self.customize.get(CONF_UNIT_OF_MEASUREMENT, None)
        if _u is None:
            return self._unit_of_measurement
        elif isinstance(_u, str):
            return _u
        elif isinstance(_u, dict) and self.key in _u:
            return _u[self.key]
        else:
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
    def state(self):
        if self.key:
            ret = self.mega.values.get(self.port, {}).get('value', {}).get(self.key)
        else:
            ret = self.mega.values.get(self.port, {}).get('value')
        if ret is None and self._state is not None:
            ret = self._state.state
        return ret

    def _update(self, payload: dict):
        self.mega.values[self.port] = payload

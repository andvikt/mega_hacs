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
    CONF_TYPE, CONF_UNIT_OF_MEASUREMENT, CONF_VALUE_TEMPLATE,
    CONF_DEVICE_CLASS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.template import Template
from .entities import MegaPushEntity
from .const import CONF_KEY, TEMP, HUM, W1, W1BUS, CONF_CONV_TEMPLATE
from .hub import MegaD
import re

from .tools import int_ignore

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
    for tp in ['sensor', 'i2c']:
        for port, cfg in config_entry.data.get(tp, {}).items():
            port = int_ignore(port)
            for data in cfg:
                hub.lg.debug(f'add sensor on port %s with data %s', port, data)
                sensor = _constructors[tp](
                    mega=hub,
                    port=port,
                    config_entry=config_entry,
                    **data,
                )
                devices.append(sensor)

    async_add_devices(devices)


class MegaI2C(MegaPushEntity):

    def __init__(self, *args, device_class: str, params: dict, **kwargs):
        self._device_class = device_class
        self._params = tuple(params.items())
        super().__init__(*args, **kwargs)

    def device_class(self):
        return self._device_class

    @property
    def state(self):
        # self.lg.debug(f'get % all states: %', self._params, self.mega.values)
        return self.mega.values.get(self._params)

    @property
    def device_class(self):
        return self._device_class


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
        self._value = None
        self.key = key
        self._device_class = device_class
        self._unit_of_measurement = unit_of_measurement
        self.mega.sensors.append(self)

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
        _u = self.customize.get(CONF_DEVICE_CLASS, None)
        if _u is None:
            return self._device_class
        elif isinstance(_u, str):
            return _u
        elif isinstance(_u, dict) and self.key in _u:
            return _u[self.key]
        else:
            return self._device_class

    @property
    def state(self):
        ret = None
        if self.key:
            try:
                ret = self.mega.values.get(self.port, {})
                if isinstance(ret, dict):
                    ret = ret.get('value', {})
                    if isinstance(ret, dict):
                        ret = ret.get(self.key)
            except:
                self.lg.error(self.mega.values.get(self.port, {}).get('value', {}))
                return
        else:
            ret = self.mega.values.get(self.port, {}).get('value')
        if ret is None and self._state is not None:
            ret = self._state.state
        try:
            ret = float(ret)
            ret = str(ret)
        except:
            ret = None
        tmpl: Template = self.customize.get(CONF_CONV_TEMPLATE, self.customize.get(CONF_VALUE_TEMPLATE))
        if tmpl is not None and self.hass is not None:
            tmpl.hass = self.hass
            ret = tmpl.async_render({'value': ret})
        return ret

    @property
    def name(self):
        n = super().name
        c = self.customize.get(CONF_NAME, {})
        if isinstance(c, dict):
            c = c.get(self.key)
        return c or n


_constructors = {
    'sensor': Mega1WSensor,
    'i2c': MegaI2C,
}
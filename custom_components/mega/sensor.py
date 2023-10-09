"""Platform for light integration."""
import logging
import voluptuous as vol
import struct

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_SCHEMA, SensorEntity, SensorDeviceClass
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
from .const import CONF_KEY, TEMP, HUM, W1, W1BUS, CONF_CONV_TEMPLATE, CONF_HEX_TO_FLOAT, DOMAIN, CONF_CUSTOM, \
    CONF_SKIP, CONF_FILTER_VALUES, CONF_FILTER_SCALE, CONF_FILTER_LOW, CONF_FILTER_HIGH, CONF_FILL_NA
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
    TEMP: SensorDeviceClass.TEMPERATURE,
    HUM: SensorDeviceClass.HUMIDITY
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
    customize = hass.data.get(DOMAIN, {}).get(CONF_CUSTOM, {}).get(mid, {})
    for tp in ['sensor', 'i2c']:
        for port, cfg in config_entry.data.get(tp, {}).items():
            port = int_ignore(port)
            c = customize.get(port, {})
            if c.get(CONF_SKIP):
                hub.skip_ports |= {port}
                continue
            for data in cfg:
                hub.lg.debug(f'add sensor on port %s with data %s, constructor: %s', port, data, _constructors[tp])
                sensor = _constructors[tp](
                    mega=hub,
                    port=port,
                    config_entry=config_entry,
                    **data,
                )
                if '<' in sensor.name:
                    continue
                devices.append(sensor)

    async_add_devices(devices)


class FilterBadValues(MegaPushEntity, SensorEntity):

    def __init__(self, *args, **kwargs):
        self._prev_value = None
        super().__init__(*args, **kwargs)

    def filter_value(self, value):
        try:
            if value \
                    in self.filter_values \
                    or (self.filter_low is not None and value < self.filter_low) \
                    or (self.filter_high is not None and value > self.filter_high) \
                    or (
                    self._prev_value is not None
                    and self.filter_scale is not None
                    and (
                            abs(value - self._prev_value) / self._prev_value > self.filter_scale
                    )
            ):
                if self.fill_na == 'last':
                    value = self._prev_value
                else:
                    value = None
            self._prev_value = value
            return value
        except Exception as exc:
            lg.exception(f'while parsing value')
            return None

    @property
    def filter_values(self):
        return self.customize.get(CONF_FILTER_VALUES, self.mega.customize.get(CONF_FILTER_VALUES, []))

    @property
    def filter_scale(self):
        return self.customize.get(CONF_FILTER_SCALE, self.mega.customize.get(CONF_FILTER_SCALE, None))

    @property
    def filter_low(self):
        return self.customize.get(CONF_FILTER_LOW, self.mega.customize.get(CONF_FILTER_LOW, None))

    @property
    def filter_high(self):
        return self.customize.get(CONF_FILTER_HIGH, self.mega.customize.get(CONF_FILTER_HIGH, None))

    @property
    def fill_na(self):
        return self.customize.get(CONF_FILL_NA, 'last')


class MegaI2C(FilterBadValues):

    def __init__(
            self,
            *args,
            device_class: str,
            params: dict,
            unit_of_measurement: str = None,
            **kwargs
    ):
        self._device_class = device_class
        self._params = tuple(params.items())
        self._unit_of_measurement = unit_of_measurement
        super().__init__(*args, **kwargs)

    @property
    def customize(self):
        ret = super().customize
        _old = ret.get(self.id_suffix)
        if _old is not None:
            ret = ret.copy()
            ret.update(_old)
        return ret

    @property
    def extra_state_attributes(self):
        attrs = super().extra_state_attributes or {}
        attrs.update({
            'i2c_id': self.id_suffix,
        })
        return attrs

    @property
    def device_class(self):
        return self._device_class

    @property
    def native_unit_of_measurement(self):
        return self._unit_of_measurement

    @property
    def native_value(self):
        try:
            ret = self.mega.values.get(self._params)
            if self.customize.get(CONF_HEX_TO_FLOAT):
                try:
                    ret = struct.unpack('!f', bytes.fromhex(ret))[0]
                except:
                    self.lg.warning(f'could not convert {ret} form hex to float')
            tmpl: Template = self.customize.get(CONF_CONV_TEMPLATE, self.customize.get(CONF_VALUE_TEMPLATE))
            try:
                ret = float(ret)
                if tmpl is not None and self.hass is not None:
                    tmpl.hass = self.hass
                    ret = tmpl.async_render({'value': ret})
            except:
                ret = ret
            ret = self.filter_value(ret)
            if ret is not None:
                return str(ret)
        except Exception:
            lg.exception('while getting value')
            return None

    @property
    def device_class(self):
        return self._device_class


class Mega1WSensor(FilterBadValues):

    def __init__(
            self,
            unit_of_measurement=None,
            device_class=None,
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
        self.key = key
        self._value = None
        self._device_class = device_class
        self._unit_of_measurement = unit_of_measurement
        self.mega.sensors.append(self)
        self.prev_value = None

    @property
    def native_unit_of_measurement(self):
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
            return super().unique_id

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
    def native_value(self):
        try:
            ret = None
            if not hasattr(self, 'key'):
                return None
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
            if ret is None and self.fill_na == 'fill_na' and self.prev_value is not None:
                ret = self.prev_value
            elif ret is None and self.fill_na == 'fill_na' and self._state is not None:
                ret = self._state.state
            try:
                ret = float(ret)
                ret = str(ret)
            except:
                self.lg.debug(f'could not convert to float "{ret}"')
                ret = self.prev_value
            if self.customize.get(CONF_HEX_TO_FLOAT):
                try:
                    ret = struct.unpack('!f', bytes.fromhex(ret))[0]
                except:
                    self.lg.warning(f'could not convert {ret} form hex to float')
            tmpl: Template = self.customize.get(CONF_CONV_TEMPLATE, self.customize.get(CONF_VALUE_TEMPLATE))
            try:
                ret = float(ret)
                if tmpl is not None and self.hass is not None:
                    tmpl.hass = self.hass
                    ret = tmpl.async_render({'value': ret})
            except:
                pass
            ret = self.filter_value(ret)
            self.prev_value = ret
            if ret is not None:
                return str(ret)
        except Exception:
            lg.exception('while parsing state')
            return None

    @property
    def name(self):
        n = super().name
        c = self.customize.get(CONF_NAME, {})
        if isinstance(c, dict):
            try:
                c = c.get(self.key)
            except:
                pass
        return c or n


_constructors = {
    'sensor': Mega1WSensor,
    'i2c': MegaI2C,
}

import typing
from dataclasses import dataclass, astuple
from urllib.parse import parse_qsl, urlparse
from bs4 import BeautifulSoup

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import (
    PERCENTAGE,
    LIGHT_LUX,
    CONCENTRATION_PARTS_PER_MILLION,
    UnitOfTemperature,
    UnitOfPressure
)
from collections import namedtuple


# DeviceType = namedtuple('DeviceType', 'device_class,unit_of_measurement,suffix')


@dataclass
class DeviceType:
    device_class: typing.Optional[str] = None
    unit_of_measurement: typing.Optional[str] = None
    suffix: typing.Optional[str] = None
    delay: typing.Optional[float] = None
    i2c_par: typing.Optional[int] = None
    idx: typing.Optional[
        int
    ] = None  # на случай если все значения представлены одной строчкой (как с scd4x)


def parse_scan_page(page: str):
    ret = []
    req = []
    page = BeautifulSoup(page, features="lxml")
    for x in page.find_all("a"):
        params = x.get("href")
        if params is None:
            continue
        params = dict(parse_qsl(urlparse(params).query))
        dev = params.get("i2c_dev")
        if dev is None:
            continue
        classes = i2c_classes.get(dev, [])
        i2c_par, idx = (None, None)
        for i, c in enumerate(classes):
            _params = params.copy()
            if c is Skip:
                continue
            elif c is Request:
                req.append(_params)
                continue
            elif isinstance(c, Request):
                if c.delay:
                    _params["delay"] = c.delay
                req.append(_params)
                continue
            elif isinstance(c, DeviceType):
                c, m, suffix, delay, i2c_par, idx = astuple(c)
                if delay is not None:
                    _params["delay"] = delay
            else:
                continue
            suffix = suffix or c
            if "addr" in _params:
                suffix += f"_{_params['addr']}" if suffix else str(_params["addr"])
            if suffix:
                _dev = f"{dev}_{suffix}"
            else:
                _dev = dev
            if i > 0 and i2c_par is None:
                _params["i2c_par"] = i
            # i2c_par может быть явно указан в DeviceType
            elif i2c_par is not None and i2c_par > 0:
                _params["i2c_par"] = i2c_par
            # idx - тема фактически только для scd4x, означает номер внутри текстового значения разделенного знаком "/"
            if idx is not None:
                _params["idx"] = idx

            ret.append(
                {
                    "id_suffix": _dev,
                    "device_class": c,
                    "params": _params,
                    "unit_of_measurement": m,
                }
            )
            req.append(_params)
    return req, ret


class Skip:
    pass


@dataclass
class Request:
    delay: float = None


i2c_classes = {
    "htu21d": [
        DeviceType(SensorDeviceClass.HUMIDITY, PERCENTAGE, None),
        DeviceType(SensorDeviceClass.TEMPERATURE, UnitOfTemperature.CELSIUS, None),
    ],
    "sht31": [
        DeviceType(SensorDeviceClass.HUMIDITY, PERCENTAGE, None, delay=0.1),
        DeviceType(SensorDeviceClass.TEMPERATURE, UnitOfTemperature.CELSIUS, None),
    ],
    "max44009": [DeviceType(SensorDeviceClass.ILLUMINANCE, LIGHT_LUX, None)],
    "bh1750": [DeviceType(SensorDeviceClass.ILLUMINANCE, LIGHT_LUX, None)],
    "tsl2591": [DeviceType(SensorDeviceClass.ILLUMINANCE, LIGHT_LUX, None)],
    "bmp180": [
        DeviceType(SensorDeviceClass.PRESSURE, UnitOfPressure.BAR, None),
        DeviceType(SensorDeviceClass.TEMPERATURE, UnitOfTemperature.CELSIUS, None),
    ],
    "bmx280": [
        DeviceType(SensorDeviceClass.PRESSURE, UnitOfPressure.BAR, None),
        DeviceType(SensorDeviceClass.TEMPERATURE, UnitOfTemperature.CELSIUS, None),
        DeviceType(SensorDeviceClass.HUMIDITY, PERCENTAGE, None),
    ],
    "dps368": [
        DeviceType(SensorDeviceClass.PRESSURE, UnitOfPressure.BAR, None),
        DeviceType(SensorDeviceClass.TEMPERATURE, UnitOfTemperature.CELSIUS, None),
    ],
    "mlx90614": [
        Skip,
        DeviceType(SensorDeviceClass.TEMPERATURE, UnitOfTemperature.CELSIUS, "temp"),
        DeviceType(SensorDeviceClass.TEMPERATURE, UnitOfTemperature.CELSIUS, "object"),
    ],
    "ptsensor": [
        Skip,
        Request(delay=3),  # запрос на измерение
        DeviceType(SensorDeviceClass.PRESSURE, UnitOfPressure.BAR, None),
        DeviceType(SensorDeviceClass.TEMPERATURE, UnitOfTemperature.CELSIUS, None),
    ],
    "mcp9600": [
        DeviceType(SensorDeviceClass.TEMPERATURE, UnitOfTemperature.CELSIUS, None),  # термопара
        DeviceType(
            SensorDeviceClass.TEMPERATURE, UnitOfTemperature.CELSIUS, None
        ),  # сенсор встроенный в микросхему
    ],
    "t67xx": [DeviceType(SensorDeviceClass.CO2, CONCENTRATION_PARTS_PER_MILLION, None)],
    "tmp117": [
        DeviceType(SensorDeviceClass.TEMPERATURE, UnitOfTemperature.CELSIUS, None),
    ],
    "ads1115": [
        DeviceType(None, None, "ch0"),
        DeviceType(None, None, "ch1"),
        DeviceType(None, None, "ch2"),
        DeviceType(None, None, "ch3"),
    ],
    "ads1015": [
        DeviceType(None, None, "ch0"),
        DeviceType(None, None, "ch1"),
        DeviceType(None, None, "ch2"),
        DeviceType(None, None, "ch3"),
    ],
    "opt3001": [
        DeviceType(SensorDeviceClass.ILLUMINANCE, LIGHT_LUX, None),
    ],
    "ina226": [
        Skip,
        DeviceType(SensorDeviceClass.CURRENT, "A", None),
        DeviceType(SensorDeviceClass.VOLTAGE, "V", None),
    ],
    "scd4x": [
        DeviceType(
            SensorDeviceClass.CO2,
            CONCENTRATION_PARTS_PER_MILLION,
            None,
            i2c_par=0,
            idx=0,
        ),
        DeviceType(SensorDeviceClass.TEMPERATURE, UnitOfTemperature.CELSIUS, None, i2c_par=0, idx=1),
        DeviceType(SensorDeviceClass.HUMIDITY, PERCENTAGE, None, i2c_par=0, idx=2),
    ],
}

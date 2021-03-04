from dataclasses import dataclass, field
from urllib.parse import parse_qsl, urlparse
from bs4 import BeautifulSoup
from homeassistant.const import (
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_ILLUMINANCE,
    DEVICE_CLASS_PRESSURE,
)


def parse_scan_page(page: str):
    ret = []
    req = []
    page = BeautifulSoup(page, features="lxml")
    for x in page.find_all('a'):
        params = x.get('href')
        if params is None:
            continue
        params = dict(parse_qsl(urlparse(params).query))
        dev = params.get('i2c_dev')
        if dev is None:
            continue
        classes = i2c_classes.get(dev, [])
        for i, c in enumerate(classes):
            if c is Skip:
                continue
            elif c is Request:
                req.append(params)
                continue
            elif isinstance(c, Request):
                if c.delay:
                    params = params.copy()
                    params['delay'] = c.delay
                req.append(params)
                continue
            elif isinstance(c, tuple):
                suffix, c = c
            elif isinstance(c, str):
                suffix = c
            else:
                suffix = ''
            if 'addr' in params:
                suffix += f"_{params['addr']}" if suffix else str(params['addr'])
            if suffix:
                _dev = f'{dev}_{suffix}'
            else:
                _dev = dev
            params = params.copy()
            if i > 0:
                params['i2c_par'] = i
            ret.append({
                'id_suffix': _dev,
                'device_class': c,
                'params': params,
            })
            req.append(params)
    return req, ret


class Skip:
    pass


@dataclass
class Request:
    delay: float = None


i2c_classes = {
    'htu21d': [
        DEVICE_CLASS_HUMIDITY,
        DEVICE_CLASS_TEMPERATURE,
    ],
    'sht31': [
        DEVICE_CLASS_HUMIDITY,
        DEVICE_CLASS_TEMPERATURE,
    ],
    'max44009': [
        DEVICE_CLASS_ILLUMINANCE
    ],
    'bh1750': [
        DEVICE_CLASS_ILLUMINANCE
    ],
    'tsl2591': [
        DEVICE_CLASS_ILLUMINANCE
    ],
    'bmp180': [
        DEVICE_CLASS_PRESSURE,
        DEVICE_CLASS_TEMPERATURE,
    ],
    'bmx280': [
        DEVICE_CLASS_PRESSURE,
        DEVICE_CLASS_TEMPERATURE,
        DEVICE_CLASS_HUMIDITY
    ],
    'mlx90614': [
        Skip,
        ('temp', DEVICE_CLASS_TEMPERATURE),
        ('object', DEVICE_CLASS_TEMPERATURE),
    ],
    'ptsensor': [
        Skip,
        Request(delay=1),  # запрос на измерение
        DEVICE_CLASS_PRESSURE,
        DEVICE_CLASS_TEMPERATURE,
    ],
    'mcp9600': [
        DEVICE_CLASS_TEMPERATURE,  # термопара
        DEVICE_CLASS_TEMPERATURE,  # сенсор встроенный в микросхему
    ],
    't67xx': [
        None  # для co2 нет класса в HA
    ],
    'tmp117': [
        DEVICE_CLASS_TEMPERATURE,
    ]
}

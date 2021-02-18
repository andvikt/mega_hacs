import asyncio
import logging
from collections import defaultdict
from datetime import datetime, timedelta

import aiohttp
import typing
import re
import json

from bs4 import BeautifulSoup
from homeassistant.components import mqtt
from homeassistant.const import (
    DEVICE_CLASS_TEMPERATURE, DEVICE_CLASS_HUMIDITY, DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_ILLUMINANCE, TEMP_CELSIUS, PERCENTAGE, LIGHT_LUX
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from .const import (
    TEMP, HUM, PRESS,
    LUX, PATT_SPLIT, DOMAIN,
    CONF_HTTP, EVENT_BINARY_SENSOR, CONF_CUSTOM, CONF_FORCE_D
)
from .entities import set_events_off, BaseMegaEntity
from .exceptions import CannotConnect, NoPort
from .tools import make_ints

TEMP_PATT = re.compile(r'temp:([01234567890\.]+)')
HUM_PATT = re.compile(r'hum:([01234567890\.]+)')
PRESS_PATT = re.compile(r'press:([01234567890\.]+)')
LUX_PATT = re.compile(r'lux:([01234567890\.]+)')
PATTERNS = {
    TEMP: TEMP_PATT,
    HUM: HUM_PATT,
    PRESS: PRESS_PATT,
    LUX: LUX_PATT
}
UNITS = {
    TEMP: TEMP_CELSIUS, 
    HUM: PERCENTAGE,
    PRESS: 'mmHg',
    LUX: LIGHT_LUX
}
CLASSES = {
    TEMP: DEVICE_CLASS_TEMPERATURE,
    HUM: DEVICE_CLASS_HUMIDITY,
    PRESS: DEVICE_CLASS_PRESSURE,
    LUX: DEVICE_CLASS_ILLUMINANCE
}
I2C_DEVICE_TYPES = {
    "2":  LUX,  # BH1750
    "3":  LUX,  # TSL2591
    "7":  LUX,  # MAX44009
    "70": LUX,  # OPT3001
}


class MegaD:
    """MegaD Hub"""

    def __init__(
            self,
            hass: HomeAssistant,
            loop: asyncio.AbstractEventLoop,
            host: str,
            password: str,
            mqtt: mqtt.MQTT,
            lg: logging.Logger,
            id: str,
            mqtt_inputs: bool = True,
            mqtt_id: str = None,
            scan_interval=60,
            port_to_scan=0,
            nports=38,
            inverted: typing.List[int] = None,
            update_all=True,
            poll_outs=False,
            **kwargs,
    ):
        """Initialize."""
        if mqtt_inputs is None or mqtt_inputs == 'None' or mqtt_inputs is False:
            self.http = hass.data.get(DOMAIN, {}).get(CONF_HTTP)
            if not self.http is None:
                self.http.allowed_hosts |= {host}
        else:
            self.http = None
        self.poll_outs = poll_outs
        self.update_all = update_all if update_all is not None else True
        self.nports = nports
        self.mqtt_inputs = mqtt_inputs
        self.loop: asyncio.AbstractEventLoop = None
        self.hass = hass
        self.host = host
        self.sec = password
        self.mqtt = mqtt
        self.id = id
        self.lck = asyncio.Lock()
        self.last_long = {}
        self._http_lck = asyncio.Lock()
        self._notif_lck = asyncio.Lock()
        self.cnd = asyncio.Condition()
        self.online = True
        self.entities: typing.List[BaseMegaEntity] = []
        self.ds2413_ports = set()
        self.poll_interval = scan_interval
        self.subs = None
        self.lg: logging.Logger = lg.getChild(self.id)
        self._scanned = {}
        self.sensors = []
        self.port_to_scan = port_to_scan
        self.last_update = datetime.now()
        self._callbacks: typing.DefaultDict[int, typing.List[typing.Callable[[dict], typing.Coroutine]]] = defaultdict(list)
        self._loop = loop
        self._customize = None
        self.values = {}
        self.last_port = None
        self.updater = DataUpdateCoordinator(
            hass,
            self.lg,
            name="sensors",
            update_method=self.poll,
            update_interval=timedelta(seconds=self.poll_interval) if self.poll_interval else None,
        )
        self.notifiers = defaultdict(asyncio.Condition)
        if not mqtt_id:
            _id = host.split(".")[-1]
            self.mqtt_id = f"megad/{_id}"
        else:
            self.mqtt_id = mqtt_id

    async def start(self):
        self.loop = asyncio.get_event_loop()
        if self.mqtt is not None:
            set_events_off()
            self.subs = await self.mqtt.async_subscribe(
                topic=f"{self.mqtt_id}/+",
                msg_callback=self._process_msg,
                qos=0,
            )

    async def stop(self):
        if self.subs is not None:
            self.subs()
        for x in self._callbacks.values():
            x.clear()

    async def add_entity(self, ent):
        async with self.lck:
            self.entities.append(ent)

    async def get_sensors(self, only_list=False):
        self.lg.debug(self.sensors)
        ports = []
        for x in self.sensors:
            if only_list and x.http_cmd != 'list':
                continue
            if x.port in ports:
                continue
            await self.get_port(x.port, force_http=True, http_cmd=x.http_cmd)
            ports.append(x.port)

    @property
    def customize(self):
        if self._customize is None:
            c = self.hass.data.get(DOMAIN, {}).get(CONF_CUSTOM) or {}
            c = c.get(self.id) or {}
            self._customize = c
        return self._customize

    @property
    def force_d(self):
        return self.customize.get(CONF_FORCE_D, False)

    @property
    def is_online(self):
        return (datetime.now() - self.last_update).total_seconds() < (self.poll_interval + 10)

    def _warn_offline(self):
        if self.online:
            self.lg.warning('mega is offline')
            self.hass.states.async_set(
                f'mega.{self.id}',
                'offline',
            )
            self.online = False

    def _notify_online(self):
        if not self.online:
            self.hass.states.async_set(
                f'mega.{self.id}',
                'online',
            )
            self.online = True

    async def _get_ds2413(self):
        """
        обновление ds2413 устройств
        :return:
        """
        for x in self.ds2413_ports:
            self.lg.debug(f'poll ds2413 for %s', x)
            await self.get_port(
                port=x,
                force_http=True,
                http_cmd='list',
                conv=False
            )

    async def poll(self):
        """
        Polling ports
        """
        self.lg.debug('poll')
        if self.mqtt is None:
            await self.get_all_ports()
            await self.get_sensors(only_list=True)
        elif self.poll_outs:
            await self.get_all_ports(check_skip=True)
        elif len(self.sensors) > 0:
            await self.get_sensors()
        else:
            await self.get_port(self.port_to_scan)
        await self._get_ds2413()
        return self.values

    async def get_mqtt_id(self):
        async with aiohttp.request(
            'get', f'http://{self.host}/{self.sec}/?cf=2'
        ) as req:
            data = await req.text()
            data = BeautifulSoup(data, features="lxml")
            _id = data.find(attrs={'name': 'mdid'})
            if _id:
                _id = _id['value']
            return _id or 'megad/' + self.host.split('.')[-1]

    async def send_command(self, port=None, cmd=None):
        return await self.request(pt=port, cmd=cmd)

    async def request(self, **kwargs):
        cmd = '&'.join([f'{k}={v}' for k, v in kwargs.items() if v is not None])
        url = f"http://{self.host}/{self.sec}/?{cmd}"
        self.lg.debug('request: %s', url)
        async with self._http_lck:
            async with aiohttp.request("get", url=url) as req:
                if req.status != 200:
                    self.lg.warning('%s returned %s (%s)', url, req.status, await req.text())
                    return None
                else:
                    ret = await req.text()
                    self.lg.debug('response %s', ret)
                    return ret

    async def save(self):
        await self.send_command(cmd='s')

    def parse_response(self, ret):
        if ret is None:
            raise NoPort()
        if 'busy' in ret:
            return None
        if ':' in ret:
            if ';' in ret:
                ret = ret.split(';')
            elif '/' in ret:
                ret = ret.split('/')
            ret = {'value': dict([
                x.split(':') for x in ret if x.count(':') == 1
            ])}
        elif 'ON' in ret:
            ret = {'value': 'ON'}
        elif 'OFF' in ret:
            ret = {'value': 'OFF'}
        else:
            ret = {'value': ret}
        return ret

    async def get_port(self, port, force_http=False, http_cmd='get', conv=True):
        """
        Запрос состояния порта. Состояние всегда возвращается в виде объекта, всегда сохраняется в центральное
        хранилище values
        """
        self.lg.debug(f'get port %s', port)
        if self.mqtt is None or force_http:
            if http_cmd == 'list' and conv:
                await self.request(pt=port, cmd='conv')
                await asyncio.sleep(1)
            ret = self.parse_response(await self.request(pt=port, cmd=http_cmd))
            ntry = 0
            while http_cmd == 'list' and ret is None and ntry < 3:
                await asyncio.sleep(1)
                ret = self.parse_response(await self.request(pt=port, cmd=http_cmd))
                ntry += 1
            self.lg.debug('parsed: %s', ret)
            self.values[port] = ret
            return ret

        async with self._notif_lck:
            async with self.notifiers[port]:
                cnd = self.notifiers[port]
                await self.mqtt.async_publish(
                    topic=f'{self.mqtt_id}/cmd',
                    payload=f'get:{port}',
                    qos=2,
                    retain=False,
                )
                try:
                    await asyncio.wait_for(cnd.wait(), timeout=10)
                    return self.values.get(port)
                except asyncio.TimeoutError:
                    self.lg.error(f'timeout when getting port {port}')

    @property
    def ports(self):
        return {e.port for e in self.entities}

    async def get_all_ports(self, only_out=False, check_skip=False):
        if not self.mqtt_inputs:
            ret = await self.request(cmd='all')
            for port, x in enumerate(ret.split(';')):
                if port in self.ds2413_ports:
                    continue
                if check_skip and not port in self.ports:
                    continue
                ret = self.parse_response(x)
                self.values[port] = ret
        elif not check_skip:
            for x in range(self.nports + 1):
                await self.get_port(x)
        else:
            for x in self.ports:
                await self.get_port(x)

    async def reboot(self, save=True):
        await self.save()

    async def _notify(self, port, value):
        async with self.notifiers[port]:
            cnd = self.notifiers[port]
            cnd.notify_all()

    def _process_msg(self, msg):
        try:
            d = msg.topic.split('/')
            port = d[-1]
        except ValueError:
            self.lg.warning('can not process %s', msg)
            return

        if port == 'cmd':
            return
        try:
            port = int(port)
        except:
            self.lg.warning('can not process %s', msg)
            return
        self.lg.debug(
            'process incomming message: %s', msg
        )
        value = None
        try:
            value = json.loads(msg.payload)
            if isinstance(value, dict):
                make_ints(value)
            self.values[port] = value
            for cb in self._callbacks[port]:
                cb(value)
            if isinstance(value, dict):
                value = value.copy()
                value['mega_id'] = self.id
                self.hass.bus.async_fire(
                    EVENT_BINARY_SENSOR,
                    value,
                )
        except Exception as exc:
            self.lg.warning(f'could not parse json ({msg.payload}): {exc}')
            return
        finally:
            asyncio.run_coroutine_threadsafe(self._notify(port, value), self.loop)

    def subscribe(self, port, callback):
        port = int(port)
        self.lg.debug(
            f'subscribe %s %s', port, callback
        )
        if self.mqtt_inputs:
            self._callbacks[port].append(callback)
        else:
            self.http.callbacks[self.id][port].append(callback)

    async def authenticate(self) -> bool:
        """Test if we can authenticate with the host."""
        async with aiohttp.request("get", url=f"http://{self.host}/{self.sec}") as req:
            if "Unauthorized" in await req.text():
                return False
            else:
                if req.status != 200:
                    raise CannotConnect
                return True

    async def get_port_page(self, port):
        url = f'http://{self.host}/{self.sec}/?pt={port}'
        self.lg.debug(f'get page for port {port} {url}')
        async with aiohttp.request('get', url) as req:
            return await req.text()

    async def scan_port(self, port):
        async with self.lck:
            if port in self._scanned:
                return self._scanned[port]
            url = f'http://{self.host}/{self.sec}/?pt={port}'
            self.lg.debug(
                f'scan port %s: %s', port, url
            )
            async with aiohttp.request('get', url) as req:
                html = await req.text()
                if req.status != 200:
                    return
            tree = BeautifulSoup(html, features="lxml")
            pty = tree.find('select', attrs={'name': 'pty'})
            if pty is None:
                return
            else:
                pty = pty.find(selected=True)
                if pty:
                    pty = pty['value']
                else:
                    return
            if pty in ['0', '1']:
                m = tree.find('select', attrs={'name': 'm'})
                if m:
                    m = m.find(selected=True)['value']
                self._scanned[port] = (pty, m)
                return pty, m
            elif pty == '3':
                m = tree.find('select', attrs={'name': 'd'})
                if m:
                    m = m.find(selected=True)['value']
                self._scanned[port] = (pty, m)
                return pty, m
            elif pty in ('2', '4'):  # эта часть не очень проработана, тут есть i2c который может работать неправильно
                m = tree.find('select', attrs={'name': 'd'})
                if m:
                    m = m.find(selected=True)['value']
                self._scanned[port] = (pty, m or '0')
                return pty, m or '0'

    async def scan_ports(self, nports=37):
        for x in range(0, nports+1):
            ret = await self.scan_port(x)
            if ret:
                yield [x, *ret]
        self.nports = nports+1

    async def get_config(self, nports=37):
        ret = defaultdict(lambda: defaultdict(list))
        async for port, pty, m in self.scan_ports(nports):
            if pty == "0":
                ret['binary_sensor'][port].append({})
            elif pty == "1" and (m in ['0', '1', '3'] or m is None):
                ret['light'][port].append({'dimmer': m == '1'})
            elif pty == "1" and m == "2":
                # ds2413
                _data = await self.get_port(port=port, force_http=True, http_cmd='list', conv=False)
                data = _data.get('value', {})
                if not isinstance(data, dict):
                    self.lg.warning(f'can not add ds2413 on port {port}, it has wrong data: {_data}')
                    continue
                for addr, state in data.items():
                    ret['light'][port].extend([
                        {"index": 0, "addr": addr, "id_suffix": f'{addr}_a', "http_cmd": 'ds2413'},
                        {"index": 1, "addr": addr, "id_suffix": f'{addr}_b', "http_cmd": 'ds2413'},
                    ])
            elif pty in ('3', '2', '4'):
                try:
                    http_cmd = 'get'
                    values = await self.get_port(port, force_http=True)
                    if values is None or (isinstance(values, dict) and str(values.get('value')) in ('', 'None')):
                        values = await self.get_port(port, force_http=True, http_cmd='list')
                        http_cmd = 'list'
                except asyncio.TimeoutError:
                    self.lg.warning(f'timout on port {port}')
                    continue
                self.lg.debug(f'values: %s', values)
                if values is None:
                    self.lg.warning(f'port {port} is of type sensor but response is None, skipping it')
                    continue
                if isinstance(values, dict) and 'value' in values:
                    values = values['value']
                if isinstance(values, str) and TEMP_PATT.search(values):
                    values = {TEMP: values}
                elif not isinstance(values, dict):
                    if pty == '4' and m in I2C_DEVICE_TYPES:
                        values = {I2C_DEVICE_TYPES[m]: values}
                    else:
                        values = {None: values}
                for key in values:
                    self.lg.debug(f'add sensor {key}')
                    ret['sensor'][port].append(dict(
                        key=key,
                        unit_of_measurement=UNITS.get(key, UNITS[TEMP]),
                        device_class=CLASSES.get(key, CLASSES[TEMP]),
                        id_suffix=key,
                        http_cmd=http_cmd,
                    ))
        return ret



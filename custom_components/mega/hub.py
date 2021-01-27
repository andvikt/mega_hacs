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
from homeassistant.const import DEVICE_CLASS_TEMPERATURE, DEVICE_CLASS_HUMIDITY
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from .const import TEMP, HUM, PATT_SPLIT, DOMAIN, CONF_HTTP, EVENT_BINARY_SENSOR
from .exceptions import CannotConnect
from .tools import make_ints

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

class NoPort(Exception):
    pass


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
            **kwargs,
    ):
        """Initialize."""
        if mqtt_inputs is None or mqtt_inputs == 'None' or mqtt_inputs is False:
            self.http = hass.data.get(DOMAIN, {}).get(CONF_HTTP)
            if not self.http is None:
                self.http.allowed_hosts |= {host}
        else:
            self.http = None
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
        self.entities: typing.List[Entity] = []
        self.poll_interval = scan_interval
        self.subs = None
        self.lg: logging.Logger = lg.getChild(self.id)
        self._scanned = {}
        self.sensors = []
        self.port_to_scan = port_to_scan
        self.last_update = datetime.now()
        self._callbacks: typing.DefaultDict[int, typing.List[typing.Callable[[dict], typing.Coroutine]]] = defaultdict(list)
        self._loop = loop
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

    async def poll(self):
        """
        Send get port 0 every poll_interval. When answer is received, mega.<id> becomes online else mega.<id> becomes
        offline
        """
        self.lg.debug('poll')
        if self.mqtt is None:
            await self.get_all_ports()
            await self.get_sensors(only_list=True)
            return
        if len(self.sensors) > 0:
            await self.get_sensors()
        else:
            await self.get_port(self.port_to_scan)
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
        if ':' in ret:
            ret = PATT_SPLIT.split(ret)
            ret = dict([
                x.split(':') for x in ret if x.count(':') == 1
            ])
        elif 'ON' in ret:
            ret = {'value': 'ON'}
        elif 'OFF' in ret:
            ret = {'value': 'OFF'}
        else:
            ret = {'value': ret}
        return ret

    async def get_port(self, port, force_http=False, http_cmd='get'):
        """
        Запрос состояния порта. Состояние всегда возвращается в виде объекта, всегда сохраняется в центральное
        хранилище values
        """
        self.lg.debug(f'get port %s', port)
        if self.mqtt is None or force_http:
            ret = await self.request(pt=port, cmd=http_cmd)
            ret = self.parse_response(ret)
            self.lg.debug('parsed: %s', ret)
            if http_cmd == 'list' and isinstance(ret, dict) and 'value' in ret:
                await asyncio.sleep(1)
                ret = await self.request(pt=port, http_cmd=http_cmd)
                ret = self.parse_response(ret)
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

    async def get_all_ports(self):
        if not self.mqtt_inputs:
            ret = await self.request(cmd='all')
            for port, x in enumerate(ret.split(';')):
                ret = self.parse_response(x)
                self.values[port] = ret
        else:
            for x in range(self.nports + 1):
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
            elif pty == '3':
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



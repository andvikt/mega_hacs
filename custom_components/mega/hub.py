import asyncio
import json
import logging
from functools import wraps

import aiohttp
import typing
from bs4 import BeautifulSoup

from homeassistant.components import mqtt
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from .exceptions import CannotConnect


class MegaD:
    """MegaD Hub"""

    def __init__(
            self,
            hass: HomeAssistant,
            host: str,
            password: str,
            mqtt: mqtt.MQTT,
            lg:logging.Logger,
            id: str,
            mqtt_id: str = None,
            scan_interval=60,
            port_to_scan=0,
            inverted:typing.List[int] = None,
            **kwargs,
    ):
        """Initialize."""
        self.hass = hass
        self.host = host
        self.sec = password
        self.mqtt = mqtt
        self.id = id
        self.lck = asyncio.Lock()
        self.is_alive = asyncio.Condition()
        self.online = True
        self.entities: typing.List[Entity] = []
        self.poll_interval = scan_interval
        self.subscriptions = []
        self.lg: logging.Logger = lg.getChild(self.id)
        self._scanned = {}
        self.sensors = []
        self.port_to_scan = port_to_scan
        self.inverted = inverted or []
        if not mqtt_id:
            _id = host.split(".")[-1]
            self.mqtt_id = f"megad/{_id}"
        else:
            self.mqtt_id = mqtt_id
            self._loop: asyncio.AbstractEventLoop = None

    async def add_entity(self, ent):
        async with self.lck:
            self.entities.append(ent)

    async def get_sensors(self):
        _ports = {x.port for x in self.sensors}
        for x in _ports:
            await self.get_port(x)
            await asyncio.sleep(self.poll_interval)

    async def poll(self):
        """
        Send get port 0 every poll_interval. When answer is received, mega.<id> becomes online else mega.<id> becomes
        offline
        """
        self._loop = asyncio.get_event_loop()
        if self.sensors:
            await self.subscribe(self.sensors[0].port, callback=self._notify)
        else:
            await self.subscribe(self.port_to_scan, callback=self._notify)
        while True:
            async with self.is_alive:
                if len(self.sensors) > 0:
                    await self.get_sensors()
                else:
                    await self.get_port(self.port_to_scan)

                try:
                    await asyncio.wait_for(self.is_alive.wait(), timeout=5)
                    self.hass.states.async_set(
                        f'mega.{self.id}',
                        'online',
                    )
                    self.online = True
                except asyncio.TimeoutError:
                    self.online = False
                    self.hass.states.async_set(
                        f'mega.{self.id}',
                        'offline',
                    )
                for x in self.entities:
                    try:
                        await x.async_update_ha_state()
                    except RuntimeError:
                        pass
            await asyncio.sleep(self.poll_interval)

    async def _async_notify(self):
        async with self.is_alive:
            self.is_alive.notify_all()

    def _notify(self, *args):
        asyncio.run_coroutine_threadsafe(self._async_notify(), self._loop)

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
        if port:
            url = f"http://{self.host}/{self.sec}/?pt={port}&cmd={cmd}"
        else:
            url = f"http://{self.host}/{self.sec}/?cmd={cmd}"
        self.lg.debug('run command: %s', url)
        async with self.lck:
            async with aiohttp.request("get", url=url) as req:
                if req.status != 200:
                    self.lg.warning('%s returned %s (%s)', url, req.status, await req.text())
                    return False
                else:
                    return True

    async def save(self):
        await self.send_command(cmd='s')

    async def get_port(self, port, get_value=False):
        if get_value:
            ftr = asyncio.get_event_loop().create_future()

            def cb(msg):
                try:
                    ftr.set_result(json.loads(msg.payload).get('value'))
                except Exception as exc:
                    self.lg.warning(f'could not parse {msg.payload}: {exc}')
            unsub = await self.mqtt.async_subscribe(
                topic=f'{self.mqtt_id}/{port}',
                msg_callback=cb,
                qos=1,
            )

        self.lg.debug(
            f'get port: %s', port
        )
        async with self.lck:
            await self.mqtt.async_publish(
                topic=f'{self.mqtt_id}/cmd',
                payload=f'get:{port}',
                qos=0,
                retain=False,
            )
            await asyncio.sleep(0.1)

        if get_value:
            try:
                return await asyncio.wait_for(ftr, timeout=2)
            except asyncio.TimeoutError:
                self.lg.warning(f'timeout on port {port}')
            finally:
                unsub()

    async def get_all_ports(self):
        for x in range(37):
            await self.get_port(x)

    async def reboot(self, save=True):
        await self.save()
        # await self.send_command(cmd=)

    async def subscribe(self, port, callback):

        @wraps(callback)
        def wrapper(msg):
            self.lg.debug(
                'process incomming message: %s', msg
            )
            return callback(msg)

        self.lg.debug(
            f'subscribe %s %s', port, wrapper
        )
        subs = await self.mqtt.async_subscribe(
            topic=f"{self.mqtt_id}/{port}",
            msg_callback=wrapper,
            qos=0,
        )
        self.subscriptions.append(subs)

    def unsubscribe_all(self):
        self.lg.info('unsubscribe')
        for x in self.subscriptions:
            self.lg.debug('unsubscribe %s', x)
            x()

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
        if port in self._scanned:
            return self._scanned[port]
        url = f'http://{self.host}/{self.sec}/?pt={port}'
        self.lg.debug(
            f'scan port %s: %s', port, url
        )
        async with aiohttp.request('get', url) as req:
            html = await req.text()
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

    async def scan_ports(self,):
        for x in range(37):
            ret = await self.scan_port(x)
            if ret:
                yield [x, *ret]

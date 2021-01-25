import asyncio
import logging

import typing
from collections import defaultdict

from aiohttp.web_request import Request
from aiohttp.web_response import Response

from homeassistant.helpers.template import Template
from .const import EVENT_BINARY_SENSOR, CONF_HTTP, DOMAIN, CONF_CUSTOM, CONF_RESPONSE_TEMPLATE
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import callback, HomeAssistant
from . import hub

_LOGGER = logging.getLogger(__name__).getChild('http')


class MegaView(HomeAssistantView):
    """Handle Yandex Smart Home unauthorized requests."""

    url = '/mega'
    name = 'mega'
    requires_auth = False

    def __init__(self, cfg: dict):
        self._try = 0
        self.allowed_hosts = {'::1'}
        self.callbacks: typing.DefaultDict[int, typing.List[typing.Callable[[dict], typing.Coroutine]]] \
            = defaultdict(list)
        self.templates: typing.Dict[str, typing.Dict[str, Template]] = {
            mid: {
                pt: cfg[mid][pt][CONF_RESPONSE_TEMPLATE]
                for pt in cfg[mid]
                if CONF_RESPONSE_TEMPLATE in cfg[mid][pt]
            } for mid in cfg
        }
        _LOGGER.debug('templates: %s', self.templates)

    async def get(self, request: Request) -> Response:
        auth = False
        for x in self.allowed_hosts:
            if request.remote.startswith(x):
                auth = True
                break
        if not auth:
            _LOGGER.warning(f'unauthorised attempt to connect from {request.remote}')
            return Response(status=401)

        hass: HomeAssistant = request.app['hass']
        hub: 'hub.MegaD' = hass.data.get(DOMAIN).get(request.remote)  # TODO: проверить какой remote
        if hub is None and request.remote == '::1':
            hub = hass.data.get(DOMAIN).get('__def')
        if hub is None:
            return Response(status=400)
        data = dict(request.query)
        hass.bus.async_fire(
            EVENT_BINARY_SENSOR,
            data,
        )
        _LOGGER.debug(f"Request: %s from '%s'", data, request.remote)
        make_ints(data)
        port = data.get('pt')
        data = data.copy()
        ret = 'd'
        if port is not None:
            for cb in self.callbacks[port]:
                cb(data)
            template: Template = self.templates.get(hub.id, {}).get(port)
            if hub.update_all:
                asyncio.create_task(self.later_update(hub))
            if template is not None:
                template.hass = hass
                ret = template.async_render(data)
        _LOGGER.debug('response %s', ret)
        ret = Response(body=ret or 'd', content_type='text/plain', headers={})
        ret.headers.clear()
        return ret

    async def later_update(self, hub):
        _LOGGER.debug('force update')
        await asyncio.sleep(1)
        await hub.updater.async_refresh()


def make_ints(d: dict):
    for x in d:
        try:
            d[x] = float(d[x])
        except ValueError:
            pass
    if 'm' not in d:
        d['m'] = 0
    if 'click' not in d:
        d['click'] = 0
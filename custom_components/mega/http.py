import asyncio
import logging

import typing
from collections import defaultdict

from aiohttp.web_request import Request
from aiohttp.web_response import Response

from homeassistant.helpers.template import Template
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant
from .const import EVENT_BINARY_SENSOR, DOMAIN, CONF_RESPONSE_TEMPLATE
from .tools import make_ints
from . import hub as h
_LOGGER = logging.getLogger(__name__).getChild('http')


class MegaView(HomeAssistantView):

    url = '/mega'
    name = 'mega'
    requires_auth = False

    def __init__(self, cfg: dict):
        self._try = 0
        self.allowed_hosts = {'::1'}
        self.callbacks = defaultdict(lambda: defaultdict(list))
        self.templates: typing.Dict[str, typing.Dict[str, Template]] = {
            mid: {
                pt: cfg[mid][pt][CONF_RESPONSE_TEMPLATE]
                for pt in cfg[mid]
                if isinstance(pt, int) and CONF_RESPONSE_TEMPLATE in cfg[mid][pt]
            } for mid in cfg if isinstance(cfg[mid], dict)
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
        hub: 'h.MegaD' = hass.data.get(DOMAIN).get(request.remote)  # TODO: проверить какой remote
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
        update_all = True
        if 'v' in data:
            update_all = False
            data['value'] = data.pop('v')
        data['mega_id'] = hub.id
        ret = 'd'
        if port is not None:
            hub.values[port] = data
            for cb in self.callbacks[hub.id][port]:
                cb(data)
            template: Template = self.templates.get(hub.id, {}).get(port)
            if hub.update_all and update_all:
                asyncio.create_task(self.later_update(hub))
            if template is not None:
                template.hass = hass
                ret = template.async_render(data)
        _LOGGER.debug('response %s', ret)
        ret = Response(body=ret or 'd', content_type='text/plain', headers={'Server': 's', 'Date': 'n'})
        return ret

    async def later_update(self, hub):
        _LOGGER.debug('force update')
        await asyncio.sleep(1)
        await hub.updater.async_refresh()


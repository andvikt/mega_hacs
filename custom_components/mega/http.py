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


def is_ext(data: typing.Dict[str, typing.Any]):
    for x in data:
        if x.startswith('ext'):
            return True


class MegaView(HomeAssistantView):

    url = '/mega'
    name = 'mega'
    requires_auth = False

    def __init__(self, cfg: dict):
        self._try = 0
        self.protected = True
        self.allowed_hosts = {'::1', '127.0.0.1'}
        self.notified_attempts = defaultdict(lambda : False)
        self.callbacks = defaultdict(lambda: defaultdict(list))
        self.templates: typing.Dict[str, typing.Dict[str, Template]] = {
            mid: {
                pt: cfg[mid][pt][CONF_RESPONSE_TEMPLATE]
                for pt in cfg[mid]
                if isinstance(pt, int) and CONF_RESPONSE_TEMPLATE in cfg[mid][pt]
            } for mid in cfg if isinstance(cfg[mid], dict)
        }
        _LOGGER.debug('templates: %s', self.templates)
        self.hubs = {}

    async def get(self, request: Request) -> Response:
        _LOGGER.debug('request from %s %s', request.remote, request.headers)
        hass: HomeAssistant = request.app['hass']
        if self.protected:
            auth = False
            for x in self.allowed_hosts:
                if request.remote.startswith(x):
                    auth = True
                    break
            if not auth:
                msg = f"Non-authorised request from {request.remote} to `/mega`. "\
                      f"If you want to accept requests from this host "\
                      f"please add it to allowed hosts in `mega` UI-configuration"
                if not self.notified_attempts[request.remote]:
                    await hass.services.async_call(
                        'persistent_notification',
                        'create',
                        {
                            "notification_id": request.remote,
                            "title": "Non-authorised request",
                            "message": msg
                        }
                    )
                _LOGGER.warning(msg)
                return Response(status=401)

        remote = request.headers.get('X-Real-IP', request.remote)
        hub: 'h.MegaD' = self.hubs.get(remote)
        if hub is None and 'mdid' in request.query:
            hub = self.hubs.get(request.query['mdid'])
            if hub is None:
                _LOGGER.warning(f'can not find mdid={request.query["mdid"]} in {list(self.hubs)}')
        if hub is None and request.remote in ['::1', '127.0.0.1']:
            try:
                hub = list(self.hubs.values())[0]
            except IndexError:
                _LOGGER.warning(f'can not find mdid={request.query["mdid"]} in {list(self.hubs)}')
                return Response(status=400)
        elif hub is None:
            return Response(status=400)
        data = dict(request.query)
        hass.bus.async_fire(
            EVENT_BINARY_SENSOR,
            data,
        )
        _LOGGER.debug(f"Request: %s from '%s'", data, request.remote)
        make_ints(data)
        if data.get('st') == '1':
            hass.async_create_task(self.later_restore(hub))
            return Response(status=200)
        port = data.get('pt')
        data = data.copy()
        update_all = True
        if 'v' in data:
            update_all = False
            data['value'] = data.pop('v')
        data['mega_id'] = hub.id
        ret = 'd' if hub.force_d else ''
        if port is not None:
            if is_ext(data):
                # ret = ''  # пока ответ всегда пустой, неясно какая будет реакция на непустой ответ
                if port in hub.extenders:
                    pt_orig = port
                else:
                    pt_orig = hub.ext_in.get(port, hub.ext_in.get(str(port)))
                if pt_orig is None:
                    hub.lg.warning(f'can not find extender for int port {port}, '
                                   f'have ext_int: {hub.ext_in}, ext: {hub.extenders}')
                    return Response(status=200)
                for e, v in data.items():
                    _data = data.copy()
                    if e.startswith('ext'):
                        idx = e[3:]
                        pt = f'{pt_orig}e{idx}' if not hub.new_naming else f'{int(pt_orig):02d}e{int(idx):02d}'
                        _data['pt_orig'] = pt_orig
                        _data['value'] = 'ON' if v == '1' else 'OFF'
                        _data['m'] = 1 if _data[e] == '0' else 0  # имитация поведения обычного входа, чтобы события обрабатывались аналогично
                        hub.values[pt] = _data
                        for cb in self.callbacks[hub.id][pt]:
                            cb(_data)
                        act = hub.ext_act.get(pt)
                        hub.lg.debug(f'act on port {pt}: {act}, all acts are: {hub.ext_act}')
                        template: Template = self.templates.get(hub.id, {}).get(port, hub.def_response)
                        if template is not None:
                            template.hass = hass
                            ret = template.async_render(_data)
                        hub.lg.debug(f'response={ret}, template={template}')
                        if ret == 'd' and act:
                            await hub.request(cmd=act.replace(':3', f':{v}'))
                        ret = 'd' if hub.force_d else ''
            else:
            # elif port in hub.binary_sensors:
                hub.values[port] = data
                for cb in self.callbacks[hub.id][port]:
                    cb(data)
                template: Template = self.templates.get(hub.id, {}).get(port, hub.def_response)
                if template is not None:
                    template.hass = hass
                    ret = template.async_render(data)
            if hub.update_all and update_all:
                asyncio.create_task(self.later_update(hub))
        _LOGGER.debug('response %s', ret)
        Response(body='' if hub.fake_response else ret, content_type='text/plain')

        if hub.fake_response and 'value' not in data and 'pt' in data and port in hub.binary_sensors:
            if 'd' in ret:
                await hub.request(pt=port, cmd=ret)
            else:
                await hub.request(cmd=ret)
        return ret

    async def later_restore(self, hub):
        """
        Восстановление всех выходов с небольшой задержкой. Задержка нужна чтобы ответ прошел успешно

        :param hub:
        :return:
        """
        await asyncio.sleep(0.2)
        if hub.restore_on_restart:
            await hub.restore_states()
        await hub.reload()

    async def later_update(self, hub):
        await asyncio.sleep(1)
        _LOGGER.debug('force update')
        await hub.updater.async_refresh()
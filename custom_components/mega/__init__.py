"""The mega integration."""
import asyncio
import logging
from functools import partial

import voluptuous as vol

from homeassistant.const import (
    CONF_SCAN_INTERVAL, CONF_ID, CONF_NAME, CONF_DOMAIN,
    CONF_UNIT_OF_MEASUREMENT, CONF_HOST
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.service import bind_hass
from homeassistant.helpers.template import Template
from homeassistant.helpers import config_validation as cv
from homeassistant.components import mqtt
from homeassistant.config_entries import ConfigEntry
from .const import DOMAIN, CONF_INVERT, CONF_RELOAD, PLATFORMS, CONF_PORTS, CONF_CUSTOM, CONF_SKIP, CONF_PORT_TO_SCAN, \
    CONF_MQTT_INPUTS, CONF_HTTP, CONF_RESPONSE_TEMPLATE, CONF_ACTION, CONF_GET_VALUE, CONF_ALLOW_HOSTS, \
    CONF_CONV_TEMPLATE, CONF_ALL, CONF_FORCE_D
from .hub import MegaD
from .config_flow import ConfigFlow
from .http import MegaView

_LOGGER = logging.getLogger(__name__)

CUSTOMIZE_PORT = vol.Schema({
    vol.Optional(CONF_SKIP, description='исключить порт из сканирования', default=False): bool,
    vol.Optional(CONF_INVERT, default=False): bool,
    vol.Optional(CONF_NAME): vol.Any(str, {
        vol.Required(str): str
    }),
    vol.Optional(CONF_DOMAIN): vol.Any('light', 'switch'),
    vol.Optional(CONF_UNIT_OF_MEASUREMENT, description='единицы измерений, либо строка либо мепинг'):
        vol.Any(str, {
            vol.Required(str): str
        }),
    vol.Optional(
        CONF_RESPONSE_TEMPLATE,
        description='шаблон ответа когда на этот порт приходит'
                    'сообщение из меги '): cv.template,
    vol.Optional(CONF_ACTION): cv.script_action, # пока не реализовано
    vol.Optional(CONF_GET_VALUE, default=True): bool,
    vol.Optional(CONF_CONV_TEMPLATE): cv.template
})
CUSTOMIZE_DS2413 = vol.Schema({
    vol.Optional(str.lower, description='адрес и индекс устройства'): CUSTOMIZE_PORT
})

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: {
            vol.Optional(CONF_ALLOW_HOSTS): [str],
            # vol.Optional(CONF_FORCE_D, description='Принудительно слать d после срабатывания входа', default=False): bool,
            vol.Required(str, description='id меги из веб-интерфейса'): {
                vol.Optional(CONF_FORCE_D, description='Принудительно слать d после срабатывания входа', default=False): bool,
                vol.Optional(int, description='номер порта'): vol.Any(
                    CUSTOMIZE_PORT,
                    CUSTOMIZE_DS2413,
                )
            }
        }
    },
    extra=vol.ALLOW_EXTRA,
)

ALIVE_STATE = 'alive'
DEF_ID = 'def'
_POLL_TASKS = {}
_hubs = {}
_subs = {}


async def async_setup(hass: HomeAssistant, config: dict):
    """YAML-конфигурация содержит только кастомизации портов"""
    hass.data[DOMAIN] = {CONF_CUSTOM: config.get(DOMAIN, {})}
    hass.data[DOMAIN][CONF_HTTP] = view = MegaView(cfg=config.get(DOMAIN, {}))
    hass.data[DOMAIN][CONF_ALL] = {}
    view.allowed_hosts |= set(config.get(DOMAIN, {}).get(CONF_ALLOW_HOSTS, []))
    hass.http.register_view(view)
    hass.services.async_register(
        DOMAIN, 'save', partial(_save_service, hass), schema=vol.Schema({
            vol.Optional('mega_id'): str
        })
    )
    hass.services.async_register(
        DOMAIN, 'get_port', partial(_get_port, hass), schema=vol.Schema({
            vol.Optional('mega_id'): str,
            vol.Optional('port'): vol.Any(int, [int]),
        })
    )
    hass.services.async_register(
        DOMAIN, 'run_cmd', partial(_run_cmd, hass), schema=vol.Schema({
            vol.Optional('port'): int,
            vol.Required('cmd'): str,
            vol.Optional('mega_id'): str,
        })
    )

    return True


async def get_hub(hass, entry):
    id = entry.data.get('id', entry.entry_id)
    data = dict(entry.data)
    data.update(entry.options or {})
    data.update(id=id)
    use_mqtt = data.get(CONF_MQTT_INPUTS, True)

    _mqtt = hass.data.get(mqtt.DOMAIN) if use_mqtt else None
    if _mqtt is None and use_mqtt:
        for x in range(5):
            await asyncio.sleep(5)
            _mqtt = hass.data.get(mqtt.DOMAIN)
            if _mqtt is not None:
                break
        if _mqtt is None:
            raise Exception('mqtt not configured, please configure mqtt first')
    hub = MegaD(hass, **data, mqtt=_mqtt, lg=_LOGGER, loop=asyncio.get_event_loop())
    hub.mqtt_id = await hub.get_mqtt_id()
    return hub


async def _add_mega(hass: HomeAssistant, entry: ConfigEntry):
    id = entry.data.get('id', entry.entry_id)
    hub = await get_hub(hass, entry)
    hass.data[DOMAIN][id] = hass.data[DOMAIN]['__def'] = hub
    hass.data[DOMAIN][entry.data.get(CONF_HOST)] = hub
    hass.data[DOMAIN][CONF_ALL][id] = hub
    if not await hub.authenticate():
        raise Exception("not authentificated")
    mid = await hub.get_mqtt_id()
    hub.mqtt_id = mid
    return hub


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    hub: MegaD = await _add_mega(hass, entry)
    _hubs[entry.entry_id] = hub
    _subs[entry.entry_id] = entry.add_update_listener(updater)
    await hub.start()
    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(
                entry, platform
            )
        )
    await hub.updater.async_refresh()
    return True


async def updater(hass: HomeAssistant, entry: ConfigEntry):
    """
    Обновляется конфигурация
    :param hass:
    :param entry:
    :return:
    """
    hub: MegaD = hass.data[DOMAIN][entry.data[CONF_ID]]
    hub.poll_interval = entry.options[CONF_SCAN_INTERVAL]
    hub.port_to_scan = entry.options.get(CONF_PORT_TO_SCAN, 0)
    entry.data = entry.options
    for platform in PLATFORMS:
        await hass.config_entries.async_forward_entry_unload(entry, platform)
    await async_remove_entry(hass, entry)
    await async_setup_entry(hass, entry)
    return True


async def async_remove_entry(hass, entry) -> None:
    """Handle removal of an entry."""
    id = entry.data.get('id', entry.entry_id)
    hub: MegaD = hass.data[DOMAIN][id]
    if hub is None:
        return
    _LOGGER.debug(f'remove {id}')
    _hubs.pop(id, None)
    hass.data[DOMAIN].pop(id, None)
    hass.data[DOMAIN][CONF_ALL].pop(id, None)
    task: asyncio.Task = _POLL_TASKS.pop(id, None)
    if task is not None:
        task.cancel()
    if hub is None:
        return
    await hub.stop()


async def async_migrate_entry(hass, config_entry: ConfigEntry):
    """Migrate old entry."""
    _LOGGER.debug("Migrating from version %s to version %s", config_entry.version, ConfigFlow.VERSION)
    hub = await get_hub(hass, config_entry)
    new = dict(config_entry.data)
    await hub.start()
    cfg = await hub.get_config()
    await hub.stop()
    new.update(cfg)
    _LOGGER.debug(f'new config: %s', new)
    config_entry.data = new
    config_entry.version = ConfigFlow.VERSION

    _LOGGER.info("Migration to version %s successful", config_entry.version)

    return True


async def _save_service(hass: HomeAssistant, call: ServiceCall):
    mega_id = call.data.get('mega_id')
    if mega_id:
        hub: MegaD = hass.data[DOMAIN][mega_id]
        await hub.save()
    else:
        for hub in hass.data[DOMAIN].values():
            if isinstance(hub, MegaD):
                await hub.save()


@bind_hass
async def _get_port(hass: HomeAssistant, call: ServiceCall):
    port = call.data.get('port')
    mega_id = call.data.get('mega_id')
    if mega_id:
        hub: MegaD = hass.data[DOMAIN][mega_id]
        if port is None:
            await hub.get_all_ports(check_skip=True)
        elif isinstance(port, int):
            await hub.get_port(port)
        elif isinstance(port, list):
            for x in port:
                await hub.get_port(x)
    else:
        for hub in hass.data[DOMAIN][CONF_ALL].values():
            if not isinstance(hub, MegaD):
                continue
            if port is None:
                await hub.get_all_ports(check_skip=True)
            elif isinstance(port, int):
                await hub.get_port(port)
            elif isinstance(port, list):
                for x in port:
                    await hub.get_port(x)


@bind_hass
async def _run_cmd(hass: HomeAssistant, call: ServiceCall):
    mega_id = call.data.get('mega_id')
    cmd = call.data.get('cmd')
    if mega_id:
        hub: MegaD = hass.data[DOMAIN][mega_id]
        await hub.request(cmd=cmd)
    else:
        for hub in hass.data[DOMAIN].values():
            await hub.request(cmd=cmd)

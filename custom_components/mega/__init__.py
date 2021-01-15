"""The mega integration."""
import asyncio
import logging
from functools import partial

import voluptuous as vol
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_SCAN_INTERVAL, CONF_ID
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.service import bind_hass
from homeassistant.components import mqtt
from homeassistant.config_entries import ConfigEntry
from .const import DOMAIN, CONF_INVERT, CONF_RELOAD, PLATFORMS
from .hub import MegaD


_LOGGER = logging.getLogger(__name__)
CONF_MQTT_ID = "mqtt_id"
CONF_PORT_TO_SCAN = 'port_to_scan'

MEGA = {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_MQTT_ID, default=""): str,
        vol.Optional(CONF_SCAN_INTERVAL, default=60): int,
        vol.Optional(CONF_PORT_TO_SCAN, default=0): int,
    }
MEGA_MAPPED = {str: MEGA}

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Any(MEGA, MEGA_MAPPED)
    },
    extra=vol.ALLOW_EXTRA,
)


ALIVE_STATE = 'alive'
DEF_ID = 'def'
_POLL_TASKS = {}
_hubs = {}
_subs = {}


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the mega component."""
    conf = config.get(DOMAIN)
    hass.data[DOMAIN] = {}
    hass.services.async_register(
        DOMAIN, 'save', partial(_save_service, hass), schema=vol.Schema({
            vol.Optional('mega_id'): str
        })
    )
    hass.services.async_register(
        DOMAIN, 'get_port', partial(_get_port, hass), schema=vol.Schema({
            vol.Optional('mega_id'): str,
            vol.Optional('port'): int,
        })
    )
    hass.services.async_register(
        DOMAIN, 'run_cmd', partial(_run_cmd, hass), schema=vol.Schema({
            vol.Required('port'): int,
            vol.Required('cmd'): str,
            vol.Optional('mega_id'): str,
        })
    )
    if conf is None:
        return True
    if CONF_HOST in conf:
        conf = {DEF_ID: conf}
    for id, data in conf.items():
        _LOGGER.warning('YAML configuration is deprecated, please use web-interface')
        await _add_mega(hass, id, data)

    for id, hub in hass.data[DOMAIN].items():
        _POLL_TASKS[id] = asyncio.create_task(hub.poll())
    return True


async def get_hub(hass, entry):
    id = entry.data.get('id', entry.entry_id)
    data = dict(entry.data)
    data.update(entry.options or {})
    data.update(id=id)
    _mqtt = hass.data.get(mqtt.DOMAIN)
    if _mqtt is None:
        raise Exception('mqtt not configured, please configure mqtt first')
    hub = MegaD(hass, **data, mqtt=_mqtt, lg=_LOGGER)
    return hub


async def _add_mega(hass: HomeAssistant, entry: ConfigEntry):
    id = entry.data.get('id', entry.entry_id)
    hub = await get_hub(hass, entry)
    hass.data[DOMAIN][id] = hub
    if not await hub.authenticate():
        raise Exception("not authentificated")
    mid = await hub.get_mqtt_id()
    hub.mqtt_id = mid
    return hub


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    hub = await _add_mega(hass, entry)
    _hubs[entry.entry_id] = hub
    _subs[entry.entry_id] = entry.add_update_listener(updater)

    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(
                entry, platform
            )
        )
    _POLL_TASKS[id] = asyncio.create_task(hub.poll())
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
    await async_remove_entry(hass, entry)
    await async_setup_entry(hass, entry)
    return True


async def async_remove_entry(hass, entry) -> None:
    """Handle removal of an entry."""
    id = entry.data.get('id', entry.entry_id)
    hub = hass.data[DOMAIN]
    if hub is None:
        return
    _LOGGER.debug(f'remove {id}')
    _hubs.pop(entry.entry_id)
    task: asyncio.Task = _POLL_TASKS.pop(id, None)
    if task is None:
        return
    task.cancel()
    if hub is None:
        return
    hub.unsubscribe_all()
    unsub = _subs.pop(entry.entry_id)
    if unsub:
        unsub()


async def async_migrate_entry(hass, config_entry: ConfigEntry):
    """Migrate old entry."""
    _LOGGER.debug("Migrating from version %s to version 2", config_entry.version)
    hub = await get_hub(hass, config_entry)
    new = dict(config_entry.data)
    if config_entry.version == 1:
        cfg = await hub.get_config()
        new.update(cfg)
        _LOGGER.debug(f'new config: %s', new)
        config_entry.data = new
        config_entry.version = 2

    _LOGGER.info("Migration to version %s successful", config_entry.version)

    return True


async def _save_service(hass: HomeAssistant, call: ServiceCall):
    mega_id = call.data.get('mega_id')
    if mega_id:
        hub: MegaD = hass.data[DOMAIN][mega_id]
        await hub.save()
    else:
        for hub in hass.data[DOMAIN].values():
            await hub.save()


@bind_hass
async def _get_port(hass: HomeAssistant, call: ServiceCall):
    port = call.data.get('port')
    mega_id = call.data.get('mega_id')
    if mega_id:
        hub: MegaD = hass.data[DOMAIN][mega_id]
        if port is None:
            await hub.get_all_ports()
        else:
            await hub.get_port(port)
    else:
        for hub in hass.data[DOMAIN].values():
            if port is None:
                await hub.get_all_ports()
            else:
                await hub.get_port(port)


@bind_hass
async def _run_cmd(hass: HomeAssistant, call: ServiceCall):
    port = call.data.get('port')
    mega_id = call.data.get('mega_id')
    cmd = call.data.get('cmd')
    if mega_id:
        hub: MegaD = hass.data[DOMAIN][mega_id]
        await hub.send_command(port=port, cmd=cmd)
    else:
        for hub in hass.data[DOMAIN].values():
            await hub.send_command(port=port, cmd=cmd)

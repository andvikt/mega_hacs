"""The mega integration."""
import asyncio
import logging

import voluptuous as vol
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_SCAN_INTERVAL, CONF_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers.service import bind_hass
from homeassistant.components import mqtt
from homeassistant.config_entries import ConfigEntry
from .const import DOMAIN, CONF_INVERT, CONF_RELOAD
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

PLATFORMS = [
    "light",
    "binary_sensor",
    "sensor",
]
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
        DOMAIN, 'save', _save_service, schema=vol.Schema({
            vol.Optional('mega_id'): str
        })
    )
    hass.services.async_register(
        DOMAIN, 'get_port', _get_port, schema=vol.Schema({
            vol.Optional('mega_id'): str,
            vol.Optional('port'): int,
        })
    )
    hass.services.async_register(
        DOMAIN, 'run_cmd', _run_cmd, schema=vol.Schema({
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


async def _add_mega(hass: HomeAssistant, id, data: dict):
    data.update(id=id)
    _mqtt = hass.data.get(mqtt.DOMAIN)
    if _mqtt is None:
        raise Exception('mqtt not configured, please configure mqtt first')
    hass.data[DOMAIN][id] = hub = MegaD(hass, **data, mqtt=_mqtt, lg=_LOGGER)
    if not await hub.authenticate():
        raise Exception("not authentificated")
    mid = await hub.get_mqtt_id()
    hub.mqtt_id = mid
    return hub


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    id = entry.data.get('id', entry.entry_id)
    data = dict(entry.data)
    data.update(entry.options or {})
    hub = await _add_mega(hass, id, data)
    _hubs[entry.entry_id] = hub
    _subs[entry.entry_id] = entry.add_update_listener(update)

    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(
                entry, platform
            )
        )
    _POLL_TASKS[id] = asyncio.create_task(hub.poll())
    return True


async def update(hass: HomeAssistant, entry: ConfigEntry):
    hub: MegaD = hass.data[DOMAIN][entry.data[CONF_ID]]
    hub.poll_interval = entry.options[CONF_SCAN_INTERVAL]
    hub.port_to_scan = entry.options[CONF_PORT_TO_SCAN]
    if entry.options[CONF_RELOAD]:
        await async_remove_entry(hass, entry)
        await async_setup_entry(hass, entry)
    return True


async def async_remove_entry(hass, entry) -> None:
    """Handle removal of an entry."""
    id = entry.data.get('id', entry.entry_id)
    hass.data[DOMAIN][id].unsubscribe_all()
    task: asyncio.Task = _POLL_TASKS.pop(id)
    task.cancel()
    _hubs.pop(entry.entry_id)
    unsub = _subs.pop(entry.entry_id)
    unsub()


@bind_hass
async def _save_service(hass: HomeAssistant, mega_id=None):
    if mega_id:
        hub: MegaD = hass.data[DOMAIN][mega_id]
        await hub.save()
    else:
        for hub in hass.data[DOMAIN].values():
            await hub.save()


@bind_hass
async def _get_port(hass: HomeAssistant, port=None, mega_id=None):
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
async def _run_cmd(hass: HomeAssistant, port: int, cmd: str, mega_id=None):
    if mega_id:
        hub: MegaD = hass.data[DOMAIN][mega_id]
        await hub.send_command(port=port, cmd=cmd)
    else:
        for hub in hass.data[DOMAIN].values():
            await hub.send_command(port=port, cmd=cmd)

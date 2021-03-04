"""Platform for light integration."""
import logging

import voluptuous as vol

from homeassistant.components.switch import (
    PLATFORM_SCHEMA as LIGHT_SCHEMA,
    SwitchEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_NAME,
    CONF_PORT,
    CONF_ID,
    CONF_DOMAIN,
)
from homeassistant.core import HomeAssistant
from . import hub as h
from .entities import MegaOutPort
from .const import CONF_DIMMER, CONF_SWITCH, DOMAIN, CONF_CUSTOM, CONF_SKIP
from .tools import int_ignore

_LOGGER = lg = logging.getLogger(__name__)


# Validation of the user's configuration
_EXTENDED = {
    vol.Required(CONF_PORT): int,
    vol.Optional(CONF_NAME): str,
}
_ITEM = vol.Any(int, _EXTENDED)
DIMMER = {vol.Required(CONF_DIMMER): [_ITEM]}
SWITCH = {vol.Required(CONF_SWITCH): [_ITEM]}
PLATFORM_SCHEMA = LIGHT_SCHEMA.extend(
    {
        vol.Optional(str, description="mega id"): [_ITEM],
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup_platform(hass, config, add_entities, discovery_info=None):
    lg.warning('mega integration does not support yaml for switches, please use UI configuration')
    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_devices):
    mid = config_entry.data[CONF_ID]
    hub: 'h.MegaD' = hass.data['mega'][mid]
    devices = []

    customize = hass.data.get(DOMAIN, {}).get(CONF_CUSTOM, {})
    for port, cfg in config_entry.data.get('light', {}).items():
        port = int_ignore(port)
        c = customize.get(mid, {}).get(port, {})
        if c.get(CONF_SKIP, False) or c.get(CONF_DOMAIN, 'light') != 'switch':
            continue
        for data in cfg:
            hub.lg.debug(f'add switch on port %s with data %s', port, data)
            light = MegaSwitch(mega=hub, port=port, config_entry=config_entry, **data)
            if '<' in light.name:
                continue
            devices.append(light)
    async_add_devices(devices)


class MegaSwitch(MegaOutPort, SwitchEntity):
    pass

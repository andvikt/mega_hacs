"""Platform for light integration."""
import asyncio
import json
import logging

import voluptuous as vol

from homeassistant.components.binary_sensor import (
    PLATFORM_SCHEMA as SENSOR_SCHEMA,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_NAME,
    CONF_PLATFORM,
    CONF_PORT,
    CONF_UNIQUE_ID,
    CONF_ID
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.restore_state import RestoreEntity
from .entities import BaseMegaEntity

from .hub import MegaD

lg = logging.getLogger(__name__)


# Validation of the user's configuration
_EXTENDED = {
    vol.Required(CONF_PORT): int,
    vol.Optional(CONF_NAME): str,
    vol.Optional(CONF_UNIQUE_ID): str,
}
_ITEM = vol.Any(int, _EXTENDED)
PLATFORM_SCHEMA = SENSOR_SCHEMA.extend(
    {
        vol.Optional(str, description="mega id"): [_ITEM]
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup_platform(hass, config, add_entities, discovery_info=None):
    config.pop(CONF_PLATFORM)
    ents = []
    for mid, _config in config.items():
        for x in _config:
            if isinstance(x, int):
                ent = MegaBinarySensor(
                    mega_id=mid, port=x
                )
            else:
                ent = MegaBinarySensor(
                    mega_id=mid, port=x[CONF_PORT], name=x[CONF_NAME]
                )
            ents.append(ent)
    add_entities(ents)
    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_devices):
    mid = config_entry.data[CONF_ID]
    hub: MegaD = hass.data['mega'][mid]
    devices = []
    async for port, pty, m in hub.scan_ports():
        if pty == "0":
            sensor = MegaBinarySensor(mega_id=mid, port=port)
            devices.append(sensor)

    async_add_devices(devices)


class MegaBinarySensor(BinarySensorEntity, BaseMegaEntity):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._is_on = None

    @property
    def is_on(self) -> bool:
        if self._is_on is not None:
            return self._is_on
        return self._state == 'ON'

    def _update(self, payload: dict):
        val = payload.get("value")
        self._is_on = val == 'ON'
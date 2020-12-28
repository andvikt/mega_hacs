"""Platform for light integration."""
import asyncio
import json
import logging

import voluptuous as vol

from homeassistant.components.light import (
    PLATFORM_SCHEMA as LIGHT_SCHEMA,
    SUPPORT_BRIGHTNESS,
    LightEntity,
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
from .const import CONF_DIMMER, CONF_SWITCH


lg = logging.getLogger(__name__)


# Validation of the user's configuration
_EXTENDED = {
    vol.Required(CONF_PORT): int,
    vol.Optional(CONF_NAME): str,
    vol.Optional(CONF_UNIQUE_ID): str,
}
_ITEM = vol.Any(int, _EXTENDED)
DIMMER = {vol.Required(CONF_DIMMER): [_ITEM]}
SWITCH = {vol.Required(CONF_SWITCH): [_ITEM]}
PLATFORM_SCHEMA = LIGHT_SCHEMA.extend(
    {
        vol.Optional(str, description="mega id"): {
            vol.Optional("dimmer", default=[]): [_ITEM],
            vol.Optional("switch", default=[]): [_ITEM],
        }
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup_platform(hass, config, add_entities, discovery_info=None):
    config.pop(CONF_PLATFORM)
    ents = []
    for mid, _config in config.items():
        for x in _config["dimmer"]:
            if isinstance(x, int):
                ent = MegaLight(
                    mega_id=mid, port=x, dimmer=True)
            else:
                ent = MegaLight(
                    mega_id=mid, port=x[CONF_PORT], name=x[CONF_NAME], dimmer=True
                )
            ents.append(ent)
        for x in _config["switch"]:
            if isinstance(x, int):
                ent = MegaLight(
                    mega_id=mid, port=x, dimmer=False
                )
            else:
                ent = MegaLight(
                    mega_id=mid, port=x[CONF_PORT], name=x[CONF_NAME], dimmer=False
                )
            ents.append(ent)
    add_entities(ents)
    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_devices):
    mid = config_entry.data[CONF_ID]
    hub: MegaD = hass.data['mega'][mid]
    devices = []
    async for port, pty, m in hub.scan_ports():
        if pty == "1" and m in ['0', '1']:
            light = MegaLight(mega_id=mid, port=port, dimmer=m == '1')
            devices.append(light)
    async_add_devices(devices)


class MegaLight(LightEntity, BaseMegaEntity):

    def __init__(
            self,
            dimmer=False,
            *args, **kwargs
    ):
        super().__init__(
            *args, **kwargs
        )
        self._brightness = None
        self._is_on = None
        self.dimmer = dimmer

    @property
    def brightness(self):
        if self._brightness is not None:
            return self._brightness
        if self._state:
            return self._state.attributes.get("brightness")

    @property
    def supported_features(self):
        return SUPPORT_BRIGHTNESS if self.dimmer else 0

    @property
    def is_on(self) -> bool:
        if self._is_on is not None:
            return self._is_on
        return self._state == 'ON'

    async def async_turn_on(self, brightness=None, **kwargs) -> None:
        brightness = brightness or self.brightness
        if self.dimmer and brightness == 0:
            cmd = 255
        elif self.dimmer:
            cmd = brightness
        else:
            cmd = 1
        if await self.mega.send_command(self.port, f"{self.port}:{cmd}"):
            self._is_on = True
            self._brightness = brightness
        await self.async_update_ha_state()

    async def async_turn_off(self, **kwargs) -> None:

        cmd = "0"

        if await self.mega.send_command(self.port, f"{self.port}:{cmd}"):
            self._is_on = False
        await self.async_update_ha_state()

    def _update(self, payload: dict):
        val = payload.get("value")
        try:
            val = int(val)
        except Exception:
            pass
        if isinstance(val, int):
            self._is_on = val
            if val > 0:
                self._brightness = val
        else:
            self._is_on = val == 'ON'


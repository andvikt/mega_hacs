"""Platform for light integration."""
import json
import logging

import voluptuous as vol

from homeassistant.components.switch import (
    PLATFORM_SCHEMA as LIGHT_SCHEMA,
    SwitchEntity,
)
from homeassistant.const import (
    CONF_NAME,
    CONF_PLATFORM,
    CONF_PORT,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.restore_state import RestoreEntity
from .entities import BaseMegaEntity

from .hub import MegaD
from .const import CONF_DIMMER, CONF_SWITCH

_LOGGER = logging.getLogger(__name__)


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
    config.pop(CONF_PLATFORM)
    ents = []
    for mid, _config in config.items():
        mega = hass.data["mega"][mid]
        for x in _config:
            if isinstance(x, int):
                ent = MegaSwitch(hass, mega=mega, port=x)
            else:
                ent = MegaSwitch(
                    hass, mega=mega, port=x[CONF_PORT], name=x[CONF_NAME]
                )
            ents.append(ent)

    add_entities(ents)
    return True


class MegaSwitch(SwitchEntity, BaseMegaEntity):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._is_on = None

    @property
    def is_on(self) -> bool:
        if self._is_on is not None:
            return self._is_on
        return self._state == 'ON'

    async def async_turn_on(self, **kwargs) -> None:
        cmd = 1
        if await self.mega.send_command(self.port, f"{self.port}:{cmd}"):
            self._is_on = True
        await self.async_update_ha_state()

    async def async_turn_off(self, **kwargs) -> None:

        cmd = "0"

        if await self.mega.send_command(self.port, f"{self.port}:{cmd}"):
            self._is_on = False
        await self.async_update_ha_state()

    def _update(self, payload: dict):
        val = payload.get("value")
        self._is_on = val == 'ON'

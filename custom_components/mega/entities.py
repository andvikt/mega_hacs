import asyncio

import json
import logging

from homeassistant.core import State
from .hub import MegaD
from homeassistant.helpers.restore_state import RestoreEntity
from .const import DOMAIN


class BaseMegaEntity(RestoreEntity):
    """
    Base Mega's entity. It is responsible for storing reference to mega hub
    Also provides some basic entity information: unique_id, name, availiability
    It also makes subscription to port states
    """
    def __init__(
            self,
            mega_id: str,
            port: int,
            id_suffix=None,
            name=None,
            unique_id=None
    ):
        self._state: State = None
        self.port = port
        self._name = name
        self._mega_id = mega_id
        self._lg = None
        self._unique_id = unique_id or f"mega_{mega_id}_{port}" + \
                                       (f"_{id_suffix}" if id_suffix else "")

    @property
    def lg(self) -> logging.Logger:
        if self._lg is None:
            self._lg = self.mega.lg.getChild(self._name or self.unique_id)
        return self._lg

    @property
    def mega(self) -> MegaD:
        return self.hass.data[DOMAIN][self._mega_id]

    @property
    def available(self) -> bool:
        return self.mega.online

    @property
    def name(self):
        return self._name or f"{self.mega.id}_p{self.port}"

    @property
    def unique_id(self):
        return self._unique_id

    async def async_added_to_hass(self) -> None:
        await self.mega.subscribe(self.port, callback=self.__update)
        self._state = await self.async_get_last_state()
        await asyncio.sleep(0.1)
        await self.mega.get_port(self.port)

    def __update(self, msg):
        try:
            value = json.loads(msg.payload)
        except Exception as exc:
            self.lg.warning(f'could not parse json ({msg.payload}): {exc}')
            return
        self._update(value)
        self.hass.async_create_task(self.async_update_ha_state())
        self.lg.debug(f'state after update %s', self.state)
        return

    def _update(self, payload: dict):
        raise NotImplementedError

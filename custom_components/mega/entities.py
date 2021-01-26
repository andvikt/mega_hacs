import logging
import asyncio
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import State
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.restore_state import RestoreEntity
from .hub import MegaD
from .const import DOMAIN, CONF_CUSTOM, CONF_INVERT


class BaseMegaEntity(CoordinatorEntity, RestoreEntity):
    """
    Base Mega's entity. It is responsible for storing reference to mega hub
    Also provides some basic entity information: unique_id, name, availiability
    All base entities are polled in order to be online or offline
    """
    def __init__(
            self,
            mega: MegaD,
            port: int,
            config_entry: ConfigEntry = None,
            id_suffix=None,
            name=None,
            unique_id=None,
    ):
        super().__init__(mega.updater)
        self._state: State = None
        self.port = port
        self.config_entry = config_entry
        self.mega = mega
        mega.entities.append(self)
        self._mega_id = mega.id
        self._lg = None
        self._unique_id = unique_id or f"mega_{mega.id}_{port}" + \
                                       (f"_{id_suffix}" if id_suffix else "")
        self._name = name or f"{mega.id}_{port}" + \
                            (f"_{id_suffix}" if id_suffix else "")
        self._customize: dict = None

    @property
    def customize(self):
        if self.hass is None:
            return {}
        if self._customize is None:
            c = self.hass.data.get(DOMAIN, {}).get(CONF_CUSTOM) or {}
            c = c.get(self._mega_id) or {}
            c = c.get(self.port) or {}
            self._customize = c
        return self._customize

    @property
    def device_info(self):
        return {
            "identifiers": {
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, f'{self._mega_id}', self.port),
            },
            "config_entries": [
                self.config_entry,
            ],
            "name": f'{self._mega_id} port {self.port}',
            "manufacturer": 'ab-log.ru',
            # "model": self.light.productname,
            # "sw_version": self.light.swversion,
            "via_device": (DOMAIN, self._mega_id),
        }

    @property
    def lg(self) -> logging.Logger:
        if self._lg is None:
            self._lg = self.mega.lg.getChild(self._name or self.unique_id)
        return self._lg

    @property
    def available(self) -> bool:
        return self.mega.online

    @property
    def name(self):
        c = self.customize.get(CONF_NAME)
        if not isinstance(c, str):
            c = self._name or f"{self.mega.id}_p{self.port}"
        return c

    @property
    def unique_id(self):
        return self._unique_id

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._state = await self.async_get_last_state()

    async def get_state(self):
        if self.mega.mqtt is None:
            self.async_write_ha_state()


class MegaPushEntity(BaseMegaEntity):

    """
    Updates on messages from mqtt
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mega.subscribe(self.port, callback=self.__update)
        self.is_first_update = True

    def __update(self, value: dict):
        self._update(value)
        self.async_write_ha_state()
        self.lg.debug(f'state after update %s', self.state)
        self.is_first_update = False
        return

    def _update(self, payload: dict):
        pass

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if self.mega.mqtt is not None:
            asyncio.create_task(self.mega.get_port(self.port))


class MegaOutPort(MegaPushEntity):

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
    def invert(self):
        return self.customize.get(CONF_INVERT, False)

    @property
    def brightness(self):
        val = self.mega.values.get(self.port, {}).get("value")
        if val is None and self._state is not None:
            return self._state.attributes.get("brightness")
        elif val is not None:
            try:
                val = int(val)
                return val
            except Exception:
                pass

    @property
    def is_on(self) -> bool:
        val = self.mega.values.get(self.port, {})

        if val is None and self._state is not None:
            return self._state == 'ON'
        elif val is not None:
            val = val.get("value")
            if not self.invert:
                return val == 'ON' or str(val) == '1' or (safe_int(val) is not None and safe_int(val) > 0)
            else:
                return val == 'OFF' or str(val) == '0' or (safe_int(val) is not None and safe_int(val) == 0)

    async def async_turn_on(self, brightness=None, **kwargs) -> None:
        brightness = brightness or self.brightness or 255

        if self.dimmer and brightness == 0:
            cmd = 255
        elif self.dimmer:
            cmd = brightness
        else:
            cmd = 1 if not self.invert else 0
        await self.mega.send_command(self.port, f"{self.port}:{cmd}")
        self.mega.values[self.port] = {'value': cmd}
        await self.get_state()


    async def async_turn_off(self, **kwargs) -> None:

        cmd = "0" if not self.invert else "1"

        await self.mega.send_command(self.port, f"{self.port}:{cmd}")
        self.mega.values[self.port] = {'value': cmd}
        await self.get_state()


def safe_int(v):
    if v in ['ON', 'OFF']:
        return None
    try:
        return int(v)
    except (ValueError, TypeError):
        return None
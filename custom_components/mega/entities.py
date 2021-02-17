import logging
import asyncio

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import State
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.restore_state import RestoreEntity
from . import hub as h
from .const import DOMAIN, CONF_CUSTOM, CONF_INVERT, EVENT_BINARY_SENSOR, LONG, \
    LONG_RELEASE, RELEASE, PRESS, SINGLE_CLICK, DOUBLE_CLICK, EVENT_BINARY

_events_on = False
_LOGGER = logging.getLogger(__name__)


async def _set_events_on():
    global _events_on, _task_set_ev_on
    await asyncio.sleep(10)
    _LOGGER.debug('events on')
    _events_on = True


def set_events_off():
    global _events_on, _task_set_ev_on
    _events_on = False
    _task_set_ev_on = None

_task_set_ev_on = None


class BaseMegaEntity(CoordinatorEntity, RestoreEntity):
    """
    Base Mega's entity. It is responsible for storing reference to mega hub
    Also provides some basic entity information: unique_id, name, availiability
    All base entities are polled in order to be online or offline
    """
    def __init__(
            self,
            mega: 'h.MegaD',
            port: int,
            config_entry: ConfigEntry = None,
            id_suffix=None,
            name=None,
            unique_id=None,
            http_cmd='get',
            addr: str=None,
            index=None,
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
        self.http_cmd = http_cmd
        self.index = index
        self.addr = addr

    @property
    def customize(self):
        if self.hass is None:
            return {}
        if self._customize is None:
            c = self.hass.data.get(DOMAIN, {}).get(CONF_CUSTOM) or {}
            c = c.get(self._mega_id) or {}
            c = c.get(self.port) or {}
            if self.addr is not None and self.index is not None and isinstance(c, dict):
                idx = self.addr.lower() + f'_a' if self.index == 0 else '_b'
                c = c.get(idx, {})
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
        global _task_set_ev_on
        await super().async_added_to_hass()
        self._state = await self.async_get_last_state()
        if self.mega.mqtt_inputs and _task_set_ev_on is None:
            _task_set_ev_on = asyncio.create_task(_set_events_on())

    async def get_state(self):
        self.lg.debug(f'state is %s', self.state)
        if not self.mega.mqtt_inputs:
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
        if self.mega.mqtt_inputs and not _events_on:
            _LOGGER.debug('skip event because events are off')
            return
        if not self.entity_id.startswith('binary_sensor'):
            _LOGGER.debug('skip event because not a bnary sens')
            return
        ll: bool = self.mega.last_long.get(self.port, False)
        if safe_int(value.get('click', 0)) == 1:
            self.hass.bus.async_fire(
                event_type=EVENT_BINARY,
                event_data={
                    'entity_id': self.entity_id,
                    'type': SINGLE_CLICK
                }
            )
        elif safe_int(value.get('click', 0)) == 2:
            self.hass.bus.async_fire(
                event_type=EVENT_BINARY,
                event_data={
                    'entity_id': self.entity_id,
                    'type': DOUBLE_CLICK
                }
            )
        elif safe_int(value.get('m', 0)) == 2:
            self.mega.last_long[self.port] = True
            self.hass.bus.async_fire(
                event_type=EVENT_BINARY,
                event_data={
                    'entity_id': self.entity_id,
                    'type': LONG
                }
            )
        elif safe_int(value.get('m', 0)) == 1:
            self.hass.bus.async_fire(
                event_type=EVENT_BINARY,
                event_data={
                    'entity_id': self.entity_id,
                    'type': LONG_RELEASE if ll else RELEASE,
                }
            )
        elif safe_int(value.get('m', None)) == 0:
            self.hass.bus.async_fire(
                event_type=EVENT_BINARY,
                event_data={
                    'entity_id': self.entity_id,
                    'type': PRESS,
                }
            )
            self.mega.last_long[self.port] = False
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

    # @property
    # def assumed_state(self) -> bool:
    #     return True if self.index is not None or self.mega.mqtt is None else False

    @property
    def invert(self):
        return self.customize.get(CONF_INVERT, False)

    @property
    def brightness(self):
        if not self.dimmer:
            return
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
            if self.index and self.addr:
                if not isinstance(val, dict):
                    self.mega.lg.warning(f'{self} has wrong state: {val}')
                    return
                _val = val.get(self.addr)
                if not isinstance(val, str):
                    self.mega.lg.warning(f'{self} has wrong state: {val}')
                    return
                _val = _val.split('/')
                if len(_val) >= 2:
                    val = val[self.index]
                else:
                    self.mega.lg.warning(f'{self} has wrong state: {val}')
                    return
            elif self.index and self.addr is None:
                self.mega.lg.warning(f'{self} does not has addr')
                return

            if not self.invert:
                return val == 'ON' or str(val) == '1' or (safe_int(val) is not None and safe_int(val) > 0)
            else:
                return val == 'OFF' or str(val) == '0' or (safe_int(val) is not None and safe_int(val) == 0)

    @property
    def cmd_port(self):
        if self.index is not None:
            return f'{self.port}A' if self.index == 0 else f'{self.port}B'
        else:
            return self.port

    async def async_turn_on(self, brightness=None, **kwargs) -> None:
        brightness = brightness or self.brightness or 255

        if self.dimmer and brightness == 0:
            cmd = 255
        elif self.dimmer:
            cmd = brightness
        else:
            cmd = 1 if not self.invert else 0
        _cmd = {"cmd": f"{self.cmd_port}:{cmd}"}
        if self.addr:
            _cmd['addr'] = self.addr
        await self.mega.request(**_cmd)
        if self.index is not None:
            # обновление текущего стейта для ds2413
            await self.mega.get_port(
                port=self.port,
                force_http=True,
                conv=False,
                http_cmd='list',
            )
        else:
            self.mega.values[self.port] = {'value': cmd}
        await self.get_state()

    async def async_turn_off(self, **kwargs) -> None:

        cmd = "0" if not self.invert else "1"
        _cmd = {"cmd": f"{self.cmd_port}:{cmd}"}
        if self.addr:
            _cmd['addr'] = self.addr
        await self.mega.request(**_cmd)
        if self.index is not None:
            # обновление текущего стейта для ds2413
            await self.mega.get_port(
                port=self.port,
                force_http=True,
                conv=False,
                http_cmd='list',
            )
        else:
            self.mega.values[self.port] = {'value': cmd}
        await self.get_state()


def safe_int(v):
    if v in ['ON', 'OFF']:
        return None
    try:
        return int(v)
    except (ValueError, TypeError):
        return None
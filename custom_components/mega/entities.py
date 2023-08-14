import logging
import asyncio
import time
import typing
from datetime import timedelta
from functools import partial

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import State
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.restore_state import RestoreEntity
from . import hub as h
from .const import DOMAIN, CONF_CUSTOM, CONF_INVERT, EVENT_BINARY_SENSOR, LONG, \
    LONG_RELEASE, RELEASE, PRESS, SINGLE_CLICK, DOUBLE_CLICK, EVENT_BINARY, CONF_SMOOTH, CONF_RANGE

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
            port: typing.Union[int, str, typing.List[int]],
            config_entry: ConfigEntry = None,
            id_suffix=None,
            name=None,
            unique_id=None,
            http_cmd='get',
            addr: str=None,
            index=None,
            customize=None,
            smooth=None,
            **kwargs,
    ):
        self._smooth = smooth
        self.http_cmd = http_cmd
        self._state: State = None
        self.port = port
        self.config_entry = config_entry
        self.mega = mega
        mega.entities.append(self)
        self._mega_id = mega.id
        self._lg = None
        if not isinstance(port, list):
            self._unique_id = unique_id or f"mega_{mega.id}_{port}" + \
                                           (f"_{id_suffix}" if id_suffix else "")
            _pt = port if not mega.new_naming else f'{port:02}' if isinstance(port, int) else port
            self._name = name or f"{mega.id}_{_pt}" + \
                         (f"_{id_suffix}" if id_suffix else "")
            self._customize: dict = None
        else:
            assert id_suffix is not None
            assert name is not None
            assert isinstance(customize, dict)
            self._unique_id = unique_id or f"mega_{mega.id}_{id_suffix}"
            self._name = name
            self._customize = customize

        self.index = index
        self.addr = addr
        self.id_suffix = id_suffix
        self._can_smooth_hard = None
        if self.http_cmd == 'ds2413':
            self.mega.ds2413_ports |= {self.port}
        super().__init__(coordinator=mega.updater)

    @property
    def is_ws(self):
        return False

    def get_attribute(self, name, default=None):
        attr = getattr(self, f'_{name}', None)
        if attr is None and self._state is not None:
            if name == 'is_on':
                attr = self._state.state
            else:
                attr = self._state.attributes.get(f'{name}', default)
        return attr if attr is not None else default

    @property
    def can_smooth_hardware(self):
        if self._can_smooth_hard is None:
            if self.is_ws:
                self._can_smooth_hard = False
            if not isinstance(self.port, list):
                self._can_smooth_hard = self.port in self.mega.smooth
            else:
                for x in self.port:
                    if isinstance(x, str):
                        self._can_smooth_hard = False
                        break
                    else:
                        self._can_smooth_hard = self.port in self.mega.smooth
        return self._can_smooth_hard

    @property
    def enabled(self):
        if '<' in self.name:
            return False
        else:
            return super().enabled

    @property
    def customize(self):
        if self._customize is not None:
            return self._customize
        if self.hass is None or self.entity_id is None:
            return {}
        if self._customize is None:
            c_entity_id = self.hass.data.get(DOMAIN, {}).get(CONF_CUSTOM).get('entities', {}).get(self.entity_id, {})
            c = self.hass.data.get(DOMAIN, {}).get(CONF_CUSTOM) or {}
            c = c.get(self._mega_id) or {}
            c = c.get(self.port) or {}
            if self.addr is not None and self.index is not None and isinstance(c, dict):
                idx = self.addr.lower() + f'_a' if self.index == 0 else '_b'
                c = c.get(idx, {})
            c.update(c_entity_id)
            self._customize = c

        return self._customize

    @property
    def device_info(self) -> DeviceInfo:
        if isinstance(self.port, list):
            pt_idx = self.id_suffix
        else:
            _pt = self.port if not self.mega.new_naming else f'{self.port:02}' if isinstance(self.port, int) else self.port
            if isinstance(_pt, str) and 'e' in _pt:
                pt_idx, _ = _pt.split('e')
            else:
                pt_idx = _pt
        return DeviceInfo(
            identifiers={
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, f'{self._mega_id}', pt_idx)
            },
            name=self.name,
            manufacturer='ab-log.ru',
            sw_version=self.mega.fw,
            via_device=(DOMAIN, self._mega_id),
        )

    @property
    def lg(self) -> logging.Logger:
        return _LOGGER

    @property
    def available(self) -> bool:
        return self.mega.online

    @property
    def name(self):
        c = self.customize.get(CONF_NAME)
        if not isinstance(c, str):
            if not isinstance(self.port, list):
                _pt = self.port if not self.mega.new_naming else f'{self.port:02}' if isinstance(self.port, int) else self.port
                c = self._name or f"{self.mega.id}_p{_pt}"
            else:
                c = self.id_suffix
        return c

    @property
    def unique_id(self):
        return self._unique_id

    async def async_added_to_hass(self) -> None:
        global _task_set_ev_on
        await super().async_added_to_hass()
        self._state = await self.async_get_last_state()

    async def get_state(self):
        self.lg.debug(f'state is %s', self.state)
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
        if self.hass is None:
            return
        self.async_write_ha_state()
        self.lg.debug(f'state after update %s', self.state)
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


class MegaOutPort(MegaPushEntity):

    def __init__(
            self,
            dimmer=False,
            dimmer_scale=1,
            *args, **kwargs
    ):
        super().__init__(
            *args, **kwargs
        )
        self._brightness = None
        self._is_on = None
        self.dimmer = dimmer
        self.dimmer_scale = dimmer_scale
        self.is_extender = isinstance(self.port, str) and 'e' in self.port
        self.task: asyncio.Task = None
        self._restore_brightness = None
        self._last_called: float = 0

    # @property
    # def assumed_state(self) -> bool:
    #     return True if self.index is not None or self.mega.mqtt is None else False

    @property
    def max_dim(self):
        if self.dimmer_scale == 1:
            return 255
        elif self.dimmer_scale == 16:
            return 4095
        else:
            return 255

    @property
    def range(self) -> typing.List[int]:
        return self.customize.get(CONF_RANGE, [0, 255])

    @property
    def invert(self):
        return self.customize.get(CONF_INVERT, False)

    @property
    def brightness(self):
        ret = None
        if not self.dimmer:
            return
        val = self.mega.values.get(self.port, {})
        if isinstance(val, dict) and len(val) == 0 and self._state is not None:
            ret = safe_int(self._state.attributes.get("brightness"), def_on=self.max_dim, def_off=0, def_val=0)
            ret = self._calc_brightness(ret)
        elif isinstance(self.port, str) and 'e' in self.port:
            if isinstance(val, str):
                val = safe_int(val, def_on=self.max_dim, def_off=0, def_val=0)
            else:
                val = 0
            if val == 0:
                ret = self._brightness
            elif isinstance(val, (int, float)):
                ret = int(val / self.dimmer_scale)
        elif val is not None:
            val = val.get("value")
            if val is None:
                return
            try:
                val = int(val)
                ret = val
            except Exception:
                pass
        ret = self._cal_reverse_brightness(ret)
        return ret

    @property
    def is_on(self) -> bool:
        val = self.mega.values.get(self.port, {})
        if isinstance(val, dict) and len(val) == 0 and self._state is not None:
            return self._state == 'ON'
        elif isinstance(self.port, str) and 'e' in self.port and val:
            if val is None:
                return
            if self.dimmer:
                val = safe_int(val)
                if val is not None:
                    return val > 0 if not self.invert else val == 0
            else:
                return val == 'ON' if not self.invert else val == 'OFF'
        elif val is not None:
            val = val.get("value")
            if not isinstance(val, str) and self.index is not None and self.addr is not None:
                if not isinstance(val, dict):
                    self.mega.lg.warning(f'{self.entity_id}: {val} is not a dict')
                    return
                _val = val.get(self.addr, val.get(self.addr.lower(), val.get(self.addr.upper())))
                if not isinstance(_val, str):
                    self.mega.lg.warning(f'{self.entity_id}: can not get {self.addr} from {val}, recieved {_val}')
                    return
                _val = _val.split('/')
                if len(_val) >= 2:
                    self.mega.lg.debug('%s parsed values: %s[%s]="%s"', self.entity_id, _val, self.index, _val)
                    val = _val[self.index]
                else:
                    self.mega.lg.warning(f'{self.entity_id}: {_val} has wrong length')
                    return
            elif self.index is not None and self.addr is None:
                self.mega.lg.warning(f'{self.entity_id} does not has addr')
                return
            self.mega.lg.debug('%s.state = %s', self.entity_id, val)
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

    @property
    def smooth(self) -> timedelta:
        ret = self.customize.get(CONF_SMOOTH)
        if ret is None and self._smooth:
            ret = timedelta(seconds=self._smooth)
        return ret

    @property
    def smooth_dim(self):
        if not self.dimmer:
            return False
        return self.smooth or self.can_smooth_hardware

    def update_from_smooth(self, value, update_state=False):
        if isinstance(self.port, str):
            self.mega.values[self.port] = value[0]
        else:
            self.mega.values[self.port] = {
                'value': value[0]
            }
        if update_state:
            self.async_write_ha_state()

    def _set_dim_brightness(self, from_, to_, transition):
        pct = abs(to_ - from_) / (255 if self.dimmer_scale == 1 else 4095)
        update_state = transition is not None and transition > 3
        tm = (self.smooth.total_seconds() * pct) if transition is None else transition
        if self.task is not None:
            self.task.cancel()
        self.task = asyncio.create_task(self.mega.smooth_dim(
            (self.cmd_port, from_, to_),
            time=tm,
            can_smooth_hardware=self.can_smooth_hardware,
            max_values=[255 if self.dimmer_scale == 1 else 4095],
            updater=partial(self.update_from_smooth, update_state=update_state),
        ))

    def _calc_brightness(self, brightness):
        if brightness is None:
            brightness = 0
        pct = brightness / 255
        pct = max((0, pct))
        pct = min((pct, 1))
        l, h = self.range
        d = h - l
        brightness = round(pct * d + l)
        return brightness

    def _cal_reverse_brightness(self, brightness):
        if brightness is None:
            brightness = 0
        l, h = self.range
        d = h - l
        pct = (brightness - l) / d
        pct = max((0, pct))
        pct = min((pct, 1))
        brightness = round(pct * 255)
        return brightness

    async def async_turn_on(self, brightness=None, transition=None, **kwargs):
        if (time.time() - self._last_called) < 0.1:
            return
        self._last_called = time.time()
        if not self.dimmer:
            transition = None
        if not self.is_on and (brightness is None or brightness == 0):
            brightness = self._restore_brightness
        brightness = brightness or self.brightness or 255
        brightness = self._calc_brightness(brightness)
        _prev = safe_int(self.brightness) or 0
        self._brightness = brightness
        if self.dimmer and brightness == 0:
            cmd = self.max_dim
        elif self.dimmer:
            cmd = min((brightness * self.dimmer_scale, self.max_dim))
            if self.smooth_dim or transition:
                self._set_dim_brightness(from_=_prev, to_=cmd, transition=transition)
        else:
            cmd = 1 if not self.invert else 0
        if transition is None:
            _cmd = {"cmd": f"{self.cmd_port}:{cmd}"}
        else:
            _cmd = {
                "pt": f"{self.cmd_port}",
                "pwm": cmd,
                "cnt": round(transition / (abs(_prev - brightness) / 255)),
            }
        if self.addr:
            _cmd['addr'] = self.addr
        if not (self.smooth_dim or transition):
            await self.mega.request(**_cmd, priority=-1)
        if self.index is not None:
            # обновление текущего стейта для ds2413
            await self.mega.get_port(
                port=self.port,
                force_http=True,
                conv=False,
                http_cmd='list',
            )
        elif isinstance(self.port, str) and 'e' in self.port:
            if not self.dimmer:
                self.mega.values[self.port] = 'ON' if not self.invert else 'OFF'
            else:
                self.mega.values[self.port] = cmd
        else:
            self.mega.values[self.port] = {'value': cmd}
        await self.get_state()

    async def async_turn_off(self, transition=None, **kwargs) -> None:
        if (time.time() - self._last_called) < 0.1:
            return
        self._last_called = time.time()
        self._restore_brightness = self._cal_reverse_brightness(safe_int(self._brightness))
        if not self.dimmer:
            transition = None
        cmd = "0" if not self.invert else "1"
        _cmd = {"cmd": f"{self.cmd_port}:{cmd}"}
        _prev = safe_int(self.brightness) or 0
        if self.addr:
            _cmd['addr'] = self.addr
        if not (self.smooth_dim or transition):
            await self.mega.request(**_cmd, priority=-1)
        else:
            self._set_dim_brightness(
                from_=_prev,
                to_=0,
                transition=transition,
            )
        if self.index is not None:
            # обновление текущего стейта для ds2413
            await self.mega.get_port(
                port=self.port,
                force_http=True,
                conv=False,
                http_cmd='list',
            )
        elif isinstance(self.port, str) and 'e' in self.port:
            self.mega.values[self.port] = 'OFF' if not self.invert else 'ON'
        else:
            self.mega.values[self.port] = {'value': cmd}
        await self.get_state()

    async def async_will_remove_from_hass(self) -> None:
        if self.task is not None:
            self.task.cancel()



def safe_int(v, def_on=1, def_off=0, def_val=None):
    if v == 'ON':
        return def_on
    elif v == 'OFF':
        return def_off
    try:
        return int(v)
    except (ValueError, TypeError):
        return def_val
"""Platform for light integration."""
from __future__ import annotations

import asyncio
import logging
import typing
from datetime import timedelta, datetime
from functools import partial

import voluptuous as vol
import colorsys
import time

from homeassistant.components.light import (
    PLATFORM_SCHEMA as LIGHT_SCHEMA,
    SUPPORT_BRIGHTNESS,
    LightEntity,
    SUPPORT_TRANSITION,
    SUPPORT_COLOR, ColorMode, LightEntityFeature,
    # SUPPORT_WHITE_VALUE
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_NAME,
    CONF_PORT,
    CONF_UNIQUE_ID,
    CONF_ID,
    CONF_DOMAIN,
)
from homeassistant.core import HomeAssistant
from .entities import MegaOutPort, BaseMegaEntity, safe_int

from .hub import MegaD
from .const import (
    CONF_DIMMER,
    CONF_SWITCH,
    DOMAIN,
    CONF_CUSTOM,
    CONF_SKIP, CONF_LED, CONF_WS28XX, CONF_PORTS, CONF_WHITE_SEP, CONF_SMOOTH, CONF_ORDER, CONF_CHIP, RGB,
)
from .tools import int_ignore, map_reorder_rgb

lg = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(seconds=5)

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
    lg.warning('mega integration does not support yaml for lights, please use UI configuration')
    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_devices):
    mid = config_entry.data[CONF_ID]
    hub: MegaD = hass.data['mega'][mid]
    devices = []
    customize = hass.data.get(DOMAIN, {}).get(CONF_CUSTOM, {}).get(mid, {})
    skip = []
    if CONF_LED in customize:
        for entity_id, conf in customize[CONF_LED].items():
            ports = conf.get(CONF_PORTS) or [conf.get(CONF_PORT)]
            skip.extend(ports)
            devices.append(MegaRGBW(
                mega=hub,
                port=ports,
                name=entity_id,
                customize=conf,
                id_suffix=entity_id,
                config_entry=config_entry
            ))
    for port, cfg in config_entry.data.get('light', {}).items():
        port = int_ignore(port)
        c = customize.get(port, {})
        if c.get(CONF_SKIP, False) or port in skip or c.get(CONF_DOMAIN, 'light') != 'light':
            continue
        for data in cfg:
            hub.lg.debug(f'add light on port %s with data %s', port, data)
            light = MegaLight(mega=hub, port=port, config_entry=config_entry, **data)
            if '<' in light.name:
                continue
            devices.append(light)

    async_add_devices(devices)


class MegaLight(MegaOutPort, LightEntity):

    @property
    def supported_features(self):
        return (
            (SUPPORT_BRIGHTNESS if self.dimmer else 0) |
            (SUPPORT_TRANSITION if self.dimmer else 0)
        )


class MegaRGBW(LightEntity, BaseMegaEntity):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._is_on = None
        self._brightness = None
        self._hs_color = None
        self._rgb_color: tuple[int, int, int] | None = None
        self._white_value = None
        self._task: asyncio.Task = None
        self._restore = None
        self.smooth: timedelta = self.customize[CONF_SMOOTH]
        self._color_order = self.customize.get(CONF_ORDER, 'rgb')
        self._last_called: float = 0
        self._max_values = None

    @property
    def max_values(self) -> list:
        if self._max_values is None:
            if self.is_ws:
                self._max_values = [255] * 4
            else:
                self._max_values = [
                    255 if isinstance(x, int) else 4095 for x in self.port
                ]
        return self._max_values

    @property
    def chip(self) -> int:
        return self.customize.get(CONF_CHIP, 100)

    @property
    def is_ws(self):
        return self.customize.get(CONF_WS28XX)


    @property
    def supported_color_modes(self) -> set[ColorMode] | set[str] | None:
        return {
            ColorMode.BRIGHTNESS,
            ColorMode.RGB if len(self.port) != 4 else ColorMode.RGBW
        }

    @property
    def color_mode(self) -> ColorMode | str | None:
        if len(self.port) == 4:
            return ColorMode.RGBW
        else:
            return ColorMode.RGB

    @property
    def white_value(self):
        # if self.supported_features & SUPPORT_WHITE_VALUE:
        return float(self.get_attribute('white_value', 0))

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        return self._rgb_color

    @property
    def rgbw_color(self) -> tuple[int, int, int, int] | None:
        if self._white_value is not None and self._rgb_color is not None:
            return (*self._rgb_color, self._white_value)

    @property
    def brightness(self):
        return float(self.get_attribute('brightness', 0))

    @property
    def hs_color(self):
        return self.get_attribute('hs_color', [0, 0])

    @property
    def is_on(self):
        return self.get_attribute('is_on', False)

    @property
    def supported_features(self):
        return LightEntityFeature.TRANSITION

    def get_rgbw(self):
        if not self.is_on:
            return [0 for x in range(len(self.port))] if not self.is_ws else [0] * 3
        rgb = colorsys.hsv_to_rgb(
            self.hs_color[0]/360, self.hs_color[1]/100, self.brightness / 255
        )
        rgb = [x for x in rgb]
        if self.white_value is not None:
            white = self.white_value
            if not self.customize.get(CONF_WHITE_SEP):
                white = white * (self.brightness / 255)
            rgb.append(white / 255)
        rgb = [
            round(x * self.max_values[i]) for i, x in enumerate(rgb)
        ]
        if self.is_ws:
            # восстанавливаем мэпинг
            rgb = map_reorder_rgb(rgb, RGB, self._color_order)
        return rgb

    async def async_turn_on(self, **kwargs):
        if (time.time() - self._last_called) < 0.1:
            return
        self._last_called = time.time()
        self.lg.debug(f'turn on %s with kwargs %s', self.entity_id, kwargs)
        if self._restore is not None:
            self._restore.update(kwargs)
            kwargs = self._restore
            self._restore = None
        _before = self.get_rgbw()
        self._is_on = True
        if self._task is not None:
            self._task.cancel()
        self._task = asyncio.create_task(self.set_color(_before, **kwargs))

    async def async_turn_off(self, **kwargs):
        if (time.time() - self._last_called) < 0.1:
            return
        self._last_called = time.time()
        self._restore = {
            'hs_color': self.hs_color,
            'brightness': self.brightness,
            'white_value': self.white_value,
        }
        _before = self.get_rgbw()
        self._is_on = False
        if self._task is not None:
            self._task.cancel()
        self._task = asyncio.create_task(self.set_color(_before, **kwargs))

    async def set_color(self, _before, **kwargs):
        transition = kwargs.get('transition')
        update_state = transition is not None and transition > 3
        for item, value in kwargs.items():
            setattr(self, f'_{item}', value)
        _after = self.get_rgbw()
        self._rgb_color = tuple(_after[:3])
        if transition is None:
            transition = self.smooth.total_seconds()
            ratio = self.calc_speed_ratio(_before, _after)
            transition = transition * ratio
        self.async_write_ha_state()
        ports = self.port if not self.is_ws else self.port*3
        config = [(port, _before[i], _after[i]) for i, port in enumerate(ports)]
        try:
            await self.mega.smooth_dim(
                *config,
                time=transition,
                ws=self.is_ws,
                jitter=50,
                updater=partial(self._update_from_rgb, update_state=update_state),
                can_smooth_hardware=self.can_smooth_hardware,
                max_values=self.max_values,
                chip=self.chip,
            )
        except asyncio.CancelledError:
            return
        except:
            self.lg.exception('while dimming')

    async def async_will_remove_from_hass(self) -> None:
        await super().async_will_remove_from_hass()
        if self._task is not None:
            self._task.cancel()

    def _update_from_rgb(self, rgbw, update_state=False):
        if len(self.port) == 4:
            w = rgbw[-1]
            rgb = rgbw[:3]
        else:
            w = None
            rgb = rgbw
        if self.is_ws:
            rgb = map_reorder_rgb(
                rgb, self._color_order, RGB
            )
        h, s, v = colorsys.rgb_to_hsv(*[x/self.max_values[i] for i, x in enumerate(rgb)])
        h *= 360
        s *= 100
        v *= 255
        self._hs_color = [h, s]
        if self.is_on:
            self._brightness = v
        if w is not None:
            if not self.customize.get(CONF_WHITE_SEP):
                w = w/(self._brightness / 255)
            else:
                w = w
            w = w / (self.max_values[-1] / 255)
            self._white_value = w
        # print(f'updated state {self.hs_color=} {self.brightness=}')
        if update_state:
            self.async_write_ha_state()

    async def async_update(self):
        """
        Эта штука нужна для синхронизации статуса вкл/выкл с реальностью. Если все цвета сброшены в ноль, значит мега
        рестартнулась и не запомнила настройки, поэтому извещаем HA о выключении
        Если вручную править цвет на стороне меги, тут изменения отражаться не будут
        :return:
        """
        if not self.enabled:
            return
        rgbw = []
        for x in self.port:
            data = self.coordinator.data
            if not isinstance(data, dict):
                return
            data = data.get(x, None)
            if isinstance(data, dict):
                data = data.get('value')
            data = safe_int(data)
            if data is None:
                return
            rgbw.append(data)
        if sum(rgbw) == 0:
            self._is_on = False
        self.async_write_ha_state()

    def calc_speed_ratio(self, _before, _after):
        ret = None
        for i, x in enumerate(_before):
            r = abs(x - _after[i]) / self.max_values[i]
            if ret is None:
                ret = r
            else:
                ret = max([r, ret])
        return ret
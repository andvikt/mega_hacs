"""Пока не сделано"""
import asyncio
import logging

import voluptuous as vol

from homeassistant import config_entries, core
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_ID, CONF_PASSWORD, CONF_SCAN_INTERVAL
from homeassistant.core import callback, HomeAssistant
from .const import DOMAIN, CONF_RELOAD, \
    CONF_NPORTS, CONF_UPDATE_ALL, CONF_POLL_OUTS, CONF_FAKE_RESPONSE, CONF_FORCE_D, \
    CONF_ALLOW_HOSTS, CONF_PROTECTED, CONF_RESTORE_ON_RESTART, CONF_UPDATE_TIME
from .hub import MegaD
from . import exceptions

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ID, default='mega'): str,
        vol.Required(CONF_HOST, default="192.168.0.14"): str,
        vol.Required(CONF_PASSWORD, default="sec"): str,
        vol.Optional(CONF_SCAN_INTERVAL, default=30): int,
        vol.Optional(CONF_POLL_OUTS, default=False): bool,
        # vol.Optional(CONF_PORT_TO_SCAN, default=0): int,
        # vol.Optional(CONF_MQTT_INPUTS, default=False): bool,
        vol.Optional(CONF_NPORTS, default=37): int,
        vol.Optional(CONF_UPDATE_ALL, default=True): bool,
        vol.Optional(CONF_FAKE_RESPONSE, default=True): bool,
        vol.Optional(CONF_FORCE_D, default=True): bool,
        vol.Optional(CONF_RESTORE_ON_RESTART, default=True): bool,
        vol.Optional(CONF_PROTECTED, default=True): bool,
        vol.Optional(CONF_ALLOW_HOSTS, default='::1;127.0.0.1'): str,
        vol.Optional(CONF_UPDATE_TIME, default=True): bool,
    },
)


async def get_hub(hass: HomeAssistant, data):
    # _mqtt = hass.data.get(mqtt.DOMAIN)
    # if not isinstance(_mqtt, mqtt.MQTT):
    #     raise exceptions.MqttNotConfigured("mqtt must be configured first")
    hub = MegaD(hass, **data, lg=_LOGGER, loop=asyncio.get_event_loop()) #mqtt=_mqtt,
    hub.mqtt_id = await hub.get_mqtt_id()
    if not await hub.authenticate():
        raise exceptions.InvalidAuth
    return hub


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    if data[CONF_ID] in hass.data.get(DOMAIN, []):
        raise exceptions.DuplicateId('duplicate_id')
    hub = await get_hub(hass, data)

    return hub


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for mega."""

    VERSION = 26
    CONNECTION_CLASS = config_entries.CONN_CLASS_ASSUMED

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        try:
            hub = await validate_input(self.hass, user_input)
            await hub.start()
            hub.new_naming=True
            config = await hub.get_config(nports=user_input.get(CONF_NPORTS, 37))
            await hub.stop()
            hub.lg.debug(f'config loaded: %s', config)
            config.update(user_input)
            config['new_naming'] = True
            return self.async_create_entry(
                title=user_input.get(CONF_ID, user_input[CONF_HOST]),
                data=config,
            )
        except exceptions.CannotConnect:
            errors["base"] = "cannot_connect"
        except exceptions.InvalidAuth:
            errors["base"] = "invalid_auth"
        except exceptions.DuplicateId:
            errors["base"] = "duplicate_id"
        except Exception as exc:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors[CONF_ID] = str(exc)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):

    def __init__(self, config_entry: ConfigEntry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        new_naming = self.config_entry.data.get('new_naming', False)
        if user_input is not None:
            reload = user_input.pop(CONF_RELOAD)
            cfg = dict(self.config_entry.data)
            cfg.update(user_input)
            cfg['new_naming'] = new_naming
            self.config_entry.data = cfg
            await get_hub(self.hass, cfg)

            if reload:
                id = self.config_entry.data.get('id', self.config_entry.entry_id)
                hub: MegaD = self.hass.data[DOMAIN].get(id)
                cfg = await hub.reload(reload_entry=False)

            return self.async_create_entry(
                title='',
                data=cfg,
            )
        e = self.config_entry.data
        ret = self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional(CONF_SCAN_INTERVAL, default=e.get(CONF_SCAN_INTERVAL, 0)): int,
                vol.Optional(CONF_POLL_OUTS, default=e.get(CONF_POLL_OUTS, False)): bool,
                # vol.Optional(CONF_PORT_TO_SCAN, default=e.get(CONF_PORT_TO_SCAN, 0)): int,
                # vol.Optional(CONF_MQTT_INPUTS, default=e.get(CONF_MQTT_INPUTS, True)): bool,
                vol.Optional(CONF_NPORTS, default=e.get(CONF_NPORTS, 37)): int,
                vol.Optional(CONF_RELOAD, default=False): bool,
                vol.Optional(CONF_UPDATE_ALL, default=e.get(CONF_UPDATE_ALL, True)): bool,
                vol.Optional(CONF_FAKE_RESPONSE, default=e.get(CONF_FAKE_RESPONSE, True)): bool,
                vol.Optional(CONF_FORCE_D, default=e.get(CONF_FORCE_D, False)): bool,
                vol.Optional(CONF_RESTORE_ON_RESTART, default=e.get(CONF_RESTORE_ON_RESTART, False)): bool,
                vol.Optional(CONF_PROTECTED, default=e.get(CONF_PROTECTED, True)): bool,
                vol.Optional(CONF_ALLOW_HOSTS, default='::1;127.0.0.1'): str,
                vol.Optional(CONF_UPDATE_TIME, default=e.get(CONF_UPDATE_TIME, False)): bool,
                # vol.Optional(CONF_INVERT, default=''): str,
            }),
        )
        return ret
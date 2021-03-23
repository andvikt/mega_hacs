from homeassistant import exceptions


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class DuplicateId(exceptions.HomeAssistantError):
    """Error to indicate duplicate id"""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""


class NoPort(Exception):
    pass
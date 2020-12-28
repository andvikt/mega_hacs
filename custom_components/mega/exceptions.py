from homeassistant import exceptions


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class MqttNotConfigured(exceptions.HomeAssistantError):
    """Error to indicate mqtt is not configured"""


class DuplicateId(exceptions.HomeAssistantError):
    """Error to indicate duplicate id"""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""

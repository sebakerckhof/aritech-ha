"""Config flow for Aritech ATS integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
import homeassistant.helpers.config_validation as cv

from aritech_client import AritechClient

from .const import (
    DOMAIN,
    CONF_ENCRYPTION_KEY,
    CONF_PIN_CODE,
    DEFAULT_PORT,
    DEFAULT_PIN_CODE,
    DEFAULT_ENCRYPTION_KEY,
)

_LOGGER = logging.getLogger(__name__)

# Configuration schema
DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
        vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Required(CONF_ENCRYPTION_KEY, default=DEFAULT_ENCRYPTION_KEY): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
        vol.Required(CONF_PIN_CODE, default=DEFAULT_PIN_CODE): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
    }
)


class CannotConnect(Exception):
    """Error to indicate we cannot connect."""


class InvalidAuth(Exception):
    """Error to indicate invalid authentication."""


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    host = data[CONF_HOST]
    port = data[CONF_PORT]
    encryption_key = data[CONF_ENCRYPTION_KEY]
    pin_code = data[CONF_PIN_CODE]

    # Validate encryption key format
    if not encryption_key.isdigit():
        raise vol.Invalid("Encryption key must contain only digits")
    if len(encryption_key) != 24:
        raise vol.Invalid("Encryption key must be exactly 24 digits")

    # Validate PIN code format
    if not pin_code.isdigit():
        raise vol.Invalid("PIN code must contain only digits")

    # Attempt to connect to the alarm panel
    client = AritechClient({
        "host": host,
        "port": port,
        "pin": pin_code,
        "encryption_password": encryption_key,
    })

    try:
        await client.connect()
        await client.initialize()

        panel_name = client.panel_name or "Aritech ATS"
        panel_model = client.panel_model or ""

        return {
            "title": f"{panel_name} ({host})" if panel_model else f"Aritech ATS ({host})",
            "panel_model": panel_model,
            "panel_name": panel_name,
        }

    except Exception as err:
        _LOGGER.error("Failed to connect to Aritech panel: %s", err)
        if "login" in str(err).lower() or "auth" in str(err).lower():
            raise InvalidAuth(f"Login failed: {err}") from err
        raise CannotConnect(f"Failed to connect: {err}") from err
    finally:
        await client.disconnect()


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Aritech ATS."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except vol.Invalid as err:
                errors["base"] = "invalid_input"
                _LOGGER.error("Validation error: %s", err)
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                # Check if already configured
                await self.async_set_unique_id(user_input[CONF_HOST])
                self._abort_if_unique_id_configured()

                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

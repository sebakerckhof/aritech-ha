"""Config flow for Aritech integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_USERNAME, CONF_PASSWORD
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
    CONF_PANEL_TYPE,
    PANEL_TYPE_X500,
    PANEL_TYPE_X700,
    DEFAULT_PORT,
    DEFAULT_PIN_CODE,
    DEFAULT_ENCRYPTION_KEY,
)

_LOGGER = logging.getLogger(__name__)

# Step 1: Connection schema (host, port, encryption key)
CONNECTION_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
        vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Required(CONF_ENCRYPTION_KEY, default=DEFAULT_ENCRYPTION_KEY): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
    }
)

# Step 2a: x500 PIN authentication schema
X500_AUTH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PIN_CODE, default=DEFAULT_PIN_CODE): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
    }
)

# Step 2b: x700 username/password authentication schema
X700_AUTH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
        vol.Required(CONF_PASSWORD): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
    }
)


class CannotConnect(Exception):
    """Error to indicate we cannot connect."""


class InvalidAuth(Exception):
    """Error to indicate invalid authentication."""


async def validate_connection(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate connection details and detect panel type.

    Connects to the panel without authenticating to detect panel type.
    Returns panel info including whether it's an x700 panel.
    """
    host = data[CONF_HOST]
    port = data[CONF_PORT]
    encryption_key = data[CONF_ENCRYPTION_KEY]

    # Validate encryption key format
    if not encryption_key.isdigit():
        raise vol.Invalid("Encryption key must contain only digits")
    if len(encryption_key) != 24:
        raise vol.Invalid("Encryption key must be exactly 24 digits")

    # Connect to panel to detect type (without login)
    client = AritechClient({
        "host": host,
        "port": port,
        "encryption_key": encryption_key,
    })

    try:
        await client.connect()

        # Get panel description (unencrypted query, doesn't require login)
        await client.get_description()

        panel_name = client.panel_name or "Aritech"
        panel_model = client.panel_model or ""
        is_x700 = client.is_x700_panel

        return {
            "panel_model": panel_model,
            "panel_name": panel_name,
            "is_x700": is_x700,
        }

    except Exception as err:
        _LOGGER.error("Failed to connect to Aritech panel: %s", err)
        raise CannotConnect(f"Failed to connect: {err}") from err
    finally:
        await client.disconnect()


async def validate_full_connection(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate full connection including authentication.

    Data should contain all connection details plus auth credentials.
    """
    host = data[CONF_HOST]
    port = data[CONF_PORT]
    encryption_key = data[CONF_ENCRYPTION_KEY]
    panel_type = data.get(CONF_PANEL_TYPE, PANEL_TYPE_X500)

    # Build client config based on panel type
    client_config = {
        "host": host,
        "port": port,
        "encryption_key": encryption_key,
    }

    if panel_type == PANEL_TYPE_X700:
        client_config["username"] = data[CONF_USERNAME]
        client_config["password"] = data[CONF_PASSWORD]
    else:
        client_config["pin"] = data[CONF_PIN_CODE]

    client = AritechClient(client_config)

    try:
        await client.connect()
        await client.initialize()

        panel_name = client.panel_name or "Aritech"
        panel_model = client.panel_model or ""

        return {
            "title": f"{panel_name} ({host})" if panel_model else f"Aritech ({host})",
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
    """Handle a config flow for Aritech."""

    VERSION = 2

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._connection_data: dict[str, Any] = {}
        self._panel_info: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle step 1: connection details."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                # Validate connection and detect panel type
                self._panel_info = await validate_connection(self.hass, user_input)
                self._connection_data = user_input

                # Check if already configured
                await self.async_set_unique_id(user_input[CONF_HOST])
                self._abort_if_unique_id_configured()

                # Route to appropriate auth step based on panel type
                if self._panel_info["is_x700"]:
                    return await self.async_step_x700_auth()
                else:
                    return await self.async_step_x500_auth()

            except CannotConnect:
                errors["base"] = "cannot_connect"
            except vol.Invalid as err:
                errors["base"] = "invalid_input"
                _LOGGER.error("Validation error: %s", err)
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=CONNECTION_SCHEMA,
            errors=errors,
            description_placeholders={
                "panel_info": "",
            },
        )

    async def async_step_x500_auth(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle step 2a: x500 PIN authentication."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate PIN format
            pin_code = user_input.get(CONF_PIN_CODE, "")
            if not pin_code.isdigit():
                errors["base"] = "invalid_pin"
            else:
                try:
                    # Combine connection data with auth data
                    full_data = {
                        **self._connection_data,
                        **user_input,
                        CONF_PANEL_TYPE: PANEL_TYPE_X500,
                    }

                    info = await validate_full_connection(self.hass, full_data)
                    return self.async_create_entry(title=info["title"], data=full_data)

                except CannotConnect:
                    errors["base"] = "cannot_connect"
                except InvalidAuth:
                    errors["base"] = "invalid_auth"
                except Exception:  # pylint: disable=broad-except
                    _LOGGER.exception("Unexpected exception")
                    errors["base"] = "unknown"

        panel_name = self._panel_info.get("panel_name", "Unknown")
        panel_model = self._panel_info.get("panel_model", "")

        return self.async_show_form(
            step_id="x500_auth",
            data_schema=X500_AUTH_SCHEMA,
            errors=errors,
            description_placeholders={
                "panel_name": panel_name,
                "panel_model": panel_model,
            },
        )

    async def async_step_x700_auth(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle step 2b: x700 username/password authentication."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                # Combine connection data with auth data
                full_data = {
                    **self._connection_data,
                    **user_input,
                    CONF_PANEL_TYPE: PANEL_TYPE_X700,
                }

                info = await validate_full_connection(self.hass, full_data)
                return self.async_create_entry(title=info["title"], data=full_data)

            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        panel_name = self._panel_info.get("panel_name", "Unknown")
        panel_model = self._panel_info.get("panel_model", "")

        return self.async_show_form(
            step_id="x700_auth",
            data_schema=X700_AUTH_SCHEMA,
            errors=errors,
            description_placeholders={
                "panel_name": panel_name,
                "panel_model": panel_model,
            },
        )

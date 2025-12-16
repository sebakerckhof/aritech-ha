"""Tests for Aritech ATS config flow."""
from __future__ import annotations

import sys
from pathlib import Path

# Add custom_components directory to path for proper package imports
_custom_components_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_custom_components_dir))

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from aritech_ats.const import (
    CONF_ENCRYPTION_KEY,
    CONF_PIN_CODE,
    DEFAULT_PORT,
    DOMAIN,
)
from aritech_ats.config_flow import validate_input, CannotConnect, InvalidAuth

from .conftest import (
    MOCK_CONFIG,
    MOCK_ENCRYPTION_KEY,
    MOCK_HOST,
    MOCK_PIN,
    MOCK_PORT,
    create_mock_client,
)


class TestValidateInput:
    """Tests for validate_input function that don't require full HA setup."""

    @pytest.mark.asyncio
    async def test_valid_input_connects_successfully(self, hass: HomeAssistant) -> None:
        """Test validate_input with valid configuration."""
        mock_client = create_mock_client()

        with patch(
            "aritech_ats.config_flow.AritechClient",
            return_value=mock_client,
        ):
            result = await validate_input(hass, MOCK_CONFIG)

        assert result["title"] == f"Test Panel ({MOCK_HOST})"
        assert result["panel_model"] == "ATS4500"
        assert result["panel_name"] == "Test Panel"
        mock_client.connect.assert_called_once()
        mock_client.initialize.assert_called_once()
        mock_client.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_connection_error_raises_cannot_connect(self, hass: HomeAssistant) -> None:
        """Test validate_input raises CannotConnect on connection failure."""
        mock_client = create_mock_client()
        mock_client.connect.side_effect = Exception("Connection refused")

        with patch(
            "aritech_ats.config_flow.AritechClient",
            return_value=mock_client,
        ):
            with pytest.raises(CannotConnect):
                await validate_input(hass, MOCK_CONFIG)

    @pytest.mark.asyncio
    async def test_auth_error_raises_invalid_auth(self, hass: HomeAssistant) -> None:
        """Test validate_input raises InvalidAuth on authentication failure."""
        mock_client = create_mock_client()
        mock_client.initialize.side_effect = Exception("Login failed: invalid credentials")

        with patch(
            "aritech_ats.config_flow.AritechClient",
            return_value=mock_client,
        ):
            with pytest.raises(InvalidAuth):
                await validate_input(hass, MOCK_CONFIG)

    @pytest.mark.asyncio
    async def test_invalid_encryption_key_not_digits(self, hass: HomeAssistant) -> None:
        """Test validate_input with non-digit encryption key."""
        invalid_config = MOCK_CONFIG.copy()
        invalid_config[CONF_ENCRYPTION_KEY] = "abcdefghijklmnopqrstuvwx"

        with pytest.raises(vol.Invalid, match="Encryption key must contain only digits"):
            await validate_input(hass, invalid_config)

    @pytest.mark.asyncio
    async def test_invalid_encryption_key_wrong_length(self, hass: HomeAssistant) -> None:
        """Test validate_input with wrong length encryption key."""
        invalid_config = MOCK_CONFIG.copy()
        invalid_config[CONF_ENCRYPTION_KEY] = "123456789012"

        with pytest.raises(vol.Invalid, match="Encryption key must be exactly 24 digits"):
            await validate_input(hass, invalid_config)

    @pytest.mark.asyncio
    async def test_invalid_pin_not_digits(self, hass: HomeAssistant) -> None:
        """Test validate_input with non-digit PIN code."""
        invalid_config = MOCK_CONFIG.copy()
        invalid_config[CONF_PIN_CODE] = "abcd"

        with pytest.raises(vol.Invalid, match="PIN code must contain only digits"):
            await validate_input(hass, invalid_config)

    @pytest.mark.asyncio
    async def test_panel_without_name(self, hass: HomeAssistant) -> None:
        """Test validate_input when panel doesn't report a name."""
        mock_client = create_mock_client()
        mock_client.panel_name = None
        mock_client.panel_model = None

        with patch(
            "aritech_ats.config_flow.AritechClient",
            return_value=mock_client,
        ):
            result = await validate_input(hass, MOCK_CONFIG)

        assert result["title"] == f"Aritech ATS ({MOCK_HOST})"


# The following tests require full integration setup with pytest-homeassistant-custom-component
# They are skipped by default but can be run when the integration is properly loaded

@pytest.mark.skip(reason="Requires full integration setup - integration must be loadable by HA")
class TestConfigFlowIntegration:
    """Integration tests for config flow that require full HA setup."""

    async def test_form_shows_correctly(self, hass: HomeAssistant) -> None:
        """Test that the config flow form is displayed correctly."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {}

    async def test_form_successful_connection(
        self,
        hass: HomeAssistant,
        mock_setup_entry: AsyncMock,
    ) -> None:
        """Test successful configuration flow."""
        mock_client = create_mock_client()

        with patch(
            "aritech_ats.config_flow.AritechClient",
            return_value=mock_client,
        ):
            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_USER}
            )

            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                MOCK_CONFIG,
            )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == f"Test Panel ({MOCK_HOST})"
        assert result["data"] == MOCK_CONFIG

    async def test_form_connection_error(self, hass: HomeAssistant) -> None:
        """Test handling of connection errors."""
        mock_client = create_mock_client()
        mock_client.connect.side_effect = Exception("Connection refused")

        with patch(
            "aritech_ats.config_flow.AritechClient",
            return_value=mock_client,
        ):
            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_USER}
            )

            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                MOCK_CONFIG,
            )

        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "cannot_connect"}

    async def test_form_duplicate_host(
        self,
        hass: HomeAssistant,
        mock_setup_entry: AsyncMock,
    ) -> None:
        """Test that duplicate hosts are rejected."""
        mock_client = create_mock_client()

        # Create first entry
        with patch(
            "aritech_ats.config_flow.AritechClient",
            return_value=mock_client,
        ):
            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_USER}
            )
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                MOCK_CONFIG,
            )
            assert result["type"] == FlowResultType.CREATE_ENTRY

        # Try to create duplicate entry
        with patch(
            "aritech_ats.config_flow.AritechClient",
            return_value=mock_client,
        ):
            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_USER}
            )
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                MOCK_CONFIG,
            )

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "already_configured"

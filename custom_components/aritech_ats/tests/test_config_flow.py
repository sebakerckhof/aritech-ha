"""Tests for Aritech config flow."""
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
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_USERNAME, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from aritech_ats.const import (
    CONF_ENCRYPTION_KEY,
    CONF_PIN_CODE,
    CONF_PANEL_TYPE,
    PANEL_TYPE_X500,
    PANEL_TYPE_X700,
    DEFAULT_PORT,
    DOMAIN,
)
from aritech_ats.config_flow import (
    validate_connection,
    validate_full_connection,
    CannotConnect,
    InvalidAuth,
)

from .conftest import (
    MOCK_CONFIG,
    MOCK_CONNECTION_CONFIG,
    MOCK_X500_CONFIG,
    MOCK_X700_CONFIG,
    MOCK_ENCRYPTION_KEY,
    MOCK_HOST,
    MOCK_PIN,
    MOCK_USERNAME,
    MOCK_PASSWORD,
    MOCK_PORT,
    create_mock_client,
)


class TestValidateConnection:
    """Tests for validate_connection function (step 1)."""

    @pytest.mark.asyncio
    async def test_valid_connection_x500(self, hass: HomeAssistant) -> None:
        """Test validate_connection with valid configuration for x500 panel."""
        mock_client = create_mock_client(is_x700=False)

        with patch(
            "aritech_ats.config_flow.AritechClient",
            return_value=mock_client,
        ):
            result = await validate_connection(hass, MOCK_CONNECTION_CONFIG)

        assert result["panel_model"] == "ATS4500"
        assert result["panel_name"] == "Test Panel"
        assert result["is_x700"] is False
        mock_client.connect.assert_called_once()
        mock_client.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_valid_connection_x700(self, hass: HomeAssistant) -> None:
        """Test validate_connection with valid configuration for x700 panel."""
        mock_client = create_mock_client(is_x700=True)

        with patch(
            "aritech_ats.config_flow.AritechClient",
            return_value=mock_client,
        ):
            result = await validate_connection(hass, MOCK_CONNECTION_CONFIG)

        assert result["panel_model"] == "ATS4700"
        assert result["panel_name"] == "Test Panel"
        assert result["is_x700"] is True

    @pytest.mark.asyncio
    async def test_connection_error_raises_cannot_connect(self, hass: HomeAssistant) -> None:
        """Test validate_connection raises CannotConnect on connection failure."""
        mock_client = create_mock_client()
        mock_client.connect.side_effect = Exception("Connection refused")

        with patch(
            "aritech_ats.config_flow.AritechClient",
            return_value=mock_client,
        ):
            with pytest.raises(CannotConnect):
                await validate_connection(hass, MOCK_CONNECTION_CONFIG)

    @pytest.mark.asyncio
    async def test_invalid_encryption_key_not_digits(self, hass: HomeAssistant) -> None:
        """Test validate_connection with non-digit encryption key."""
        invalid_config = MOCK_CONNECTION_CONFIG.copy()
        invalid_config[CONF_ENCRYPTION_KEY] = "abcdefghijklmnopqrstuvwx"

        with pytest.raises(vol.Invalid, match="Encryption key must contain only digits"):
            await validate_connection(hass, invalid_config)

    @pytest.mark.asyncio
    async def test_invalid_encryption_key_wrong_length(self, hass: HomeAssistant) -> None:
        """Test validate_connection with wrong length encryption key."""
        invalid_config = MOCK_CONNECTION_CONFIG.copy()
        invalid_config[CONF_ENCRYPTION_KEY] = "123456789012"

        with pytest.raises(vol.Invalid, match="Encryption key must be exactly 24 digits"):
            await validate_connection(hass, invalid_config)


class TestValidateFullConnection:
    """Tests for validate_full_connection function (step 2)."""

    @pytest.mark.asyncio
    async def test_valid_full_connection_x500(self, hass: HomeAssistant) -> None:
        """Test validate_full_connection with valid x500 configuration."""
        mock_client = create_mock_client(is_x700=False)

        with patch(
            "aritech_ats.config_flow.AritechClient",
            return_value=mock_client,
        ):
            result = await validate_full_connection(hass, MOCK_X500_CONFIG)

        assert result["title"] == f"Test Panel ({MOCK_HOST})"
        assert result["panel_model"] == "ATS4500"
        mock_client.connect.assert_called_once()
        mock_client.initialize.assert_called_once()
        mock_client.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_valid_full_connection_x700(self, hass: HomeAssistant) -> None:
        """Test validate_full_connection with valid x700 configuration."""
        mock_client = create_mock_client(is_x700=True)

        with patch(
            "aritech_ats.config_flow.AritechClient",
            return_value=mock_client,
        ):
            result = await validate_full_connection(hass, MOCK_X700_CONFIG)

        assert result["title"] == f"Test Panel ({MOCK_HOST})"
        assert result["panel_model"] == "ATS4700"

    @pytest.mark.asyncio
    async def test_auth_error_raises_invalid_auth(self, hass: HomeAssistant) -> None:
        """Test validate_full_connection raises InvalidAuth on authentication failure."""
        mock_client = create_mock_client()
        mock_client.initialize.side_effect = Exception("Login failed: invalid credentials")

        with patch(
            "aritech_ats.config_flow.AritechClient",
            return_value=mock_client,
        ):
            with pytest.raises(InvalidAuth):
                await validate_full_connection(hass, MOCK_X500_CONFIG)

    @pytest.mark.asyncio
    async def test_panel_without_name(self, hass: HomeAssistant) -> None:
        """Test validate_full_connection when panel doesn't report a name."""
        mock_client = create_mock_client()
        mock_client.panel_name = None
        mock_client.panel_model = None

        with patch(
            "aritech_ats.config_flow.AritechClient",
            return_value=mock_client,
        ):
            result = await validate_full_connection(hass, MOCK_X500_CONFIG)

        assert result["title"] == f"Aritech ({MOCK_HOST})"


# The following tests require full integration setup with pytest-homeassistant-custom-component
# They are skipped by default but can be run when the integration is properly loaded

@pytest.mark.skip(reason="Requires full integration setup - integration must be loadable by HA")
class TestConfigFlowIntegration:
    """Integration tests for config flow that require full HA setup."""

    async def test_form_shows_correctly(self, hass: HomeAssistant) -> None:
        """Test that the config flow form (step 1) is displayed correctly."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {}

    async def test_x500_flow_successful(
        self,
        hass: HomeAssistant,
        mock_setup_entry: AsyncMock,
    ) -> None:
        """Test successful 2-step configuration flow for x500 panel."""
        mock_client = create_mock_client(is_x700=False)

        with patch(
            "aritech_ats.config_flow.AritechClient",
            return_value=mock_client,
        ):
            # Step 1: Connection details
            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_USER}
            )
            assert result["type"] == FlowResultType.FORM
            assert result["step_id"] == "user"

            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                MOCK_CONNECTION_CONFIG,
            )

            # Step 2: x500 PIN auth
            assert result["type"] == FlowResultType.FORM
            assert result["step_id"] == "x500_auth"

            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {CONF_PIN_CODE: MOCK_PIN},
            )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == f"Test Panel ({MOCK_HOST})"
        assert result["data"][CONF_PANEL_TYPE] == PANEL_TYPE_X500

    async def test_x700_flow_successful(
        self,
        hass: HomeAssistant,
        mock_setup_entry: AsyncMock,
    ) -> None:
        """Test successful 2-step configuration flow for x700 panel."""
        mock_client = create_mock_client(is_x700=True)

        with patch(
            "aritech_ats.config_flow.AritechClient",
            return_value=mock_client,
        ):
            # Step 1: Connection details
            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_USER}
            )
            assert result["type"] == FlowResultType.FORM
            assert result["step_id"] == "user"

            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                MOCK_CONNECTION_CONFIG,
            )

            # Step 2: x700 username/password auth
            assert result["type"] == FlowResultType.FORM
            assert result["step_id"] == "x700_auth"

            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {CONF_USERNAME: MOCK_USERNAME, CONF_PASSWORD: MOCK_PASSWORD},
            )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == f"Test Panel ({MOCK_HOST})"
        assert result["data"][CONF_PANEL_TYPE] == PANEL_TYPE_X700

    async def test_form_connection_error(self, hass: HomeAssistant) -> None:
        """Test handling of connection errors in step 1."""
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
                MOCK_CONNECTION_CONFIG,
            )

        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "cannot_connect"}

    async def test_form_auth_error_x500(self, hass: HomeAssistant) -> None:
        """Test handling of authentication errors for x500 panel."""
        mock_client = create_mock_client(is_x700=False)

        with patch(
            "aritech_ats.config_flow.AritechClient",
            return_value=mock_client,
        ):
            # Step 1: Connection details (success)
            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_USER}
            )
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                MOCK_CONNECTION_CONFIG,
            )
            assert result["step_id"] == "x500_auth"

            # Step 2: Auth fails
            mock_client.initialize.side_effect = Exception("Login failed")
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {CONF_PIN_CODE: "wrong"},
            )

        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "invalid_auth"}

    async def test_form_duplicate_host(
        self,
        hass: HomeAssistant,
        mock_setup_entry: AsyncMock,
    ) -> None:
        """Test that duplicate hosts are rejected."""
        mock_client = create_mock_client()

        with patch(
            "aritech_ats.config_flow.AritechClient",
            return_value=mock_client,
        ):
            # Create first entry
            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_USER}
            )
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                MOCK_CONNECTION_CONFIG,
            )
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {CONF_PIN_CODE: MOCK_PIN},
            )
            assert result["type"] == FlowResultType.CREATE_ENTRY

            # Try to create duplicate entry
            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_USER}
            )
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                MOCK_CONNECTION_CONFIG,
            )

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "already_configured"

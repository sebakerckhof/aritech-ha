"""Tests for Aritech switches."""
from __future__ import annotations

import sys
from pathlib import Path

# Add custom_components directory to path for proper package imports
_custom_components_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_custom_components_dir))

from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.switch import SwitchDeviceClass
from homeassistant.core import HomeAssistant

from aritech_ats.switch import (
    AritechZoneInhibitSwitch,
    AritechOutputSwitch,
    AritechTriggerSwitch,
    AritechForceArmSwitch,
)

from .conftest import MockZoneState, MockOutputState, MockTriggerState


def create_mock_coordinator() -> MagicMock:
    """Create a mock coordinator for testing."""
    coordinator = MagicMock()
    coordinator.config_entry = MagicMock()
    coordinator.config_entry.entry_id = "test_entry_id"
    coordinator.connected = True
    coordinator.panel_model = "ATS4500"
    coordinator.panel_name = "Test Panel"
    coordinator.firmware_version = "1.2.3"
    coordinator.async_add_listener = MagicMock(return_value=lambda: None)
    coordinator.register_zone_callback = MagicMock(return_value=lambda: None)
    coordinator.register_output_callback = MagicMock(return_value=lambda: None)
    coordinator.register_trigger_callback = MagicMock(return_value=lambda: None)
    coordinator.get_zone_state_obj = MagicMock(return_value=MockZoneState())
    coordinator.get_output_state_obj = MagicMock(return_value=MockOutputState())
    coordinator.get_trigger_state_obj = MagicMock(return_value=MockTriggerState())
    coordinator.async_inhibit_zone = AsyncMock()
    coordinator.async_uninhibit_zone = AsyncMock()
    coordinator.async_activate_output = AsyncMock()
    coordinator.async_deactivate_output = AsyncMock()
    coordinator.async_activate_trigger = AsyncMock()
    coordinator.async_deactivate_trigger = AsyncMock()
    coordinator.set_force_arm = MagicMock()
    return coordinator


class TestZoneInhibitSwitch:
    """Tests for AritechZoneInhibitSwitch."""

    def test_entity_attributes(self) -> None:
        """Test entity attributes are set correctly."""
        coordinator = create_mock_coordinator()

        switch = AritechZoneInhibitSwitch(
            coordinator=coordinator,
            zone_number=1,
            zone_name="Front Door",
        )

        assert switch._attr_unique_id == "test_entry_id_zone_1_inhibit"
        assert switch._attr_name == "Inhibit"
        assert switch._attr_device_class == SwitchDeviceClass.SWITCH
        assert switch._attr_icon == "mdi:shield-off"

    def test_is_on_when_inhibited(self) -> None:
        """Test is_on returns True when zone is inhibited."""
        coordinator = create_mock_coordinator()
        coordinator.get_zone_state_obj.return_value = MockZoneState(is_inhibited=True)

        switch = AritechZoneInhibitSwitch(
            coordinator=coordinator,
            zone_number=1,
            zone_name="Front Door",
        )

        assert switch.is_on is True

    def test_is_off_when_not_inhibited(self) -> None:
        """Test is_on returns False when zone is not inhibited."""
        coordinator = create_mock_coordinator()
        coordinator.get_zone_state_obj.return_value = MockZoneState(is_inhibited=False)

        switch = AritechZoneInhibitSwitch(
            coordinator=coordinator,
            zone_number=1,
            zone_name="Front Door",
        )

        assert switch.is_on is False

    def test_is_none_when_no_state(self) -> None:
        """Test is_on returns None when no state available."""
        coordinator = create_mock_coordinator()
        coordinator.get_zone_state_obj.return_value = None

        switch = AritechZoneInhibitSwitch(
            coordinator=coordinator,
            zone_number=1,
            zone_name="Front Door",
        )

        assert switch.is_on is None

    @pytest.mark.asyncio
    async def test_turn_on_inhibits_zone(self) -> None:
        """Test turning on inhibits the zone."""
        coordinator = create_mock_coordinator()

        switch = AritechZoneInhibitSwitch(
            coordinator=coordinator,
            zone_number=1,
            zone_name="Front Door",
        )

        await switch.async_turn_on()
        coordinator.async_inhibit_zone.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_turn_off_uninhibits_zone(self) -> None:
        """Test turning off uninhibits the zone."""
        coordinator = create_mock_coordinator()

        switch = AritechZoneInhibitSwitch(
            coordinator=coordinator,
            zone_number=1,
            zone_name="Front Door",
        )

        await switch.async_turn_off()
        coordinator.async_uninhibit_zone.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_turn_on_error_handling(self) -> None:
        """Test error handling when inhibiting fails."""
        coordinator = create_mock_coordinator()
        coordinator.async_inhibit_zone.side_effect = Exception("Inhibit failed")

        switch = AritechZoneInhibitSwitch(
            coordinator=coordinator,
            zone_number=1,
            zone_name="Front Door",
        )

        with pytest.raises(Exception, match="Inhibit failed"):
            await switch.async_turn_on()

    def test_extra_state_attributes(self) -> None:
        """Test extra state attributes are returned."""
        coordinator = create_mock_coordinator()
        zone_state = MockZoneState(is_inhibited=True)
        coordinator.get_zone_state_obj.return_value = zone_state

        switch = AritechZoneInhibitSwitch(
            coordinator=coordinator,
            zone_number=1,
            zone_name="Front Door",
        )

        attrs = switch.extra_state_attributes
        assert attrs["zone_number"] == 1
        assert "state_text" in attrs


class TestOutputSwitch:
    """Tests for AritechOutputSwitch."""

    def test_entity_attributes(self) -> None:
        """Test entity attributes are set correctly."""
        coordinator = create_mock_coordinator()

        switch = AritechOutputSwitch(
            coordinator=coordinator,
            output_number=1,
            output_name="Siren",
        )

        assert switch._attr_unique_id == "test_entry_id_output_1"
        assert switch._attr_name == "Switch"
        assert switch._attr_device_class == SwitchDeviceClass.OUTLET
        assert switch._attr_icon == "mdi:electric-switch"

    def test_is_on_when_output_on(self) -> None:
        """Test is_on returns True when output is on."""
        coordinator = create_mock_coordinator()
        coordinator.get_output_state_obj.return_value = MockOutputState(is_on=True)

        switch = AritechOutputSwitch(
            coordinator=coordinator,
            output_number=1,
            output_name="Siren",
        )

        assert switch.is_on is True

    def test_is_on_when_output_active(self) -> None:
        """Test is_on returns True when output is active."""
        coordinator = create_mock_coordinator()
        coordinator.get_output_state_obj.return_value = MockOutputState(is_active=True)

        switch = AritechOutputSwitch(
            coordinator=coordinator,
            output_number=1,
            output_name="Siren",
        )

        assert switch.is_on is True

    def test_is_off_when_output_off(self) -> None:
        """Test is_on returns False when output is off."""
        coordinator = create_mock_coordinator()
        coordinator.get_output_state_obj.return_value = MockOutputState(
            is_on=False, is_active=False
        )

        switch = AritechOutputSwitch(
            coordinator=coordinator,
            output_number=1,
            output_name="Siren",
        )

        assert switch.is_on is False

    @pytest.mark.asyncio
    async def test_turn_on_activates_output(self) -> None:
        """Test turning on activates the output."""
        coordinator = create_mock_coordinator()

        switch = AritechOutputSwitch(
            coordinator=coordinator,
            output_number=1,
            output_name="Siren",
        )

        await switch.async_turn_on()
        coordinator.async_activate_output.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_turn_off_deactivates_output(self) -> None:
        """Test turning off deactivates the output."""
        coordinator = create_mock_coordinator()

        switch = AritechOutputSwitch(
            coordinator=coordinator,
            output_number=1,
            output_name="Siren",
        )

        await switch.async_turn_off()
        coordinator.async_deactivate_output.assert_called_once_with(1)

    def test_extra_state_attributes(self) -> None:
        """Test extra state attributes are returned."""
        coordinator = create_mock_coordinator()
        output_state = MockOutputState(is_on=True, is_forced=False)
        coordinator.get_output_state_obj.return_value = output_state

        switch = AritechOutputSwitch(
            coordinator=coordinator,
            output_number=1,
            output_name="Siren",
        )

        attrs = switch.extra_state_attributes
        assert attrs["output_number"] == 1
        assert attrs["is_forced"] is False


class TestTriggerSwitch:
    """Tests for AritechTriggerSwitch."""

    def test_entity_attributes(self) -> None:
        """Test entity attributes are set correctly."""
        coordinator = create_mock_coordinator()

        switch = AritechTriggerSwitch(
            coordinator=coordinator,
            trigger_number=1,
            trigger_name="Panic Button",
        )

        assert switch._attr_unique_id == "test_entry_id_trigger_1"
        assert switch._attr_name == "Panic Button"
        assert switch._attr_device_class == SwitchDeviceClass.SWITCH
        assert switch._attr_icon == "mdi:gesture-tap-button"

    def test_is_on_when_trigger_active(self) -> None:
        """Test is_on returns True when trigger is active."""
        coordinator = create_mock_coordinator()
        coordinator.get_trigger_state_obj.return_value = MockTriggerState(is_active=True)

        switch = AritechTriggerSwitch(
            coordinator=coordinator,
            trigger_number=1,
            trigger_name="Panic Button",
        )

        assert switch.is_on is True

    def test_is_off_when_trigger_inactive(self) -> None:
        """Test is_on returns False when trigger is inactive."""
        coordinator = create_mock_coordinator()
        coordinator.get_trigger_state_obj.return_value = MockTriggerState(is_active=False)

        switch = AritechTriggerSwitch(
            coordinator=coordinator,
            trigger_number=1,
            trigger_name="Panic Button",
        )

        assert switch.is_on is False

    @pytest.mark.asyncio
    async def test_turn_on_activates_trigger(self) -> None:
        """Test turning on activates the trigger."""
        coordinator = create_mock_coordinator()

        switch = AritechTriggerSwitch(
            coordinator=coordinator,
            trigger_number=1,
            trigger_name="Panic Button",
        )

        await switch.async_turn_on()
        coordinator.async_activate_trigger.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_turn_off_deactivates_trigger(self) -> None:
        """Test turning off deactivates the trigger."""
        coordinator = create_mock_coordinator()

        switch = AritechTriggerSwitch(
            coordinator=coordinator,
            trigger_number=1,
            trigger_name="Panic Button",
        )

        await switch.async_turn_off()
        coordinator.async_deactivate_trigger.assert_called_once_with(1)

    def test_extra_state_attributes(self) -> None:
        """Test extra state attributes are returned."""
        coordinator = create_mock_coordinator()
        trigger_state = MockTriggerState(
            is_active=False,
            is_remote_output=False,
            is_fob=False,
            is_schedule=False,
            is_function_key=True,
        )
        coordinator.get_trigger_state_obj.return_value = trigger_state

        switch = AritechTriggerSwitch(
            coordinator=coordinator,
            trigger_number=1,
            trigger_name="Panic Button",
        )

        attrs = switch.extra_state_attributes
        assert attrs["trigger_number"] == 1
        assert attrs["is_function_key"] is True


class TestForceArmSwitch:
    """Tests for AritechForceArmSwitch."""

    def test_entity_attributes(self) -> None:
        """Test entity attributes are set correctly."""
        coordinator = create_mock_coordinator()

        switch = AritechForceArmSwitch(
            coordinator=coordinator,
            area_number=1,
            area_name="Ground Floor",
        )

        assert switch._attr_unique_id == "test_entry_id_area_1_force_arm"
        assert switch._attr_name == "Force Arm"
        assert switch._attr_device_class == SwitchDeviceClass.SWITCH
        assert switch._attr_icon == "mdi:shield-lock"

    def test_is_on_default_false(self) -> None:
        """Test is_on returns False by default."""
        coordinator = create_mock_coordinator()

        switch = AritechForceArmSwitch(
            coordinator=coordinator,
            area_number=1,
            area_name="Ground Floor",
        )

        assert switch.is_on is False

    @pytest.mark.asyncio
    async def test_turn_on_enables_force_arm(self) -> None:
        """Test turning on enables force arm."""
        coordinator = create_mock_coordinator()

        switch = AritechForceArmSwitch(
            coordinator=coordinator,
            area_number=1,
            area_name="Ground Floor",
        )
        # Mock async_write_ha_state to avoid hass dependency
        switch.async_write_ha_state = MagicMock()

        await switch.async_turn_on()

        assert switch.is_on is True
        coordinator.set_force_arm.assert_called_once_with(1, True)

    @pytest.mark.asyncio
    async def test_turn_off_disables_force_arm(self) -> None:
        """Test turning off disables force arm."""
        coordinator = create_mock_coordinator()

        switch = AritechForceArmSwitch(
            coordinator=coordinator,
            area_number=1,
            area_name="Ground Floor",
        )
        # Mock async_write_ha_state to avoid hass dependency
        switch.async_write_ha_state = MagicMock()

        # First enable it
        await switch.async_turn_on()
        coordinator.set_force_arm.reset_mock()

        # Then disable it
        await switch.async_turn_off()

        assert switch.is_on is False
        coordinator.set_force_arm.assert_called_once_with(1, False)

    def test_available_when_connected(self) -> None:
        """Test switch is available when connected."""
        coordinator = create_mock_coordinator()
        coordinator.connected = True

        switch = AritechForceArmSwitch(
            coordinator=coordinator,
            area_number=1,
            area_name="Ground Floor",
        )

        assert switch.available is True

    def test_unavailable_when_disconnected(self) -> None:
        """Test switch is unavailable when disconnected."""
        coordinator = create_mock_coordinator()
        coordinator.connected = False

        switch = AritechForceArmSwitch(
            coordinator=coordinator,
            area_number=1,
            area_name="Ground Floor",
        )

        assert switch.available is False

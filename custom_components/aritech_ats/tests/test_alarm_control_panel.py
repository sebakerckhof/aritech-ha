"""Tests for Aritech ATS alarm control panel."""
from __future__ import annotations

import sys
from pathlib import Path

# Add custom_components directory to path for proper package imports
_custom_components_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_custom_components_dir))

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.alarm_control_panel import AlarmControlPanelState
from homeassistant.core import HomeAssistant

from aritech_ats.alarm_control_panel import (
    AritechAlarmControlPanel,
    _get_alarm_state,
)

from .conftest import (
    MOCK_CONFIG,
    MockAreaState,
    create_mock_client,
    create_mock_monitor,
)


def create_mock_coordinator() -> MagicMock:
    """Create a mock coordinator for testing."""
    coordinator = MagicMock()
    coordinator.config_entry = MagicMock()
    coordinator.config_entry.entry_id = "test_entry_id"
    coordinator.connected = True
    coordinator.async_add_listener = MagicMock(return_value=lambda: None)
    coordinator.register_area_callback = MagicMock(return_value=lambda: None)
    coordinator.get_area_state_obj = MagicMock(return_value=MockAreaState())
    coordinator.get_force_arm = MagicMock(return_value=False)
    coordinator.async_arm_area = AsyncMock()
    coordinator.async_disarm_area = AsyncMock()
    return coordinator


class TestGetAlarmState:
    """Tests for _get_alarm_state function."""

    def test_none_returns_disarmed(self) -> None:
        """Test that None state returns disarmed."""
        assert _get_alarm_state(None) == AlarmControlPanelState.DISARMED

    def test_unset_returns_disarmed(self) -> None:
        """Test that unset area returns disarmed."""
        state = MockAreaState(is_unset=True)
        assert _get_alarm_state(state) == AlarmControlPanelState.DISARMED

    def test_full_set_returns_armed_away(self) -> None:
        """Test that full set returns armed away."""
        state = MockAreaState(is_unset=False, is_full_set=True)
        assert _get_alarm_state(state) == AlarmControlPanelState.ARMED_AWAY

    def test_partially_set_returns_armed_home(self) -> None:
        """Test that part set 1 returns armed home."""
        state = MockAreaState(is_unset=False, is_partially_set=True)
        assert _get_alarm_state(state) == AlarmControlPanelState.ARMED_HOME

    def test_partially_set_2_returns_armed_night(self) -> None:
        """Test that part set 2 returns armed night."""
        state = MockAreaState(is_unset=False, is_partially_set_2=True)
        assert _get_alarm_state(state) == AlarmControlPanelState.ARMED_NIGHT

    def test_alarming_returns_triggered(self) -> None:
        """Test that alarming state returns triggered."""
        state = MockAreaState(is_alarming=True)
        assert _get_alarm_state(state) == AlarmControlPanelState.TRIGGERED

    def test_entering_returns_pending(self) -> None:
        """Test that entering state returns pending."""
        state = MockAreaState(is_entering=True)
        assert _get_alarm_state(state) == AlarmControlPanelState.PENDING

    def test_exiting_returns_arming(self) -> None:
        """Test that exiting state returns arming."""
        state = MockAreaState(is_exiting=True)
        assert _get_alarm_state(state) == AlarmControlPanelState.ARMING

    def test_alarming_takes_priority(self) -> None:
        """Test that alarming takes priority over armed states."""
        state = MockAreaState(is_alarming=True, is_full_set=True)
        assert _get_alarm_state(state) == AlarmControlPanelState.TRIGGERED


class TestAritechAlarmControlPanel:
    """Tests for AritechAlarmControlPanel entity."""

    def test_entity_attributes(self) -> None:
        """Test entity attributes are set correctly."""
        coordinator = create_mock_coordinator()

        panel = AritechAlarmControlPanel(
            coordinator=coordinator,
            area_number=1,
            area_name="Test Area",
        )

        assert panel._area_number == 1
        assert panel._area_name == "Test Area"
        assert panel._attr_unique_id == "test_entry_id_area_1"
        assert panel._attr_name == "Test Area"

    def test_available_when_connected(self) -> None:
        """Test entity is available when coordinator is connected."""
        coordinator = create_mock_coordinator()
        coordinator.connected = True

        panel = AritechAlarmControlPanel(
            coordinator=coordinator,
            area_number=1,
            area_name="Test Area",
        )

        assert panel.available is True

    def test_unavailable_when_disconnected(self) -> None:
        """Test entity is unavailable when coordinator is disconnected."""
        coordinator = create_mock_coordinator()
        coordinator.connected = False

        panel = AritechAlarmControlPanel(
            coordinator=coordinator,
            area_number=1,
            area_name="Test Area",
        )

        assert panel.available is False

    def test_alarm_state_disarmed(self) -> None:
        """Test alarm state returns disarmed when area is unset."""
        coordinator = create_mock_coordinator()
        coordinator.get_area_state_obj.return_value = MockAreaState(is_unset=True)

        panel = AritechAlarmControlPanel(
            coordinator=coordinator,
            area_number=1,
            area_name="Test Area",
        )

        assert panel.alarm_state == AlarmControlPanelState.DISARMED

    def test_alarm_state_armed_away(self) -> None:
        """Test alarm state returns armed away when full set."""
        coordinator = create_mock_coordinator()
        coordinator.get_area_state_obj.return_value = MockAreaState(
            is_unset=False, is_full_set=True
        )

        panel = AritechAlarmControlPanel(
            coordinator=coordinator,
            area_number=1,
            area_name="Test Area",
        )

        assert panel.alarm_state == AlarmControlPanelState.ARMED_AWAY

    def test_extra_state_attributes(self) -> None:
        """Test extra state attributes are returned."""
        coordinator = create_mock_coordinator()
        area_state = MockAreaState(
            is_ready_to_arm=True,
            is_tampered=False,
            has_fire=False,
        )
        coordinator.get_area_state_obj.return_value = area_state

        panel = AritechAlarmControlPanel(
            coordinator=coordinator,
            area_number=1,
            area_name="Test Area",
        )

        attrs = panel.extra_state_attributes
        assert attrs["area_number"] == 1
        assert attrs["is_ready_to_arm"] is True
        assert attrs["is_tampered"] is False
        assert attrs["has_fire"] is False

    def test_extra_state_attributes_no_state(self) -> None:
        """Test extra state attributes when no state available."""
        coordinator = create_mock_coordinator()
        coordinator.get_area_state_obj.return_value = None

        panel = AritechAlarmControlPanel(
            coordinator=coordinator,
            area_number=1,
            area_name="Test Area",
        )

        attrs = panel.extra_state_attributes
        assert attrs == {"area_number": 1}

    @pytest.mark.asyncio
    async def test_alarm_disarm(self) -> None:
        """Test disarming the alarm."""
        coordinator = create_mock_coordinator()

        panel = AritechAlarmControlPanel(
            coordinator=coordinator,
            area_number=1,
            area_name="Test Area",
        )

        await panel.async_alarm_disarm()
        coordinator.async_disarm_area.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_alarm_arm_away(self) -> None:
        """Test arming away (full set)."""
        coordinator = create_mock_coordinator()
        coordinator.get_force_arm.return_value = False

        panel = AritechAlarmControlPanel(
            coordinator=coordinator,
            area_number=1,
            area_name="Test Area",
        )

        await panel.async_alarm_arm_away()
        coordinator.async_arm_area.assert_called_once_with(1, "full", force=False)

    @pytest.mark.asyncio
    async def test_alarm_arm_away_with_force(self) -> None:
        """Test arming away with force enabled."""
        coordinator = create_mock_coordinator()
        coordinator.get_force_arm.return_value = True

        panel = AritechAlarmControlPanel(
            coordinator=coordinator,
            area_number=1,
            area_name="Test Area",
        )

        await panel.async_alarm_arm_away()
        coordinator.async_arm_area.assert_called_once_with(1, "full", force=True)

    @pytest.mark.asyncio
    async def test_alarm_arm_home(self) -> None:
        """Test arming home (part set 1)."""
        coordinator = create_mock_coordinator()
        coordinator.get_force_arm.return_value = False

        panel = AritechAlarmControlPanel(
            coordinator=coordinator,
            area_number=1,
            area_name="Test Area",
        )

        await panel.async_alarm_arm_home()
        coordinator.async_arm_area.assert_called_once_with(1, "part1", force=False)

    @pytest.mark.asyncio
    async def test_alarm_arm_night(self) -> None:
        """Test arming night (part set 2)."""
        coordinator = create_mock_coordinator()
        coordinator.get_force_arm.return_value = False

        panel = AritechAlarmControlPanel(
            coordinator=coordinator,
            area_number=1,
            area_name="Test Area",
        )

        await panel.async_alarm_arm_night()
        coordinator.async_arm_area.assert_called_once_with(1, "part2", force=False)

    @pytest.mark.asyncio
    async def test_alarm_disarm_error(self) -> None:
        """Test disarm error handling."""
        coordinator = create_mock_coordinator()
        coordinator.async_disarm_area.side_effect = Exception("Disarm failed")

        panel = AritechAlarmControlPanel(
            coordinator=coordinator,
            area_number=1,
            area_name="Test Area",
        )

        with pytest.raises(Exception, match="Disarm failed"):
            await panel.async_alarm_disarm()

    @pytest.mark.asyncio
    async def test_alarm_arm_error(self) -> None:
        """Test arm error handling."""
        coordinator = create_mock_coordinator()
        coordinator.async_arm_area.side_effect = Exception("Arm failed")

        panel = AritechAlarmControlPanel(
            coordinator=coordinator,
            area_number=1,
            area_name="Test Area",
        )

        with pytest.raises(Exception, match="Arm failed"):
            await panel.async_alarm_arm_away()

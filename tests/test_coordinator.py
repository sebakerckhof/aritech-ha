"""Tests for Aritech ATS coordinator."""
from __future__ import annotations

import sys
from pathlib import Path

# Add custom_components directory to path for proper package imports
_custom_components_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_custom_components_dir))

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from aritech_ats.coordinator import AritechCoordinator, AritechData

from .conftest import (
    MOCK_CONFIG,
    MockAreaState,
    MockZoneState,
    MockOutputState,
    MockTriggerState,
    create_mock_client,
    create_mock_monitor,
    create_mock_initialized_event,
)


def create_mock_config_entry(hass: HomeAssistant) -> MagicMock:
    """Create a mock config entry."""
    entry = MagicMock()
    entry.entry_id = "test_entry_id"
    entry.data = MOCK_CONFIG
    return entry


async def test_coordinator_connect_success(hass: HomeAssistant) -> None:
    """Test successful coordinator connection."""
    mock_client = create_mock_client()
    mock_monitor = create_mock_monitor()
    entry = create_mock_config_entry(hass)

    with (
        patch(
            "aritech_ats.coordinator.AritechClient",
            return_value=mock_client,
        ),
        patch(
            "aritech_ats.coordinator.AritechMonitor",
            return_value=mock_monitor,
        ),
    ):
        coordinator = AritechCoordinator(hass, entry)
        await coordinator.async_connect()

        assert coordinator.connected is True
        assert coordinator.panel_model == "ATS4500"
        assert coordinator.panel_name == "Test Panel"
        assert coordinator.firmware_version == "1.2.3"

        mock_client.connect.assert_called_once()
        mock_client.initialize.assert_called_once()
        mock_monitor.start.assert_called_once()


async def test_coordinator_connect_failure(hass: HomeAssistant) -> None:
    """Test coordinator connection failure."""
    mock_client = create_mock_client()
    mock_client.connect.side_effect = Exception("Connection failed")
    entry = create_mock_config_entry(hass)

    with patch(
        "aritech_ats.coordinator.AritechClient",
        return_value=mock_client,
    ):
        coordinator = AritechCoordinator(hass, entry)

        with pytest.raises(UpdateFailed, match="Failed to connect"):
            await coordinator.async_connect()

        assert coordinator.connected is False


async def test_coordinator_disconnect(hass: HomeAssistant) -> None:
    """Test coordinator disconnection."""
    mock_client = create_mock_client()
    mock_monitor = create_mock_monitor()
    entry = create_mock_config_entry(hass)

    with (
        patch(
            "aritech_ats.coordinator.AritechClient",
            return_value=mock_client,
        ),
        patch(
            "aritech_ats.coordinator.AritechMonitor",
            return_value=mock_monitor,
        ),
    ):
        coordinator = AritechCoordinator(hass, entry)
        await coordinator.async_connect()
        await coordinator.async_disconnect()

        assert coordinator.connected is False
        mock_client.disconnect.assert_called_once()
        mock_monitor.stop.assert_called_once()


async def test_coordinator_get_areas(hass: HomeAssistant) -> None:
    """Test getting areas from coordinator."""
    mock_client = create_mock_client()
    mock_monitor = create_mock_monitor()
    entry = create_mock_config_entry(hass)

    with (
        patch(
            "aritech_ats.coordinator.AritechClient",
            return_value=mock_client,
        ),
        patch(
            "aritech_ats.coordinator.AritechMonitor",
            return_value=mock_monitor,
        ),
    ):
        coordinator = AritechCoordinator(hass, entry)
        await coordinator.async_connect()

        # Simulate initialized event
        event = create_mock_initialized_event()
        coordinator._data.areas = [
            {"number": a.number, "name": a.name} for a in event.areas
        ]
        coordinator._data.area_states = event.area_states

        areas = coordinator.get_areas()
        assert len(areas) == 2
        assert areas[0]["number"] == 1
        assert areas[0]["name"] == "Ground Floor"


async def test_coordinator_get_zones(hass: HomeAssistant) -> None:
    """Test getting zones from coordinator."""
    mock_client = create_mock_client()
    mock_monitor = create_mock_monitor()
    entry = create_mock_config_entry(hass)

    with (
        patch(
            "aritech_ats.coordinator.AritechClient",
            return_value=mock_client,
        ),
        patch(
            "aritech_ats.coordinator.AritechMonitor",
            return_value=mock_monitor,
        ),
    ):
        coordinator = AritechCoordinator(hass, entry)
        await coordinator.async_connect()

        # Simulate initialized event
        event = create_mock_initialized_event()
        coordinator._data.zones = [
            {"number": z.number, "name": z.name} for z in event.zones
        ]

        zones = coordinator.get_zones()
        assert len(zones) == 3
        assert zones[0]["name"] == "Front Door"


async def test_coordinator_get_area_state(hass: HomeAssistant) -> None:
    """Test getting area state from coordinator."""
    mock_client = create_mock_client()
    mock_monitor = create_mock_monitor()
    entry = create_mock_config_entry(hass)

    with (
        patch(
            "aritech_ats.coordinator.AritechClient",
            return_value=mock_client,
        ),
        patch(
            "aritech_ats.coordinator.AritechMonitor",
            return_value=mock_monitor,
        ),
    ):
        coordinator = AritechCoordinator(hass, entry)
        await coordinator.async_connect()

        # Set up area state
        area_state = MockAreaState(is_unset=True)
        coordinator._data.area_states[1] = {"state": area_state}

        state_obj = coordinator.get_area_state_obj(1)
        assert state_obj is not None
        assert state_obj.is_unset is True
        assert state_obj.is_full_set is False


async def test_coordinator_get_zone_state(hass: HomeAssistant) -> None:
    """Test getting zone state from coordinator."""
    mock_client = create_mock_client()
    mock_monitor = create_mock_monitor()
    entry = create_mock_config_entry(hass)

    with (
        patch(
            "aritech_ats.coordinator.AritechClient",
            return_value=mock_client,
        ),
        patch(
            "aritech_ats.coordinator.AritechMonitor",
            return_value=mock_monitor,
        ),
    ):
        coordinator = AritechCoordinator(hass, entry)
        await coordinator.async_connect()

        # Set up zone state
        zone_state = MockZoneState(is_active=True)
        coordinator._data.zone_states[1] = {"state": zone_state}

        state_obj = coordinator.get_zone_state_obj(1)
        assert state_obj is not None
        assert state_obj.is_active is True


async def test_coordinator_arm_area(hass: HomeAssistant) -> None:
    """Test arming an area."""
    mock_client = create_mock_client()
    mock_monitor = create_mock_monitor()
    entry = create_mock_config_entry(hass)

    with (
        patch(
            "aritech_ats.coordinator.AritechClient",
            return_value=mock_client,
        ),
        patch(
            "aritech_ats.coordinator.AritechMonitor",
            return_value=mock_monitor,
        ),
    ):
        coordinator = AritechCoordinator(hass, entry)
        await coordinator.async_connect()

        await coordinator.async_arm_area(1, mode="full", force=False)
        mock_client.arm_area.assert_called_once_with(1, set_type="full", force=False)


async def test_coordinator_disarm_area(hass: HomeAssistant) -> None:
    """Test disarming an area."""
    mock_client = create_mock_client()
    mock_monitor = create_mock_monitor()
    entry = create_mock_config_entry(hass)

    with (
        patch(
            "aritech_ats.coordinator.AritechClient",
            return_value=mock_client,
        ),
        patch(
            "aritech_ats.coordinator.AritechMonitor",
            return_value=mock_monitor,
        ),
    ):
        coordinator = AritechCoordinator(hass, entry)
        await coordinator.async_connect()

        await coordinator.async_disarm_area(1)
        mock_client.disarm_area.assert_called_once_with(1)


async def test_coordinator_inhibit_zone(hass: HomeAssistant) -> None:
    """Test inhibiting a zone."""
    mock_client = create_mock_client()
    mock_monitor = create_mock_monitor()
    entry = create_mock_config_entry(hass)

    with (
        patch(
            "aritech_ats.coordinator.AritechClient",
            return_value=mock_client,
        ),
        patch(
            "aritech_ats.coordinator.AritechMonitor",
            return_value=mock_monitor,
        ),
    ):
        coordinator = AritechCoordinator(hass, entry)
        await coordinator.async_connect()

        await coordinator.async_inhibit_zone(1)
        mock_client.inhibit_zone.assert_called_once_with(1)


async def test_coordinator_uninhibit_zone(hass: HomeAssistant) -> None:
    """Test uninhibiting a zone."""
    mock_client = create_mock_client()
    mock_monitor = create_mock_monitor()
    entry = create_mock_config_entry(hass)

    with (
        patch(
            "aritech_ats.coordinator.AritechClient",
            return_value=mock_client,
        ),
        patch(
            "aritech_ats.coordinator.AritechMonitor",
            return_value=mock_monitor,
        ),
    ):
        coordinator = AritechCoordinator(hass, entry)
        await coordinator.async_connect()

        await coordinator.async_uninhibit_zone(1)
        mock_client.uninhibit_zone.assert_called_once_with(1)


async def test_coordinator_activate_output(hass: HomeAssistant) -> None:
    """Test activating an output."""
    mock_client = create_mock_client()
    mock_monitor = create_mock_monitor()
    entry = create_mock_config_entry(hass)

    with (
        patch(
            "aritech_ats.coordinator.AritechClient",
            return_value=mock_client,
        ),
        patch(
            "aritech_ats.coordinator.AritechMonitor",
            return_value=mock_monitor,
        ),
    ):
        coordinator = AritechCoordinator(hass, entry)
        await coordinator.async_connect()

        await coordinator.async_activate_output(1)
        mock_client.activate_output.assert_called_once_with(1)


async def test_coordinator_deactivate_output(hass: HomeAssistant) -> None:
    """Test deactivating an output."""
    mock_client = create_mock_client()
    mock_monitor = create_mock_monitor()
    entry = create_mock_config_entry(hass)

    with (
        patch(
            "aritech_ats.coordinator.AritechClient",
            return_value=mock_client,
        ),
        patch(
            "aritech_ats.coordinator.AritechMonitor",
            return_value=mock_monitor,
        ),
    ):
        coordinator = AritechCoordinator(hass, entry)
        await coordinator.async_connect()

        await coordinator.async_deactivate_output(1)
        mock_client.deactivate_output.assert_called_once_with(1)


async def test_coordinator_force_arm(hass: HomeAssistant) -> None:
    """Test force arm state management."""
    mock_client = create_mock_client()
    mock_monitor = create_mock_monitor()
    entry = create_mock_config_entry(hass)

    with (
        patch(
            "aritech_ats.coordinator.AritechClient",
            return_value=mock_client,
        ),
        patch(
            "aritech_ats.coordinator.AritechMonitor",
            return_value=mock_monitor,
        ),
    ):
        coordinator = AritechCoordinator(hass, entry)

        # Default is False
        assert coordinator.get_force_arm(1) is False

        # Set to True
        coordinator.set_force_arm(1, True)
        assert coordinator.get_force_arm(1) is True

        # Set back to False
        coordinator.set_force_arm(1, False)
        assert coordinator.get_force_arm(1) is False


async def test_coordinator_register_callbacks(hass: HomeAssistant) -> None:
    """Test registering and unregistering callbacks."""
    mock_client = create_mock_client()
    mock_monitor = create_mock_monitor()
    entry = create_mock_config_entry(hass)

    with (
        patch(
            "aritech_ats.coordinator.AritechClient",
            return_value=mock_client,
        ),
        patch(
            "aritech_ats.coordinator.AritechMonitor",
            return_value=mock_monitor,
        ),
    ):
        coordinator = AritechCoordinator(hass, entry)

        callback_called = False

        def test_callback() -> None:
            nonlocal callback_called
            callback_called = True

        # Register callback
        unregister = coordinator.register_area_callback(1, test_callback)
        assert 1 in coordinator._area_callbacks
        assert test_callback in coordinator._area_callbacks[1]

        # Unregister callback
        unregister()
        assert test_callback not in coordinator._area_callbacks[1]


async def test_coordinator_command_not_connected(hass: HomeAssistant) -> None:
    """Test that commands fail when not connected."""
    entry = create_mock_config_entry(hass)
    coordinator = AritechCoordinator(hass, entry)

    with pytest.raises(UpdateFailed, match="Not connected to panel"):
        await coordinator.async_arm_area(1)

    with pytest.raises(UpdateFailed, match="Not connected to panel"):
        await coordinator.async_disarm_area(1)

    with pytest.raises(UpdateFailed, match="Not connected to panel"):
        await coordinator.async_inhibit_zone(1)


async def test_coordinator_get_nonexistent_state(hass: HomeAssistant) -> None:
    """Test getting state for nonexistent entity returns None."""
    entry = create_mock_config_entry(hass)
    coordinator = AritechCoordinator(hass, entry)

    assert coordinator.get_area_state_obj(999) is None
    assert coordinator.get_zone_state_obj(999) is None
    assert coordinator.get_output_state_obj(999) is None
    assert coordinator.get_trigger_state_obj(999) is None


async def test_coordinator_activate_trigger(hass: HomeAssistant) -> None:
    """Test activating a trigger."""
    mock_client = create_mock_client()
    mock_monitor = create_mock_monitor()
    entry = create_mock_config_entry(hass)

    with (
        patch(
            "aritech_ats.coordinator.AritechClient",
            return_value=mock_client,
        ),
        patch(
            "aritech_ats.coordinator.AritechMonitor",
            return_value=mock_monitor,
        ),
    ):
        coordinator = AritechCoordinator(hass, entry)
        await coordinator.async_connect()

        await coordinator.async_activate_trigger(1)
        mock_client.activate_trigger.assert_called_once_with(1)


async def test_coordinator_deactivate_trigger(hass: HomeAssistant) -> None:
    """Test deactivating a trigger."""
    mock_client = create_mock_client()
    mock_monitor = create_mock_monitor()
    entry = create_mock_config_entry(hass)

    with (
        patch(
            "aritech_ats.coordinator.AritechClient",
            return_value=mock_client,
        ),
        patch(
            "aritech_ats.coordinator.AritechMonitor",
            return_value=mock_monitor,
        ),
    ):
        coordinator = AritechCoordinator(hass, entry)
        await coordinator.async_connect()

        await coordinator.async_deactivate_trigger(1)
        mock_client.deactivate_trigger.assert_called_once_with(1)

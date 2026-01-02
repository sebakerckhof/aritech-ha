"""Tests for Aritech sensors."""
from __future__ import annotations

import sys
from pathlib import Path

# Add custom_components directory to path for proper package imports
_custom_components_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_custom_components_dir))

from unittest.mock import MagicMock

import pytest

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant

from aritech_ats.sensor import (
    AritechPanelModelSensor,
    AritechFirmwareVersionSensor,
    AritechConnectionStatusSensor,
    AritechAreaStateSensor,
    AritechZoneStateSensor,
)

from .conftest import MockAreaState, MockZoneState


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
    coordinator.register_area_callback = MagicMock(return_value=lambda: None)
    coordinator.register_zone_callback = MagicMock(return_value=lambda: None)
    coordinator.get_area_state_obj = MagicMock(return_value=MockAreaState())
    coordinator.get_zone_state_obj = MagicMock(return_value=MockZoneState())
    return coordinator


class TestPanelModelSensor:
    """Tests for AritechPanelModelSensor."""

    def test_entity_attributes(self) -> None:
        """Test entity attributes are set correctly."""
        coordinator = create_mock_coordinator()

        sensor = AritechPanelModelSensor(coordinator)

        assert sensor._attr_unique_id == "test_entry_id_panel_model"
        assert sensor._attr_name == "Panel Model"
        assert sensor._attr_entity_category == EntityCategory.DIAGNOSTIC
        assert sensor._attr_icon == "mdi:shield-home"

    def test_native_value(self) -> None:
        """Test native value returns panel model."""
        coordinator = create_mock_coordinator()

        sensor = AritechPanelModelSensor(coordinator)

        assert sensor.native_value == "ATS4500"

    def test_available_when_connected(self) -> None:
        """Test sensor is available when connected."""
        coordinator = create_mock_coordinator()
        coordinator.connected = True

        sensor = AritechPanelModelSensor(coordinator)

        assert sensor.available is True

    def test_unavailable_when_disconnected(self) -> None:
        """Test sensor is unavailable when disconnected."""
        coordinator = create_mock_coordinator()
        coordinator.connected = False

        sensor = AritechPanelModelSensor(coordinator)

        assert sensor.available is False


class TestFirmwareVersionSensor:
    """Tests for AritechFirmwareVersionSensor."""

    def test_entity_attributes(self) -> None:
        """Test entity attributes are set correctly."""
        coordinator = create_mock_coordinator()

        sensor = AritechFirmwareVersionSensor(coordinator)

        assert sensor._attr_unique_id == "test_entry_id_firmware_version"
        assert sensor._attr_name == "Firmware Version"
        assert sensor._attr_entity_category == EntityCategory.DIAGNOSTIC
        assert sensor._attr_icon == "mdi:chip"

    def test_native_value(self) -> None:
        """Test native value returns firmware version."""
        coordinator = create_mock_coordinator()

        sensor = AritechFirmwareVersionSensor(coordinator)

        assert sensor.native_value == "1.2.3"


class TestConnectionStatusSensor:
    """Tests for AritechConnectionStatusSensor."""

    def test_entity_attributes(self) -> None:
        """Test entity attributes are set correctly."""
        coordinator = create_mock_coordinator()

        sensor = AritechConnectionStatusSensor(coordinator)

        assert sensor._attr_unique_id == "test_entry_id_connection_status"
        assert sensor._attr_name == "Connection Status"
        assert sensor._attr_entity_category == EntityCategory.DIAGNOSTIC
        assert sensor._attr_icon == "mdi:lan-connect"
        assert sensor._attr_device_class == SensorDeviceClass.ENUM
        assert sensor._attr_options == ["connected", "disconnected"]

    def test_native_value_connected(self) -> None:
        """Test native value returns connected when connected."""
        coordinator = create_mock_coordinator()
        coordinator.connected = True

        sensor = AritechConnectionStatusSensor(coordinator)

        assert sensor.native_value == "connected"

    def test_native_value_disconnected(self) -> None:
        """Test native value returns disconnected when disconnected."""
        coordinator = create_mock_coordinator()
        coordinator.connected = False

        sensor = AritechConnectionStatusSensor(coordinator)

        assert sensor.native_value == "disconnected"

    def test_always_available(self) -> None:
        """Test sensor is always available."""
        coordinator = create_mock_coordinator()
        coordinator.connected = False

        sensor = AritechConnectionStatusSensor(coordinator)

        # Connection status sensor should always be available
        assert sensor.available is True


class TestAreaStateSensor:
    """Tests for AritechAreaStateSensor."""

    def test_entity_attributes(self) -> None:
        """Test entity attributes are set correctly."""
        coordinator = create_mock_coordinator()

        sensor = AritechAreaStateSensor(
            coordinator=coordinator,
            area_number=1,
            area_name="Ground Floor",
        )

        assert sensor._attr_unique_id == "test_entry_id_area_1_state"
        assert sensor._attr_name == "State"
        assert sensor._attr_icon == "mdi:shield-home-outline"

    def test_native_value_unset(self) -> None:
        """Test native value returns unset state."""
        coordinator = create_mock_coordinator()
        coordinator.get_area_state_obj.return_value = MockAreaState(is_unset=True)

        sensor = AritechAreaStateSensor(
            coordinator=coordinator,
            area_number=1,
            area_name="Ground Floor",
        )

        assert sensor.native_value == "Unset"

    def test_native_value_full_set(self) -> None:
        """Test native value returns full set state."""
        coordinator = create_mock_coordinator()
        coordinator.get_area_state_obj.return_value = MockAreaState(
            is_unset=False, is_full_set=True
        )

        sensor = AritechAreaStateSensor(
            coordinator=coordinator,
            area_number=1,
            area_name="Ground Floor",
        )

        assert sensor.native_value == "Full Set"

    def test_native_value_alarming(self) -> None:
        """Test native value returns alarming state."""
        coordinator = create_mock_coordinator()
        coordinator.get_area_state_obj.return_value = MockAreaState(is_alarming=True)

        sensor = AritechAreaStateSensor(
            coordinator=coordinator,
            area_number=1,
            area_name="Ground Floor",
        )

        assert sensor.native_value == "Alarming"

    def test_native_value_unknown(self) -> None:
        """Test native value returns unknown when no state."""
        coordinator = create_mock_coordinator()
        coordinator.get_area_state_obj.return_value = None

        sensor = AritechAreaStateSensor(
            coordinator=coordinator,
            area_number=1,
            area_name="Ground Floor",
        )

        assert sensor.native_value == "unknown"

    def test_extra_state_attributes(self) -> None:
        """Test extra state attributes are returned."""
        coordinator = create_mock_coordinator()
        area_state = MockAreaState(
            is_ready_to_arm=True,
            is_exiting=False,
            is_entering=False,
        )
        coordinator.get_area_state_obj.return_value = area_state

        sensor = AritechAreaStateSensor(
            coordinator=coordinator,
            area_number=1,
            area_name="Ground Floor",
        )

        attrs = sensor.extra_state_attributes
        assert attrs["area_number"] == 1
        assert attrs["is_ready_to_arm"] is True
        assert attrs["is_exiting"] is False
        assert attrs["is_entering"] is False

    def test_extra_state_attributes_no_state(self) -> None:
        """Test extra state attributes when no state available."""
        coordinator = create_mock_coordinator()
        coordinator.get_area_state_obj.return_value = None

        sensor = AritechAreaStateSensor(
            coordinator=coordinator,
            area_number=1,
            area_name="Ground Floor",
        )

        attrs = sensor.extra_state_attributes
        assert attrs == {"area_number": 1}


class TestZoneStateSensor:
    """Tests for AritechZoneStateSensor."""

    def test_entity_attributes(self) -> None:
        """Test entity attributes are set correctly."""
        coordinator = create_mock_coordinator()

        sensor = AritechZoneStateSensor(
            coordinator=coordinator,
            zone_number=1,
            zone_name="Front Door",
        )

        assert sensor._attr_unique_id == "test_entry_id_zone_1_state"
        assert sensor._attr_name == "State"
        assert sensor._attr_icon == "mdi:motion-sensor"

    def test_native_value_normal(self) -> None:
        """Test native value returns normal state."""
        coordinator = create_mock_coordinator()
        coordinator.get_zone_state_obj.return_value = MockZoneState()

        sensor = AritechZoneStateSensor(
            coordinator=coordinator,
            zone_number=1,
            zone_name="Front Door",
        )

        assert sensor.native_value == "Normal"

    def test_native_value_active(self) -> None:
        """Test native value returns active state."""
        coordinator = create_mock_coordinator()
        coordinator.get_zone_state_obj.return_value = MockZoneState(is_active=True)

        sensor = AritechZoneStateSensor(
            coordinator=coordinator,
            zone_number=1,
            zone_name="Front Door",
        )

        assert sensor.native_value == "Active"

    def test_native_value_multiple_states(self) -> None:
        """Test native value returns multiple states."""
        coordinator = create_mock_coordinator()
        coordinator.get_zone_state_obj.return_value = MockZoneState(
            is_active=True, is_tampered=True
        )

        sensor = AritechZoneStateSensor(
            coordinator=coordinator,
            zone_number=1,
            zone_name="Front Door",
        )

        assert "Active" in sensor.native_value
        assert "Tampered" in sensor.native_value

    def test_native_value_unknown(self) -> None:
        """Test native value returns unknown when no state."""
        coordinator = create_mock_coordinator()
        coordinator.get_zone_state_obj.return_value = None

        sensor = AritechZoneStateSensor(
            coordinator=coordinator,
            zone_number=1,
            zone_name="Front Door",
        )

        assert sensor.native_value == "unknown"

    def test_extra_state_attributes(self) -> None:
        """Test extra state attributes are returned."""
        coordinator = create_mock_coordinator()
        zone_state = MockZoneState(
            is_set=False,
            is_inhibited=False,
            is_isolated=False,
        )
        coordinator.get_zone_state_obj.return_value = zone_state

        sensor = AritechZoneStateSensor(
            coordinator=coordinator,
            zone_number=1,
            zone_name="Front Door",
        )

        attrs = sensor.extra_state_attributes
        assert attrs["zone_number"] == 1
        assert attrs["is_set"] is False
        assert attrs["is_inhibited"] is False
        assert attrs["is_isolated"] is False

    def test_extra_state_attributes_no_state(self) -> None:
        """Test extra state attributes when no state available."""
        coordinator = create_mock_coordinator()
        coordinator.get_zone_state_obj.return_value = None

        sensor = AritechZoneStateSensor(
            coordinator=coordinator,
            zone_number=1,
            zone_name="Front Door",
        )

        attrs = sensor.extra_state_attributes
        assert attrs == {"zone_number": 1}

    def test_available_when_connected(self) -> None:
        """Test sensor is available when connected."""
        coordinator = create_mock_coordinator()
        coordinator.connected = True

        sensor = AritechZoneStateSensor(
            coordinator=coordinator,
            zone_number=1,
            zone_name="Front Door",
        )

        assert sensor.available is True

    def test_unavailable_when_disconnected(self) -> None:
        """Test sensor is unavailable when disconnected."""
        coordinator = create_mock_coordinator()
        coordinator.connected = False

        sensor = AritechZoneStateSensor(
            coordinator=coordinator,
            zone_number=1,
            zone_name="Front Door",
        )

        assert sensor.available is False

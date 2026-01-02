"""Tests for Aritech binary sensors."""
from __future__ import annotations

import sys
from pathlib import Path

# Add custom_components directory to path for proper package imports
_custom_components_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_custom_components_dir))

from unittest.mock import MagicMock

import pytest

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.core import HomeAssistant

from aritech_ats.binary_sensor import (
    AritechZoneActiveBinarySensor,
    AritechZoneTamperBinarySensor,
    AritechZoneFaultBinarySensor,
    AritechZoneAlarmingBinarySensor,
    AritechZoneIsolatedBinarySensor,
    AritechAreaAlarmBinarySensor,
    AritechAreaTamperBinarySensor,
    AritechAreaFireBinarySensor,
    AritechAreaPanicBinarySensor,
    guess_device_class,
)

from .conftest import MockAreaState, MockZoneState


def create_mock_coordinator() -> MagicMock:
    """Create a mock coordinator for testing."""
    coordinator = MagicMock()
    coordinator.config_entry = MagicMock()
    coordinator.config_entry.entry_id = "test_entry_id"
    coordinator.connected = True
    coordinator.async_add_listener = MagicMock(return_value=lambda: None)
    coordinator.register_zone_callback = MagicMock(return_value=lambda: None)
    coordinator.register_area_callback = MagicMock(return_value=lambda: None)
    coordinator.get_zone_state_obj = MagicMock(return_value=MockZoneState())
    coordinator.get_area_state_obj = MagicMock(return_value=MockAreaState())
    return coordinator


class TestGuessDeviceClass:
    """Tests for guess_device_class function."""

    def test_pir_returns_motion(self) -> None:
        """Test PIR in name returns motion class."""
        assert guess_device_class("Living Room PIR") == BinarySensorDeviceClass.MOTION

    def test_motion_returns_motion(self) -> None:
        """Test motion in name returns motion class."""
        assert guess_device_class("Motion Sensor") == BinarySensorDeviceClass.MOTION

    def test_door_returns_door(self) -> None:
        """Test door in name returns door class."""
        assert guess_device_class("Front Door") == BinarySensorDeviceClass.DOOR

    def test_window_returns_window(self) -> None:
        """Test window in name returns window class."""
        assert guess_device_class("Kitchen Window") == BinarySensorDeviceClass.WINDOW

    def test_smoke_returns_smoke(self) -> None:
        """Test smoke in name returns smoke class."""
        # Note: "Smoke Detector" would match "detector" -> MOTION first
        assert guess_device_class("Smoke Alarm") == BinarySensorDeviceClass.SMOKE

    def test_glass_returns_vibration(self) -> None:
        """Test glass break in name returns vibration class."""
        assert guess_device_class("Glass Break") == BinarySensorDeviceClass.VIBRATION

    def test_garage_returns_garage_door(self) -> None:
        """Test garage in name returns garage door class."""
        # Note: "Garage Door" matches "door" -> DOOR first, use just "Garage"
        assert guess_device_class("Garage") == BinarySensorDeviceClass.GARAGE_DOOR

    def test_tamper_returns_tamper(self) -> None:
        """Test tamper in name returns tamper class."""
        assert guess_device_class("Tamper Zone") == BinarySensorDeviceClass.TAMPER

    def test_panic_returns_safety(self) -> None:
        """Test panic in name returns safety class."""
        assert guess_device_class("Panic Button") == BinarySensorDeviceClass.SAFETY

    def test_water_returns_moisture(self) -> None:
        """Test water in name returns moisture class."""
        assert guess_device_class("Water Leak") == BinarySensorDeviceClass.MOISTURE

    def test_heat_returns_heat(self) -> None:
        """Test heat in name returns heat class."""
        # Note: "Heat Detector" would match "detector" -> MOTION first
        assert guess_device_class("Heat Sensor") == BinarySensorDeviceClass.HEAT

    def test_gas_returns_gas(self) -> None:
        """Test gas in name returns gas class."""
        # Note: "Gas Detector" would match "detector" -> MOTION first
        assert guess_device_class("Gas Sensor") == BinarySensorDeviceClass.GAS

    def test_unknown_defaults_to_motion(self) -> None:
        """Test unknown name defaults to motion class."""
        assert guess_device_class("Zone 1") == BinarySensorDeviceClass.MOTION

    def test_case_insensitive(self) -> None:
        """Test matching is case insensitive."""
        assert guess_device_class("FRONT DOOR") == BinarySensorDeviceClass.DOOR
        assert guess_device_class("front door") == BinarySensorDeviceClass.DOOR


class TestZoneActiveBinarySensor:
    """Tests for AritechZoneActiveBinarySensor."""

    def test_entity_attributes(self) -> None:
        """Test entity attributes are set correctly."""
        coordinator = create_mock_coordinator()

        sensor = AritechZoneActiveBinarySensor(
            coordinator=coordinator,
            zone_number=1,
            zone_name="Front Door",
        )

        assert sensor._zone_number == 1
        assert sensor._zone_name == "Front Door"
        assert sensor._attr_unique_id == "test_entry_id_zone_1_active"
        assert sensor._attr_name == "Active"
        assert sensor._attr_device_class == BinarySensorDeviceClass.DOOR

    def test_is_on_when_active(self) -> None:
        """Test is_on returns True when zone is active."""
        coordinator = create_mock_coordinator()
        coordinator.get_zone_state_obj.return_value = MockZoneState(is_active=True)

        sensor = AritechZoneActiveBinarySensor(
            coordinator=coordinator,
            zone_number=1,
            zone_name="Front Door",
        )

        assert sensor.is_on is True

    def test_is_off_when_inactive(self) -> None:
        """Test is_on returns False when zone is inactive."""
        coordinator = create_mock_coordinator()
        coordinator.get_zone_state_obj.return_value = MockZoneState(is_active=False)

        sensor = AritechZoneActiveBinarySensor(
            coordinator=coordinator,
            zone_number=1,
            zone_name="Front Door",
        )

        assert sensor.is_on is False

    def test_is_none_when_no_state(self) -> None:
        """Test is_on returns None when no state available."""
        coordinator = create_mock_coordinator()
        coordinator.get_zone_state_obj.return_value = None

        sensor = AritechZoneActiveBinarySensor(
            coordinator=coordinator,
            zone_number=1,
            zone_name="Front Door",
        )

        assert sensor.is_on is None

    def test_extra_state_attributes(self) -> None:
        """Test extra state attributes are returned."""
        coordinator = create_mock_coordinator()
        zone_state = MockZoneState(
            is_active=True,
            is_set=False,
            is_anti_mask=False,
            is_in_soak_test=False,
            has_battery_fault=False,
            is_dirty=False,
        )
        coordinator.get_zone_state_obj.return_value = zone_state

        sensor = AritechZoneActiveBinarySensor(
            coordinator=coordinator,
            zone_number=1,
            zone_name="Front Door",
        )

        attrs = sensor.extra_state_attributes
        assert attrs["zone_number"] == 1
        assert attrs["is_set"] is False
        assert attrs["is_anti_mask"] is False


class TestZoneTamperBinarySensor:
    """Tests for AritechZoneTamperBinarySensor."""

    def test_device_class_is_tamper(self) -> None:
        """Test device class is tamper."""
        coordinator = create_mock_coordinator()

        sensor = AritechZoneTamperBinarySensor(
            coordinator=coordinator,
            zone_number=1,
            zone_name="Front Door",
        )

        assert sensor._attr_device_class == BinarySensorDeviceClass.TAMPER

    def test_is_on_when_tampered(self) -> None:
        """Test is_on returns True when zone is tampered."""
        coordinator = create_mock_coordinator()
        coordinator.get_zone_state_obj.return_value = MockZoneState(is_tampered=True)

        sensor = AritechZoneTamperBinarySensor(
            coordinator=coordinator,
            zone_number=1,
            zone_name="Front Door",
        )

        assert sensor.is_on is True


class TestZoneFaultBinarySensor:
    """Tests for AritechZoneFaultBinarySensor."""

    def test_device_class_is_problem(self) -> None:
        """Test device class is problem."""
        coordinator = create_mock_coordinator()

        sensor = AritechZoneFaultBinarySensor(
            coordinator=coordinator,
            zone_number=1,
            zone_name="Front Door",
        )

        assert sensor._attr_device_class == BinarySensorDeviceClass.PROBLEM

    def test_is_on_when_fault(self) -> None:
        """Test is_on returns True when zone has fault."""
        coordinator = create_mock_coordinator()
        coordinator.get_zone_state_obj.return_value = MockZoneState(has_fault=True)

        sensor = AritechZoneFaultBinarySensor(
            coordinator=coordinator,
            zone_number=1,
            zone_name="Front Door",
        )

        assert sensor.is_on is True


class TestZoneAlarmingBinarySensor:
    """Tests for AritechZoneAlarmingBinarySensor."""

    def test_device_class_is_safety(self) -> None:
        """Test device class is safety."""
        coordinator = create_mock_coordinator()

        sensor = AritechZoneAlarmingBinarySensor(
            coordinator=coordinator,
            zone_number=1,
            zone_name="Front Door",
        )

        assert sensor._attr_device_class == BinarySensorDeviceClass.SAFETY

    def test_is_on_when_alarming(self) -> None:
        """Test is_on returns True when zone is alarming."""
        coordinator = create_mock_coordinator()
        coordinator.get_zone_state_obj.return_value = MockZoneState(is_alarming=True)

        sensor = AritechZoneAlarmingBinarySensor(
            coordinator=coordinator,
            zone_number=1,
            zone_name="Front Door",
        )

        assert sensor.is_on is True


class TestZoneIsolatedBinarySensor:
    """Tests for AritechZoneIsolatedBinarySensor."""

    def test_is_on_when_isolated(self) -> None:
        """Test is_on returns True when zone is isolated."""
        coordinator = create_mock_coordinator()
        coordinator.get_zone_state_obj.return_value = MockZoneState(is_isolated=True)

        sensor = AritechZoneIsolatedBinarySensor(
            coordinator=coordinator,
            zone_number=1,
            zone_name="Front Door",
        )

        assert sensor.is_on is True

    def test_icon_is_link_off(self) -> None:
        """Test icon is link-off."""
        coordinator = create_mock_coordinator()

        sensor = AritechZoneIsolatedBinarySensor(
            coordinator=coordinator,
            zone_number=1,
            zone_name="Front Door",
        )

        assert sensor._attr_icon == "mdi:link-off"


class TestAreaAlarmBinarySensor:
    """Tests for AritechAreaAlarmBinarySensor."""

    def test_device_class_is_safety(self) -> None:
        """Test device class is safety."""
        coordinator = create_mock_coordinator()

        sensor = AritechAreaAlarmBinarySensor(
            coordinator=coordinator,
            area_number=1,
            area_name="Ground Floor",
        )

        assert sensor._attr_device_class == BinarySensorDeviceClass.SAFETY

    def test_is_on_when_alarming(self) -> None:
        """Test is_on returns True when area is alarming."""
        coordinator = create_mock_coordinator()
        coordinator.get_area_state_obj.return_value = MockAreaState(is_alarming=True)

        sensor = AritechAreaAlarmBinarySensor(
            coordinator=coordinator,
            area_number=1,
            area_name="Ground Floor",
        )

        assert sensor.is_on is True

    def test_is_on_when_acknowledged(self) -> None:
        """Test is_on returns True when alarm is acknowledged."""
        coordinator = create_mock_coordinator()
        coordinator.get_area_state_obj.return_value = MockAreaState(
            is_alarm_acknowledged=True
        )

        sensor = AritechAreaAlarmBinarySensor(
            coordinator=coordinator,
            area_number=1,
            area_name="Ground Floor",
        )

        assert sensor.is_on is True


class TestAreaTamperBinarySensor:
    """Tests for AritechAreaTamperBinarySensor."""

    def test_device_class_is_tamper(self) -> None:
        """Test device class is tamper."""
        coordinator = create_mock_coordinator()

        sensor = AritechAreaTamperBinarySensor(
            coordinator=coordinator,
            area_number=1,
            area_name="Ground Floor",
        )

        assert sensor._attr_device_class == BinarySensorDeviceClass.TAMPER

    def test_is_on_when_tampered(self) -> None:
        """Test is_on returns True when area is tampered."""
        coordinator = create_mock_coordinator()
        coordinator.get_area_state_obj.return_value = MockAreaState(is_tampered=True)

        sensor = AritechAreaTamperBinarySensor(
            coordinator=coordinator,
            area_number=1,
            area_name="Ground Floor",
        )

        assert sensor.is_on is True


class TestAreaFireBinarySensor:
    """Tests for AritechAreaFireBinarySensor."""

    def test_device_class_is_smoke(self) -> None:
        """Test device class is smoke."""
        coordinator = create_mock_coordinator()

        sensor = AritechAreaFireBinarySensor(
            coordinator=coordinator,
            area_number=1,
            area_name="Ground Floor",
        )

        assert sensor._attr_device_class == BinarySensorDeviceClass.SMOKE

    def test_is_on_when_fire(self) -> None:
        """Test is_on returns True when area has fire."""
        coordinator = create_mock_coordinator()
        coordinator.get_area_state_obj.return_value = MockAreaState(has_fire=True)

        sensor = AritechAreaFireBinarySensor(
            coordinator=coordinator,
            area_number=1,
            area_name="Ground Floor",
        )

        assert sensor.is_on is True


class TestAreaPanicBinarySensor:
    """Tests for AritechAreaPanicBinarySensor."""

    def test_device_class_is_safety(self) -> None:
        """Test device class is safety."""
        coordinator = create_mock_coordinator()

        sensor = AritechAreaPanicBinarySensor(
            coordinator=coordinator,
            area_number=1,
            area_name="Ground Floor",
        )

        assert sensor._attr_device_class == BinarySensorDeviceClass.SAFETY

    def test_is_on_when_panic(self) -> None:
        """Test is_on returns True when area has panic."""
        coordinator = create_mock_coordinator()
        coordinator.get_area_state_obj.return_value = MockAreaState(has_panic=True)

        sensor = AritechAreaPanicBinarySensor(
            coordinator=coordinator,
            area_number=1,
            area_name="Ground Floor",
        )

        assert sensor.is_on is True

    def test_icon_is_alert(self) -> None:
        """Test icon is alert."""
        coordinator = create_mock_coordinator()

        sensor = AritechAreaPanicBinarySensor(
            coordinator=coordinator,
            area_number=1,
            area_name="Ground Floor",
        )

        assert sensor._attr_icon == "mdi:alert"

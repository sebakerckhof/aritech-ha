"""Fixtures for Aritech ATS tests."""
from __future__ import annotations

import sys
from pathlib import Path

# Add custom_components directory to path for proper package imports
_custom_components_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_custom_components_dir))

from collections.abc import Generator
from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from aritech_ats.const import (
    CONF_ENCRYPTION_KEY,
    CONF_PIN_CODE,
    DOMAIN,
)

# Test configuration
MOCK_HOST = "192.168.1.100"
MOCK_PORT = 32000
MOCK_PIN = "1234"
MOCK_ENCRYPTION_KEY = "123456789012345678901234"

MOCK_CONFIG = {
    CONF_HOST: MOCK_HOST,
    CONF_PORT: MOCK_PORT,
    CONF_PIN_CODE: MOCK_PIN,
    CONF_ENCRYPTION_KEY: MOCK_ENCRYPTION_KEY,
}


# Mock state dataclasses to simulate aritech_client library
@dataclass
class MockAreaState:
    """Mock AreaState from aritech_client."""

    is_unset: bool = True
    is_full_set: bool = False
    is_partially_set: bool = False
    is_partially_set_2: bool = False
    is_alarming: bool = False
    is_alarm_acknowledged: bool = False
    is_tampered: bool = False
    is_ready_to_arm: bool = True
    is_exiting: bool = False
    is_entering: bool = False
    has_fire: bool = False
    has_panic: bool = False
    has_medical: bool = False
    has_duress: bool = False
    has_technical: bool = False
    has_active_zones: bool = False
    has_inhibited_zones: bool = False
    has_isolated_zones: bool = False
    has_zone_faults: bool = False
    has_zone_tamper: bool = False
    is_buzzer_active: bool = False
    is_internal_siren: bool = False
    is_external_siren: bool = False
    is_strobe_active: bool = False

    def __str__(self) -> str:
        """Return string representation."""
        if self.is_alarming:
            return "Alarming"
        if self.is_full_set:
            return "Full Set"
        if self.is_partially_set:
            return "Part Set 1"
        if self.is_partially_set_2:
            return "Part Set 2"
        return "Unset"


@dataclass
class MockZoneState:
    """Mock ZoneState from aritech_client."""

    is_active: bool = False
    is_tampered: bool = False
    has_fault: bool = False
    is_alarming: bool = False
    is_isolated: bool = False
    is_inhibited: bool = False
    is_set: bool = False
    is_anti_mask: bool = False
    is_in_soak_test: bool = False
    has_battery_fault: bool = False
    is_dirty: bool = False

    def __str__(self) -> str:
        """Return string representation."""
        states = []
        if self.is_active:
            states.append("Active")
        if self.is_tampered:
            states.append("Tampered")
        if self.has_fault:
            states.append("Fault")
        if self.is_alarming:
            states.append("Alarming")
        if self.is_isolated:
            states.append("Isolated")
        if self.is_inhibited:
            states.append("Inhibited")
        return ", ".join(states) if states else "Normal"


@dataclass
class MockOutputState:
    """Mock OutputState from aritech_client."""

    is_on: bool = False
    is_active: bool = False
    is_forced: bool = False

    def __str__(self) -> str:
        """Return string representation."""
        if self.is_on or self.is_active:
            return "On"
        return "Off"


@dataclass
class MockTriggerState:
    """Mock TriggerState from aritech_client."""

    is_active: bool = False
    is_remote_output: bool = False
    is_fob: bool = False
    is_schedule: bool = False
    is_function_key: bool = False

    def __str__(self) -> str:
        """Return string representation."""
        return "Active" if self.is_active else "Inactive"


@dataclass
class MockNamedItem:
    """Mock NamedItem from aritech_client."""

    number: int
    name: str


@dataclass
class MockInitializedEvent:
    """Mock InitializedEvent from aritech_client."""

    zones: list[MockNamedItem]
    areas: list[MockNamedItem]
    outputs: list[MockNamedItem]
    triggers: list[MockNamedItem]
    zone_states: dict[int, dict[str, Any]]
    area_states: dict[int, dict[str, Any]]
    output_states: dict[int, dict[str, Any]]
    trigger_states: dict[int, dict[str, Any]]


@dataclass
class MockChangeEvent:
    """Mock ChangeEvent from aritech_client."""

    id: int
    name: str
    old_data: dict[str, Any] | None
    new_data: dict[str, Any]


def create_mock_client() -> MagicMock:
    """Create a mock AritechClient."""
    client = MagicMock()
    client.connect = AsyncMock()
    client.disconnect = AsyncMock()
    client.initialize = AsyncMock()
    client.arm_area = AsyncMock()
    client.disarm_area = AsyncMock()
    client.inhibit_zone = AsyncMock()
    client.uninhibit_zone = AsyncMock()
    client.activate_output = AsyncMock()
    client.deactivate_output = AsyncMock()
    client.activate_trigger = AsyncMock()
    client.deactivate_trigger = AsyncMock()

    # Panel info
    client.panel_model = "ATS4500"
    client.panel_name = "Test Panel"
    client.firmware_version = "1.2.3"

    return client


def create_mock_monitor() -> MagicMock:
    """Create a mock AritechMonitor."""
    monitor = MagicMock()
    monitor.start = AsyncMock()
    monitor.stop = MagicMock()

    # Event handler decorators
    monitor.on_initialized = MagicMock(side_effect=lambda fn: fn)
    monitor.on_zone_changed = MagicMock(side_effect=lambda fn: fn)
    monitor.on_area_changed = MagicMock(side_effect=lambda fn: fn)
    monitor.on_output_changed = MagicMock(side_effect=lambda fn: fn)
    monitor.on_trigger_changed = MagicMock(side_effect=lambda fn: fn)
    monitor.on_error = MagicMock(side_effect=lambda fn: fn)

    return monitor


def create_mock_initialized_event() -> MockInitializedEvent:
    """Create a mock InitializedEvent with sample data."""
    return MockInitializedEvent(
        zones=[
            MockNamedItem(1, "Front Door"),
            MockNamedItem(2, "Living Room PIR"),
            MockNamedItem(3, "Kitchen Window"),
        ],
        areas=[
            MockNamedItem(1, "Ground Floor"),
            MockNamedItem(2, "First Floor"),
        ],
        outputs=[
            MockNamedItem(1, "Siren"),
            MockNamedItem(2, "Strobe"),
        ],
        triggers=[
            MockNamedItem(1, "Panic Button"),
        ],
        zone_states={
            1: {"state": MockZoneState()},
            2: {"state": MockZoneState()},
            3: {"state": MockZoneState()},
        },
        area_states={
            1: {"state": MockAreaState()},
            2: {"state": MockAreaState()},
        },
        output_states={
            1: {"state": MockOutputState()},
            2: {"state": MockOutputState()},
        },
        trigger_states={
            1: {"state": MockTriggerState()},
        },
    )


@pytest.fixture
def mock_config() -> dict[str, Any]:
    """Return mock configuration."""
    return MOCK_CONFIG.copy()


@pytest.fixture
def mock_client() -> MagicMock:
    """Return a mock AritechClient."""
    return create_mock_client()


@pytest.fixture
def mock_monitor() -> MagicMock:
    """Return a mock AritechMonitor."""
    return create_mock_monitor()


@pytest.fixture
def mock_initialized_event() -> MockInitializedEvent:
    """Return a mock InitializedEvent."""
    return create_mock_initialized_event()


@pytest.fixture
def mock_aritech_client(mock_client: MagicMock) -> Generator[MagicMock]:
    """Patch the AritechClient class."""
    with patch(
        "aritech_ats.coordinator.AritechClient",
        return_value=mock_client,
    ) as mock_class:
        yield mock_class


@pytest.fixture
def mock_aritech_monitor(mock_monitor: MagicMock) -> Generator[MagicMock]:
    """Patch the AritechMonitor class."""
    with patch(
        "aritech_ats.coordinator.AritechMonitor",
        return_value=mock_monitor,
    ) as mock_class:
        yield mock_class


@pytest.fixture
def mock_config_flow_client(mock_client: MagicMock) -> Generator[MagicMock]:
    """Patch the AritechClient class in config_flow."""
    with patch(
        "aritech_ats.config_flow.AritechClient",
        return_value=mock_client,
    ) as mock_class:
        yield mock_class


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock async_setup_entry."""
    with patch(
        "aritech_ats.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        yield mock_setup

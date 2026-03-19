"""Binary sensor platform for Aritech integration."""
from __future__ import annotations

import logging
import re
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AritechCoordinator
from .helpers import get_entity_device_info

_LOGGER = logging.getLogger(__name__)

# Map zone name patterns to device classes
ZONE_NAME_DEVICE_CLASS_PATTERNS: list[tuple[str, BinarySensorDeviceClass]] = [
    (r"(?i)(smoke|rook|brand)", BinarySensorDeviceClass.SMOKE),
    (r"(?i)(heat|warmte|temp)", BinarySensorDeviceClass.HEAT),
    (r"(?i)\bgas\b", BinarySensorDeviceClass.GAS),
    (r"(?i)(co2|carbon)", BinarySensorDeviceClass.CO),
    (r"(?i)(pir|motion|beweging|detector)", BinarySensorDeviceClass.MOTION),
    (r"(?i)(window|raam|venster)", BinarySensorDeviceClass.WINDOW),
    (r"(?i)(glass|glas|break)", BinarySensorDeviceClass.VIBRATION),
    (r"(?i)(garage|poort|gate)", BinarySensorDeviceClass.GARAGE_DOOR),
    (r"(?i)(door|deur|entrance|entry|ingang)", BinarySensorDeviceClass.DOOR),
    (r"(?i)(tamper|sabotage)", BinarySensorDeviceClass.TAMPER),
    (r"(?i)(panic|paniek|overval)", BinarySensorDeviceClass.SAFETY),
    (r"(?i)(water|leak|lek)", BinarySensorDeviceClass.MOISTURE),
]


def guess_device_class(zone_name: str) -> BinarySensorDeviceClass | None:
    """Guess the device class based on the zone name."""
    for pattern, device_class in ZONE_NAME_DEVICE_CLASS_PATTERNS:
        if re.search(pattern, zone_name):
            return device_class
    return None


# =============================================================================
# Base class — eliminates boilerplate across all binary sensor classes
# =============================================================================


class AritechBinarySensor(CoordinatorEntity[AritechCoordinator], BinarySensorEntity):
    """Base class for all Aritech binary sensors.

    Uses CoordinatorEntity for automatic listener registration/cleanup,
    eliminating manual callback management in each subclass.
    """

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AritechCoordinator,
        entity_type: str,
        number: int,
        name: str,
        suffix: str,
        device_class: BinarySensorDeviceClass | None = None,
        icon: str | None = None,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self._number = number

        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{entity_type}_{number}_{suffix}"
        self._attr_name = suffix.replace("_", " ").title()
        self._attr_device_info = get_entity_device_info(coordinator, entity_type, number, name)
        if device_class:
            self._attr_device_class = device_class
        if icon:
            self._attr_icon = icon

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.connected


# =============================================================================
# Zone Binary Sensors
# =============================================================================


class AritechZoneActiveBinarySensor(AritechBinarySensor):
    """Zone active/motion sensor."""

    def __init__(self, coordinator: AritechCoordinator, zone_number: int, zone_name: str) -> None:
        super().__init__(
            coordinator, "zone", zone_number, zone_name, "active",
            device_class=guess_device_class(zone_name),
        )

    @property
    def is_on(self) -> bool | None:
        zone_state = self.coordinator.get_zone_state_obj(self._number)
        return zone_state.is_active if zone_state else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        zone_state = self.coordinator.get_zone_state_obj(self._number)
        if not zone_state:
            return {"zone_number": self._number}
        return {
            "zone_number": self._number,
            "state_text": str(zone_state),
            "is_set": zone_state.is_set,
            "is_anti_mask": zone_state.is_anti_mask,
            "is_in_soak_test": zone_state.is_in_soak_test,
            "has_battery_fault": zone_state.has_battery_fault,
            "is_dirty": zone_state.is_dirty,
        }


class AritechZoneTamperBinarySensor(AritechBinarySensor):
    """Zone tamper sensor."""

    def __init__(self, coordinator: AritechCoordinator, zone_number: int, zone_name: str) -> None:
        super().__init__(coordinator, "zone", zone_number, zone_name, "tamper", BinarySensorDeviceClass.TAMPER)

    @property
    def is_on(self) -> bool | None:
        zone_state = self.coordinator.get_zone_state_obj(self._number)
        return zone_state.is_tampered if zone_state else None


class AritechZoneFaultBinarySensor(AritechBinarySensor):
    """Zone fault sensor."""

    def __init__(self, coordinator: AritechCoordinator, zone_number: int, zone_name: str) -> None:
        super().__init__(coordinator, "zone", zone_number, zone_name, "fault", BinarySensorDeviceClass.PROBLEM)

    @property
    def is_on(self) -> bool | None:
        zone_state = self.coordinator.get_zone_state_obj(self._number)
        return zone_state.has_fault if zone_state else None


class AritechZoneAlarmingBinarySensor(AritechBinarySensor):
    """Zone alarming sensor."""

    def __init__(self, coordinator: AritechCoordinator, zone_number: int, zone_name: str) -> None:
        super().__init__(coordinator, "zone", zone_number, zone_name, "alarming", BinarySensorDeviceClass.SAFETY)

    @property
    def is_on(self) -> bool | None:
        zone_state = self.coordinator.get_zone_state_obj(self._number)
        return zone_state.is_alarming if zone_state else None


class AritechZoneIsolatedBinarySensor(AritechBinarySensor):
    """Zone isolated sensor."""

    def __init__(self, coordinator: AritechCoordinator, zone_number: int, zone_name: str) -> None:
        super().__init__(coordinator, "zone", zone_number, zone_name, "isolated", icon="mdi:link-off")

    @property
    def is_on(self) -> bool | None:
        zone_state = self.coordinator.get_zone_state_obj(self._number)
        return zone_state.is_isolated if zone_state else None


# =============================================================================
# Area Binary Sensors
# =============================================================================


class AritechAreaAlarmBinarySensor(AritechBinarySensor):
    """Area alarm sensor."""

    def __init__(self, coordinator: AritechCoordinator, area_number: int, area_name: str) -> None:
        super().__init__(coordinator, "area", area_number, area_name, "alarm", BinarySensorDeviceClass.SAFETY)

    @property
    def is_on(self) -> bool | None:
        area_state = self.coordinator.get_area_state_obj(self._number)
        if not area_state:
            return None
        return area_state.is_alarming or area_state.is_alarm_acknowledged


class AritechAreaTamperBinarySensor(AritechBinarySensor):
    """Area tamper sensor."""

    def __init__(self, coordinator: AritechCoordinator, area_number: int, area_name: str) -> None:
        super().__init__(coordinator, "area", area_number, area_name, "tamper", BinarySensorDeviceClass.TAMPER)

    @property
    def is_on(self) -> bool | None:
        area_state = self.coordinator.get_area_state_obj(self._number)
        return area_state.is_tampered if area_state else None


class AritechAreaFireBinarySensor(AritechBinarySensor):
    """Area fire sensor."""

    def __init__(self, coordinator: AritechCoordinator, area_number: int, area_name: str) -> None:
        super().__init__(coordinator, "area", area_number, area_name, "fire", BinarySensorDeviceClass.SMOKE)

    @property
    def is_on(self) -> bool | None:
        area_state = self.coordinator.get_area_state_obj(self._number)
        return area_state.has_fire if area_state else None


class AritechAreaPanicBinarySensor(AritechBinarySensor):
    """Area panic sensor."""

    def __init__(self, coordinator: AritechCoordinator, area_number: int, area_name: str) -> None:
        super().__init__(
            coordinator, "area", area_number, area_name, "panic",
            BinarySensorDeviceClass.SAFETY, icon="mdi:alert",
        )

    @property
    def is_on(self) -> bool | None:
        area_state = self.coordinator.get_area_state_obj(self._number)
        return area_state.has_panic if area_state else None


# =============================================================================
# Door Binary Sensors
# =============================================================================


class AritechDoorLockBinarySensor(AritechBinarySensor):
    """Door lock state sensor."""

    def __init__(self, coordinator: AritechCoordinator, door_number: int, door_name: str) -> None:
        super().__init__(coordinator, "door", door_number, door_name, "lock", BinarySensorDeviceClass.LOCK)

    @property
    def is_on(self) -> bool | None:
        door_state = self.coordinator.get_door_state_obj(self._number)
        if not door_state:
            return None
        return not door_state.is_locked

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        door_state = self.coordinator.get_door_state_obj(self._number)
        if not door_state:
            return {"door_number": self._number}
        return {
            "door_number": self._number,
            "state_text": str(door_state),
            "is_unlocked": door_state.is_unlocked,
            "is_time_unlocked": door_state.is_time_unlocked,
            "is_standard_time_unlocked": door_state.is_standard_time_unlocked,
            "is_unlocked_period": door_state.is_unlocked_period,
            "is_disabled": door_state.is_disabled,
        }


class AritechDoorOpenBinarySensor(AritechBinarySensor):
    """Door open/close sensor."""

    def __init__(self, coordinator: AritechCoordinator, door_number: int, door_name: str) -> None:
        super().__init__(coordinator, "door", door_number, door_name, "open", BinarySensorDeviceClass.DOOR)

    @property
    def is_on(self) -> bool | None:
        door_state = self.coordinator.get_door_state_obj(self._number)
        return door_state.is_opened if door_state else None


class AritechDoorForcedBinarySensor(AritechBinarySensor):
    """Door forced open sensor."""

    def __init__(self, coordinator: AritechCoordinator, door_number: int, door_name: str) -> None:
        super().__init__(coordinator, "door", door_number, door_name, "forced", BinarySensorDeviceClass.PROBLEM)

    @property
    def is_on(self) -> bool | None:
        door_state = self.coordinator.get_door_state_obj(self._number)
        return door_state.is_forced if door_state else None


class AritechDoorOpenTooLongBinarySensor(AritechBinarySensor):
    """Door open too long sensor."""

    def __init__(self, coordinator: AritechCoordinator, door_number: int, door_name: str) -> None:
        super().__init__(
            coordinator, "door", door_number, door_name, "open_too_long",
            BinarySensorDeviceClass.PROBLEM, icon="mdi:timer-alert",
        )

    @property
    def is_on(self) -> bool | None:
        door_state = self.coordinator.get_door_state_obj(self._number)
        return door_state.is_door_open_too_long if door_state else None


class AritechDoorTamperBinarySensor(AritechBinarySensor):
    """Door reader tamper sensor."""

    def __init__(self, coordinator: AritechCoordinator, door_number: int, door_name: str) -> None:
        super().__init__(coordinator, "door", door_number, door_name, "tamper", BinarySensorDeviceClass.TAMPER)

    @property
    def is_on(self) -> bool | None:
        door_state = self.coordinator.get_door_state_obj(self._number)
        return door_state.is_reader_tamper if door_state else None


# =============================================================================
# Output Binary Sensors (read-only)
# =============================================================================


class AritechOutputActiveBinarySensor(AritechBinarySensor):
    """Output active state sensor (read-only)."""

    def __init__(self, coordinator: AritechCoordinator, output_number: int, output_name: str) -> None:
        super().__init__(
            coordinator, "output", output_number, output_name, "active",
            BinarySensorDeviceClass.POWER, icon="mdi:electric-switch",
        )

    @property
    def is_on(self) -> bool | None:
        output_state = self.coordinator.get_output_state_obj(self._number)
        if not output_state:
            return None
        return output_state.is_on or output_state.is_active

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        output_state = self.coordinator.get_output_state_obj(self._number)
        if not output_state:
            return {"output_number": self._number}
        return {
            "output_number": self._number,
            "is_on": output_state.is_on,
            "is_active": output_state.is_active,
            "is_forced": output_state.is_forced,
            "state_text": str(output_state),
        }


class AritechOutputForcedBinarySensor(AritechBinarySensor):
    """Output forced state sensor (read-only)."""

    def __init__(self, coordinator: AritechCoordinator, output_number: int, output_name: str) -> None:
        super().__init__(coordinator, "output", output_number, output_name, "forced", icon="mdi:lock")

    @property
    def is_on(self) -> bool | None:
        output_state = self.coordinator.get_output_state_obj(self._number)
        return output_state.is_forced if output_state else None


# =============================================================================
# Filter Binary Sensors
# =============================================================================


class AritechFilterActiveBinarySensor(AritechBinarySensor):
    """Filter active state sensor."""

    def __init__(self, coordinator: AritechCoordinator, filter_number: int, filter_name: str) -> None:
        super().__init__(coordinator, "filter", filter_number, filter_name, "active", icon="mdi:filter")

    @property
    def is_on(self) -> bool | None:
        filter_state = self.coordinator.get_filter_state_obj(self._number)
        return filter_state.is_active if filter_state else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"filter_number": self._number}


# =============================================================================
# Platform setup
# =============================================================================


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Aritech binary sensors from a config entry."""
    coordinator: AritechCoordinator = hass.data[DOMAIN][entry.entry_id]

    if not coordinator.data:
        _LOGGER.warning("Coordinator has no data yet, waiting for initialization")
        await coordinator.async_config_entry_first_refresh()

    entities: list[BinarySensorEntity] = []

    # Zone sensors
    for zone in coordinator.get_zones():
        num, name = zone["number"], zone["name"]
        entities.extend([
            AritechZoneActiveBinarySensor(coordinator, num, name),
            AritechZoneTamperBinarySensor(coordinator, num, name),
            AritechZoneFaultBinarySensor(coordinator, num, name),
            AritechZoneAlarmingBinarySensor(coordinator, num, name),
            AritechZoneIsolatedBinarySensor(coordinator, num, name),
        ])

    # Area sensors
    for area in coordinator.get_areas():
        num, name = area["number"], area["name"]
        entities.extend([
            AritechAreaAlarmBinarySensor(coordinator, num, name),
            AritechAreaTamperBinarySensor(coordinator, num, name),
            AritechAreaFireBinarySensor(coordinator, num, name),
            AritechAreaPanicBinarySensor(coordinator, num, name),
        ])

    # Door sensors
    for door in coordinator.get_doors():
        num, name = door["number"], door["name"]
        entities.extend([
            AritechDoorLockBinarySensor(coordinator, num, name),
            AritechDoorOpenBinarySensor(coordinator, num, name),
            AritechDoorForcedBinarySensor(coordinator, num, name),
            AritechDoorOpenTooLongBinarySensor(coordinator, num, name),
            AritechDoorTamperBinarySensor(coordinator, num, name),
        ])

    # Output sensors (read-only)
    for output in coordinator.get_outputs():
        num, name = output["number"], output["name"]
        entities.extend([
            AritechOutputActiveBinarySensor(coordinator, num, name),
            AritechOutputForcedBinarySensor(coordinator, num, name),
        ])

    # Filter sensors
    for filter_ in coordinator.get_filters():
        entities.append(AritechFilterActiveBinarySensor(coordinator, filter_["number"], filter_["name"]))

    if entities:
        _LOGGER.info("Setting up %d binary sensors", len(entities))
        async_add_entities(entities)
    else:
        _LOGGER.warning("No binary sensors created")

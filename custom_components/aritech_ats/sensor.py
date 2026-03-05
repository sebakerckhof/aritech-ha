"""Sensor platform for Aritech integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AritechCoordinator
from .helpers import get_panel_device_info, get_entity_device_info

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Aritech sensors from a config entry."""
    coordinator: AritechCoordinator = hass.data[DOMAIN][entry.entry_id]

    if not coordinator.data:
        _LOGGER.warning("Coordinator has no data yet, waiting for initialization")
        await coordinator.async_config_entry_first_refresh()

    entities: list[SensorEntity] = []

    # Panel diagnostic sensors
    entities.append(AritechPanelModelSensor(coordinator))
    entities.append(AritechFirmwareVersionSensor(coordinator))
    entities.append(AritechConnectionStatusSensor(coordinator))

    # Area state sensors
    for area in coordinator.get_areas():
        entities.append(AritechAreaStateSensor(coordinator, area["number"], area["name"]))

    # Zone state sensors
    for zone in coordinator.get_zones():
        entities.append(AritechZoneStateSensor(coordinator, zone["number"], zone["name"]))

    if entities:
        _LOGGER.info("Setting up %d sensors", len(entities))
        async_add_entities(entities)
    else:
        _LOGGER.warning("No sensors created")


# =============================================================================
# Panel diagnostic sensors
# =============================================================================


class AritechPanelModelSensor(CoordinatorEntity[AritechCoordinator], SensorEntity):
    """Sensor showing the panel model."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:shield-home"

    def __init__(self, coordinator: AritechCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_panel_model"
        self._attr_name = "Panel Model"
        self._attr_device_info = get_panel_device_info(coordinator)

    @property
    def available(self) -> bool:
        return self.coordinator.connected

    @property
    def native_value(self) -> str | None:
        return self.coordinator.panel_model


class AritechFirmwareVersionSensor(CoordinatorEntity[AritechCoordinator], SensorEntity):
    """Sensor showing the firmware version."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:chip"

    def __init__(self, coordinator: AritechCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_firmware_version"
        self._attr_name = "Firmware Version"
        self._attr_device_info = get_panel_device_info(coordinator)

    @property
    def available(self) -> bool:
        return self.coordinator.connected

    @property
    def native_value(self) -> str | None:
        return self.coordinator.firmware_version


class AritechConnectionStatusSensor(CoordinatorEntity[AritechCoordinator], SensorEntity):
    """Sensor showing the connection status."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:lan-connect"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["connected", "disconnected"]

    def __init__(self, coordinator: AritechCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_connection_status"
        self._attr_name = "Connection Status"
        self._attr_device_info = get_panel_device_info(coordinator)

    @property
    def available(self) -> bool:
        return True  # Always available so we can show disconnected state

    @property
    def native_value(self) -> str:
        return "connected" if self.coordinator.connected else "disconnected"


# =============================================================================
# Area/Zone state text sensors
# =============================================================================


class AritechAreaStateSensor(CoordinatorEntity[AritechCoordinator], SensorEntity):
    """Sensor showing the textual state of an area."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:shield-home-outline"

    def __init__(self, coordinator: AritechCoordinator, area_number: int, area_name: str) -> None:
        super().__init__(coordinator)
        self._area_number = area_number
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_area_{area_number}_state"
        self._attr_name = "State"
        self._attr_device_info = get_entity_device_info(coordinator, "area", area_number, area_name)

    @property
    def available(self) -> bool:
        return self.coordinator.connected

    @property
    def native_value(self) -> str:
        area_state = self.coordinator.get_area_state_obj(self._area_number)
        return str(area_state) if area_state else "unknown"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        area_state = self.coordinator.get_area_state_obj(self._area_number)
        if not area_state:
            return {"area_number": self._area_number}
        return {
            "area_number": self._area_number,
            "is_ready_to_arm": area_state.is_ready_to_arm,
            "is_exiting": area_state.is_exiting,
            "is_entering": area_state.is_entering,
        }


class AritechZoneStateSensor(CoordinatorEntity[AritechCoordinator], SensorEntity):
    """Sensor showing the textual state of a zone."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:motion-sensor"

    def __init__(self, coordinator: AritechCoordinator, zone_number: int, zone_name: str) -> None:
        super().__init__(coordinator)
        self._zone_number = zone_number
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_zone_{zone_number}_state"
        self._attr_name = "State"
        self._attr_device_info = get_entity_device_info(coordinator, "zone", zone_number, zone_name)

    @property
    def available(self) -> bool:
        return self.coordinator.connected

    @property
    def native_value(self) -> str:
        zone_state = self.coordinator.get_zone_state_obj(self._zone_number)
        return str(zone_state) if zone_state else "unknown"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        zone_state = self.coordinator.get_zone_state_obj(self._zone_number)
        if not zone_state:
            return {"zone_number": self._zone_number}
        return {
            "zone_number": self._zone_number,
            "is_set": zone_state.is_set,
            "is_inhibited": zone_state.is_inhibited,
            "is_isolated": zone_state.is_isolated,
        }

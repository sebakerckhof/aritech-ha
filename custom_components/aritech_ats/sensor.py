"""Sensor platform for Aritech ATS integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, MANUFACTURER
from .coordinator import AritechCoordinator

_LOGGER = logging.getLogger(__name__)


def _get_panel_device_info(coordinator: AritechCoordinator) -> DeviceInfo:
    """Get device info for the main panel."""
    return DeviceInfo(
        identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
        name=coordinator.panel_name or "Aritech ATS Panel",
        manufacturer=MANUFACTURER,
        model=coordinator.panel_model or "ATS Panel",
        sw_version=coordinator.firmware_version,
    )


def _get_area_device_info(
    coordinator: AritechCoordinator, area_number: int, area_name: str
) -> DeviceInfo:
    """Get device info for an area."""
    return DeviceInfo(
        identifiers={(DOMAIN, f"{coordinator.config_entry.entry_id}_area_{area_number}")},
        name=area_name,
        manufacturer=MANUFACTURER,
        model="Area",
        via_device=(DOMAIN, coordinator.config_entry.entry_id),
    )


def _get_zone_device_info(
    coordinator: AritechCoordinator, zone_number: int, zone_name: str
) -> DeviceInfo:
    """Get device info for a zone (each zone is its own device)."""
    return DeviceInfo(
        identifiers={(DOMAIN, f"{coordinator.config_entry.entry_id}_zone_{zone_number}")},
        name=zone_name,
        manufacturer=MANUFACTURER,
        model="Zone",
        via_device=(DOMAIN, coordinator.config_entry.entry_id),
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Aritech ATS sensors from a config entry."""
    coordinator: AritechCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Wait for coordinator to have data
    if not coordinator.data:
        _LOGGER.warning("Coordinator has no data yet, waiting for initialization")
        await coordinator.async_config_entry_first_refresh()

    entities: list[SensorEntity] = []

    # Panel diagnostic sensors
    entities.append(AritechPanelModelSensor(coordinator))
    entities.append(AritechFirmwareVersionSensor(coordinator))
    entities.append(AritechConnectionStatusSensor(coordinator))

    # Area state sensors (textual state for automations)
    for area in coordinator.get_areas():
        entities.append(
            AritechAreaStateSensor(
                coordinator=coordinator,
                area_number=area["number"],
                area_name=area["name"],
            )
        )

    # Zone state sensors (textual state for automations) - part of zone device
    for zone in coordinator.get_zones():
        entities.append(
            AritechZoneStateSensor(
                coordinator=coordinator,
                zone_number=zone["number"],
                zone_name=zone["name"],
            )
        )

    if entities:
        _LOGGER.info("Setting up %d sensors", len(entities))
        async_add_entities(entities)
    else:
        _LOGGER.warning("No sensors created")


class AritechPanelModelSensor(SensorEntity):
    """Sensor showing the panel model."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:shield-home"

    def __init__(self, coordinator: AritechCoordinator) -> None:
        """Initialize the sensor."""
        self.coordinator = coordinator

        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_panel_model"
        self._attr_name = "Panel Model"
        self._attr_device_info = _get_panel_device_info(coordinator)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.connected

    @property
    def native_value(self) -> str | None:
        """Return the panel model."""
        return self.coordinator.panel_model


class AritechFirmwareVersionSensor(SensorEntity):
    """Sensor showing the firmware version."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:chip"

    def __init__(self, coordinator: AritechCoordinator) -> None:
        """Initialize the sensor."""
        self.coordinator = coordinator

        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_firmware_version"
        self._attr_name = "Firmware Version"
        self._attr_device_info = _get_panel_device_info(coordinator)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.connected

    @property
    def native_value(self) -> str | None:
        """Return the firmware version."""
        return self.coordinator.firmware_version


class AritechConnectionStatusSensor(SensorEntity):
    """Sensor showing the connection status."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:lan-connect"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["connected", "disconnected"]

    def __init__(self, coordinator: AritechCoordinator) -> None:
        """Initialize the sensor."""
        self.coordinator = coordinator

        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_connection_status"
        self._attr_name = "Connection Status"
        self._attr_device_info = _get_panel_device_info(coordinator)

    async def async_added_to_hass(self) -> None:
        """Run when entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return True  # This sensor is always available

    @property
    def native_value(self) -> str:
        """Return the connection status."""
        return "connected" if self.coordinator.connected else "disconnected"


class AritechAreaStateSensor(SensorEntity):
    """Sensor showing the textual state of an area."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:shield-home-outline"

    def __init__(
        self,
        coordinator: AritechCoordinator,
        area_number: int,
        area_name: str,
    ) -> None:
        """Initialize the sensor."""
        self.coordinator = coordinator
        self._area_number = area_number
        self._area_name = area_name
        self._unregister_callback: callable | None = None

        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_area_{area_number}_state"
        self._attr_name = "State"
        self._attr_device_info = _get_area_device_info(coordinator, area_number, area_name)

    async def async_added_to_hass(self) -> None:
        """Run when entity is added to hass."""
        await super().async_added_to_hass()

        self._unregister_callback = self.coordinator.register_area_callback(
            self._area_number, self._handle_area_update
        )

        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity is being removed."""
        if self._unregister_callback:
            self._unregister_callback()
            self._unregister_callback = None
        await super().async_will_remove_from_hass()

    @callback
    def _handle_area_update(self) -> None:
        """Handle area state update."""
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.connected

    @property
    def native_value(self) -> str:
        """Return the area state as text."""
        area_state = self.coordinator.get_area_state_obj(self._area_number)
        if not area_state:
            return "unknown"
        return str(area_state)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        area_state = self.coordinator.get_area_state_obj(self._area_number)
        if not area_state:
            return {"area_number": self._area_number}

        return {
            "area_number": self._area_number,
            "is_ready_to_arm": area_state.is_ready_to_arm,
            "is_exiting": area_state.is_exiting,
            "is_entering": area_state.is_entering,
        }


class AritechZoneStateSensor(SensorEntity):
    """Sensor showing the textual state of a zone."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:motion-sensor"

    def __init__(
        self,
        coordinator: AritechCoordinator,
        zone_number: int,
        zone_name: str,
    ) -> None:
        """Initialize the sensor."""
        self.coordinator = coordinator
        self._zone_number = zone_number
        self._zone_name = zone_name
        self._unregister_callback: callable | None = None

        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_zone_{zone_number}_state"
        self._attr_name = "State"

        # Zone state sensor belongs to the zone device
        self._attr_device_info = _get_zone_device_info(coordinator, zone_number, zone_name)

    async def async_added_to_hass(self) -> None:
        """Run when entity is added to hass."""
        await super().async_added_to_hass()

        self._unregister_callback = self.coordinator.register_zone_callback(
            self._zone_number, self._handle_zone_update
        )

        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity is being removed."""
        if self._unregister_callback:
            self._unregister_callback()
            self._unregister_callback = None
        await super().async_will_remove_from_hass()

    @callback
    def _handle_zone_update(self) -> None:
        """Handle zone state update."""
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.connected

    @property
    def native_value(self) -> str:
        """Return the zone state as text."""
        zone_state = self.coordinator.get_zone_state_obj(self._zone_number)
        if not zone_state:
            return "unknown"
        return str(zone_state)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        zone_state = self.coordinator.get_zone_state_obj(self._zone_number)
        if not zone_state:
            return {"zone_number": self._zone_number}

        return {
            "zone_number": self._zone_number,
            "is_set": zone_state.is_set,
            "is_inhibited": zone_state.is_inhibited,
            "is_isolated": zone_state.is_isolated,
        }

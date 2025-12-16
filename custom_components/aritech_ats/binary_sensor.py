"""Binary sensor platform for Aritech ATS integration."""
from __future__ import annotations

import logging
import re
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from aritech_client import AreaState, ZoneState

from .const import DOMAIN, MANUFACTURER
from .coordinator import AritechCoordinator

_LOGGER = logging.getLogger(__name__)

# Map zone name patterns to device classes
ZONE_NAME_DEVICE_CLASS_PATTERNS: list[tuple[str, BinarySensorDeviceClass]] = [
    (r"(?i)(pir|motion|beweging|detector)", BinarySensorDeviceClass.MOTION),
    (r"(?i)(door|deur|entrance|entry|ingang)", BinarySensorDeviceClass.DOOR),
    (r"(?i)(window|raam|venster)", BinarySensorDeviceClass.WINDOW),
    (r"(?i)(smoke|rook|brand)", BinarySensorDeviceClass.SMOKE),
    (r"(?i)(glass|glas|break)", BinarySensorDeviceClass.VIBRATION),
    (r"(?i)(garage|poort|gate)", BinarySensorDeviceClass.GARAGE_DOOR),
    (r"(?i)(tamper|sabotage)", BinarySensorDeviceClass.TAMPER),
    (r"(?i)(panic|paniek|overval)", BinarySensorDeviceClass.SAFETY),
    (r"(?i)(water|leak|lek)", BinarySensorDeviceClass.MOISTURE),
    (r"(?i)(heat|warmte|temp)", BinarySensorDeviceClass.HEAT),
    (r"(?i)(gas)", BinarySensorDeviceClass.GAS),
    (r"(?i)(co2|carbon)", BinarySensorDeviceClass.CO),
]


def guess_device_class(zone_name: str) -> BinarySensorDeviceClass | None:
    """Guess the device class based on zone name."""
    for pattern, device_class in ZONE_NAME_DEVICE_CLASS_PATTERNS:
        if re.search(pattern, zone_name):
            return device_class
    # Default to motion for generic zones
    return BinarySensorDeviceClass.MOTION


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
    """Set up Aritech ATS binary sensors from a config entry."""
    coordinator: AritechCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Wait for coordinator to have data
    if not coordinator.data:
        _LOGGER.warning("Coordinator has no data yet, waiting for initialization")
        await coordinator.async_config_entry_first_refresh()

    entities: list[BinarySensorEntity] = []

    # Create multiple binary sensors per zone (each zone is its own device)
    for zone in coordinator.get_zones():
        zone_num = zone["number"]
        zone_name = zone["name"]

        # Main zone sensor (active state - motion/door/etc)
        entities.append(
            AritechZoneActiveBinarySensor(
                coordinator=coordinator,
                zone_number=zone_num,
                zone_name=zone_name,
            )
        )

        # Zone tamper sensor
        entities.append(
            AritechZoneTamperBinarySensor(
                coordinator=coordinator,
                zone_number=zone_num,
                zone_name=zone_name,
            )
        )

        # Zone fault sensor
        entities.append(
            AritechZoneFaultBinarySensor(
                coordinator=coordinator,
                zone_number=zone_num,
                zone_name=zone_name,
            )
        )

        # Zone alarming sensor
        entities.append(
            AritechZoneAlarmingBinarySensor(
                coordinator=coordinator,
                zone_number=zone_num,
                zone_name=zone_name,
            )
        )

        # Zone isolated sensor
        entities.append(
            AritechZoneIsolatedBinarySensor(
                coordinator=coordinator,
                zone_number=zone_num,
                zone_name=zone_name,
            )
        )

    # Create area status binary sensors (alarm, tamper, fire, panic)
    for area in coordinator.get_areas():
        area_num = area["number"]
        area_name = area["name"]

        # Alarm sensor for each area
        entities.append(
            AritechAreaAlarmBinarySensor(
                coordinator=coordinator,
                area_number=area_num,
                area_name=area_name,
            )
        )
        # Tamper sensor for each area
        entities.append(
            AritechAreaTamperBinarySensor(
                coordinator=coordinator,
                area_number=area_num,
                area_name=area_name,
            )
        )
        # Fire sensor for each area
        entities.append(
            AritechAreaFireBinarySensor(
                coordinator=coordinator,
                area_number=area_num,
                area_name=area_name,
            )
        )
        # Panic sensor for each area
        entities.append(
            AritechAreaPanicBinarySensor(
                coordinator=coordinator,
                area_number=area_num,
                area_name=area_name,
            )
        )

    if entities:
        _LOGGER.info("Setting up %d binary sensors", len(entities))
        async_add_entities(entities)
    else:
        _LOGGER.warning("No zones or areas found to create binary sensors")


# =============================================================================
# Zone Binary Sensors (each zone is its own device)
# =============================================================================


class AritechZoneActiveBinarySensor(BinarySensorEntity):
    """Zone active/motion sensor - the primary sensor for zone detection."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AritechCoordinator,
        zone_number: int,
        zone_name: str,
    ) -> None:
        """Initialize the zone active binary sensor."""
        self.coordinator = coordinator
        self._zone_number = zone_number
        self._zone_name = zone_name
        self._unregister_callback: callable | None = None

        # Entity attributes
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_zone_{zone_number}_active"
        self._attr_name = "Active"

        # Guess device class from zone name
        self._attr_device_class = guess_device_class(zone_name)

        # Each zone is its own device
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
    def is_on(self) -> bool | None:
        """Return true if the zone is active."""
        zone_state = self.coordinator.get_zone_state_obj(self._zone_number)
        if not zone_state:
            return None
        return zone_state.is_active

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        zone_state = self.coordinator.get_zone_state_obj(self._zone_number)
        if not zone_state:
            return {"zone_number": self._zone_number}

        return {
            "zone_number": self._zone_number,
            "state_text": str(zone_state),
            "is_set": zone_state.is_set,
            "is_anti_mask": zone_state.is_anti_mask,
            "is_in_soak_test": zone_state.is_in_soak_test,
            "has_battery_fault": zone_state.has_battery_fault,
            "is_dirty": zone_state.is_dirty,
        }


class AritechZoneTamperBinarySensor(BinarySensorEntity):
    """Zone tamper sensor."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.TAMPER

    def __init__(
        self,
        coordinator: AritechCoordinator,
        zone_number: int,
        zone_name: str,
    ) -> None:
        """Initialize the zone tamper binary sensor."""
        self.coordinator = coordinator
        self._zone_number = zone_number
        self._unregister_callback: callable | None = None

        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_zone_{zone_number}_tamper"
        self._attr_name = "Tamper"
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
    def is_on(self) -> bool | None:
        """Return true if the zone is tampered."""
        zone_state = self.coordinator.get_zone_state_obj(self._zone_number)
        if not zone_state:
            return None
        return zone_state.is_tampered


class AritechZoneFaultBinarySensor(BinarySensorEntity):
    """Zone fault sensor."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(
        self,
        coordinator: AritechCoordinator,
        zone_number: int,
        zone_name: str,
    ) -> None:
        """Initialize the zone fault binary sensor."""
        self.coordinator = coordinator
        self._zone_number = zone_number
        self._unregister_callback: callable | None = None

        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_zone_{zone_number}_fault"
        self._attr_name = "Fault"
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
    def is_on(self) -> bool | None:
        """Return true if the zone has a fault."""
        zone_state = self.coordinator.get_zone_state_obj(self._zone_number)
        if not zone_state:
            return None
        return zone_state.has_fault


class AritechZoneAlarmingBinarySensor(BinarySensorEntity):
    """Zone alarming sensor."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.SAFETY

    def __init__(
        self,
        coordinator: AritechCoordinator,
        zone_number: int,
        zone_name: str,
    ) -> None:
        """Initialize the zone alarming binary sensor."""
        self.coordinator = coordinator
        self._zone_number = zone_number
        self._unregister_callback: callable | None = None

        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_zone_{zone_number}_alarming"
        self._attr_name = "Alarming"
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
    def is_on(self) -> bool | None:
        """Return true if the zone is alarming."""
        zone_state = self.coordinator.get_zone_state_obj(self._zone_number)
        if not zone_state:
            return None
        return zone_state.is_alarming


class AritechZoneIsolatedBinarySensor(BinarySensorEntity):
    """Zone isolated sensor."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:link-off"

    def __init__(
        self,
        coordinator: AritechCoordinator,
        zone_number: int,
        zone_name: str,
    ) -> None:
        """Initialize the zone isolated binary sensor."""
        self.coordinator = coordinator
        self._zone_number = zone_number
        self._unregister_callback: callable | None = None

        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_zone_{zone_number}_isolated"
        self._attr_name = "Isolated"
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
    def is_on(self) -> bool | None:
        """Return true if the zone is isolated."""
        zone_state = self.coordinator.get_zone_state_obj(self._zone_number)
        if not zone_state:
            return None
        return zone_state.is_isolated


# =============================================================================
# Area Binary Sensors
# =============================================================================


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


class AritechAreaAlarmBinarySensor(BinarySensorEntity):
    """Binary sensor for area alarm status."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.SAFETY

    def __init__(
        self,
        coordinator: AritechCoordinator,
        area_number: int,
        area_name: str,
    ) -> None:
        """Initialize the area alarm binary sensor."""
        self.coordinator = coordinator
        self._area_number = area_number
        self._unregister_callback: callable | None = None

        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_area_{area_number}_alarm"
        self._attr_name = "Alarm"
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
    def is_on(self) -> bool | None:
        """Return true if the area is in alarm."""
        area_state = self.coordinator.get_area_state_obj(self._area_number)
        if not area_state:
            return None
        return area_state.is_alarming or area_state.is_alarm_acknowledged


class AritechAreaTamperBinarySensor(BinarySensorEntity):
    """Binary sensor for area tamper status."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.TAMPER

    def __init__(
        self,
        coordinator: AritechCoordinator,
        area_number: int,
        area_name: str,
    ) -> None:
        """Initialize the area tamper binary sensor."""
        self.coordinator = coordinator
        self._area_number = area_number
        self._unregister_callback: callable | None = None

        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_area_{area_number}_tamper"
        self._attr_name = "Tamper"
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
    def is_on(self) -> bool | None:
        """Return true if the area has tamper."""
        area_state = self.coordinator.get_area_state_obj(self._area_number)
        if not area_state:
            return None
        return area_state.is_tampered


class AritechAreaFireBinarySensor(BinarySensorEntity):
    """Binary sensor for area fire status."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.SMOKE

    def __init__(
        self,
        coordinator: AritechCoordinator,
        area_number: int,
        area_name: str,
    ) -> None:
        """Initialize the area fire binary sensor."""
        self.coordinator = coordinator
        self._area_number = area_number
        self._unregister_callback: callable | None = None

        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_area_{area_number}_fire"
        self._attr_name = "Fire"
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
    def is_on(self) -> bool | None:
        """Return true if the area has fire alarm."""
        area_state = self.coordinator.get_area_state_obj(self._area_number)
        if not area_state:
            return None
        return area_state.has_fire


class AritechAreaPanicBinarySensor(BinarySensorEntity):
    """Binary sensor for area panic status."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.SAFETY
    _attr_icon = "mdi:alert"

    def __init__(
        self,
        coordinator: AritechCoordinator,
        area_number: int,
        area_name: str,
    ) -> None:
        """Initialize the area panic binary sensor."""
        self.coordinator = coordinator
        self._area_number = area_number
        self._unregister_callback: callable | None = None

        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_area_{area_number}_panic"
        self._attr_name = "Panic"
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
    def is_on(self) -> bool | None:
        """Return true if the area has panic alarm."""
        area_state = self.coordinator.get_area_state_obj(self._area_number)
        if not area_state:
            return None
        return area_state.has_panic

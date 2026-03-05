"""Shared helpers for the Aritech integration."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN, MANUFACTURER

if __import__("typing").TYPE_CHECKING:
    from .coordinator import AritechCoordinator


def get_panel_device_info(coordinator: AritechCoordinator) -> DeviceInfo:
    """Get device info for the main panel."""
    return DeviceInfo(
        identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
        name=coordinator.panel_name or "Aritech Panel",
        manufacturer=MANUFACTURER,
        model=coordinator.panel_model or "ATS Panel",
        sw_version=coordinator.firmware_version,
    )


def get_entity_device_info(
    coordinator: AritechCoordinator,
    entity_type: str,
    number: int,
    name: str,
) -> DeviceInfo:
    """Get device info for a sub-entity (zone, area, door, output, trigger, filter)."""
    model_map = {
        "zone": "Zone",
        "area": "Area",
        "door": "Door",
        "output": "Output",
        "trigger": "Trigger",
        "filter": "Filter",
    }
    return DeviceInfo(
        identifiers={(DOMAIN, f"{coordinator.config_entry.entry_id}_{entity_type}_{number}")},
        name=name,
        manufacturer=MANUFACTURER,
        model=model_map.get(entity_type, entity_type.title()),
        via_device=(DOMAIN, coordinator.config_entry.entry_id),
    )

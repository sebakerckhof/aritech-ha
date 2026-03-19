"""Diagnostics support for Aritech integration."""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_USERNAME, CONF_PASSWORD
from homeassistant.core import HomeAssistant

from .const import DOMAIN, CONF_ENCRYPTION_KEY, CONF_PIN_CODE
from .coordinator import AritechCoordinator

REDACT_KEYS = {CONF_HOST, CONF_ENCRYPTION_KEY, CONF_PIN_CODE, CONF_USERNAME, CONF_PASSWORD}


def _redact_entity_names(entities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Redact entity names from a list of entity dicts."""
    return [
        {**entity, "name": "**REDACTED**"} if "name" in entity else entity
        for entity in entities
    ]


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: AritechCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Redact sensitive config data
    config_data = {
        k: "**REDACTED**" if k in REDACT_KEYS else v
        for k, v in entry.data.items()
    }

    return {
        "config": config_data,
        "panel": {
            "model": coordinator.panel_model,
            "name": coordinator.panel_name,
            "firmware": coordinator.firmware_version,
            "connected": coordinator.connected,
        },
        "entity_counts": {
            "areas": len(coordinator.get_areas()),
            "zones": len(coordinator.get_zones()),
            "outputs": len(coordinator.get_outputs()),
            "triggers": len(coordinator.get_triggers()),
            "doors": len(coordinator.get_doors()),
            "filters": len(coordinator.get_filters()),
        },
        "areas": _redact_entity_names(coordinator.get_areas()),
        "zones": _redact_entity_names(coordinator.get_zones()),
        "outputs": _redact_entity_names(coordinator.get_outputs()),
        "triggers": _redact_entity_names(coordinator.get_triggers()),
        "doors": _redact_entity_names(coordinator.get_doors()),
        "filters": _redact_entity_names(coordinator.get_filters()),
    }

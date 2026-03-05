"""Diagnostics support for Aritech integration."""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_USERNAME, CONF_PASSWORD
from homeassistant.core import HomeAssistant

from .const import DOMAIN, CONF_ENCRYPTION_KEY, CONF_PIN_CODE
from .coordinator import AritechCoordinator

REDACT_KEYS = {CONF_HOST, CONF_ENCRYPTION_KEY, CONF_PIN_CODE, CONF_USERNAME, CONF_PASSWORD}


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
        "areas": coordinator.get_areas(),
        "zones": coordinator.get_zones(),
        "outputs": coordinator.get_outputs(),
        "triggers": coordinator.get_triggers(),
        "doors": coordinator.get_doors(),
        "filters": coordinator.get_filters(),
    }

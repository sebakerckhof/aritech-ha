"""The Aritech ATS integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN
from .coordinator import AritechCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.ALARM_CONTROL_PANEL,
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Aritech ATS from a config entry."""
    _LOGGER.debug("Setting up Aritech ATS integration")

    # Create coordinator
    coordinator = AritechCoordinator(hass, entry)

    # Connect to the alarm panel
    try:
        await coordinator.async_connect()
    except Exception as err:
        _LOGGER.error("Failed to connect to Aritech panel: %s", err)
        raise ConfigEntryNotReady(f"Failed to connect: {err}") from err

    # Store coordinator in hass.data
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Forward setup to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading Aritech ATS integration")

    # Unload platforms
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        # Disconnect and cleanup coordinator
        coordinator: AritechCoordinator = hass.data[DOMAIN][entry.entry_id]
        await coordinator.async_disconnect()
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok

"""The Aritech integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN, CONF_PANEL_TYPE, PANEL_TYPE_X500
from .coordinator import AritechCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.ALARM_CONTROL_PANEL,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry to new version.

    Version 1 -> 2: Added panel_type field for x500/x700 distinction.
    Old entries are assumed to be x500 panels (PIN-based auth).
    """
    _LOGGER.debug("Migrating config entry from version %s", config_entry.version)

    if config_entry.version == 1:
        # Version 1 entries are x500 panels with PIN auth
        new_data = {**config_entry.data}

        # Add panel_type if not present (assume x500 for old entries)
        if CONF_PANEL_TYPE not in new_data:
            new_data[CONF_PANEL_TYPE] = PANEL_TYPE_X500

        hass.config_entries.async_update_entry(
            config_entry, data=new_data, version=2
        )
        _LOGGER.info("Migrated config entry to version 2")

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Aritech from a config entry."""
    _LOGGER.debug("Setting up Aritech integration")

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
    _LOGGER.debug("Unloading Aritech integration")

    # Unload platforms
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        # Disconnect and cleanup coordinator
        coordinator: AritechCoordinator = hass.data[DOMAIN][entry.entry_id]
        await coordinator.async_disconnect()
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok

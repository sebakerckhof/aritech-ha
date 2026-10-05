"""The Aritech integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceEntry

from .const import DOMAIN, MANUFACTURER, CONF_PANEL_TYPE, PANEL_TYPE_X500
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

    # Register the panel device up front so child devices can link to it by id
    panel_device = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name=coordinator.panel_name or "Aritech Panel",
        manufacturer=MANUFACTURER,
        model=coordinator.panel_model or "ATS Panel",
        sw_version=coordinator.firmware_version,
    )
    coordinator.panel_device_id = panel_device.id

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


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    device_entry: DeviceEntry,
) -> bool:
    """Allow removal of devices no longer present on the panel.

    This enables the "Delete" button in the UI for stale devices
    (e.g., zones/areas/outputs that were removed from the panel config).
    Devices that still exist on the panel cannot be deleted.
    """
    coordinator: AritechCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    entry_id = config_entry.entry_id

    # Build set of currently valid device identifiers from panel data
    valid_identifiers: set[tuple[str, str]] = {
        (DOMAIN, entry_id),  # Panel device itself - never allow removal
    }

    for zone in coordinator.get_zones():
        valid_identifiers.add((DOMAIN, f"{entry_id}_zone_{zone['number']}"))

    for area in coordinator.get_areas():
        valid_identifiers.add((DOMAIN, f"{entry_id}_area_{area['number']}"))

    for door in coordinator.get_doors():
        valid_identifiers.add((DOMAIN, f"{entry_id}_door_{door['number']}"))

    for trigger in coordinator.get_triggers():
        valid_identifiers.add((DOMAIN, f"{entry_id}_trigger_{trigger['number']}"))

    for output in coordinator.get_outputs():
        valid_identifiers.add((DOMAIN, f"{entry_id}_output_{output['number']}"))

    for filter_ in coordinator.get_filters():
        valid_identifiers.add((DOMAIN, f"{entry_id}_filter_{filter_['number']}"))

    # Allow removal only if device is NOT in current panel data
    return not bool(device_entry.identifiers & valid_identifiers)

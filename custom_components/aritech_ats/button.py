"""Button platform for Aritech integration."""
from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, MANUFACTURER
from .coordinator import AritechCoordinator

_LOGGER = logging.getLogger(__name__)


def _get_door_device_info(
    coordinator: AritechCoordinator, door_number: int, door_name: str
) -> DeviceInfo:
    """Get device info for a door (each door is its own device)."""
    return DeviceInfo(
        identifiers={(DOMAIN, f"{coordinator.config_entry.entry_id}_door_{door_number}")},
        name=door_name,
        manufacturer=MANUFACTURER,
        model="Door",
        via_device=(DOMAIN, coordinator.config_entry.entry_id),
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Aritech buttons from a config entry."""
    coordinator: AritechCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Wait for coordinator to have data
    if not coordinator.data:
        _LOGGER.warning("Coordinator has no data yet, waiting for initialization")
        await coordinator.async_config_entry_first_refresh()

    entities: list[ButtonEntity] = []

    # Create door unlock buttons
    for door in coordinator.get_doors():
        entities.append(
            AritechDoorUnlockButton(
                coordinator=coordinator,
                door_number=door["number"],
                door_name=door["name"],
            )
        )

    if entities:
        _LOGGER.info("Setting up %d buttons", len(entities))
        async_add_entities(entities)
    else:
        _LOGGER.debug("No doors found to create button entities")


class AritechDoorUnlockButton(ButtonEntity):
    """Button to unlock door for standard time."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:door-open"

    def __init__(
        self,
        coordinator: AritechCoordinator,
        door_number: int,
        door_name: str,
    ) -> None:
        """Initialize the door unlock button."""
        self.coordinator = coordinator
        self._door_number = door_number
        self._door_name = door_name

        # Entity attributes
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_door_{door_number}_unlock_standard"
        self._attr_name = "Unlock (Standard Time)"
        self._attr_device_info = _get_door_device_info(coordinator, door_number, door_name)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.connected

    async def async_press(self) -> None:
        """Unlock the door for standard time."""
        _LOGGER.info("Unlocking door %d (%s) for standard time", self._door_number, self._door_name)
        try:
            await self.coordinator.async_unlock_door_standard_time(self._door_number)
        except Exception as err:
            _LOGGER.error("Failed to unlock door %d: %s", self._door_number, err)
            raise

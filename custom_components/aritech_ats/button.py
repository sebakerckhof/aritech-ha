"""Button platform for Aritech integration."""
from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AritechCoordinator
from .helpers import get_entity_device_info

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Aritech buttons from a config entry."""
    coordinator: AritechCoordinator = hass.data[DOMAIN][entry.entry_id]

    if not coordinator.data:
        _LOGGER.warning("Coordinator has no data yet, waiting for initialization")
        await coordinator.async_config_entry_first_refresh()

    entities = [
        AritechDoorUnlockButton(coordinator, door["number"], door["name"])
        for door in coordinator.get_doors()
    ]

    if entities:
        _LOGGER.info("Setting up %d buttons", len(entities))
        async_add_entities(entities)
    else:
        _LOGGER.debug("No doors found to create button entities")


class AritechDoorUnlockButton(CoordinatorEntity[AritechCoordinator], ButtonEntity):
    """Button to unlock door for standard time."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:door-open"

    def __init__(self, coordinator: AritechCoordinator, door_number: int, door_name: str) -> None:
        super().__init__(coordinator)
        self._door_number = door_number
        self._door_name = door_name
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_door_{door_number}_unlock_standard"
        self._attr_name = "Unlock (Standard Time)"
        self._attr_device_info = get_entity_device_info(coordinator, "door", door_number, door_name)

    @property
    def available(self) -> bool:
        return self.coordinator.connected

    async def async_press(self) -> None:
        _LOGGER.info("Unlocking door %d (%s) for standard time", self._door_number, self._door_name)
        await self.coordinator.async_unlock_door_standard_time(self._door_number)

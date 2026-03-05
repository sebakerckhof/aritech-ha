"""Switch platform for Aritech integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AritechCoordinator, AritechData
from .helpers import get_panel_device_info, get_entity_device_info

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Aritech switches from a config entry."""
    coordinator: AritechCoordinator = hass.data[DOMAIN][entry.entry_id]

    if not coordinator.data:
        _LOGGER.warning("Coordinator has no data yet, waiting for initialization")
        await coordinator.async_config_entry_first_refresh()

    entities: list[SwitchEntity] = []

    # Zone inhibit switches
    for zone in coordinator.get_zones():
        entities.append(AritechZoneInhibitSwitch(coordinator, zone["number"], zone["name"]))

    # Trigger switches
    for trigger in coordinator.get_triggers():
        entities.append(AritechTriggerSwitch(coordinator, trigger["number"], trigger["name"]))

    # Force arm switches per area
    for area in coordinator.get_areas():
        entities.append(AritechForceArmSwitch(coordinator, area["number"], area["name"]))

    # Door switches
    for door in coordinator.get_doors():
        num, name = door["number"], door["name"]
        entities.append(AritechDoorEnableSwitch(coordinator, num, name))
        entities.append(AritechDoorLockSwitch(coordinator, num, name))

    if entities:
        _LOGGER.info("Setting up %d switches", len(entities))
        async_add_entities(entities)
    else:
        _LOGGER.warning("No zones, outputs, or triggers found to create switches")


# =============================================================================
# Zone switches
# =============================================================================


class AritechZoneInhibitSwitch(CoordinatorEntity[AritechCoordinator], SwitchEntity):
    """Switch to inhibit/uninhibit a zone."""

    _attr_has_entity_name = True
    _attr_device_class = SwitchDeviceClass.SWITCH
    _attr_icon = "mdi:shield-off"

    def __init__(self, coordinator: AritechCoordinator, zone_number: int, zone_name: str) -> None:
        super().__init__(coordinator)
        self._zone_number = zone_number
        self._zone_name = zone_name
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_zone_{zone_number}_inhibit"
        self._attr_name = "Inhibit"
        self._attr_device_info = get_entity_device_info(coordinator, "zone", zone_number, zone_name)

    @property
    def available(self) -> bool:
        return self.coordinator.connected

    @property
    def is_on(self) -> bool | None:
        zone_state = self.coordinator.get_zone_state_obj(self._zone_number)
        return zone_state.is_inhibited if zone_state else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        zone_state = self.coordinator.get_zone_state_obj(self._zone_number)
        if not zone_state:
            return {"zone_number": self._zone_number}
        return {
            "zone_number": self._zone_number,
            "state_text": str(zone_state),
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        _LOGGER.info("Inhibiting zone %d (%s)", self._zone_number, self._zone_name)
        await self.coordinator.async_inhibit_zone(self._zone_number)

    async def async_turn_off(self, **kwargs: Any) -> None:
        _LOGGER.info("Uninhibiting zone %d (%s)", self._zone_number, self._zone_name)
        await self.coordinator.async_uninhibit_zone(self._zone_number)


# =============================================================================
# Trigger switches
# =============================================================================


class AritechTriggerSwitch(CoordinatorEntity[AritechCoordinator], SwitchEntity):
    """Switch to control a trigger."""

    _attr_has_entity_name = True
    _attr_device_class = SwitchDeviceClass.SWITCH
    _attr_icon = "mdi:gesture-tap-button"

    def __init__(self, coordinator: AritechCoordinator, trigger_number: int, trigger_name: str) -> None:
        super().__init__(coordinator)
        self._trigger_number = trigger_number
        self._trigger_name = trigger_name
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_trigger_{trigger_number}"
        self._attr_name = trigger_name
        self._attr_device_info = get_panel_device_info(coordinator)

    @property
    def available(self) -> bool:
        return self.coordinator.connected

    @property
    def is_on(self) -> bool | None:
        trigger_state = self.coordinator.get_trigger_state_obj(self._trigger_number)
        return trigger_state.is_active if trigger_state else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        trigger_state = self.coordinator.get_trigger_state_obj(self._trigger_number)
        if not trigger_state:
            return {"trigger_number": self._trigger_number}
        return {
            "trigger_number": self._trigger_number,
            "state_text": str(trigger_state),
            "is_remote_output": trigger_state.is_remote_output,
            "is_fob": trigger_state.is_fob,
            "is_schedule": trigger_state.is_schedule,
            "is_function_key": trigger_state.is_function_key,
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        _LOGGER.info("Activating trigger %d (%s)", self._trigger_number, self._trigger_name)
        await self.coordinator.async_activate_trigger(self._trigger_number)

    async def async_turn_off(self, **kwargs: Any) -> None:
        _LOGGER.info("Deactivating trigger %d (%s)", self._trigger_number, self._trigger_name)
        await self.coordinator.async_deactivate_trigger(self._trigger_number)


# =============================================================================
# Force arm switch (uses RestoreEntity to persist across restarts)
# =============================================================================


class AritechForceArmSwitch(CoordinatorEntity[AritechCoordinator], SwitchEntity, RestoreEntity):
    """Switch to enable/disable force arm mode for an area."""

    _attr_has_entity_name = True
    _attr_device_class = SwitchDeviceClass.SWITCH
    _attr_icon = "mdi:shield-lock"

    def __init__(self, coordinator: AritechCoordinator, area_number: int, area_name: str) -> None:
        super().__init__(coordinator)
        self._area_number = area_number
        self._area_name = area_name
        self._is_on = False
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_area_{area_number}_force_arm"
        self._attr_name = "Force Arm"
        self._attr_device_info = get_entity_device_info(coordinator, "area", area_number, area_name)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_state()) is not None:
            self._is_on = last_state.state == "on"
            self.coordinator.set_force_arm(self._area_number, self._is_on)

    @property
    def available(self) -> bool:
        return self.coordinator.connected

    @property
    def is_on(self) -> bool:
        return self._is_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        _LOGGER.info("Enabling force arm for area %d (%s)", self._area_number, self._area_name)
        self._is_on = True
        self.coordinator.set_force_arm(self._area_number, True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        _LOGGER.info("Disabling force arm for area %d (%s)", self._area_number, self._area_name)
        self._is_on = False
        self.coordinator.set_force_arm(self._area_number, False)
        self.async_write_ha_state()


# =============================================================================
# Door switches
# =============================================================================


class AritechDoorEnableSwitch(CoordinatorEntity[AritechCoordinator], SwitchEntity):
    """Switch to enable/disable a door."""

    _attr_has_entity_name = True
    _attr_device_class = SwitchDeviceClass.SWITCH
    _attr_icon = "mdi:door"

    def __init__(self, coordinator: AritechCoordinator, door_number: int, door_name: str) -> None:
        super().__init__(coordinator)
        self._door_number = door_number
        self._door_name = door_name
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_door_{door_number}_enable"
        self._attr_name = "Enabled"
        self._attr_device_info = get_entity_device_info(coordinator, "door", door_number, door_name)

    @property
    def available(self) -> bool:
        return self.coordinator.connected

    @property
    def is_on(self) -> bool | None:
        door_state = self.coordinator.get_door_state_obj(self._door_number)
        if not door_state:
            return None
        return not door_state.is_disabled

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        door_state = self.coordinator.get_door_state_obj(self._door_number)
        if not door_state:
            return {"door_number": self._door_number}
        return {
            "door_number": self._door_number,
            "state_text": str(door_state),
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        _LOGGER.info("Enabling door %d (%s)", self._door_number, self._door_name)
        await self.coordinator.async_enable_door(self._door_number)

    async def async_turn_off(self, **kwargs: Any) -> None:
        _LOGGER.info("Disabling door %d (%s)", self._door_number, self._door_name)
        await self.coordinator.async_disable_door(self._door_number)


class AritechDoorLockSwitch(CoordinatorEntity[AritechCoordinator], SwitchEntity):
    """Switch to lock/unlock a door."""

    _attr_has_entity_name = True
    _attr_device_class = SwitchDeviceClass.SWITCH

    def __init__(self, coordinator: AritechCoordinator, door_number: int, door_name: str) -> None:
        super().__init__(coordinator)
        self._door_number = door_number
        self._door_name = door_name
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_door_{door_number}_lock"
        self._attr_name = "Unlocked"
        self._attr_device_info = get_entity_device_info(coordinator, "door", door_number, door_name)

    @property
    def available(self) -> bool:
        return self.coordinator.connected

    @property
    def is_on(self) -> bool | None:
        door_state = self.coordinator.get_door_state_obj(self._door_number)
        if not door_state:
            return None
        return not door_state.is_locked

    @property
    def icon(self) -> str:
        return "mdi:door-open" if self.is_on else "mdi:door-closed-lock"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        door_state = self.coordinator.get_door_state_obj(self._door_number)
        if not door_state:
            return {"door_number": self._door_number}
        return {
            "door_number": self._door_number,
            "state_text": str(door_state),
            "is_opened": door_state.is_opened,
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        _LOGGER.info("Unlocking door %d (%s)", self._door_number, self._door_name)
        await self.coordinator.async_unlock_door(self._door_number)

    async def async_turn_off(self, **kwargs: Any) -> None:
        _LOGGER.info("Locking door %d (%s)", self._door_number, self._door_name)
        await self.coordinator.async_lock_door(self._door_number)

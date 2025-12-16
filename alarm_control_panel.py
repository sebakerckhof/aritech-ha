"""Alarm control panel platform for Aritech ATS integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from aritech_client import AreaState

from .const import DOMAIN, MANUFACTURER
from .coordinator import AritechCoordinator

_LOGGER = logging.getLogger(__name__)


def _get_alarm_state(area_state: AreaState | None) -> AlarmControlPanelState:
    """Convert AreaState flags to Home Assistant alarm state."""
    if area_state is None:
        return AlarmControlPanelState.DISARMED

    # Priority order: alarm states first, then armed states
    if area_state.is_alarming:
        return AlarmControlPanelState.TRIGGERED
    if area_state.is_entering:
        return AlarmControlPanelState.PENDING
    if area_state.is_exiting:
        return AlarmControlPanelState.ARMING
    if area_state.is_full_set:
        return AlarmControlPanelState.ARMED_AWAY
    if area_state.is_partially_set:
        return AlarmControlPanelState.ARMED_HOME
    if area_state.is_partially_set_2:
        return AlarmControlPanelState.ARMED_NIGHT
    if area_state.is_unset:
        return AlarmControlPanelState.DISARMED

    return AlarmControlPanelState.DISARMED


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Aritech ATS alarm control panels from a config entry."""
    coordinator: AritechCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Wait for coordinator to have data
    if not coordinator.data:
        _LOGGER.warning("Coordinator has no data yet, waiting for initialization")
        await coordinator.async_config_entry_first_refresh()

    # Create an alarm panel entity for each area
    entities = []
    for area in coordinator.get_areas():
        entities.append(
            AritechAlarmControlPanel(
                coordinator=coordinator,
                area_number=area["number"],
                area_name=area["name"],
            )
        )

    if entities:
        _LOGGER.info("Setting up %d alarm control panels", len(entities))
        async_add_entities(entities)
    else:
        _LOGGER.warning("No areas found to create alarm control panels")


class AritechAlarmControlPanel(AlarmControlPanelEntity):
    """Representation of an Aritech ATS area as an alarm control panel."""

    _attr_has_entity_name = True
    _attr_supported_features = (
        AlarmControlPanelEntityFeature.ARM_HOME
        | AlarmControlPanelEntityFeature.ARM_AWAY
        | AlarmControlPanelEntityFeature.ARM_NIGHT
    )
    _attr_code_arm_required = False

    def __init__(
        self,
        coordinator: AritechCoordinator,
        area_number: int,
        area_name: str,
    ) -> None:
        """Initialize the alarm control panel."""
        self.coordinator = coordinator
        self._area_number = area_number
        self._area_name = area_name
        self._unregister_callback: callable | None = None

        # Entity attributes
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_area_{area_number}"
        self._attr_name = area_name
        
        # Device info - each area is its own device under the panel
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{coordinator.config_entry.entry_id}_area_{area_number}")},
            name=area_name,
            manufacturer=MANUFACTURER,
            model="Area",
            via_device=(DOMAIN, coordinator.config_entry.entry_id),
        )

    async def async_added_to_hass(self) -> None:
        """Run when entity is added to hass."""
        await super().async_added_to_hass()
        
        # Register for area-specific callbacks
        self._unregister_callback = self.coordinator.register_area_callback(
            self._area_number, self._handle_area_update
        )
        
        # Also listen to coordinator updates
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
    def alarm_state(self) -> AlarmControlPanelState | None:
        """Return the state of the alarm."""
        area_state = self.coordinator.get_area_state_obj(self._area_number)
        return _get_alarm_state(area_state)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        area_state = self.coordinator.get_area_state_obj(self._area_number)
        if not area_state:
            return {"area_number": self._area_number}

        return {
            "area_number": self._area_number,
            "state_text": str(area_state),
            "is_alarming": area_state.is_alarming,
            "is_alarm_acknowledged": area_state.is_alarm_acknowledged,
            "is_tampered": area_state.is_tampered,
            "is_ready_to_arm": area_state.is_ready_to_arm,
            "is_exiting": area_state.is_exiting,
            "is_entering": area_state.is_entering,
            "has_fire": area_state.has_fire,
            "has_panic": area_state.has_panic,
            "has_medical": area_state.has_medical,
            "has_duress": area_state.has_duress,
            "has_technical": area_state.has_technical,
            "has_active_zones": area_state.has_active_zones,
            "has_inhibited_zones": area_state.has_inhibited_zones,
            "has_isolated_zones": area_state.has_isolated_zones,
            "has_zone_faults": area_state.has_zone_faults,
            "has_zone_tamper": area_state.has_zone_tamper,
            "is_buzzer_active": area_state.is_buzzer_active,
            "is_internal_siren": area_state.is_internal_siren,
            "is_external_siren": area_state.is_external_siren,
            "is_strobe_active": area_state.is_strobe_active,
        }

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command."""
        _LOGGER.info("Disarming area %d (%s)", self._area_number, self._area_name)
        try:
            await self.coordinator.async_disarm_area(self._area_number)
        except Exception as err:
            _LOGGER.error("Failed to disarm area %d: %s", self._area_number, err)
            raise

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm away (full) command."""
        force = self.coordinator.get_force_arm(self._area_number)
        _LOGGER.info("Arming area %d (%s) - full%s", self._area_number, self._area_name, " (force)" if force else "")
        try:
            await self.coordinator.async_arm_area(self._area_number, "full", force=force)
        except Exception as err:
            _LOGGER.error("Failed to arm area %d: %s", self._area_number, err)
            raise

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Send arm home (part 1) command."""
        force = self.coordinator.get_force_arm(self._area_number)
        _LOGGER.info("Arming area %d (%s) - part1%s", self._area_number, self._area_name, " (force)" if force else "")
        try:
            await self.coordinator.async_arm_area(self._area_number, "part1", force=force)
        except Exception as err:
            _LOGGER.error("Failed to arm area %d (part1): %s", self._area_number, err)
            raise

    async def async_alarm_arm_night(self, code: str | None = None) -> None:
        """Send arm night (part 2) command."""
        force = self.coordinator.get_force_arm(self._area_number)
        _LOGGER.info("Arming area %d (%s) - part2%s", self._area_number, self._area_name, " (force)" if force else "")
        try:
            await self.coordinator.async_arm_area(self._area_number, "part2", force=force)
        except Exception as err:
            _LOGGER.error("Failed to arm area %d (part2): %s", self._area_number, err)
            raise

"""Switch platform for Aritech integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import AritechCoordinator

_LOGGER = logging.getLogger(__name__)


def _get_zone_device_info(
    coordinator: AritechCoordinator, zone_number: int, zone_name: str
) -> DeviceInfo:
    """Get device info for a zone (each zone is its own device)."""
    return DeviceInfo(
        identifiers={(DOMAIN, f"{coordinator.config_entry.entry_id}_zone_{zone_number}")},
        name=zone_name,
        manufacturer=MANUFACTURER,
        model="Zone",
        via_device=(DOMAIN, coordinator.config_entry.entry_id),
    )


def _get_output_device_info(
    coordinator: AritechCoordinator, output_number: int, output_name: str
) -> DeviceInfo:
    """Get device info for an output (each output is its own device)."""
    return DeviceInfo(
        identifiers={(DOMAIN, f"{coordinator.config_entry.entry_id}_output_{output_number}")},
        name=output_name,
        manufacturer=MANUFACTURER,
        model="Output",
        via_device=(DOMAIN, coordinator.config_entry.entry_id),
    )


def _get_panel_device_info(coordinator: AritechCoordinator) -> DeviceInfo:
    """Get device info for the main panel."""
    return DeviceInfo(
        identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
        name=coordinator.panel_name or "Aritech Panel",
        manufacturer=MANUFACTURER,
        model=coordinator.panel_model or "ATS Panel",
        sw_version=coordinator.firmware_version,
    )


def _get_area_device_info(
    coordinator: AritechCoordinator, area_number: int, area_name: str
) -> DeviceInfo:
    """Get device info for an area (each area is its own device)."""
    return DeviceInfo(
        identifiers={(DOMAIN, f"{coordinator.config_entry.entry_id}_area_{area_number}")},
        name=area_name,
        manufacturer=MANUFACTURER,
        model="Area",
        via_device=(DOMAIN, coordinator.config_entry.entry_id),
    )


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
    """Set up Aritech switches from a config entry."""
    coordinator: AritechCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Wait for coordinator to have data
    if not coordinator.data:
        _LOGGER.warning("Coordinator has no data yet, waiting for initialization")
        await coordinator.async_config_entry_first_refresh()

    entities: list[SwitchEntity] = []

    # Create zone inhibit switches (part of zone device)
    for zone in coordinator.get_zones():
        entities.append(
            AritechZoneInhibitSwitch(
                coordinator=coordinator,
                zone_number=zone["number"],
                zone_name=zone["name"],
            )
        )

    # Create output switches (part of panel device)
    for output in coordinator.get_outputs():
        entities.append(
            AritechOutputSwitch(
                coordinator=coordinator,
                output_number=output["number"],
                output_name=output["name"],
            )
        )

    # Create trigger switches (part of panel device)
    for trigger in coordinator.get_triggers():
        entities.append(
            AritechTriggerSwitch(
                coordinator=coordinator,
                trigger_number=trigger["number"],
                trigger_name=trigger["name"],
            )
        )

    # Create force arm switches for each area
    for area in coordinator.get_areas():
        entities.append(
            AritechForceArmSwitch(
                coordinator=coordinator,
                area_number=area["number"],
                area_name=area["name"],
            )
        )

    # Create door switches
    for door in coordinator.get_doors():
        # Door enable switch
        entities.append(
            AritechDoorEnableSwitch(
                coordinator=coordinator,
                door_number=door["number"],
                door_name=door["name"],
            )
        )
        # Door lock switch
        entities.append(
            AritechDoorLockSwitch(
                coordinator=coordinator,
                door_number=door["number"],
                door_name=door["name"],
            )
        )

    if entities:
        _LOGGER.info("Setting up %d switches", len(entities))
        async_add_entities(entities)
    else:
        _LOGGER.warning("No zones, outputs, or triggers found to create switches")


class AritechZoneInhibitSwitch(SwitchEntity):
    """Switch to inhibit/uninhibit a zone."""

    _attr_has_entity_name = True
    _attr_device_class = SwitchDeviceClass.SWITCH
    _attr_icon = "mdi:shield-off"

    def __init__(
        self,
        coordinator: AritechCoordinator,
        zone_number: int,
        zone_name: str,
    ) -> None:
        """Initialize the zone inhibit switch."""
        self.coordinator = coordinator
        self._zone_number = zone_number
        self._zone_name = zone_name
        self._unregister_callback: callable | None = None

        # Entity attributes
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_zone_{zone_number}_inhibit"
        self._attr_name = "Inhibit"

        # Zone inhibit switch belongs to the zone device
        self._attr_device_info = _get_zone_device_info(coordinator, zone_number, zone_name)

    async def async_added_to_hass(self) -> None:
        """Run when entity is added to hass."""
        await super().async_added_to_hass()

        self._unregister_callback = self.coordinator.register_zone_callback(
            self._zone_number, self._handle_zone_update
        )

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
    def _handle_zone_update(self) -> None:
        """Handle zone state update."""
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.connected

    @property
    def is_on(self) -> bool | None:
        """Return true if zone is inhibited."""
        zone_state = self.coordinator.get_zone_state_obj(self._zone_number)
        if not zone_state:
            return None
        return zone_state.is_inhibited

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        zone_state = self.coordinator.get_zone_state_obj(self._zone_number)
        if not zone_state:
            return {"zone_number": self._zone_number}

        return {
            "zone_number": self._zone_number,
            "state_text": str(zone_state),
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Inhibit the zone."""
        _LOGGER.info("Inhibiting zone %d (%s)", self._zone_number, self._zone_name)
        try:
            await self.coordinator.async_inhibit_zone(self._zone_number)
        except Exception as err:
            _LOGGER.error("Failed to inhibit zone %d: %s", self._zone_number, err)
            raise

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Uninhibit the zone."""
        _LOGGER.info("Uninhibiting zone %d (%s)", self._zone_number, self._zone_name)
        try:
            await self.coordinator.async_uninhibit_zone(self._zone_number)
        except Exception as err:
            _LOGGER.error("Failed to uninhibit zone %d: %s", self._zone_number, err)
            raise


class AritechOutputSwitch(SwitchEntity):
    """Switch to control an output."""

    _attr_has_entity_name = True
    _attr_device_class = SwitchDeviceClass.OUTLET
    _attr_icon = "mdi:electric-switch"

    def __init__(
        self,
        coordinator: AritechCoordinator,
        output_number: int,
        output_name: str,
    ) -> None:
        """Initialize the output switch."""
        self.coordinator = coordinator
        self._output_number = output_number
        self._output_name = output_name
        self._unregister_callback: callable | None = None

        # Entity attributes
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_output_{output_number}"
        self._attr_name = "Switch"

        # Output switch belongs to its own output device
        self._attr_device_info = _get_output_device_info(coordinator, output_number, output_name)

    async def async_added_to_hass(self) -> None:
        """Run when entity is added to hass."""
        await super().async_added_to_hass()

        self._unregister_callback = self.coordinator.register_output_callback(
            self._output_number, self._handle_output_update
        )

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
    def _handle_output_update(self) -> None:
        """Handle output state update."""
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.connected

    @property
    def is_on(self) -> bool | None:
        """Return true if output is active."""
        output_state = self.coordinator.get_output_state_obj(self._output_number)
        if not output_state:
            return None
        return output_state.is_on or output_state.is_active

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        output_state = self.coordinator.get_output_state_obj(self._output_number)
        if not output_state:
            return {"output_number": self._output_number}

        return {
            "output_number": self._output_number,
            "state_text": str(output_state),
            "is_forced": output_state.is_forced,
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Activate the output."""
        _LOGGER.info("Activating output %d (%s)", self._output_number, self._output_name)
        try:
            await self.coordinator.async_activate_output(self._output_number)
        except Exception as err:
            _LOGGER.error("Failed to activate output %d: %s", self._output_number, err)
            raise

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Deactivate the output."""
        _LOGGER.info("Deactivating output %d (%s)", self._output_number, self._output_name)
        try:
            await self.coordinator.async_deactivate_output(self._output_number)
        except Exception as err:
            _LOGGER.error("Failed to deactivate output %d: %s", self._output_number, err)
            raise


class AritechTriggerSwitch(SwitchEntity):
    """Switch to control a trigger (manual activation only)."""

    _attr_has_entity_name = True
    _attr_device_class = SwitchDeviceClass.SWITCH
    _attr_icon = "mdi:gesture-tap-button"

    def __init__(
        self,
        coordinator: AritechCoordinator,
        trigger_number: int,
        trigger_name: str,
    ) -> None:
        """Initialize the trigger switch."""
        self.coordinator = coordinator
        self._trigger_number = trigger_number
        self._trigger_name = trigger_name
        self._unregister_callback: callable | None = None

        # Entity attributes
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_trigger_{trigger_number}"
        self._attr_name = trigger_name

        # Trigger switches belong to the main panel device
        self._attr_device_info = _get_panel_device_info(coordinator)

    async def async_added_to_hass(self) -> None:
        """Run when entity is added to hass."""
        await super().async_added_to_hass()

        self._unregister_callback = self.coordinator.register_trigger_callback(
            self._trigger_number, self._handle_trigger_update
        )

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
    def _handle_trigger_update(self) -> None:
        """Handle trigger state update."""
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.connected

    @property
    def is_on(self) -> bool | None:
        """Return true if trigger is active."""
        trigger_state = self.coordinator.get_trigger_state_obj(self._trigger_number)
        if not trigger_state:
            return None
        return trigger_state.is_active

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
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
        """Activate the trigger."""
        _LOGGER.info("Activating trigger %d (%s)", self._trigger_number, self._trigger_name)
        try:
            await self.coordinator.async_activate_trigger(self._trigger_number)
        except Exception as err:
            _LOGGER.error("Failed to activate trigger %d: %s", self._trigger_number, err)
            raise

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Deactivate the trigger."""
        _LOGGER.info("Deactivating trigger %d (%s)", self._trigger_number, self._trigger_name)
        try:
            await self.coordinator.async_deactivate_trigger(self._trigger_number)
        except Exception as err:
            _LOGGER.error("Failed to deactivate trigger %d: %s", self._trigger_number, err)
            raise


class AritechForceArmSwitch(SwitchEntity, RestoreEntity):
    """Switch to enable/disable force arm mode for an area."""

    _attr_has_entity_name = True
    _attr_device_class = SwitchDeviceClass.SWITCH
    _attr_icon = "mdi:shield-lock"

    def __init__(
        self,
        coordinator: AritechCoordinator,
        area_number: int,
        area_name: str,
    ) -> None:
        """Initialize the force arm switch."""
        self.coordinator = coordinator
        self._area_number = area_number
        self._area_name = area_name
        self._is_on = False

        # Entity attributes
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_area_{area_number}_force_arm"
        self._attr_name = "Force Arm"

        # Force arm switch belongs to the area device
        self._attr_device_info = _get_area_device_info(coordinator, area_number, area_name)

    async def async_added_to_hass(self) -> None:
        """Run when entity is added to hass."""
        await super().async_added_to_hass()

        # Restore previous state
        if (last_state := await self.async_get_last_state()) is not None:
            self._is_on = last_state.state == "on"
            # Update coordinator with restored state
            self.coordinator.set_force_arm(self._area_number, self._is_on)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.connected

    @property
    def is_on(self) -> bool:
        """Return true if force arm mode is enabled."""
        return self._is_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable force arm mode."""
        _LOGGER.info("Enabling force arm for area %d (%s)", self._area_number, self._area_name)
        self._is_on = True
        self.coordinator.set_force_arm(self._area_number, True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable force arm mode."""
        _LOGGER.info("Disabling force arm for area %d (%s)", self._area_number, self._area_name)
        self._is_on = False
        self.coordinator.set_force_arm(self._area_number, False)
        self.async_write_ha_state()


class AritechDoorEnableSwitch(SwitchEntity):
    """Switch to enable/disable a door."""

    _attr_has_entity_name = True
    _attr_device_class = SwitchDeviceClass.SWITCH
    _attr_icon = "mdi:door"

    def __init__(
        self,
        coordinator: AritechCoordinator,
        door_number: int,
        door_name: str,
    ) -> None:
        """Initialize the door enable switch."""
        self.coordinator = coordinator
        self._door_number = door_number
        self._door_name = door_name
        self._unregister_callback: callable | None = None

        # Entity attributes
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_door_{door_number}_enable"
        self._attr_name = "Enabled"

        # Door enable switch belongs to the door device
        self._attr_device_info = _get_door_device_info(coordinator, door_number, door_name)

    async def async_added_to_hass(self) -> None:
        """Run when entity is added to hass."""
        await super().async_added_to_hass()

        self._unregister_callback = self.coordinator.register_door_callback(
            self._door_number, self._handle_door_update
        )

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
    def _handle_door_update(self) -> None:
        """Handle door state update."""
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.connected

    @property
    def is_on(self) -> bool | None:
        """Return true if door is enabled (not disabled)."""
        door_state = self.coordinator.get_door_state_obj(self._door_number)
        if not door_state:
            return None
        # Switch is ON when door is enabled (not disabled)
        return not door_state.is_disabled

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        door_state = self.coordinator.get_door_state_obj(self._door_number)
        if not door_state:
            return {"door_number": self._door_number}

        return {
            "door_number": self._door_number,
            "state_text": str(door_state),
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable the door."""
        _LOGGER.info("Enabling door %d (%s)", self._door_number, self._door_name)
        try:
            await self.coordinator.async_enable_door(self._door_number)
        except Exception as err:
            _LOGGER.error("Failed to enable door %d: %s", self._door_number, err)
            raise

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable the door."""
        _LOGGER.info("Disabling door %d (%s)", self._door_number, self._door_name)
        try:
            await self.coordinator.async_disable_door(self._door_number)
        except Exception as err:
            _LOGGER.error("Failed to disable door %d: %s", self._door_number, err)
            raise


class AritechDoorLockSwitch(SwitchEntity):
    """Switch to lock/unlock a door."""

    _attr_has_entity_name = True
    _attr_device_class = SwitchDeviceClass.SWITCH
    _attr_icon = "mdi:door-closed-lock"

    def __init__(
        self,
        coordinator: AritechCoordinator,
        door_number: int,
        door_name: str,
    ) -> None:
        """Initialize the door lock switch."""
        self.coordinator = coordinator
        self._door_number = door_number
        self._door_name = door_name
        self._unregister_callback: callable | None = None

        # Entity attributes
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_door_{door_number}_lock"
        self._attr_name = "Unlocked"

        # Door lock switch belongs to the door device
        self._attr_device_info = _get_door_device_info(coordinator, door_number, door_name)

    async def async_added_to_hass(self) -> None:
        """Run when entity is added to hass."""
        await super().async_added_to_hass()

        self._unregister_callback = self.coordinator.register_door_callback(
            self._door_number, self._handle_door_update
        )

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
    def _handle_door_update(self) -> None:
        """Handle door state update."""
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.connected

    @property
    def is_on(self) -> bool | None:
        """Return true if door is unlocked."""
        door_state = self.coordinator.get_door_state_obj(self._door_number)
        if not door_state:
            return None
        # Switch is ON when door is unlocked
        return not door_state.is_locked

    @property
    def icon(self) -> str:
        """Return icon based on lock state."""
        if self.is_on:
            return "mdi:door-open"
        return "mdi:door-closed-lock"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        door_state = self.coordinator.get_door_state_obj(self._door_number)
        if not door_state:
            return {"door_number": self._door_number}

        return {
            "door_number": self._door_number,
            "state_text": str(door_state),
            "is_opened": door_state.is_opened,
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Unlock the door."""
        _LOGGER.info("Unlocking door %d (%s)", self._door_number, self._door_name)
        try:
            await self.coordinator.async_unlock_door(self._door_number)
        except Exception as err:
            _LOGGER.error("Failed to unlock door %d: %s", self._door_number, err)
            raise

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Lock the door."""
        _LOGGER.info("Locking door %d (%s)", self._door_number, self._door_name)
        try:
            await self.coordinator.async_lock_door(self._door_number)
        except Exception as err:
            _LOGGER.error("Failed to lock door %d: %s", self._door_number, err)
            raise

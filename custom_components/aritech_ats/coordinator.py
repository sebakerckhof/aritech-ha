"""DataUpdateCoordinator for Aritech ATS integration."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from aritech_client import AritechClient, AritechMonitor, ChangeEvent, InitializedEvent
from aritech_client import AreaState, ZoneState, OutputState, TriggerState

from .const import (
    DOMAIN,
    CONF_ENCRYPTION_KEY,
    CONF_PIN_CODE,
    UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class AritechData:
    """Class to hold all Aritech panel data."""

    # Panel info
    panel_model: str | None = None
    panel_name: str | None = None
    firmware_version: str | None = None
    protocol_version: int | None = None

    # Entity lists (name + number)
    areas: list[dict[str, Any]] = field(default_factory=list)
    zones: list[dict[str, Any]] = field(default_factory=list)
    outputs: list[dict[str, Any]] = field(default_factory=list)
    triggers: list[dict[str, Any]] = field(default_factory=list)

    # Current states keyed by entity number
    area_states: dict[int, dict[str, Any]] = field(default_factory=dict)
    zone_states: dict[int, dict[str, Any]] = field(default_factory=dict)
    output_states: dict[int, dict[str, Any]] = field(default_factory=dict)
    trigger_states: dict[int, dict[str, Any]] = field(default_factory=dict)


class AritechCoordinator(DataUpdateCoordinator[AritechData]):
    """Coordinator to manage Aritech ATS panel connection and updates."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=None,  # We use push updates, not polling
        )
        self.config_entry = entry
        self._client: AritechClient | None = None
        self._monitor: AritechMonitor | None = None
        self._data = AritechData()
        self._connected = False
        self._reconnect_task: asyncio.Task | None = None

        # Reconnection backoff settings
        self._reconnect_attempt: int = 0
        self._reconnect_delays: list[int] = [5, 10, 20, 40, 60, 120]  # Exponential backoff delays in seconds
        self._max_reconnect_attempts: int = 20  # Max attempts before longer pause

        # Callbacks for entity updates
        self._area_callbacks: dict[int, list[callable]] = {}
        self._zone_callbacks: dict[int, list[callable]] = {}
        self._output_callbacks: dict[int, list[callable]] = {}
        self._trigger_callbacks: dict[int, list[callable]] = {}

        # Force arm state per area
        self._force_arm: dict[int, bool] = {}

    @property
    def client(self) -> AritechClient | None:
        """Return the Aritech client."""
        return self._client

    @property
    def connected(self) -> bool:
        """Return connection status."""
        return self._connected

    @property
    def panel_model(self) -> str | None:
        """Return the panel model."""
        return self._data.panel_model

    @property
    def panel_name(self) -> str | None:
        """Return the panel name."""
        return self._data.panel_name

    @property
    def firmware_version(self) -> str | None:
        """Return the firmware version."""
        return self._data.firmware_version

    async def async_connect(self) -> None:
        """Connect to the alarm panel and start monitoring."""
        config = self.config_entry.data

        # Create client
        self._client = AritechClient({
            "host": config[CONF_HOST],
            "port": config[CONF_PORT],
            "pin": config[CONF_PIN_CODE],
            "encryption_key": config[CONF_ENCRYPTION_KEY],
        })

        try:
            _LOGGER.debug("Connecting to Aritech panel at %s:%s", config[CONF_HOST], config[CONF_PORT])

            # Connect and authenticate (new library combines connect + key exchange + login)
            await self._client.connect()
            await self._client.initialize()

            # Get panel info from client properties
            self._data.panel_model = self._client.panel_model
            self._data.panel_name = self._client.panel_name
            self._data.firmware_version = self._client.firmware_version

            _LOGGER.info(
                "Connected to %s (%s) firmware %s",
                self._data.panel_name,
                self._data.panel_model,
                self._data.firmware_version,
            )

            # Create monitor and set up callbacks
            self._monitor = AritechMonitor(self._client)
            self._setup_monitor_callbacks()

            # Start monitoring (this fetches all entity names and states)
            await self._monitor.start()

            self._connected = True
            _LOGGER.info("Aritech ATS monitoring started")

        except Exception as err:
            self._connected = False
            _LOGGER.error("Failed to connect to Aritech panel: %s", err)
            await self.async_disconnect()
            raise UpdateFailed(f"Failed to connect: {err}") from err

    async def async_disconnect(self) -> None:
        """Disconnect from the alarm panel."""
        if self._monitor:
            self._monitor.stop()
            self._monitor = None

        if self._client:
            await self._client.disconnect()
            self._client = None

        self._connected = False
        _LOGGER.debug("Disconnected from Aritech panel")

    def _setup_monitor_callbacks(self) -> None:
        """Set up callbacks for monitor events."""
        if not self._monitor:
            return

        @self._monitor.on_initialized
        def handle_initialized(event: InitializedEvent) -> None:
            """Handle initialization event with all entity data."""
            _LOGGER.debug(
                "Initialized: %d zones, %d areas, %d outputs, %d triggers",
                len(event.zones),
                len(event.areas),
                len(event.outputs),
                len(event.triggers),
            )

            # Convert NamedItem lists to dicts for backward compatibility
            self._data.zones = [{"number": z.number, "name": z.name} for z in event.zones]
            self._data.areas = [{"number": a.number, "name": a.name} for a in event.areas]
            self._data.outputs = [{"number": o.number, "name": o.name} for o in event.outputs]
            self._data.triggers = [{"number": t.number, "name": t.name} for t in event.triggers]

            # Store initial states (these contain state dataclass objects)
            self._data.zone_states = event.zone_states
            self._data.area_states = event.area_states
            self._data.output_states = event.output_states
            self._data.trigger_states = event.trigger_states

            # Update coordinator data
            self.async_set_updated_data(self._data)

        @self._monitor.on_zone_changed
        def handle_zone_changed(event: ChangeEvent) -> None:
            """Handle zone state change."""
            _LOGGER.debug(
                "Zone %d (%s) changed: %s -> %s",
                event.id,
                event.name,
                event.old_data.get("state") if event.old_data else "NEW",
                event.new_data.get("state"),
            )
            
            # Update stored state
            self._data.zone_states[event.id] = event.new_data
            
            # Notify specific zone callbacks
            self._notify_callbacks(self._zone_callbacks, event.id)
            
            # Update coordinator
            self.async_set_updated_data(self._data)

        @self._monitor.on_area_changed
        def handle_area_changed(event: ChangeEvent) -> None:
            """Handle area state change."""
            _LOGGER.debug(
                "Area %d (%s) changed: %s -> %s",
                event.id,
                event.name,
                event.old_data.get("state") if event.old_data else "NEW",
                event.new_data.get("state"),
            )
            
            # Update stored state
            self._data.area_states[event.id] = event.new_data
            
            # Notify specific area callbacks
            self._notify_callbacks(self._area_callbacks, event.id)
            
            # Update coordinator
            self.async_set_updated_data(self._data)

        @self._monitor.on_output_changed
        def handle_output_changed(event: ChangeEvent) -> None:
            """Handle output state change."""
            _LOGGER.debug(
                "Output %d (%s) changed: %s -> %s",
                event.id,
                event.name,
                event.old_data.get("state") if event.old_data else "NEW",
                event.new_data.get("state"),
            )
            
            # Update stored state
            self._data.output_states[event.id] = event.new_data
            
            # Notify specific output callbacks
            self._notify_callbacks(self._output_callbacks, event.id)
            
            # Update coordinator
            self.async_set_updated_data(self._data)

        @self._monitor.on_trigger_changed
        def handle_trigger_changed(event: ChangeEvent) -> None:
            """Handle trigger state change."""
            _LOGGER.debug(
                "Trigger %d (%s) changed: %s -> %s",
                event.id,
                event.name,
                event.old_data.get("state") if event.old_data else "NEW",
                event.new_data.get("state"),
            )
            
            # Update stored state
            self._data.trigger_states[event.id] = event.new_data
            
            # Notify specific trigger callbacks
            self._notify_callbacks(self._trigger_callbacks, event.id)
            
            # Update coordinator
            self.async_set_updated_data(self._data)

        @self._monitor.on_error
        def handle_error(error: Exception) -> None:
            """Handle monitor errors."""
            _LOGGER.error("Aritech monitor error: %s", error)
            # Schedule reconnection
            self._schedule_reconnect()

        # Register client connection lost callback
        if self._client:
            @self._client.on_connection_lost
            def handle_connection_lost() -> None:
                """Handle client connection lost (e.g., keep-alive failures)."""
                _LOGGER.warning("Aritech client connection lost detected")
                self._schedule_reconnect()

    @callback
    def _notify_callbacks(self, callbacks: dict[int, list[callable]], entity_id: int) -> None:
        """Notify callbacks for a specific entity."""
        if entity_id in callbacks:
            for callback_fn in callbacks[entity_id]:
                try:
                    callback_fn()
                except Exception as err:
                    _LOGGER.error("Error in entity callback: %s", err)

    def register_area_callback(self, area_num: int, callback_fn: callable) -> callable:
        """Register a callback for area state changes."""
        if area_num not in self._area_callbacks:
            self._area_callbacks[area_num] = []
        self._area_callbacks[area_num].append(callback_fn)
        
        def unregister() -> None:
            self._area_callbacks[area_num].remove(callback_fn)
        
        return unregister

    def register_zone_callback(self, zone_num: int, callback_fn: callable) -> callable:
        """Register a callback for zone state changes."""
        if zone_num not in self._zone_callbacks:
            self._zone_callbacks[zone_num] = []
        self._zone_callbacks[zone_num].append(callback_fn)
        
        def unregister() -> None:
            self._zone_callbacks[zone_num].remove(callback_fn)
        
        return unregister

    def register_output_callback(self, output_num: int, callback_fn: callable) -> callable:
        """Register a callback for output state changes."""
        if output_num not in self._output_callbacks:
            self._output_callbacks[output_num] = []
        self._output_callbacks[output_num].append(callback_fn)
        
        def unregister() -> None:
            self._output_callbacks[output_num].remove(callback_fn)
        
        return unregister

    def register_trigger_callback(self, trigger_num: int, callback_fn: callable) -> callable:
        """Register a callback for trigger state changes."""
        if trigger_num not in self._trigger_callbacks:
            self._trigger_callbacks[trigger_num] = []
        self._trigger_callbacks[trigger_num].append(callback_fn)
        
        def unregister() -> None:
            self._trigger_callbacks[trigger_num].remove(callback_fn)
        
        return unregister

    def _get_reconnect_delay(self) -> int:
        """Get the delay for the current reconnection attempt using exponential backoff."""
        if self._reconnect_attempt >= len(self._reconnect_delays):
            return self._reconnect_delays[-1]  # Use max delay
        return self._reconnect_delays[self._reconnect_attempt]

    def _schedule_reconnect(self) -> None:
        """Schedule a reconnection attempt with exponential backoff."""
        if self._reconnect_task and not self._reconnect_task.done():
            return  # Already scheduled

        delay = self._get_reconnect_delay()
        self._reconnect_attempt += 1

        async def reconnect() -> None:
            """Attempt to reconnect."""
            _LOGGER.info(
                "Attempting to reconnect to Aritech panel in %d seconds (attempt %d)...",
                delay,
                self._reconnect_attempt,
            )
            await asyncio.sleep(delay)

            try:
                await self.async_disconnect()
                await self.async_connect()
                _LOGGER.info(
                    "Reconnected to Aritech panel successfully after %d attempts",
                    self._reconnect_attempt,
                )
                # Reset attempt counter on successful reconnection
                self._reconnect_attempt = 0
            except Exception as err:
                _LOGGER.error(
                    "Reconnection failed (attempt %d): %s",
                    self._reconnect_attempt,
                    err,
                )
                if self._reconnect_attempt >= self._max_reconnect_attempts:
                    _LOGGER.warning(
                        "Max reconnection attempts (%d) reached. Will continue retrying with max delay (%ds).",
                        self._max_reconnect_attempts,
                        self._reconnect_delays[-1],
                    )
                self._schedule_reconnect()

        self._reconnect_task = self.hass.async_create_task(reconnect())

    async def _async_update_data(self) -> AritechData:
        """Fetch data from the panel (fallback, not normally used)."""
        # Push updates handle most cases, this is a fallback
        if not self._connected:
            raise UpdateFailed("Not connected to panel")
        
        return self._data

    # =========================================================================
    # FORCE ARM STATE
    # =========================================================================

    def set_force_arm(self, area_num: int, enabled: bool) -> None:
        """Set force arm state for an area."""
        self._force_arm[area_num] = enabled

    def get_force_arm(self, area_num: int) -> bool:
        """Get force arm state for an area."""
        return self._force_arm.get(area_num, False)

    # =========================================================================
    # CONTROL METHODS
    # =========================================================================

    async def async_arm_area(self, area_num: int, mode: str = "full", force: bool = False) -> None:
        """Arm an area."""
        if not self._client:
            raise UpdateFailed("Not connected to panel")

        try:
            await self._client.arm_area(area_num, set_type=mode, force=force)
        except Exception as err:
            _LOGGER.error("Failed to arm area %d: %s", area_num, err)
            raise

    async def async_disarm_area(self, area_num: int) -> None:
        """Disarm an area."""
        if not self._client:
            raise UpdateFailed("Not connected to panel")

        try:
            await self._client.disarm_area(area_num)
        except Exception as err:
            _LOGGER.error("Failed to disarm area %d: %s", area_num, err)
            raise

    async def async_inhibit_zone(self, zone_num: int) -> None:
        """Inhibit a zone."""
        if not self._client:
            raise UpdateFailed("Not connected to panel")

        try:
            await self._client.inhibit_zone(zone_num)
        except Exception as err:
            _LOGGER.error("Failed to inhibit zone %d: %s", zone_num, err)
            raise

    async def async_uninhibit_zone(self, zone_num: int) -> None:
        """Uninhibit a zone."""
        if not self._client:
            raise UpdateFailed("Not connected to panel")

        try:
            await self._client.uninhibit_zone(zone_num)
        except Exception as err:
            _LOGGER.error("Failed to uninhibit zone %d: %s", zone_num, err)
            raise

    async def async_activate_output(self, output_num: int) -> None:
        """Activate an output."""
        if not self._client:
            raise UpdateFailed("Not connected to panel")

        try:
            await self._client.activate_output(output_num)
        except Exception as err:
            _LOGGER.error("Failed to activate output %d: %s", output_num, err)
            raise

    async def async_deactivate_output(self, output_num: int) -> None:
        """Deactivate an output."""
        if not self._client:
            raise UpdateFailed("Not connected to panel")

        try:
            await self._client.deactivate_output(output_num)
        except Exception as err:
            _LOGGER.error("Failed to deactivate output %d: %s", output_num, err)
            raise

    async def async_activate_trigger(self, trigger_num: int) -> None:
        """Activate a trigger."""
        if not self._client:
            raise UpdateFailed("Not connected to panel")

        try:
            await self._client.activate_trigger(trigger_num)
        except Exception as err:
            _LOGGER.error("Failed to activate trigger %d: %s", trigger_num, err)
            raise

    async def async_deactivate_trigger(self, trigger_num: int) -> None:
        """Deactivate a trigger."""
        if not self._client:
            raise UpdateFailed("Not connected to panel")

        try:
            await self._client.deactivate_trigger(trigger_num)
        except Exception as err:
            _LOGGER.error("Failed to deactivate trigger %d: %s", trigger_num, err)
            raise

    # =========================================================================
    # DATA ACCESS
    # =========================================================================

    def get_area_state(self, area_num: int) -> dict[str, Any] | None:
        """Get current state dict of an area (contains 'state' key with AreaState dataclass)."""
        return self._data.area_states.get(area_num)

    def get_area_state_obj(self, area_num: int) -> AreaState | None:
        """Get the AreaState dataclass for an area."""
        state_data = self._data.area_states.get(area_num)
        if state_data:
            return state_data.get("state")
        return None

    def get_zone_state(self, zone_num: int) -> dict[str, Any] | None:
        """Get current state dict of a zone (contains 'state' key with ZoneState dataclass)."""
        return self._data.zone_states.get(zone_num)

    def get_zone_state_obj(self, zone_num: int) -> ZoneState | None:
        """Get the ZoneState dataclass for a zone."""
        state_data = self._data.zone_states.get(zone_num)
        if state_data:
            return state_data.get("state")
        return None

    def get_output_state(self, output_num: int) -> dict[str, Any] | None:
        """Get current state dict of an output (contains 'state' key with OutputState dataclass)."""
        return self._data.output_states.get(output_num)

    def get_output_state_obj(self, output_num: int) -> OutputState | None:
        """Get the OutputState dataclass for an output."""
        state_data = self._data.output_states.get(output_num)
        if state_data:
            return state_data.get("state")
        return None

    def get_trigger_state(self, trigger_num: int) -> dict[str, Any] | None:
        """Get current state dict of a trigger (contains 'state' key with TriggerState dataclass)."""
        return self._data.trigger_states.get(trigger_num)

    def get_trigger_state_obj(self, trigger_num: int) -> TriggerState | None:
        """Get the TriggerState dataclass for a trigger."""
        state_data = self._data.trigger_states.get(trigger_num)
        if state_data:
            return state_data.get("state")
        return None

    def get_areas(self) -> list[dict[str, Any]]:
        """Get list of all areas."""
        return self._data.areas

    def get_zones(self) -> list[dict[str, Any]]:
        """Get list of all zones."""
        return self._data.zones

    def get_outputs(self) -> list[dict[str, Any]]:
        """Get list of all outputs."""
        return self._data.outputs

    def get_triggers(self) -> list[dict[str, Any]]:
        """Get list of all triggers."""
        return self._data.triggers

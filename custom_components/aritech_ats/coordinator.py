"""DataUpdateCoordinator for Aritech integration."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_USERNAME, CONF_PASSWORD
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from aritech_client import AritechClient, AritechMonitor, ChangeEvent, InitializedEvent
from aritech_client import AreaState, ZoneState, OutputState, TriggerState, DoorState, FilterState

from .const import (
    DOMAIN,
    CONF_ENCRYPTION_KEY,
    CONF_PIN_CODE,
    CONF_PANEL_TYPE,
    PANEL_TYPE_X700,
    CONNECT_TIMEOUT,
    INITIALIZE_TIMEOUT,
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
    doors: list[dict[str, Any]] = field(default_factory=list)
    filters: list[dict[str, Any]] = field(default_factory=list)

    # Current states keyed by entity number
    area_states: dict[int, dict[str, Any]] = field(default_factory=dict)
    zone_states: dict[int, dict[str, Any]] = field(default_factory=dict)
    output_states: dict[int, dict[str, Any]] = field(default_factory=dict)
    trigger_states: dict[int, dict[str, Any]] = field(default_factory=dict)
    door_states: dict[int, dict[str, Any]] = field(default_factory=dict)
    filter_states: dict[int, dict[str, Any]] = field(default_factory=dict)


class AritechCoordinator(DataUpdateCoordinator[AritechData]):
    """Coordinator to manage Aritech panel connection and updates."""

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
        self._shutting_down = False
        self._reconnect_task: asyncio.Task | None = None

        # Reconnection backoff settings
        self._reconnect_attempt: int = 0
        self._reconnect_delays: list[int] = [5, 10, 20, 40, 60, 120]
        self._max_reconnect_attempts: int = 20

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

        client_config = {
            "host": config[CONF_HOST],
            "port": config[CONF_PORT],
            "encryption_key": config[CONF_ENCRYPTION_KEY],
        }

        panel_type = config.get(CONF_PANEL_TYPE)
        if panel_type == PANEL_TYPE_X700:
            client_config["username"] = config[CONF_USERNAME]
            client_config["password"] = config[CONF_PASSWORD]
        else:
            client_config["pin"] = config.get(CONF_PIN_CODE, "")

        self._client = AritechClient(client_config)

        try:
            _LOGGER.debug("Connecting to Aritech panel at %s:%s", config[CONF_HOST], config[CONF_PORT])

            await asyncio.wait_for(self._client.connect(), timeout=CONNECT_TIMEOUT)
            await asyncio.wait_for(self._client.initialize(), timeout=INITIALIZE_TIMEOUT)

            self._data.panel_model = self._client.panel_model
            self._data.panel_name = self._client.panel_name
            self._data.firmware_version = self._client.firmware_version

            _LOGGER.info(
                "Connected to %s (%s) firmware %s",
                self._data.panel_name,
                self._data.panel_model,
                self._data.firmware_version,
            )

            self._monitor = AritechMonitor(self._client)
            self._setup_monitor_callbacks()
            await self._monitor.start()

            self._connected = True
            self._reconnect_attempt = 0
            _LOGGER.info("Aritech monitoring started")

        except asyncio.TimeoutError as err:
            self._connected = False
            _LOGGER.error("Timeout connecting to Aritech panel at %s:%s", config[CONF_HOST], config[CONF_PORT])
            await self.async_disconnect()
            raise UpdateFailed("Connection timed out") from err
        except Exception as err:
            self._connected = False
            _LOGGER.error("Failed to connect to Aritech panel: %s", err)
            await self.async_disconnect()
            raise UpdateFailed(f"Failed to connect: {err}") from err

    async def async_disconnect(self, _from_reconnect: bool = False) -> None:
        """Disconnect from the alarm panel.

        Args:
            _from_reconnect: True when called from within the reconnect task,
                to avoid the task trying to cancel and await itself.
        """
        self._shutting_down = True

        # Cancel any pending reconnect task (but not if we're inside it)
        if not _from_reconnect and self._reconnect_task and not self._reconnect_task.done():
            self._reconnect_task.cancel()
            try:
                await self._reconnect_task
            except asyncio.CancelledError:
                pass
        self._reconnect_task = None

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
            """Handle initialization event — dispatch to event loop for thread safety."""
            self.hass.loop.call_soon_threadsafe(self._handle_initialized, event)

        # State change callbacks — use call_soon_threadsafe because the
        # aritech_client library may invoke these from a background thread.
        @self._monitor.on_zone_changed
        def handle_zone_changed(event: ChangeEvent) -> None:
            self.hass.loop.call_soon_threadsafe(
                self._handle_state_change, "Zone", event, self._data.zone_states
            )

        @self._monitor.on_area_changed
        def handle_area_changed(event: ChangeEvent) -> None:
            self.hass.loop.call_soon_threadsafe(
                self._handle_state_change, "Area", event, self._data.area_states
            )

        @self._monitor.on_output_changed
        def handle_output_changed(event: ChangeEvent) -> None:
            self.hass.loop.call_soon_threadsafe(
                self._handle_state_change, "Output", event, self._data.output_states
            )

        @self._monitor.on_trigger_changed
        def handle_trigger_changed(event: ChangeEvent) -> None:
            self.hass.loop.call_soon_threadsafe(
                self._handle_state_change, "Trigger", event, self._data.trigger_states
            )

        @self._monitor.on_door_changed
        def handle_door_changed(event: ChangeEvent) -> None:
            self.hass.loop.call_soon_threadsafe(
                self._handle_state_change, "Door", event, self._data.door_states
            )

        @self._monitor.on_filter_changed
        def handle_filter_changed(event: ChangeEvent) -> None:
            self.hass.loop.call_soon_threadsafe(
                self._handle_state_change, "Filter", event, self._data.filter_states
            )

        @self._monitor.on_error
        def handle_error(error: Exception) -> None:
            _LOGGER.error("Aritech monitor error: %s", error)
            self.hass.loop.call_soon_threadsafe(self._handle_connection_lost)

        if self._client:
            @self._client.on_connection_lost
            def handle_connection_lost() -> None:
                _LOGGER.warning("Aritech client connection lost detected")
                self.hass.loop.call_soon_threadsafe(self._handle_connection_lost)

    @callback
    def _handle_initialized(self, event: InitializedEvent) -> None:
        """Handle initialization event with all entity data."""
        _LOGGER.debug(
            "Initialized: %d zones, %d areas, %d outputs, %d triggers, %d doors, %d filters",
            len(event.zones), len(event.areas), len(event.outputs),
            len(event.triggers), len(event.doors), len(event.filters),
        )

        self._data.zones = [{"number": z.number, "name": z.name} for z in event.zones]
        self._data.areas = [{"number": a.number, "name": a.name} for a in event.areas]
        self._data.outputs = [{"number": o.number, "name": o.name} for o in event.outputs]
        self._data.triggers = [{"number": t.number, "name": t.name} for t in event.triggers]
        self._data.doors = [{"number": d.number, "name": d.name} for d in event.doors]
        self._data.filters = [{"number": f.number, "name": f.name} for f in event.filters]

        self._data.zone_states = event.zone_states
        self._data.area_states = event.area_states
        self._data.output_states = event.output_states
        self._data.trigger_states = event.trigger_states
        self._data.door_states = event.door_states
        self._data.filter_states = event.filter_states

        self.async_set_updated_data(self._data)

    @callback
    def _handle_connection_lost(self) -> None:
        """Handle connection loss — mark disconnected and schedule reconnect."""
        if self._shutting_down:
            return
        self._connected = False
        self.async_set_updated_data(self._data)
        self._schedule_reconnect()

    @callback
    def _handle_state_change(
        self,
        entity_type: str,
        event: ChangeEvent,
        state_dict: dict[int, dict[str, Any]],
    ) -> None:
        """Handle a state change event — update data and notify listeners once."""
        _LOGGER.debug(
            "%s %d (%s) changed: %s -> %s",
            entity_type, event.id, event.name,
            event.old_data.get("state") if event.old_data else "NEW",
            event.new_data.get("state"),
        )
        state_dict[event.id] = event.new_data
        self.async_set_updated_data(self._data)

    def _get_reconnect_delay(self) -> int:
        """Get the delay for the current reconnection attempt using exponential backoff."""
        if self._reconnect_attempt >= len(self._reconnect_delays):
            return self._reconnect_delays[-1]
        return self._reconnect_delays[self._reconnect_attempt]

    @callback
    def _schedule_reconnect(self) -> None:
        """Schedule a reconnection attempt with exponential backoff."""
        if self._shutting_down:
            return
        if self._reconnect_task and not self._reconnect_task.done():
            return

        delay = self._get_reconnect_delay()
        self._reconnect_attempt += 1

        async def reconnect() -> None:
            _LOGGER.info(
                "Attempting to reconnect to Aritech panel in %d seconds (attempt %d)...",
                delay, self._reconnect_attempt,
            )
            await asyncio.sleep(delay)

            try:
                await self.async_disconnect(_from_reconnect=True)
                await self.async_connect()
                _LOGGER.info(
                    "Reconnected to Aritech panel successfully after %d attempts",
                    self._reconnect_attempt,
                )
            except Exception as err:
                _LOGGER.error("Reconnection failed (attempt %d): %s", self._reconnect_attempt, err)
                if self._reconnect_attempt >= self._max_reconnect_attempts:
                    _LOGGER.warning(
                        "Max reconnection attempts (%d) reached. Will continue retrying with max delay (%ds).",
                        self._max_reconnect_attempts, self._reconnect_delays[-1],
                    )
                self._schedule_reconnect()

        self._reconnect_task = self.hass.async_create_task(reconnect())

    async def _async_update_data(self) -> AritechData:
        """Fetch data from the panel (fallback, not normally used)."""
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
        await self._client.arm_area(area_num, set_type=mode, force=force)

    async def async_disarm_area(self, area_num: int) -> None:
        """Disarm an area."""
        if not self._client:
            raise UpdateFailed("Not connected to panel")
        await self._client.disarm_area(area_num)

    async def async_inhibit_zone(self, zone_num: int) -> None:
        """Inhibit a zone."""
        if not self._client:
            raise UpdateFailed("Not connected to panel")
        await self._client.inhibit_zone(zone_num)

    async def async_uninhibit_zone(self, zone_num: int) -> None:
        """Uninhibit a zone."""
        if not self._client:
            raise UpdateFailed("Not connected to panel")
        await self._client.uninhibit_zone(zone_num)

    async def async_activate_output(self, output_num: int) -> None:
        """Activate an output."""
        if not self._client:
            raise UpdateFailed("Not connected to panel")
        await self._client.activate_output(output_num)

    async def async_deactivate_output(self, output_num: int) -> None:
        """Deactivate an output."""
        if not self._client:
            raise UpdateFailed("Not connected to panel")
        await self._client.deactivate_output(output_num)

    async def async_activate_trigger(self, trigger_num: int) -> None:
        """Activate a trigger."""
        if not self._client:
            raise UpdateFailed("Not connected to panel")
        await self._client.activate_trigger(trigger_num)

    async def async_deactivate_trigger(self, trigger_num: int) -> None:
        """Deactivate a trigger."""
        if not self._client:
            raise UpdateFailed("Not connected to panel")
        await self._client.deactivate_trigger(trigger_num)

    async def async_lock_door(self, door_num: int) -> None:
        """Lock a door."""
        if not self._client:
            raise UpdateFailed("Not connected to panel")
        await self._client.lock_door(door_num)

    async def async_unlock_door(self, door_num: int) -> None:
        """Unlock a door."""
        if not self._client:
            raise UpdateFailed("Not connected to panel")
        await self._client.unlock_door(door_num)

    async def async_unlock_door_standard_time(self, door_num: int) -> None:
        """Unlock a door for the standard configured time."""
        if not self._client:
            raise UpdateFailed("Not connected to panel")
        await self._client.unlock_door_standard_time(door_num)

    async def async_enable_door(self, door_num: int) -> None:
        """Enable a door."""
        if not self._client:
            raise UpdateFailed("Not connected to panel")
        await self._client.enable_door(door_num)

    async def async_disable_door(self, door_num: int) -> None:
        """Disable a door."""
        if not self._client:
            raise UpdateFailed("Not connected to panel")
        await self._client.disable_door(door_num)

    # =========================================================================
    # DATA ACCESS
    # =========================================================================

    def get_area_state_obj(self, area_num: int) -> AreaState | None:
        """Get the AreaState dataclass for an area."""
        state_data = self._data.area_states.get(area_num)
        if state_data:
            return state_data.get("state")
        return None

    def get_zone_state_obj(self, zone_num: int) -> ZoneState | None:
        """Get the ZoneState dataclass for a zone."""
        state_data = self._data.zone_states.get(zone_num)
        if state_data:
            return state_data.get("state")
        return None

    def get_output_state_obj(self, output_num: int) -> OutputState | None:
        """Get the OutputState dataclass for an output."""
        state_data = self._data.output_states.get(output_num)
        if state_data:
            return state_data.get("state")
        return None

    def get_trigger_state_obj(self, trigger_num: int) -> TriggerState | None:
        """Get the TriggerState dataclass for a trigger."""
        state_data = self._data.trigger_states.get(trigger_num)
        if state_data:
            return state_data.get("state")
        return None

    def get_door_state_obj(self, door_num: int) -> DoorState | None:
        """Get the DoorState dataclass for a door."""
        state_data = self._data.door_states.get(door_num)
        if state_data:
            return state_data.get("state")
        return None

    def get_filter_state_obj(self, filter_num: int) -> FilterState | None:
        """Get the FilterState dataclass for a filter."""
        state_data = self._data.filter_states.get(filter_num)
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

    def get_doors(self) -> list[dict[str, Any]]:
        """Get list of all doors."""
        return self._data.doors

    def get_filters(self) -> list[dict[str, Any]]:
        """Get list of all filters."""
        return self._data.filters

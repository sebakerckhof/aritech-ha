# Aritech Integration for Home Assistant

A custom Home Assistant integration for Aritech alarm panels, providing real-time monitoring and control of your security system.

## Supported Panels

| Panel Series | Status | Notes |
|--------------|--------|-------|
| ATS x500 | Supported | Tested with x500 firmware 4.1, 4.8 and 4.11 |
| ATS x700 (everon) |Supported | Tested with x700 firmware 4.1 |
| ATS x000 | Not Supported | Uses a different protocol |

The Classic 1000 series panels use a legacy protocol that is fundamentally different from the x500/x700 series, and there are no plans to support them. But we're open to PR's if you want to add support.

## Features

### Alarm Control Panel
- Arm/disarm areas (Full, Part 1, Part 2 modes)
- Real-time alarm state monitoring (Disarmed, Armed Away, Armed Home, Armed Night, Arming, Pending, Triggered)
- Force arm option for each area

### Binary Sensors

**Zone sensors** (per zone device):
- Active - motion/door/window detection with auto-detected device class
- Tamper - zone tamper detection
- Fault - zone fault/trouble detection
- Alarming - zone is currently in alarm
- Isolated - zone is isolated/bypassed

**Area sensors** (per area device):
- Alarm - area is in alarm state
- Tamper - area tamper detected
- Fire - fire alarm active
- Panic - panic alarm active

**Door sensors** (per door device):
- Lock - door lock state (ON = unlocked)
- Open - door open/closed state
- Forced - door was forced open
- Open Too Long - door has been open too long
- Tamper - door reader tamper detection

**Output sensors** (per output device, read-only):
- Active - output is currently active (attributes include is_on, is_active, is_forced)
- Forced - output is being force controlled

**Filter sensors** (per filter device, read-only):
- Active - filter condition is active

### Sensors
- Panel model and firmware version
- Connection status
- Area state text
- Zone state text

### Switches

**Zone controls** (per zone device):
- Inhibit - inhibit/uninhibit zone (ON = inhibited)

**Area controls** (per area device):
- Force Arm - enable force arming for this area

**Trigger controls** (per panel device):
- One switch per trigger for manual activation

**Door controls** (per door device):
- Unlocked - lock/unlock door (ON = unlocked)
- Enabled - enable/disable door (ON = enabled)

### Buttons

**Door controls** (per door device):
- Unlock (Standard Time) - momentary unlock for panel-configured duration

### Diagnostics

The integration provides a diagnostics download from the Home Assistant UI for troubleshooting. Sensitive data (host, encryption key, credentials) is automatically redacted.

## Architecture

The integration uses a **push-based** architecture (`local_push`) — the panel pushes state changes via a persistent TCP connection. There is no polling.

```
aritech_client (PyPI library)
    └── coordinator.py          — DataUpdateCoordinator, TCP connection, push callbacks
        ├── alarm_control_panel.py  — Arm/disarm per area
        ├── binary_sensor.py        — Zone/area/door/output/filter states
        ├── sensor.py               — Panel info + state text sensors
        ├── switch.py               — Zone inhibit, triggers, force arm, door lock
        └── button.py               — Door unlock (standard time)
```

### Key design decisions

- **CoordinatorEntity** base class for all entities — automatic listener cleanup, no manual callback registration
- **AritechBinarySensor** base class eliminates boilerplate across 17+ binary sensor types
- **helpers.py** centralizes shared DeviceInfo functions
- **No polling**: `update_interval=None`, the panel pushes state changes via TCP
- **Thread safety**: aritech_client callbacks can arrive from background threads — all callbacks use `call_soon_threadsafe` to safely schedule on the event loop
- **Unified state handler**: A single `_handle_state_change` method processes all entity type updates
- **Reconnect with exponential backoff**: 5s → 120s delay, with proper task cancellation on unload

## Requirements

- Home Assistant 2024.1 or newer
- Aritech panel with network connectivity (IP module)
- Panel encryption key and PIN code (x500) or username/password (x700)

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Click the three dots menu and select "Custom repositories"
3. Add the repository URL and select "Integration" as the category
4. Search for "Aritech" and install
5. Restart Home Assistant

### Manual Installation

1. Copy the `aritech_ats` folder to your `custom_components` directory
2. Restart Home Assistant

## Configuration

1. Go to **Settings** > **Devices & Services**
2. Click **+ Add Integration**
3. Search for "Aritech"
4. Enter your panel's connection details (host, port, encryption key)
5. The integration will auto-detect your panel type:
   - **x500 panels**: Enter your PIN code
   - **x700 panels**: Enter your username and password

## Entities

After setup, the integration creates:

| Entity Type | Description |
|-------------|-------------|
| `alarm_control_panel` | One per area - arm/disarm control |
| `binary_sensor` | Zone states, area alerts, door states, output states (read-only), filter states |
| `sensor` | Panel info, connection status, state text sensors |
| `switch` | Zone inhibit, triggers, force arm, door lock/unlock, door enable |
| `button` | Door unlock (standard time) |

## Arming Modes

| Home Assistant | Aritech mode |
|----------------|-----------|
| Arm Away | Full Set |
| Arm Home | Part Set 1 |
| Arm Night | Part Set 2 |

## Force Arm

Enable the "Force Arm" switch for an area to arm even when zones are not ready. The setting persists across Home Assistant restarts. Use with caution.

## Disk Wear Considerations

Since this is a push-based integration, busy panels (many PIR zones) can generate frequent state updates. Each update notifies all entities, and Home Assistant's recorder writes changed states to SQLite.

To reduce disk writes on SD card / USB installations, consider adding recorder excludes for high-frequency entities:

```yaml
recorder:
  exclude:
    entity_globs:
      - binary_sensor.*_zone_*_active   # PIR motion sensors
      - sensor.*_zone_*_state           # Zone state text
```

## Troubleshooting

### Cannot connect
- Verify the panel IP address and port
- Ensure the IP module is enabled and configured
- Check firewall settings

### Invalid authentication
- Verify the encryption key (must be exactly 24 digits)
- Verify the PIN code
- Ensure the user has appropriate permissions

### Entities unavailable
- Check the Connection Status sensor
- Review Home Assistant logs for error messages
- Download diagnostics via **Settings** > **Devices & Services** > **Aritech** > **...** > **Download diagnostics**

## Support

For issues and feature requests, please open an issue on GitHub.

## License

This project is licensed under the MIT License.

## Disclaimer

This integration is provided "as is" without warranty of any kind. Use at your own risk. The authors are not responsible for any damage or security issues that may arise from using this integration.

**This is an unofficial integration and is not affiliated with, endorsed by, or connected to Aritech, Kidde Global Services, or any of their subsidiaries.**

## Trademarks

- **Aritech** is a trademark of Kidde Global Services.
- **ATS** is a trademark of Kidde Global Services.
- **KGS** is a trademark of Kidde Global Services.
- **Home Assistant** is a trademark of the Home Assistant project.

All other trademarks are the property of their respective owners. The use of these trademarks in this project does not imply any affiliation with or endorsement by the trademark holders.

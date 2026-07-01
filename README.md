# Aritech Integration for Home Assistant

A custom Home Assistant integration for Aritech alarm panels, providing real-time monitoring and control of your security system.

## Supported Panels

| Panel Series | Status | Notes |
|--------------|--------|-------|
| ATS x500 | Supported | Tested with x500 firmware 4.1, 4.8 and 4.11 |
| ATS x700 (everon) |Supported | Tested with x700 firmware 4.1 |
| ATS x000 | Beta | Only the ATSX000IP panels, not the older ones, requires a separate login. DUE TO LIMITATIONS IN THE X000 API, NOT ALL ZONES CAN BE READ |

The X000 panels only allow 1 active connection per user. Therefore you'll have to create a separate user for the integration if you still want to be able to use the advisor advanced app.

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

**Door sensors** (per door device, not on X000 panels):
- Lock - door lock state (ON = locked)
- Open - door open/closed state
- Forced - door was forced open
- Open Too Long - door has been open too long
- Tamper - door reader tamper detection

**Output sensors** (per output device, read-only, not on X000 panels):
- Active - output is currently active (attributes include is_on, is_active, is_forced)
- Forced - output is being force controlled

**Filter sensors** (per filter device, read-only, not on X000 panels):
- Active - filter condition is active

### Sensors
- Panel model and firmware version
- Connection status
- Area state text
- Zone state text
- Trigger state text

### Switches

**Zone controls** (per zone device):
- Inhibit - inhibit/uninhibit zone (ON = inhibited)

**Area controls** (per area device):
- Force Arm - enable force arming for this area

**Trigger controls** (per panel device):
- One switch per trigger for manual activation

**Door controls** (per door device, not on X000 panels):
- Unlocked - lock/unlock door (ON = unlocked)
- Enabled - enable/disable door (ON = enabled)

### Buttons

**Door controls** (per door device, not on X000 panels):
- Unlock (Standard Time) - momentary unlock for panel-configured duration

## Requirements

- Home Assistant 2024.1 or newer
- Aritech panel with network connectivity (IP module)
- Panel encryption key and PIN code (x000 / x500) or username/password (x700)

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

Enable the "Force Arm" switch for an area to arm even when zones are not ready. Use with caution.

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

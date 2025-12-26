# Aritech ATS Integration for Home Assistant

A custom Home Assistant integration for Aritech ATS alarm panels, providing real-time monitoring and control of your security system.

## Supported Panels

| Panel Series | Status | Notes |
|--------------|--------|-------|
| ATS x500 | Supported | |
| ATS x700 | In Development | Coming soon |
| ATS x000 | Not Supported | Uses a different protocol |

The Classic 1000 series panels use a legacy protocol that is fundamentally different from the x500/x700 series, and there are no plans to support them. But we're open to PR's if you want to add support.

## Features

### Alarm Control Panel
- Arm/disarm areas (Full, Part 1, Part 2 modes)
- Real-time alarm state monitoring (Disarmed, Armed Away, Armed Home, Armed Night, Arming, Pending, Triggered)
- Force arm option for each area

### Binary Sensors
**Zone sensors:**
- Active state (motion/door/window detection with auto-detected device class)
- Tamper detection
- Fault detection
- Alarm state
- Isolated state

**Area sensors:**
- Alarm status
- Tamper status
- Fire alarm
- Panic alarm

### Sensors
- Panel model and firmware version
- Connection status
- Area state (textual)
- Zone state (textual)

### Switches
- Zone inhibit control
- Output control
- Trigger activation
- Force arm toggle per area

## Requirements

- Home Assistant 2024.1 or newer
- Aritech ATS panel with network connectivity (IP module)
- `aritech-client` Python library (v0.2.1+)
- Panel encryption key and PIN code

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Click the three dots menu and select "Custom repositories"
3. Add the repository URL and select "Integration" as the category
4. Search for "Aritech ATS" and install
5. Restart Home Assistant

### Manual Installation

1. Copy the `aritech_ats` folder to your `custom_components` directory
2. Restart Home Assistant

## Configuration

1. Go to **Settings** > **Devices & Services**
2. Click **+ Add Integration**
3. Search for "Aritech ATS"
4. Enter the following:
   - **Host**: IP address of your ATS panel
   - **Port**: Communication port (default: 32000)
   - **Encryption Key**: 24-digit encryption key configured on the panel
   - **PIN Code**: User PIN for authentication

## Entities

After setup, the integration creates:

| Entity Type | Description |
|-------------|-------------|
| `alarm_control_panel` | One per area - arm/disarm control |
| `binary_sensor` | Zone states (active, tamper, fault, alarm, isolated) and area alerts |
| `sensor` | Panel info, connection status, area/zone state text |
| `switch` | Zone inhibit, outputs, triggers, force arm |

## Arming Modes

| Home Assistant | ATS Panel |
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

**This is an unofficial integration and is not affiliated with, endorsed by, or connected to Aritech, Carrier Global Corporation, or any of their subsidiaries.**

## Trademarks

- **Aritech** is a trademark of Carrier Global Corporation.
- **ATS** is a trademark of Carrier Global Corporation.
- **Carrier** is a trademark of Carrier Global Corporation.
- **Home Assistant** is a trademark of the Home Assistant project.

All other trademarks are the property of their respective owners. The use of these trademarks in this project does not imply any affiliation with or endorsement by the trademark holders.

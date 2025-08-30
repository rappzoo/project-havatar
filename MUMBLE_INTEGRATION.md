# Mumble Integration for Avatar Tank

This document describes the Mumble integration for the Avatar Tank system, providing two-way audio streaming capabilities over ZeroTier networks.

## Architecture

The integration uses:
- **Mumble Server (Murmur)**: Running on the Raspberry Pi 5
- **Mumble Client**: Headless client controlled via D-Bus
- **Web Interface**: Custom controls in the existing Flask web UI
- **Network**: ZeroTier for secure connectivity over 4G

## Features

1. **Two-Way Audio Streaming**: Full duplex audio communication
2. **Headless Operation**: No GUI required for the client
3. **Web Control Interface**: Connect, disconnect, and mute controls via web UI
4. **D-Bus Control**: System-level control of the Mumble client
5. **Battery Optimized**: Designed for Raspberry Pi 5 with 4G router

## Installation

1. Run the setup script:
   ```bash
   ./setup_mumble.sh
   ```

2. Reboot the system to apply all changes

3. Start the Mumble server:
   ```bash
   sudo systemctl start mumble-server
   ```

## Configuration

The Mumble server is configured with:
- Port: 64738 (default)
- No server password (for easy testing)
- Support for up to 100 users
- Opus codec enabled for best quality
- Bonjour/ZeroConf enabled for discovery

## Web Interface Controls

The web interface includes new controls for Mumble:
- Server IP and port input
- Username field
- Connect/Disconnect buttons
- Mute toggle
- Status indicator

## API Endpoints

The following new endpoints are available:

- `POST /mumble/connect` - Connect to a Mumble server
- `POST /mumble/disconnect` - Disconnect from the Mumble server
- `POST /mumble/toggle_mute` - Toggle mute status
- `GET /mumble/status` - Get current connection status

## Usage

1. Start the Mumble server on the Pi:
   ```bash
   sudo systemctl start mumble-server
   ```

2. Access the web interface and enter:
   - Server IP: localhost (or Pi's IP on ZeroTier)
   - Port: 64738
   - Username: AvatarTank (or custom)

3. Click "Connect" to establish the Mumble connection

4. Use the mute button to control audio transmission

## Troubleshooting

1. **Connection Issues**:
   - Verify the Mumble server is running
   - Check firewall settings (port 64738 UDP/TCP)
   - Ensure ZeroTier is properly configured

2. **Audio Problems**:
   - Check ALSA device configuration
   - Verify PulseAudio is running
   - Test with standard Mumble client

3. **Mute Control Not Working**:
   - Ensure xdotool is installed
   - Check that the Mumble client window can be found

## Security Considerations

- The default configuration has no server password
- In production, set a strong server password
- Use ZeroTier's access controls for network security
- Regularly update Mumble to the latest version

## Performance Optimization

- The system is optimized for low bandwidth (72 kbps default)
- Opus codec provides excellent quality at low bitrates
- ZeroTier provides encrypted, low-latency connections
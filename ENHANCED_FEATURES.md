# Avatar Tank Enhanced - New Features Documentation

## Overview
This enhanced version of the Avatar Tank system includes several major improvements for better performance, reliability, and user experience.

## New Features

### 1. Bandwidth Usage Counter
- **Location**: Video info bar (shows total data usage since startup)
- **Features**:
  - Real-time bandwidth monitoring in KB/s
  - Total cumulative usage display (KB/MB/GB)
  - Color coding for data conservation (optimized for 4G usage)
  - Automatic tracking from system uptime

### 2. Camera Crash/Reconnection Fix
- **Improvements**:
  - Robust camera initialization with retry logic
  - Graceful resolution changes without crashes
  - Better error handling and recovery
  - Fallback to dummy camera when hardware fails
  - Consecutive failure detection and automatic restart

### 3. Romanian Diacritics Support
- **Location**: TTS input area (appears when Romanian language is selected)
- **Characters**: ă, â, î, ș, ț
- **Features**:
  - One-click insertion at cursor position
  - Automatic visibility based on language selection
  - Enhanced Romanian dictionary with proper diacritics
  - Improved prediction system with Unicode normalization

### 4. Ultra-Low Latency Microphone Streaming
Three streaming modes available:

#### Standard Mode (🎤 Standard)
- Traditional AAC streaming
- Good quality, moderate latency
- Compatible with all browsers

#### Optimized Mode (📡 Optimized)
- Opus codec at 16kbps
- VoIP optimized for speech
- ~50% bandwidth reduction
- Sub-1-second latency

#### Realtime Mode (⚡ Realtime)
- WebSocket-based streaming
- μ-law compression (8-bit)
- Ultra-minimal buffering
- Sub-500ms latency target
- Automatic fallback if WebSocket fails

### 5. Mumble Integration for Two-Way Audio
- **Architecture**: Headless Mumble + Web Control Interface
- **Control**: Simple D-Bus Control (Recommended)
- **Network**: Optimized for ZeroTier + 4G Router
- **Features**:
  - Full-duplex two-way audio communication
  - Web-based connection management
  - Mute/unmute controls
  - Status monitoring
  - Replaces previous WebRTC/WebSocket implementations as primary solution

## Technical Details

### Bandwidth Tracking
```python
# Tracks every frame size
frame_size_kb = len(frame_bytes) / 1024.0
total_bandwidth_usage += frame_size_kb
```

### Camera Recovery
```python
# Consecutive failure detection
consecutive_failures += 1
if consecutive_failures >= max_failures:
    reinitialize_camera()
```

### Audio Streaming Options
```bash
# Optimized mode uses Opus
ffmpeg -f alsa -i $MIC_PLUG -c:a libopus -b:a 16k -application voip

# Realtime mode uses μ-law
ffmpeg -f alsa -i $MIC_PLUG -c:a pcm_mulaw -f mulaw
```

### Mumble Integration
```python
# Mumble controller class
class MumbleController:
    def connect(self, server_ip, username=None, port=64738):
        # Connect to Mumble server in headless mode
        pass
    
    def toggle_mute(self):
        # Toggle mute status using system commands
        pass
```

## Usage Instructions

### Starting the System
```bash
cd havatar
python3 avatar_tank_enhanced.py
```

### Using Diacritics
1. Select Romanian language (RO button)
2. Diacritics pills appear automatically
3. Click any diacritic to insert at cursor position
4. Continue typing normally

### Microphone Streaming
1. **Standard**: Click "🎤 Standard" for regular streaming
2. **Optimized**: Click "📡 Optimized" for low-bandwidth mode
3. **Realtime**: Click "⚡ Realtime" for ultra-low latency

### Mumble Integration
1. **Setup**: Run `./setup_mumble.sh` and reboot
2. **Connect**: Enter server IP, port, and username in web UI
3. **Control**: Use Connect/Disconnect and Mute buttons
4. **Monitor**: Check status indicator for connection state

## Color Coding

### Bandwidth (Optimized for 4G)
- 🟢 Green (<400 KB/s): Efficient data usage
- 🟠 Orange (400-800 KB/s): Moderate usage
- 🔴 Red (>800 KB/s): High usage, may affect stability/cost

### Battery
- 🟢 Green (>50%): Good charge
- 🟠 Orange (20-50%): Medium charge
- 🔴 Red (<20%): Low charge

## Troubleshooting

### Camera Issues
- System automatically detects and retries failed cameras
- Check "Camera:" status below video feed
- Resolution changes now more reliable with fallback

### Audio Issues
- Try different streaming modes if one fails
- Check ALSA device permissions
- WebSocket mode requires modern browser

### Mumble Issues
- Verify Mumble server is running (`sudo systemctl status mumble-server`)
- Check network connectivity to the server
- Ensure xdotool is installed for mute control
- Test with standard Mumble client to isolate issues

### Dependencies
Run the installation script:
```bash
chmod +x install_dependencies.sh
./install_dependencies.sh
```

Additional Mumble setup:
```bash
chmod +x setup_mumble.sh
./setup_mumble.sh
```

## Configuration Files

### Audio Devices
- Automatically detected and prioritized (USB devices preferred)
- Manual override via environment variables:
  ```bash
  export AV_MIC='plughw:1,0'
  export AV_SPK='plughw:1,0'
  ```

### Language Dictionaries
- `dicts/ro.txt`: Romanian words with diacritics
- `dicts/en.txt`: English words
- `dicts/words.txt`: Combined vocabulary

### Mumble Configuration
- Server config: `mumble-server.ini`
- Service file: `mumble-server.service`
- Client runs headless via web interface

## API Endpoints

### New Endpoints
- `/bandwidth_stats`: Get usage statistics
- `/stream_mic_optimized`: Opus-based low-bandwidth stream
- `/stream_mic_pcm_minimal`: μ-law minimal latency stream
- `/mumble/connect`: Connect to Mumble server
- `/mumble/disconnect`: Disconnect from Mumble server
- `/mumble/toggle_mute`: Toggle mute status
- `/mumble/status`: Get Mumble connection status

### WebSocket Events
- `start_audio_stream`: Begin real-time streaming
- `stop_audio_stream`: End real-time streaming  
- `audio_chunk`: Receive audio data

## Performance Notes

### Memory Usage
- Minimal queue sizes for low latency
- Automatic cleanup of old audio chunks
- Efficient frame encoding

### Network Usage
- Optimized mode: ~16 kbps audio + video bandwidth
- Realtime mode: ~8 kbps audio + video bandwidth
- Standard mode: ~96 kbps audio + video bandwidth
- Mumble: ~40 kbps bidirectional audio (configurable)

### Latency Targets
- Standard: 1-3 seconds end-to-end
- Optimized: 0.5-1 second end-to-end  
- Realtime: 0.2-0.5 seconds end-to-end
- Mumble: ~50-100ms codec latency + network latency

### Battery Considerations
- Mumble client optimized for low CPU usage
- Headless operation reduces power consumption
- 4G router power management recommended
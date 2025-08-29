# Havatar - Remote Presence Tank Robot

![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)
![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![Platform](https://img.shields.io/badge/platform-Raspberry%20Pi%205-red.svg)

A remotely controlled, Raspberry Pi 5 + ESP32-powered tracked robot designed for **remote presence** and **accessibility**. Built specifically for hands-free control via eye-gaze tracking and optimized for users with mobility limitations.

## 🎯 Project Goals

**Havatar** provides independent remote presence capabilities for users with **ALS** (Amyotrophic Lateral Sclerosis) and other mobility challenges. The system enables:

- 🏠 **Remote home monitoring** and presence
- 🎮 **Eye-gaze and keyboard control** from anywhere
- 🔊 **Real-time audio/video communication**
- 🔋 **Long-range operation** via 4G/WiFi
- 🛡️ **Safety-first design** with fail-safe controls

## ✨ Key Features

### 🎥 **Live Video Streaming**
- Ultra-wide USB camera with selectable resolution (320p-720p)
- Low-latency MJPEG streaming
- Auto-reconnection and error recovery

### 🕹️ **Intuitive Controls**
- **WASD keyboard** and on-screen "hold-to-move" buttons
- **Variable speed control** (0-100%)
- **Eye-gaze optimized** interface with minimal clicks
- **Safety**: Motors only move while controls are actively held

### 🔊 **Audio Features**
- **Live microphone streaming** ("Listen" button)
- **Text-to-Speech (TTS)** output for remote communication
- **Synchronized audio/video recording**

### 📊 **Real-time Monitoring**
- Battery voltage and current monitoring
- Network bandwidth and uptime tracking
- Device status and error reporting
- Live FPS and resolution display

### 🌐 **Remote Access**
- **ZeroTier VPN** for secure remote access
- **4G modem support** for long-range connectivity
- **Web-based interface** - no app installation required

## 🛠️ Hardware Platform

### **Main Components**
- **Chassis**: 30cm tank-style tracked base
- **Motors**: 2x DC motors (520) with encoder feedback
- **Main Computer**: Raspberry Pi 5 (8GB RAM)
- **Motor Controller**: ESP32-based board (Waveshare)
- **Camera**: USB ultra-wide webcam
- **Audio**: USB microphone (SF-558) + future speaker support
- **Power**: 12V LiPo battery with INA219 monitoring
- **Connectivity**: Ethernet, WiFi, 4G modem

### **Optional Expansions**
- HDMI display for local status/messages
- IMU/compass for navigation feedback
- Servo control for camera tilt
- LIDAR for obstacle detection

## 🏗️ Software Architecture

### **Raspberry Pi 5 Services**

#### **Flask Web Server** (`avatar_tank_enhanced.py`)
- Main web UI and control interface
- RESTful API for all robot functions
- Serial communication with ESP32
- Device auto-detection and configuration

#### **OpenCV Video Streaming**
- Direct V4L2 camera integration
- Multiple resolution support (320p-720p)
- MJPEG format optimization
- Auto-detection of camera capabilities

#### **FFmpeg**
- Synchronized audio+video recording
- Live microphone streaming
- Audio processing and encoding

#### **ZeroTier (External Configuration)**
- Secure P2P networking (configured externally)
- Remote access from anywhere
- Network-level VPN solution

### **ESP32 Firmware**
- DC motor control with encoder feedback
- Battery monitoring via INA219
- Serial communication with Raspberry Pi
- Real-time status reporting
- Expandable for additional sensors

## 🚀 Quick Start

### **Prerequisites**
- Raspberry Pi 5 (4GB+ recommended)
- ESP32 development board
- Python 3.8+ with pip
- USB camera and microphone

### **Installation**

1. **Clone the repository**
   ```bash
   git clone https://github.com/rappzoo/project-havatar.git
   cd project-havatar
   ```

2. **Create and activate virtual environment (recommended)**
   ```bash
   # On Debian/Ubuntu/most Linux distributions
   python3 -m venv venv
   source venv/bin/activate
   
   # On Windows
   python -m venv venv
   venv\Scripts\activate
   ```

3. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Hardware setup**
   - Connect ESP32 via USB/Serial
   - Connect USB camera and microphone
   - Configure battery monitoring (optional)

5. **Run the application**
   ```bash
   python avatar_tank_enhanced.py
   ```

6. **Access the web interface**
   - Local: `http://localhost:5000`
   - Remote: Configure ZeroTier VPN externally for secure access

### **Configuration**

The system auto-detects devices on startup and saves configuration to `avatar_tank_config.json`. Manual configuration options include:

- Camera resolution and FPS settings
- Audio device selection
- Motor controller port assignment
- Network and streaming parameters

## 🎮 Usage

### **Web Interface Controls**

- **Movement**: WASD keys or on-screen directional buttons
- **Speed**: Adjust via slider (0-100%)
- **Camera**: Live feed with resolution selection
- **Audio**: "Listen" button for environment audio
- **Recording**: Snapshot and video recording buttons
- **TTS**: Text input for robot speech output
- **Monitoring**: Real-time battery, network, and system status

### **Safety Features**

- **Dead-man's switch**: Motors stop when controls are released
- **Auto-detection**: Wrong ports and missing devices are handled gracefully
- **Error reporting**: All failures are logged and displayed
- **Connection monitoring**: Automatic reconnection for video/audio streams

## 📁 Project Structure

```
project-havatar/
├── avatar_tank_enhanced.py     # Main Flask application
├── avatar_tank_config.json     # Auto-generated device configuration
├── dicts/                      # TTS language dictionaries
│   ├── common.txt
│   ├── en.txt
│   └── ro.txt
├── docs/                       # Documentation
├── snapshots/                  # Captured images
├── recordings/                 # Video recordings
└── sounds/                     # Audio files
```

## 🔧 Development Status

### **✅ Working Features**
- [x] Tank movement control (hold-to-move)
- [x] Live video streaming (OpenCV/V4L2)
- [x] Real-time audio streaming (WebRTC + WebSocket fallback)
- [x] Battery monitoring
- [x] Snapshot and video recording
- [x] Text-to-Speech output
- [x] Remote access (via external ZeroTier configuration)
- [x] Device auto-detection
- [x] Web UI with responsive design

### **🚧 In Progress**
- [ ] Enhanced audio streaming (WebRTC)
- [ ] Direct SSD boot support
- [ ] IMU/compass integration
- [ ] Mobile-optimized UI
- [ ] Servo camera control

### **📋 Planned Features**
- [ ] LIDAR obstacle detection
- [ ] Voice control integration
- [ ] Multi-user access control
- [ ] Cloud recording storage
- [ ] Mobile companion app

## 🤝 Contributing

Contributions are welcome! This project aims to improve accessibility and independence for users with mobility challenges.

### **Ways to Contribute**
- 🐛 **Bug reports** and feature requests
- 💻 **Code improvements** and optimizations
- 📖 **Documentation** enhancements
- 🧪 **Testing** on different hardware configurations
- 🎨 **UI/UX improvements** for accessibility

### **Development Setup**
1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## 👥 Authors

- **Adrian Balahura** - adrian.balahura@gmail.com (Original idea, original implementation)
- **Marian Simpetru** - marian.simpetru@esolutions.ro (Co-developer)

## 🙏 Acknowledgments

- Built for users with ALS and mobility challenges
- Raspberry Pi Foundation for excellent hardware platform
- Open source community for tools and libraries
- Accessibility advocates for guidance and feedback

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/rappzoo/project-havatar/issues)
- **Discussions**: [GitHub Discussions](https://github.com/rappzoo/project-havatar/discussions)


---

**Made with ❤️ for accessibility and independence**

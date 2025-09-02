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

### **Modular Design (NEW!)**

Proiectul a fost complet refactorizat într-o arhitectură modulară pentru o mai bună mentenabilitate și scalabilitate:

#### **Core Modules**
- **`modules/main_app.py`** - Aplicația principală Flask care coordonează toate modulele
- **`modules/device_detector.py`** - Detectarea automată a camerelor, dispozitivelor audio și controllerelor motor
- **`modules/camera.py`** - Inițializarea camerelor, configurarea și generarea frame-urilor
- **`modules/motor_controller.py`** - Controlul motoarelor și comunicația cu ESP32
- **`modules/tts.py`** - Funcționalitatea Text-to-Speech folosind Piper sau motoare fallback
- **`modules/recorder.py`** - Înregistrarea video și audio
- **`modules/audio_utils.py`** - Utilitare audio pentru controlul volumului și managementul dispozitivelor
- **`modules/predictor.py`** - Sistemul de predicție și sugerare de cuvinte
- **`modules/audio_streamer.py`** - Funcționalitatea de streaming audio prin WebSocket

#### **Launcher Enhanced** (`avatar_tank_enhanced.py`)
- Punct de intrare cu verificări complete ale sistemului
- Testarea modulelor și diagnostice
- Verificarea permisiunilor și grupurilor utilizator
- Setup automat al mediului Python
- Monitoring în timp real al stării sistemului

#### **Raspberry Pi 5 Services**

##### **Flask Web Server Modular**
- Interfața web principală și controlul
- API RESTful pentru toate funcțiile robotului
- Comunicarea serială cu ESP32
- Auto-detectarea și configurarea dispozitivelor
- Gestionarea robustă a erorilor cu module dummy pentru fallback

##### **OpenCV Video Streaming**
- Integrarea directă V4L2 pentru cameră
- Suport pentru multiple rezoluții (320p-720p)
- Optimizarea formatului MJPEG
- Auto-detectarea capabilităților camerei

##### **FFmpeg & Audio Processing**
- Înregistrarea sincronizată audio+video
- Streaming live al microfonului
- Procesarea și encodarea audio
- Suport pentru multiple moduri de streaming audio

##### **ZeroTier (External Configuration)**
- Networking P2P securizat (configurat extern)
- Acces remote de oriunde
- Soluție VPN la nivel de rețea

### **ESP32 Firmware**
- Controlul motoarelor DC cu feedback de la encodere
- Monitorizarea bateriei prin INA219
- Comunicarea serială cu Raspberry Pi
- Raportarea statusului în timp real
- Extensibil pentru senzori suplimentari

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
   # Versiunea modulară (recomandată)
   python avatar_tank_enhanced.py
   
   # Sau direct modulul principal
   python modules/main_app.py
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
├── avatar_tank_enhanced.py     # Enhanced launcher with system checks
├── avatar_tank_config.json     # Auto-generated device configuration
├── modules/                    # Modular architecture (NEW!)
│   ├── __init__.py
│   ├── main_app.py            # Main Flask application coordinator
│   ├── device_detector.py     # Auto-detection of hardware devices
│   ├── camera.py              # Camera management and streaming
│   ├── motor_controller.py    # ESP32 communication and motor control
│   ├── tts.py                 # Text-to-Speech with Piper support
│   ├── recorder.py            # Video/audio recording functionality
│   ├── audio_utils.py         # Audio device management utilities
│   ├── predictor.py           # Word prediction and text suggestions
│   └── audio_streamer.py      # WebSocket audio streaming
├── static/                    # Web interface files
│   ├── index.html             # Updated web UI
│   └── predict.js             # JavaScript for predictions
├── dicts/                     # TTS language dictionaries
│   ├── common.txt
│   ├── en.txt
│   └── ro.txt
├── docs/                      # Enhanced documentation
│   ├── fluxuri.md             # Communication flows documentation
│   └── propunere.md           # Server-centralized architecture proposal
├── esp_firmware/              # ESP32 firmware
│   └── espfirmware.ino        # Combined motor + battery monitoring
├── backup/                    # Backup of previous versions
├── snapshots/                 # Captured images
├── recordings/                # Video recordings
├── sounds/                    # Audio files
├── MODULAR_REFACTOR_SUMMARY.md # Refactoring documentation
├── MODULES_README.md          # Module usage guide
├── module_examples.py         # Examples of module usage
└── requirements.txt           # Python dependencies
```

## 🔧 Development Status

### **✅ Working Features**
- [x] **Modular Architecture** - Completely refactored for maintainability
- [x] **Enhanced System Launcher** - Comprehensive system checks and diagnostics
- [x] **Tank movement control** (hold-to-move)
- [x] **Live video streaming** (OpenCV/V4L2)
- [x] **Multi-mode audio streaming** (Standard/Optimized/Realtime via WebSocket)
- [x] **Battery monitoring** with INA219 sensor
- [x] **Snapshot and video recording** with synchronized audio
- [x] **Text-to-Speech output** with Piper TTS support
- [x] **Word prediction system** for faster text input
- [x] **Remote access** (via external ZeroTier configuration)
- [x] **Robust device auto-detection** with fallback mechanisms
- [x] **Web UI with responsive design**
- [x] **Audio utilities** for volume control and device management

### **🚧 In Progress**
- [ ] **Server-centralized architecture** (detailed proposal available in docs/)
- [ ] **Enhanced WebRTC integration** for lower latency
- [ ] **Direct SSD boot support**
- [ ] **IMU/compass integration**
- [ ] **Mobile-optimized UI improvements**
- [ ] **Servo camera control**

### **📋 Planned Features**
- [ ] **LIDAR obstacle detection**
- [ ] **Voice control integration**
- [ ] **Multi-user access control**
- [ ] **Cloud recording storage**
- [ ] **Mobile companion app**
- [ ] **Mumble integration** for bidirectional audio communication

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

## 📚 Advanced Documentation

Pentru informații detaliate despre arhitectură și funcționalități avansate, consultă:

- **[fluxuri.md](docs/fluxuri.md)** - Documentația completă a fluxurilor de comunicare (video, audio, control motor, ZeroTier VPN)
- **[propunere.md](docs/propunere.md)** - Propunerea tehnică pentru migrarea la arhitectura server-centralizată
- **[MODULAR_REFACTOR_SUMMARY.md](MODULAR_REFACTOR_SUMMARY.md)** - Rezumatul refactorizării modulare
- **[MODULES_README.md](MODULES_README.md)** - Ghidul de utilizare al modulelor

### **Caracteristici Tehnice Avansate**

- **Audio Streaming Multi-Modal**: Standard (AAC), Optimized (Opus 16kbps), Realtime (PCM/WebSocket)
- **Video Adaptiv**: Rezoluție și calitate adaptivă în funcție de bandwidth
- **Predicție de Text**: Sistem inteligent de sugerare cuvinte pentru TTS
- **Diagnostice Complete**: Verificări automate de sistem, permisiuni și dependențe
- **Fallback Robust**: Module dummy pentru funcționarea continuă la eșecuri hardware

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

#!/usr/bin/env python3
"""
Setup script for Avatar Tank modular system.
Creates proper directory structure and places files correctly.
"""

import os
import shutil
from pathlib import Path


def create_directory_structure():
    """Create the required directory structure"""
    directories = [
        'modules',
        'static', 
        'snapshots',
        'recordings',
        'sounds',
        'dicts'  # For word prediction dictionaries
    ]
    
    print("Creating directory structure...")
    for directory in directories:
        path = Path(directory)
        if not path.exists():
            path.mkdir(exist_ok=True, parents=True)
            print(f"  ✓ Created: {directory}/")
        else:
            print(f"  ○ Exists: {directory}/")


def create_modules_init():
    """Create __init__.py in modules directory"""
    init_file = Path("modules") / "__init__.py"
    if not init_file.exists():
        with open(init_file, 'w') as f:
            f.write('"""Avatar Tank Modules Package"""\n')
        print("  ✓ Created: modules/__init__.py")


def create_requirements_file():
    """Create requirements.txt with necessary dependencies"""
    requirements_content = """# Avatar Tank System Requirements
flask>=2.3.0
flask-socketio>=5.3.0
opencv-python>=4.8.0
pyserial>=3.5
numpy>=1.24.0
simple-websocket>=0.10.0
python-engineio>=4.7.0
python-socketio>=5.8.0

# Optional but recommended for better performance
eventlet>=0.33.0
"""
    
    requirements_file = Path("requirements.txt")
    if not requirements_file.exists():
        with open(requirements_file, 'w') as f:
            f.write(requirements_content)
        print("  ✓ Created: requirements.txt")


def create_sample_dictionary():
    """Create a sample words dictionary for predictions"""
    words_file = Path("dicts") / "words.txt"
    if not words_file.exists():
        sample_words = """# Sample words for Avatar Tank prediction system
hello
help
please
thank
you
yes
no
stop
go
forward
backward
left
right
battery
camera
audio
video
record
snapshot
move
motor
system
status
reboot
volume
microphone
speaker
control
interface
streaming
connection
wifi
network
settings
configuration
calibration
emergency
warning
error
success
complete
ready
initialize
activate
deactivate
start
finish
update
upgrade
maintenance
diagnostic
test
verification
demonstration
tutorial
guide
manual
documentation
troubleshooting
"""
        with open(words_file, 'w') as f:
            f.write(sample_words)
        print("  ✓ Created: dicts/words.txt with sample words")


def create_startup_script():
    """Create a startup script for easier launching"""
    startup_script = """#!/bin/bash
# Avatar Tank System Startup Script

echo "========================================"
echo "Avatar Tank Control System - Starting..."
echo "========================================"

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    echo "Warning: Running as root is not recommended"
fi

# Check for Python 3
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is required but not found"
    exit 1
fi

# Check if virtual environment exists
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
fi

# Install/update requirements if needed
if [ -f "requirements.txt" ]; then
    echo "Installing/updating requirements..."
    pip install -r requirements.txt --quiet
fi

# Set environment variables for better performance
export PYTHONUNBUFFERED=1
export FLASK_ENV=production

# Add current user to required groups (if not already)
echo "Checking user groups..."
if ! groups $USER | grep -q "audio"; then
    echo "Note: Add user to audio group: sudo usermod -a -G audio $USER"
fi
if ! groups $USER | grep -q "video"; then
    echo "Note: Add user to video group: sudo usermod -a -G video $USER"
fi
if ! groups $USER | grep -q "dialout"; then
    echo "Note: Add user to dialout group: sudo usermod -a -G dialout $USER"
fi

echo "Starting Avatar Tank system..."
python3 run_modular.py

echo "Avatar Tank system stopped."
"""
    
    startup_file = Path("start_avatar_tank.sh")
    with open(startup_file, 'w') as f:
        f.write(startup_script)
    
    # Make it executable
    os.chmod(startup_file, 0o755)
    print("  ✓ Created: start_avatar_tank.sh (executable)")


def create_systemd_service():
    """Create a systemd service file for auto-startup"""
    service_content = """[Unit]
Description=Avatar Tank Control System
After=network.target sound.target
Wants=network.target

[Service]
Type=simple
User=pi
Group=pi
WorkingDirectory=/home/pi/avatar_tank
ExecStart=/usr/bin/python3 /home/pi/avatar_tank/run_modular.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
Environment=PYTHONUNBUFFERED=1
Environment=FLASK_ENV=production

# Security settings
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=strict
ReadWritePaths=/home/pi/avatar_tank/snapshots /home/pi/avatar_tank/recordings /home/pi/avatar_tank/dicts
DeviceAllow=/dev/video0 rw
DeviceAllow=/dev/video1 rw
DeviceAllow=/dev/ttyUSB0 rw
DeviceAllow=/dev/ttyUSB1 rw
DeviceAllow=/dev/ttyACM0 rw

[Install]
WantedBy=multi-user.target
"""
    
    service_file = Path("avatar-tank.service")
    with open(service_file, 'w') as f:
        f.write(service_content)
    
    print("  ✓ Created: avatar-tank.service")
    print("    To install: sudo cp avatar-tank.service /etc/systemd/system/")
    print("    To enable: sudo systemctl enable avatar-tank.service")
    print("    To start: sudo systemctl start avatar-tank.service")


def create_readme():
    """Create a comprehensive README file"""
    readme_content = """# Avatar Tank Control System - Modular Version

A modular robot control system with web interface, designed for Raspberry Pi.

## Features

- **Web-based Control Interface**: Modern responsive web UI
- **Real-time Video Streaming**: Camera feed with adjustable resolution
- **Motor Control**: Directional movement with speed control
- **Audio System**: Microphone streaming and speaker control
- **Text-to-Speech**: Multi-language support with Piper TTS
- **Recording**: Video/audio recording with smart device management
- **Word Prediction**: Smart text completion system
- **System Monitoring**: Real-time status and diagnostics

## Quick Start

1. **Setup System**:
   ```bash
   python3 setup_structure.py
   pip install -r requirements.txt
   ```

2. **Add User to Groups** (logout/login required):
   ```bash
   sudo usermod -a -G audio,video,dialout $USER
   ```

3. **Run System**:
   ```bash
   python3 run_modular.py
   # or
   ./start_avatar_tank.sh
   ```

4. **Access Interface**: http://localhost:5000

## Directory Structure

```
avatar_tank/
├── modules/              # Core system modules
│   ├── device_detector.py
│   ├── camera.py
│   ├── motor_controller.py
│   ├── tts.py
│   ├── recorder.py
│   ├── audio_utils.py
│   ├── predictor.py
│   ├── audio_streamer.py
│   └── main_app.py
├── static/               # Web interface files
│   └── index.html
├── snapshots/           # Camera snapshots
├── recordings/          # Video recordings
├── sounds/              # Sound effect files
├── dicts/              # Word prediction dictionaries
├── run_modular.py      # Main launcher
└── requirements.txt    # Python dependencies
```

## Configuration

### Environment Variables

Override device detection by setting:
- `AV_CAMERA=/dev/video1` - Camera device
- `AV_MIC=plughw:1,0` - Microphone device  
- `AV_SPK=plughw:1,0` - Speaker device
- `AV_MOTOR=/dev/ttyUSB0` - Motor controller port

### Hardware Requirements

- Raspberry Pi 4/5 (recommended)
- USB Camera or Pi Camera
- USB Audio device (optional, uses built-in if available)
- Serial motor controller (Arduino/ESP32 based)

## Troubleshooting

### Common Issues

1. **Camera not found**: Check `/dev/video*` permissions and camera connection
2. **Audio device busy**: Stop other audio applications or use different device
3. **Motor controller not responding**: Check serial device permissions and connection
4. **Web interface not loading**: Verify all modules imported successfully

### Logs

Check console output from `run_modular.py` for detailed error messages.

### Device Testing

- Test camera: `v4l2-ctl --list-devices`
- Test audio: `arecord -l` and `aplay -l`
- Test serial: `ls -la /dev/tty*`

## Advanced Usage

### Auto-start Service

1. Install systemd service:
   ```bash
   sudo cp avatar-tank.service /etc/systemd/system/
   sudo systemctl enable avatar-tank.service
   sudo systemctl start avatar-tank.service
   ```

2. Check status:
   ```bash
   sudo systemctl status avatar-tank.service
   ```

### Custom Sound Effects

Place audio files in `sounds/` directory:
- `sound1.wav` through `sound10.wav`
- Supported formats: WAV, MP3, OGG, FLAC

### Word Prediction

Add custom dictionaries to `dicts/` directory:
- `words.txt` - Main dictionary
- `custom_words.txt` - Learned words (auto-generated)
- Any `*.txt` files will be loaded

## Development

### Module Structure

Each module is designed to be independent with graceful fallbacks:
- Import errors don't crash the system
- Missing hardware is handled gracefully
- Resource conflicts are managed automatically

### Adding Features

1. Create new module in `modules/`
2. Import in `main_app.py` with error handling
3. Add routes and WebSocket handlers as needed
4. Update frontend interface if required

## License

Open source project - see individual module headers for details.

## Support

For issues and questions, check the troubleshooting section or review the console logs for detailed error messages.
"""
    
    readme_file = Path("README.md")
    with open(readme_file, 'w') as f:
        f.write(readme_content)
    print("  ✓ Created: README.md")


def main():
    """Main setup function"""
    print("Avatar Tank System - Directory Structure Setup")
    print("=" * 50)
    
    # Create directories
    create_directory_structure()
    
    # Create support files
    create_modules_init()
    create_requirements_file()
    create_sample_dictionary()
    create_startup_script()
    create_systemd_service()
    create_readme()
    
    print("\n" + "=" * 50)
    print("Setup completed successfully!")
    print("\nNext steps:")
    print("1. Place your module files in the modules/ directory")
    print("2. Place the index.html file in the static/ directory")
    print("3. Install dependencies: pip install -r requirements.txt")
    print("4. Add user to groups: sudo usermod -a -G audio,video,dialout $USER")
    print("5. Run the system: python3 run_modular.py")
    print("\nFor automatic startup, see README.md for systemd service setup.")


if __name__ == '__main__':
    main()

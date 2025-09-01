# Avatar Tank System - Modular Structure

This is a modular version of the Avatar Tank system, organized into separate modules for better maintainability and scalability.

## Module Structure

- `modules/` - Contains all the modular components
  - `device_detector.py` - Handles device detection for cameras, audio devices, and motor controllers
  - `camera.py` - Camera initialization, configuration, and frame generation
  - `motor_controller.py` - Motor control and communication with the motor controller
  - `tts.py` - Text-to-speech functionality using Piper or fallback engines
  - `recorder.py` - Video and audio recording functionality
  - `audio_utils.py` - Audio utilities for volume control and device management
  - `predictor.py` - Word prediction and text suggestion system
  - `audio_streamer.py` - WebSocket audio streaming functionality
  - `main_app.py` - Main application that coordinates all modules

- `static/` - Contains the web interface files
  - `index.html` - Main web interface with all controls

## Running the System

To run the modular version of the Avatar Tank system:

```bash
python3 modules/main_app.py
```

The system will automatically detect devices and start the web interface on port 5000.

## Benefits of Modular Structure

1. **Maintainability** - Each module has a single responsibility
2. **Scalability** - Easy to add new features or modify existing ones
3. **Testability** - Individual modules can be tested independently
4. **Reusability** - Modules can be reused in other projects
5. **Collaboration** - Multiple developers can work on different modules simultaneously

## Module Dependencies

The modules are organized with the following dependencies:
- `main_app.py` imports and coordinates all other modules
- `device_detector.py` is imported by most other modules for device configuration
- Modules are designed to be as independent as possible while maintaining necessary functionality
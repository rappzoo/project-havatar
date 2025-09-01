#!/usr/bin/env python3
"""
Example script demonstrating how to use individual modules from the Avatar Tank system.
"""

import sys
import os

# Add the current directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Example 1: Using the device detector module
print("=== Device Detection Example ===")
from modules.device_detector import device_detector
print(f"Detected camera: {device_detector.detected_devices['camera']}")
print(f"Detected microphone: {device_detector.detected_devices['microphone']}")

# Example 2: Using the camera module
print("\n=== Camera Module Example ===")
from modules.camera import camera, init_camera
if camera:
    print("Camera initialized successfully")
    # Try to read a frame
    ret, frame = camera.read()
    if ret:
        print(f"Captured frame with shape: {frame.shape}")
    else:
        print("Failed to capture frame")
else:
    print("Camera not available")

# Example 3: Using the motor controller module
print("\n=== Motor Controller Example ===")
from modules.motor_controller import motors
battery_status = motors.get_battery()
print(f"Battery status: {battery_status}")

# Example 4: Using the TTS module
print("\n=== Text-to-Speech Example ===")
from modules.tts import tts
tts_status = tts.status()
print(f"TTS status: {tts_status}")

# Example 5: Using the predictor module
print("\n=== Prediction Example ===")
from modules.predictor import _predict
suggestions = _predict.suggest("hel", limit=5)
print(f"Predictions for 'hel': {suggestions}")

print("\n=== All Examples Completed ===")
#!/usr/bin/env python3
"""
Device detection module for Avatar Tank system.
Handles automatic detection of cameras, audio devices, and motor controllers.
"""

import cv2
import subprocess
import serial
import time
import os
import re
import glob
import json
from pathlib import Path
import threading


class DeviceDetector:
    """Singleton device detector with thread-safe initialization"""
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized') and self._initialized:
            return
            
        self.detected_devices = {
            'camera': None,
            'microphone': None,
            'speaker': None,
            'motor_controller': None
        }
        self.cameras = []
        self.audio_input = []
        self.audio_output = []
        self.serial_ports = []
        
        # Check environment overrides first
        self._check_env_overrides()
        
        # Scan for devices
        self._scan_all_devices()
        self._initialized = True
    
    def _check_env_overrides(self):
        """Check for environment variable overrides"""
        self.env_overrides = {
            'camera': os.environ.get('AV_CAMERA'),
            'mic': os.environ.get('AV_MIC'),
            'speaker': os.environ.get('AV_SPK'),
            'motor': os.environ.get('AV_MOTOR')
        }
        
        if any(self.env_overrides.values()):
            print("[DeviceDetector] Environment overrides detected:")
            for key, value in self.env_overrides.items():
                if value:
                    print(f"  {key.upper()}: {value}")
    
    def _scan_all_devices(self):
        """Scan for all device types"""
        print("[DeviceDetector] Scanning for devices...")
        
        try:
            self._scan_cameras()
        except Exception as e:
            print(f"[DeviceDetector] Camera scan failed: {e}")
            
        try:
            self._scan_audio_devices()
        except Exception as e:
            print(f"[DeviceDetector] Audio scan failed: {e}")
            
        try:
            self._scan_serial_devices()
        except Exception as e:
            print(f"[DeviceDetector] Serial scan failed: {e}")
        
        self._select_best_devices()
    
    def _scan_cameras(self):
        """Scan for available cameras"""
        self.cameras = []
        
        # Check environment override first
        if self.env_overrides['camera']:
            device_path = self.env_overrides['camera']
            if self._test_camera_device(device_path):
                self.cameras.append({
                    'path': device_path,
                    'name': f"Camera {device_path} (env override)",
                    'mjpeg_support': True,  # Assume yes for overrides
                    'working': True,
                    'priority': 10  # High priority for env overrides
                })
                return
        
        # Test video devices
        device_paths = ['/dev/video0', '/dev/video1', '/dev/video2', '/dev/video3']
        for device_path in device_paths:
            if os.path.exists(device_path):
                if self._test_camera_device(device_path):
                    self.cameras.append({
                        'path': device_path,
                        'name': f"Camera {device_path}",
                        'mjpeg_support': True,  # We'll test this during init
                        'working': True,
                        'priority': 1
                    })
    
    def _test_camera_device(self, device_path):
        """Test if a camera device works"""
        try:
            cap = cv2.VideoCapture(device_path, cv2.CAP_V4L2)
            if cap.isOpened():
                ret, frame = cap.read()
                cap.release()
                if ret and frame is not None and frame.size > 0:
                    print(f"[Camera] Found working camera: {device_path}")
                    return True
        except Exception as e:
            print(f"[Camera] {device_path} test failed: {e}")
        return False
    
    def _scan_audio_devices(self):
        """Scan for audio input/output devices"""
        self.audio_input = []
        self.audio_output = []
        
        # Check environment overrides
        if self.env_overrides['mic']:
            self.audio_input.append({
                'path': self.env_overrides['mic'],
                'name': f"Microphone (env override)",
                'priority': 10,
                'card': 'override',
                'device': 'override'
            })
        else:
            self._scan_alsa_input_devices()
        
        if self.env_overrides['speaker']:
            self.audio_output.append({
                'path': self.env_overrides['speaker'],
                'name': f"Speaker (env override)",
                'priority': 10,
                'card': 'override',
                'device': 'override'
            })
        else:
            self._scan_alsa_output_devices()
    
    def _scan_alsa_input_devices(self):
        """Scan ALSA input devices"""
        try:
            result = subprocess.run(['arecord', '-l'], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    match = re.search(r'card\s+(\d+):\s*([^,]+).*device\s+(\d+):\s*([^,]+)', line)
                    if match:
                        card, card_name, device, device_name = match.groups()
                        alsa_device = f"plughw:{card},{device}"
                        
                        # Prioritize USB devices
                        priority = 2 if 'usb' in card_name.lower() else 1
                        
                        self.audio_input.append({
                            'path': alsa_device,
                            'name': f"{card_name.strip()} - {device_name.strip()}",
                            'priority': priority,
                            'card': card,
                            'device': device
                        })
        except Exception as e:
            print(f"[Audio] Input scan failed: {e}")
            # Add fallback
            self.audio_input.append({
                'path': 'default',
                'name': 'Default Audio Input',
                'priority': 0,
                'card': 'default',
                'device': 'default'
            })
    
    def _scan_alsa_output_devices(self):
        """Scan ALSA output devices"""
        try:
            result = subprocess.run(['aplay', '-l'], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    match = re.search(r'card\s+(\d+):\s*([^,]+).*device\s+(\d+):\s*([^,]+)', line)
                    if match:
                        card, card_name, device, device_name = match.groups()
                        alsa_device = f"plughw:{card},{device}"
                        
                        # Prioritize USB devices and specific names
                        priority = 2 if ('usb' in card_name.lower() or 'uac' in card_name.lower()) else 1
                        
                        self.audio_output.append({
                            'path': alsa_device,
                            'name': f"{card_name.strip()} - {device_name.strip()}",
                            'priority': priority,
                            'card': card,
                            'device': device
                        })
        except Exception as e:
            print(f"[Audio] Output scan failed: {e}")
            # Add fallback
            self.audio_output.append({
                'path': 'default',
                'name': 'Default Audio Output',
                'priority': 0,
                'card': 'default',
                'device': 'default'
            })
    
    def _scan_serial_devices(self):
        """Scan for serial devices"""
        self.serial_ports = []
        
        # Check environment override
        if self.env_overrides['motor']:
            self.serial_ports.append({
                'path': self.env_overrides['motor'],
                'name': f"Motor Controller (env override)",
                'controller_type': 'override',
                'priority': 10
            })
            return
        
        serial_devices = glob.glob('/dev/ttyUSB*') + glob.glob('/dev/ttyACM*') + glob.glob('/dev/ttyAMA*')
        
        for device_path in sorted(serial_devices):  # Sort for consistent ordering
            try:
                controller_type = self._test_motor_controller(device_path)
                priority = 2 if controller_type != 'unknown' else 1
                
                self.serial_ports.append({
                    'path': device_path,
                    'name': f"Serial Device ({device_path})",
                    'controller_type': controller_type,
                    'priority': priority
                })
                print(f"[Serial] Found: {device_path} ({controller_type})")
            except Exception as e:
                print(f"[Serial] Failed to test {device_path}: {e}")
    
    def _test_motor_controller(self, device_path):
        """Test if a serial device is a motor controller"""
        try:
            # Add a timeout to prevent hanging
            with serial.Serial(device_path, 115200, timeout=2) as ser:
                time.sleep(0.5)
                ser.reset_input_buffer()
                
                # Send a status command to test communication
                ser.write(b'STATUS\n')
                time.sleep(0.5)
                
                # Read response with timeout
                response = b""
                start_time = time.time()
                
                while time.time() - start_time < 1.0:
                    if ser.in_waiting:
                        response += ser.read(ser.in_waiting)
                    time.sleep(0.01)
                
                response_str = response.decode('utf-8', 'ignore')
                
                if 'voltage' in response_str.lower() or 'battery' in response_str.lower():
                    return 'esp32_motor_controller'
                elif response_str.strip():
                    return 'generic_controller'
                else:
                    # Try a simple command
                    ser.write(b'?\n')
                    time.sleep(0.3)
                    response2 = ser.read_all().decode('utf-8', 'ignore')
                    if response2.strip():
                        return 'unknown_controller'
                    
        except serial.SerialException as e:
            print(f"[Serial] Serial exception for {device_path}: {e}")
        except Exception as e:
            print(f"[Serial] General exception for {device_path}: {e}")
        return 'unknown'
    
    def _select_best_devices(self):
        """Select the best device for each category"""
        # Select best camera (highest priority first)
        if self.cameras:
            sorted_cameras = sorted(self.cameras, key=lambda x: x.get('priority', 0), reverse=True)
            self.detected_devices['camera'] = sorted_cameras[0]
        
        # Select best microphone (highest priority first)
        if self.audio_input:
            sorted_mics = sorted(self.audio_input, key=lambda x: x['priority'], reverse=True)
            self.detected_devices['microphone'] = sorted_mics[0]
        
        # Select best speaker (highest priority first)
        if self.audio_output:
            sorted_speakers = sorted(self.audio_output, key=lambda x: x['priority'], reverse=True)
            self.detected_devices['speaker'] = sorted_speakers[0]
        
        # Select best motor controller (highest priority first)
        if self.serial_ports:
            sorted_controllers = sorted(self.serial_ports, key=lambda x: x['priority'], reverse=True)
            self.detected_devices['motor_controller'] = sorted_controllers[0]
    
    def get_device_config(self):
        """Get the configuration for detected devices"""
        return {
            'camera_device': self.detected_devices['camera']['path'] if self.detected_devices['camera'] else '/dev/video0',
            'mic_device': self.detected_devices['microphone']['path'] if self.detected_devices['microphone'] else 'default',
            'speaker_device': self.detected_devices['speaker']['path'] if self.detected_devices['speaker'] else 'default',
            'motor_port': self.detected_devices['motor_controller']['path'] if self.detected_devices['motor_controller'] else '/dev/ttyUSB0'
        }
    
    def print_detection_summary(self):
        """Print a summary of detected devices"""
        print("\n" + "="*60)
        print("AVATAR TANK - DEVICE DETECTION SUMMARY")
        print("="*60)
        
        for device_type, device in self.detected_devices.items():
            if device:
                priority_info = f" (priority: {device.get('priority', 'N/A')})"
                print(f"  {device_type.upper()}: {device['name']} -> {device['path']}{priority_info}")
            else:
                print(f"  {device_type.upper()}: NOT FOUND")
        
        if any(self.env_overrides.values()):
            print("\nEnvironment overrides active - detection may be bypassed")
        
        print("="*60)
    
    def refresh_devices(self):
        """Re-scan all devices"""
        print("[DeviceDetector] Refreshing device list...")
        self._scan_all_devices()
        self.print_detection_summary()


# Create singleton instance and export device paths
print("[DeviceDetector] Initializing device detection...")
device_detector = DeviceDetector()
device_detector.print_detection_summary()

# Export the device configuration
device_config = device_detector.get_device_config()
CAMERA_DEVICE = device_config['camera_device']
MIC_PLUG = device_config['mic_device']
SPK_PLUG = device_config['speaker_device']
MOTOR_PORT = device_config['motor_port']

print(f"\n[DeviceDetector] Final device assignments:")
print(f"  Camera: {CAMERA_DEVICE}")
print(f"  Microphone: {MIC_PLUG}")
print(f"  Speaker: {SPK_PLUG}")
print(f"  Motor: {MOTOR_PORT}")

# Override environment variables for compatibility with other tools
os.environ['AV_MIC'] = MIC_PLUG
os.environ['AV_SPK'] = SPK_PLUG
os.environ['AV_CAMERA'] = CAMERA_DEVICE
os.environ['AV_MOTOR'] = MOTOR_PORT
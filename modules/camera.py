#!/usr/bin/env python3
"""
Camera module for Avatar Tank system.
Handles camera initialization, configuration, and frame generation.
"""

import cv2
import numpy as np
import datetime
import os
import threading
import time
import sys
import subprocess


# Try to get device detector - handle import gracefully
try:
    # Add parent directory to path for imports
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)
    
    from modules.device_detector import device_detector, CAMERA_DEVICE
    print(f"[Camera] Using detected camera device: {CAMERA_DEVICE}")
except ImportError as e:
    print(f"[Camera] Warning: Could not import device detector ({e}), using fallback")
    CAMERA_DEVICE = '/dev/video0'


# ============== CAMERA SETTINGS ==============
current_resolution = "720p"
camera_settings = {
    "480p": {"width": 640, "height": 480, "fps": 10},
    "720p": {"width": 1280, "height": 720, "fps": 10},
    "1080p": {"width": 1920, "height": 1080, "fps": 10}
}

# ============== Camera Classes ==============
class DummyCamera:
    """Dummy camera that generates test patterns"""
    def __init__(self):
        self.frame = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.putText(self.frame, "NO CAMERA SIGNAL", (140, 240),
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        cv2.rectangle(self.frame, (50, 50), (590, 430), (0, 255, 255), 2)
        self._frame_counter = 0
        
    def read(self):
        # Create a copy and add timestamp
        temp = self.frame.copy()
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        cv2.putText(temp, ts, (250, 280), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 1)
        
        # Add frame counter for debugging
        self._frame_counter += 1
        cv2.putText(temp, f"Frame: {self._frame_counter}", (450, 450), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)
        
        return True, temp
    
    def release(self): 
        pass
    
    def set(self, prop, val): 
        return True
    
    def get(self, prop):
        if prop == cv2.CAP_PROP_FRAME_WIDTH:  
            return 640
        if prop == cv2.CAP_PROP_FRAME_HEIGHT: 
            return 480
        if prop == cv2.CAP_PROP_FPS:          
            # Return the configured FPS for the current resolution
            global camera_settings, current_resolution
            return camera_settings.get(current_resolution, {}).get("fps", 10)
        return 0
    
    def isOpened(self): 
        return True


class CameraManager:
    """Thread-safe camera manager"""
    def __init__(self):
        self.camera = None
        self.camera_device = None
        self.lock = threading.Lock()
        self._last_bgr = None
        self._last_sz = (0, 0)
        self._last_lock = threading.Lock()
        self._frame_counter = 0
        self._error_count = 0
        self._max_errors = 5
        self._initialized = False
        
    def _ensure_initialized(self):
        """Ensure camera is initialized before use"""
        if not self._initialized:
            print("[Camera] Performing delayed initialization...")
            self.init_camera()
            self._initialized = True
    
    def _kill_processes_using_device(self, device):
        """Kill any processes that might be using the camera device"""
        try:
            # Try to find processes using the device
            result = subprocess.run(['lsof', device], capture_output=True, text=True)
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                for line in lines[1:]:  # Skip header line
                    parts = line.split()
                    if len(parts) > 1:
                        pid = parts[1]
                        try:
                            os.kill(int(pid), 9)  # SIGKILL
                            print(f"[Camera] Killed process {pid} using {device}")
                        except (ValueError, ProcessLookupError):
                            pass
            return True
        except Exception as e:
            print(f"[Camera] Warning: Could not kill processes using {device}: {e}")
            return False
        
    def _try_open_camera(self, device, backend, name):
        """Try to open a camera device"""
        try:
            if backend is not None:
                cap = cv2.VideoCapture(device, backend)
            else:
                cap = cv2.VideoCapture(device)
            
            if not cap.isOpened():
                if cap:
                    cap.release()
                return None
            
            # Configure basic settings
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            # Set FPS to 10 for initial testing
            cap.set(cv2.CAP_PROP_FPS, 10)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            cap.set(cv2.CAP_PROP_AUTOFOCUS, 0)
            
            # Test frame capture
            ret, frame = cap.read()
            if ret and frame is not None and frame.size > 0:
                print(f"[Camera] ✓ {device} ({name}) - Resolution: {frame.shape[1]}x{frame.shape[0]}")
                return cap
            else:
                print(f"[Camera] ✗ {device} ({name}) - No valid frame")
                cap.release()
                return None
                
        except Exception as e:
            print(f"[Camera] ✗ {device} ({name}) - Error: {e}")
            return None
    
    def find_working_camera(self):
        """Find a working camera device with enhanced detection"""
        devices_to_try = []
        
        # First try the detected device
        if CAMERA_DEVICE and isinstance(CAMERA_DEVICE, str):
            devices_to_try.append(CAMERA_DEVICE)
        
        # Add common device paths
        common_devices = ['/dev/video0', '/dev/video1', '/dev/video2', '/dev/video3']
        for dev in common_devices:
            if dev not in devices_to_try:
                devices_to_try.append(dev)
        
        # Try each device with different backends
        backends = [
            (cv2.CAP_V4L2, "V4L2"),
            (cv2.CAP_GSTREAMER, "GStreamer"),
            (None, "default")
        ]
        
        for dev in devices_to_try:
            if isinstance(dev, str) and not os.path.exists(dev):
                continue
                
            print(f"[Camera] Testing device: {dev}")
            
            # Try each backend
            for backend, backend_name in backends:
                cap = self._try_open_camera(dev, backend, f"{backend_name}")
                if cap:
                    return cap, dev
        
        # Try numeric indices as last resort
        for idx in [0, 1, 2, 3]:
            print(f"[Camera] Testing index: {idx}")
            for backend, backend_name in backends:
                cap = self._try_open_camera(idx, backend, f"{backend_name}-index-{idx}")
                if cap:
                    return cap, idx
        
        print("[Camera] No working camera found")
        return None, None
    
    def init_camera(self):
        """Initialize the camera with thread safety"""
        with self.lock:
            print(f"[Camera] Initializing camera with resolution: {current_resolution}")
            
            # Clean up existing camera
            if self.camera and not isinstance(self.camera, DummyCamera):
                try:
                    self.camera.release()
                except:
                    pass
                self.camera = None
            
            try:
                # Try to find working camera
                new_cam, dev = self.find_working_camera()
                
                # If no camera found, try one more time with device cleanup
                if not new_cam and CAMERA_DEVICE:
                    print(f"[Camera] Attempting to free device {CAMERA_DEVICE} and retry...")
                    self._kill_processes_using_device(CAMERA_DEVICE)
                    time.sleep(1)  # Give system time to release device
                    new_cam, dev = self.find_working_camera()
                
                # If still no camera found, try a more aggressive approach
                if not new_cam and CAMERA_DEVICE:
                    print(f"[Camera] Trying aggressive device reset for {CAMERA_DEVICE}...")
                    self._aggressive_device_reset(CAMERA_DEVICE)
                    time.sleep(2)  # Give more time for device to reset
                    new_cam, dev = self.find_working_camera()
                
                if not new_cam:
                    print("[Camera] Using dummy camera")
                    self.camera = DummyCamera()
                    self.camera_device = "dummy"
                    self._error_count = 0
                    return False
                
                self.camera = new_cam
                self.camera_device = dev
                self._error_count = 0
                
                # Configure camera settings
                try:
                    # Try to enable MJPEG for better performance
                    self.camera.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M','J','P','G'))
                    
                    # Apply resolution settings
                    settings = camera_settings[current_resolution]
                    print(f"[Camera] Setting resolution to {settings['width']}x{settings['height']}@{settings['fps']}fps")
                    self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, settings["width"])
                    self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, settings["height"])
                    self.camera.set(cv2.CAP_PROP_FPS, settings["fps"])
                    
                    # Try to set additional properties to enforce FPS
                    self.camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                    self.camera.set(cv2.CAP_PROP_AUTOFOCUS, 0)
                    
                    # Verify settings
                    actual_width = int(self.camera.get(cv2.CAP_PROP_FRAME_WIDTH))
                    actual_height = int(self.camera.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    actual_fps = self.camera.get(cv2.CAP_PROP_FPS)
                    
                    print(f"[Camera] Configured: {actual_width}x{actual_height}@{actual_fps:.1f}fps")
                    
                    # If FPS doesn't match, try to enforce it through timing control
                    if abs(actual_fps - settings["fps"]) > 1.0:
                        print(f"[Camera] Warning: Camera FPS {actual_fps} differs from target {settings['fps']}, will enforce through timing control")
                    
                    return True
                    
                except Exception as e:
                    print(f"[Camera] Configuration error: {e}")
                    return False
                    
            except Exception as e:
                print(f"[Camera] Initialization error: {e}")
                # Fallback to dummy camera
                self.camera = DummyCamera()
                self.camera_device = "dummy"
                return False
    
    def _aggressive_device_reset(self, device):
        """Aggressively reset the camera device"""
        try:
            # Try to reset the USB device if it's a USB camera
            if device.startswith('/dev/video'):
                # Get the device number
                dev_num = device.replace('/dev/video', '')
                if dev_num.isdigit():
                    # Try to reset the USB device
                    reset_cmd = f"echo '{dev_num}' > /sys/class/video4linux/video{dev_num}/device/usb_reset 2>/dev/null || true"
                    subprocess.run(reset_cmd, shell=True, capture_output=True)
                    print(f"[Camera] Attempted USB device reset for {device}")
        except Exception as e:
            print(f"[Camera] Warning: Could not reset USB device {device}: {e}")
    
    def read_frame(self):
        """Read a frame from the camera with error handling"""
        self._ensure_initialized()
        
        with self.lock:
            if self.camera is None:
                return False, None
            
            try:
                ret, frame = self.camera.read()
                
                if not ret or frame is None:
                    self._error_count += 1
                    print(f"[Camera] Frame read failed (error count: {self._error_count})")
                    
                    if self._error_count >= self._max_errors:
                        print("[Camera] Too many errors, reinitializing...")
                        threading.Thread(target=self._reinit_camera, daemon=True).start()
                    
                    return False, None
                
                # Reset error count on success
                self._error_count = 0
                self._frame_counter += 1
                
                # Update shared frame buffer for recorder
                h, w = frame.shape[:2]
                with self._last_lock:
                    self._last_bgr = frame.copy()
                    self._last_sz = (w, h)
                
                return True, frame
                
            except Exception as e:
                self._error_count += 1
                print(f"[Camera] Read exception: {e} (error count: {self._error_count})")
                
                if self._error_count >= self._max_errors:
                    print("[Camera] Too many errors, reinitializing...")
                    threading.Thread(target=self._reinit_camera, daemon=True).start()
                
                return False, None
    
    def _reinit_camera(self):
        """Reinitialize camera in separate thread"""
        time.sleep(1)  # Brief delay before reinit
        self.init_camera()
    
    def get_shared_frame_data(self):
        """Get the shared frame data for recorder"""
        try:
            self._ensure_initialized()
            with self._last_lock:
                frame = self._last_bgr.copy() if self._last_bgr is not None else None
                size = self._last_sz
            return frame, size
        except Exception as e:
            print(f"[Camera] Shared frame data error: {e}")
            return None, (1280, 720)
    
    def set_resolution(self, resolution):
        """Change camera resolution"""
        global current_resolution
        
        print(f"[Camera] Changing resolution from {current_resolution} to {resolution}")
        
        if resolution in camera_settings:
            current_resolution = resolution
            # Reinitialize camera with new settings
            success = self.init_camera()
            print(f"[Camera] Resolution change {'successful' if success else 'failed'}, current: {current_resolution}")
            return success
        return False
    
    def get_status(self):
        """Get camera status information"""
        try:
            self._ensure_initialized()
            with self.lock:
                return {
                    "ok": self.camera is not None,
                    "device": self.camera_device,
                    "is_dummy": isinstance(self.camera, DummyCamera),
                    "resolution": current_resolution,
                    "frame_counter": self._frame_counter,
                    "error_count": self._error_count,
                    "initialized": self._initialized
                }
        except Exception as e:
            return {
                "ok": False,
                "msg": f"Camera status error: {e}",
                "device": "unknown",
                "is_dummy": True,
                "resolution": current_resolution,
                "frame_counter": 0,
                "error_count": 0,
                "initialized": False
            }
    
    def _create_error_frame(self, message):
        """Create an error frame with message"""
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.putText(frame, "CAMERA ERROR", (200, 200), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        cv2.putText(frame, message, (100, 250), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        cv2.putText(frame, datetime.datetime.now().strftime("%H:%M:%S"), (250, 300), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 1)
        return frame
    
    def generate_frames(self):
        """Generate MJPEG frames for HTTP streaming with improved error handling"""
        frame_count = 0
        fps_start = time.time()
        target_fps = camera_settings[current_resolution]["fps"]
        frame_interval = 1.0 / target_fps if target_fps > 0 else 0.1
        last_frame_time = time.time()
        consecutive_errors = 0
        max_consecutive_errors = 10
        
        print(f"[Camera] Starting frame generation at {target_fps} FPS")
        
        try:
            while True:
                try:
                    # Enforce target FPS by waiting if needed
                    current_time = time.time()
                    time_since_last_frame = current_time - last_frame_time
                    if time_since_last_frame < frame_interval:
                        sleep_time = frame_interval - time_since_last_frame
                        if sleep_time > 0:
                            time.sleep(sleep_time)
                    
                    frame_start = time.time()
                    ret, frame = self.read_frame()
                    
                    if not ret or frame is None:
                        consecutive_errors += 1
                        print(f"[Camera] Frame read failed (consecutive errors: {consecutive_errors})")
                        
                        # If too many consecutive errors, break the loop
                        if consecutive_errors >= max_consecutive_errors:
                            print("[Camera] Too many consecutive errors, stopping frame generation")
                            break
                        
                        # Yield an error frame instead of hanging
                        error_frame = self._create_error_frame("Camera Error")
                        _, buffer = cv2.imencode('.jpg', error_frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                        yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + 
                               buffer.tobytes() + b'\r\n')
                        
                        time.sleep(1)  # Wait before retrying
                        continue
                    
                    # Reset error counter on successful frame
                    consecutive_errors = 0
                    
                    # Encode frame as JPEG
                    encode_params = [cv2.IMWRITE_JPEG_QUALITY, 85]
                    _, buffer = cv2.imencode('.jpg', frame, encode_params)
                    
                    # Yield frame in multipart format
                    yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + 
                           buffer.tobytes() + b'\r\n')
                    
                    frame_count += 1
                    last_frame_time = time.time()
                    
                    # Log FPS periodically
                    if frame_count % 30 == 0:
                        elapsed = time.time() - fps_start
                        if elapsed > 0:
                            actual_fps = frame_count / elapsed
                            print(f"[Camera] Streaming at {actual_fps:.1f} FPS (target: {target_fps})")
                            frame_count = 0
                            fps_start = time.time()
                            
                except Exception as e:
                    consecutive_errors += 1
                    print(f"[Camera] Frame generation error: {e} (consecutive: {consecutive_errors})")
                    
                    if consecutive_errors >= max_consecutive_errors:
                        print("[Camera] Too many consecutive errors, stopping frame generation")
                        break
                    
                    # Yield error frame
                    try:
                        error_frame = self._create_error_frame(f"Error: {str(e)[:30]}")
                        _, buffer = cv2.imencode('.jpg', error_frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                        yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + 
                               buffer.tobytes() + b'\r\n')
                    except:
                        # If even error frame fails, yield simple text
                        yield b'--frame\r\nContent-Type: text/plain\r\n\r\nCamera Error\r\n'
                    
                    time.sleep(0.5)
                    
        except Exception as fatal_error:
            print(f"[Camera] Fatal error in frame generation: {fatal_error}")
            yield b'--frame\r\nContent-Type: text/plain\r\n\r\nFatal Camera Error\r\n'
        
        print("[Camera] Frame generation stopped")
    
    def take_snapshot(self, filename=None):
        """Take a snapshot and save it"""
        try:
            ret, frame = self.read_frame()
            
            if not ret or frame is None:
                return {"ok": False, "msg": "Failed to capture frame"}
            
            if filename is None:
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"snapshots/avatar_tank_{timestamp}.jpg"
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            
            # Save image
            success = cv2.imwrite(filename, frame)
            
            if success:
                return {"ok": True, "filename": filename}
            else:
                return {"ok": False, "msg": "Failed to save image"}
                
        except Exception as e:
            return {"ok": False, "msg": str(e)}
    
    def cleanup(self):
        """Clean up camera resources"""
        with self.lock:
            if self.camera and not isinstance(self.camera, DummyCamera):
                try:
                    self.camera.release()
                except:
                    pass
            self.camera = None


# ============== Module-level lazy initialization ==============

print("[Camera] Camera manager ready for lazy initialization")
camera_manager = None

def get_camera_manager():
    """Get camera manager instance with lazy initialization"""
    global camera_manager
    if camera_manager is None:
        print("[Camera] Lazy initializing camera manager...")
        try:
            camera_manager = CameraManager()
        except Exception as e:
            print(f"[Camera] Failed to initialize camera manager: {e}")
            # Return a minimal dummy manager if initialization fails
            class DummyCameraManager:
                def __init__(self):
                    self.camera = DummyCamera()
                    self.camera_device = "dummy"
                def init_camera(self): return False
                def generate_frames(self): 
                    while True:
                        yield b'--frame\r\nContent-Type: text/plain\r\n\r\nCamera Init Failed\r\n'
                        time.sleep(1)
                def get_status(self): return {"ok": False, "msg": "Camera manager failed to initialize"}
                def set_resolution(self, res): return False
                def take_snapshot(self, fn=None): return {"ok": False, "msg": "Camera not available"}
                def get_shared_frame_data(self): return None, (1280, 720)
                def cleanup(self): pass
            camera_manager = DummyCameraManager()
    return camera_manager

# Export compatibility functions for the old interface
def init_camera():
    """Compatibility function for old interface"""
    try:
        return get_camera_manager().init_camera()
    except Exception as e:
        print(f"[Camera] Init failed: {e}")
        return False

def generate_frames():
    """Compatibility function for old interface"""
    try:
        return get_camera_manager().generate_frames()
    except Exception as e:
        print(f"[Camera] Generate frames failed: {e}")
        # Return error generator
        def error_gen():
            while True:
                yield b'--frame\r\nContent-Type: text/plain\r\n\r\nCamera Error\r\n'
                time.sleep(1)
        return error_gen()

def get_camera_status():
    """Get camera status"""
    try:
        return get_camera_manager().get_status()
    except Exception as e:
        return {"ok": False, "msg": f"Camera status failed: {e}"}

def set_camera_resolution(resolution):
    """Set camera resolution"""
    try:
        return get_camera_manager().set_resolution(resolution)
    except Exception as e:
        print(f"[Camera] Resolution change failed: {e}")
        return False

def take_snapshot(filename=None):
    """Take a snapshot"""
    try:
        return get_camera_manager().take_snapshot(filename)
    except Exception as e:
        return {"ok": False, "msg": f"Snapshot failed: {e}"}

# Export shared frame buffer access for recorder
def get_shared_frame_data():
    """Get shared frame data for recorder"""
    try:
        return get_camera_manager().get_shared_frame_data()
    except Exception as e:
        print(f"[Camera] Shared frame data error: {e}")
        return None, (1280, 720)

# Export camera objects for compatibility (with lazy access)
def get_camera():
    try:
        return get_camera_manager().camera
    except:
        return None

def get_camera_device():
    try:
        return get_camera_manager().camera_device
    except:
        return "unknown"

# Export dummy shared frame buffer variables for recorder compatibility
_last_bgr = None
_last_sz = (1280, 720)
_last_lock = threading.Lock()

print("[Camera] Module loaded successfully (lazy initialization)")
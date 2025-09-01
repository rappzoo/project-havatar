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
    "480p": {"width": 640, "height": 480, "fps": 30},
    "720p": {"width": 1280, "height": 720, "fps": 15},
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
            return 30
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
        
        # Initialize camera
        self.init_camera()
    
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
        
        # Try each device
        for dev in devices_to_try:
            if isinstance(dev, str) and not os.path.exists(dev):
                continue
                
            print(f"[Camera] Testing device: {dev}")
            
            # Try V4L2 backend first (better for Pi Camera)
            cap = self._try_open_camera(dev, cv2.CAP_V4L2, "V4L2")
            if cap:
                return cap, dev
            
            # Try default backend
            cap = self._try_open_camera(dev, None, "default")
            if cap:
                return cap, dev
        
        # Try numeric indices as last resort
        for idx in [0, 1, 2, 3]:
            print(f"[Camera] Testing index: {idx}")
            cap = self._try_open_camera(idx, None, f"index-{idx}")
            if cap:
                return cap, idx
        
        print("[Camera] No working camera found")
        return None, None
    
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
            cap.set(cv2.CAP_PROP_FPS, 15)
            
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
            
            # Try to find working camera
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
                
                # Verify settings
                actual_width = int(self.camera.get(cv2.CAP_PROP_FRAME_WIDTH))
                actual_height = int(self.camera.get(cv2.CAP_PROP_FRAME_HEIGHT))
                actual_fps = self.camera.get(cv2.CAP_PROP_FPS)
                
                print(f"[Camera] Configured: {actual_width}x{actual_height}@{actual_fps:.1f}fps")
                return True
                
            except Exception as e:
                print(f"[Camera] Configuration error: {e}")
                return False
    
    def read_frame(self):
        """Read a frame from the camera with error handling"""
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
        with self._last_lock:
            frame = self._last_bgr.copy() if self._last_bgr is not None else None
            size = self._last_sz
        return frame, size
    
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
        with self.lock:
            return {
                "ok": self.camera is not None,
                "device": self.camera_device,
                "is_dummy": isinstance(self.camera, DummyCamera),
                "resolution": current_resolution,
                "frame_counter": self._frame_counter,
                "error_count": self._error_count
            }
    
    def generate_frames(self):
        """Generate MJPEG frames for HTTP streaming"""
        frame_count = 0
        fps_start = time.time()
        
        while True:
            ret, frame = self.read_frame()
            
            if not ret or frame is None:
                # On error, wait and try to reinit
                time.sleep(1)
                continue
            
            try:
                # Encode frame as JPEG
                encode_params = [cv2.IMWRITE_JPEG_QUALITY, 85]
                _, buffer = cv2.imencode('.jpg', frame, encode_params)
                
                # Yield frame in multipart format
                yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + 
                       buffer.tobytes() + b'\r\n')
                
                frame_count += 1
                
                # Log FPS periodically
                if frame_count % 100 == 0:
                    elapsed = time.time() - fps_start
                    if elapsed > 0:
                        fps = frame_count / elapsed
                        print(f"[Camera] Streaming at {fps:.1f} FPS")
                        frame_count = 0
                        fps_start = time.time()
                        
            except Exception as e:
                print(f"[Camera] Frame encoding error: {e}")
                time.sleep(0.1)
    
    def take_snapshot(self, filename=None):
        """Take a snapshot and save it"""
        ret, frame = self.read_frame()
        
        if not ret or frame is None:
            return {"ok": False, "msg": "Failed to capture frame"}
        
        try:
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


# Create global camera manager instance
print("[Camera] Initializing camera manager...")
camera_manager = CameraManager()

# Export compatibility functions for the old interface
def init_camera():
    """Compatibility function for old interface"""
    return camera_manager.init_camera()

def generate_frames():
    """Compatibility function for old interface"""
    return camera_manager.generate_frames()

def get_camera_status():
    """Get camera status"""
    return camera_manager.get_status()

def set_camera_resolution(resolution):
    """Set camera resolution"""
    return camera_manager.set_resolution(resolution)

def take_snapshot(filename=None):
    """Take a snapshot"""
    return camera_manager.take_snapshot(filename)

# Export shared frame buffer access for recorder
def get_shared_frame_data():
    """Get shared frame data for recorder"""
    return camera_manager.get_shared_frame_data()

# Export camera objects for compatibility
camera = camera_manager.camera
camera_device = camera_manager.camera_device

# Export the shared frame buffer variables for recorder compatibility
_last_bgr = camera_manager._last_bgr
_last_sz = camera_manager._last_sz  
_last_lock = camera_manager._last_lock

print(f"[Camera] Initialized with device: {camera_device}")
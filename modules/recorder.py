#!/usr/bin/env python3
"""
Recording module for Avatar Tank system.
Handles video and audio recording with ffmpeg and resource conflict management.
"""

import subprocess
import threading
import os
import datetime
import time
import sys
from subprocess import PIPE
from pathlib import Path
from typing import Optional, Dict, Any


# Try to get required imports - handle gracefully
try:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)
    
    from modules.device_detector import device_detector, MIC_PLUG
    from modules.camera import get_shared_frame_data, camera_settings, current_resolution
    print(f"[Recorder] Using detected microphone: {MIC_PLUG}")
except ImportError as e:
    print(f"[Recorder] Warning: Could not import modules ({e}), using fallbacks")
    MIC_PLUG = 'default'
    camera_settings = {
        "480p": {"width": 640, "height": 480, "fps": 10},
        "720p": {"width": 1280, "height": 720, "fps": 10},
        "1080p": {"width": 1920, "height": 1080, "fps": 10}
    }
    current_resolution = "720p"
    
    def get_shared_frame_data():
        return None, (1280, 720)


# Ensure directories exist
Path("snapshots").mkdir(exist_ok=True)
Path("recordings").mkdir(exist_ok=True)
Path("sounds").mkdir(exist_ok=True)


class RecordingManager:
    """Enhanced recording manager with better resource management"""
    
    def __init__(self):
        self.process: Optional[subprocess.Popen] = None
        self.writer_thread: Optional[threading.Thread] = None
        self.running = False
        self.lock = threading.Lock()
        self.last_file: Optional[str] = None
        self.recording_mode = 'full'  # 'full', 'video_only', 'failed'
        
        # Audio device management
        self.audio_device_busy = False
        self.recording_stats = {
            'start_time': None,
            'frames_written': 0,
            'bytes_written': 0,
            'errors': 0
        }
        
        # Don't test audio device during initialization to prevent startup issues
        # The test will be done when actually starting a recording
        print("[Recorder] Initialized without audio device testing")
    
    def _test_audio_setup(self):
        """Test audio device availability and compatibility"""
        print(f"[Recorder] Testing audio device: {MIC_PLUG}")
        
        try:
            # Quick test with arecord - but be more careful about it
            test_cmd = ["arecord", "-D", MIC_PLUG, "-f", "cd", "-d", "1", "-q"]
            result = subprocess.run(test_cmd, capture_output=True, timeout=3)
            
            if result.returncode == 0:
                print("[Recorder] Audio device test successful")
                return True
            else:
                print(f"[Recorder] Audio device test failed: {result.stderr.decode()[:100]}...")
                return False
                
        except subprocess.TimeoutExpired:
            print("[Recorder] Audio device test timed out")
            return False
        except Exception as e:
            print(f"[Recorder] Audio device test error: {e}")
            return False

    def _kill_conflicting_processes(self):
        """Kill any processes that might be using the camera or audio device"""
        try:
            # Kill any existing ffmpeg processes
            subprocess.run(['pkill', '-f', 'ffmpeg'], capture_output=True)
            
            # Kill any existing arecord processes
            subprocess.run(['pkill', '-f', 'arecord'], capture_output=True)
            
            # Wait a moment for processes to terminate
            time.sleep(0.5)
            
        except Exception as e:
            print(f"[Recorder] Warning: Could not kill conflicting processes: {e}")

    def start(self, a_bitrate="96k"):
        """Start recording with improved resource management"""
        with self.lock:
            if self.running:
                return {"ok": False, "msg": "Already recording"}
            
            print("[Recorder] Starting recording...")
            
            # Kill any conflicting processes first
            self._kill_conflicting_processes()
            
            # Mark audio device as busy
            self.audio_device_busy = True
            
            # Generate filename with timestamp
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"recordings/rec_{timestamp}.mov"
            self.last_file = output_file
            
            # Get current camera settings
            resolution = camera_settings.get(current_resolution, camera_settings["720p"])
            width, height = resolution["width"], resolution["height"]
            fps = resolution["fps"]
            
            # Build ffmpeg command
            cmd = [
                "ffmpeg",
                "-hide_banner",
                "-loglevel", "error",
                "-f", "v4l2",
                "-framerate", str(fps),
                "-video_size", f"{width}x{height}",
                "-i", "/dev/video0",
            ]
            
            # Add audio if available and working
            audio_available = self._test_audio_setup()
            if audio_available:
                print("[Recorder] Adding audio to recording")
                cmd.extend([
                    "-f", "alsa",
                    "-ar", "44100",
                    "-ac", "1",
                    "-i", MIC_PLUG,
                    "-c:a", "aac",
                    "-b:a", a_bitrate,
                    "-ac", "1"
                ])
                self.recording_mode = 'full'
            else:
                print("[Recorder] No audio available, recording video only")
                self.recording_mode = 'video_only'
            
            # Video encoding options
            cmd.extend([
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-crf", "23",
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                "-y", output_file
            ])
            
            print(f"[Recorder] Command: {' '.join(cmd)}")
            
            try:
                # Start recording process
                self.process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    stdin=subprocess.PIPE
                )
                
                self.running = True
                self.recording_stats['start_time'] = time.time()
                self.recording_stats['frames_written'] = 0
                self.recording_stats['bytes_written'] = 0
                
                # Start monitoring thread
                self.writer_thread = threading.Thread(
                    target=self._monitor_recording,
                    daemon=True
                )
                self.writer_thread.start()
                
                mode_text = "with audio" if audio_available else "video only"
                return {
                    "ok": True,
                    "msg": f"Started recording {mode_text}",
                    "file": output_file,
                    "audio": audio_available,
                    "mode": self.recording_mode
                }
                
            except Exception as e:
                self.running = False
                self.audio_device_busy = False
                print(f"[Recorder] Failed to start recording: {e}")
                return {"ok": False, "msg": f"Recording failed: {str(e)}"}

    def _monitor_recording(self):
        """Monitor recording process in background thread"""
        if not self.process:
            return
            
        try:
            # Wait for process to complete
            stdout, stderr = self.process.communicate()
            
            if self.process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown error"
                print(f"[Recorder] Recording process error: {error_msg}")
                self.recording_stats['errors'] += 1
            else:
                # Try to get file size
                try:
                    if os.path.exists(self.last_file):
                        size = os.path.getsize(self.last_file)
                        self.recording_stats['bytes_written'] = size
                        print(f"[Recorder] Recording completed, file size: {size} bytes")
                except:
                    pass
                    
        except Exception as e:
            print(f"[Recorder] Monitoring error: {e}")
            self.recording_stats['errors'] += 1
        finally:
            with self.lock:
                self.running = False
                self.audio_device_busy = False
                if self.process:
                    self.process = None

    def stop(self):
        """Stop recording with proper cleanup"""
        with self.lock:
            if not self.running or not self.process:
                return {"ok": False, "msg": "Not recording"}
            
            print("[Recorder] Stopping recording...")
            
            try:
                # Send quit signal to ffmpeg
                if self.process and self.process.stdin:
                    self.process.stdin.write(b'q')
                    self.process.stdin.flush()
                
                # Wait for process to finish (with timeout)
                timeout = 5
                start_time = time.time()
                
                while self.process.poll() is None and (time.time() - start_time) < timeout:
                    time.sleep(0.1)
                
                # If still running, terminate forcefully
                if self.process.poll() is None:
                    print("[Recorder] Force terminating recording process")
                    self.process.terminate()
                    try:
                        self.process.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        self.process.kill()
                
                self.running = False
                self.audio_device_busy = False
                
                final_file = self.last_file
                self.last_file = None
                
                return {
                    "ok": True,
                    "msg": "Recording stopped",
                    "file": final_file,
                    "stats": self.recording_stats.copy()
                }
                
            except Exception as e:
                print(f"[Recorder] Error stopping recording: {e}")
                self.running = False
                self.audio_device_busy = False
                return {"ok": False, "msg": f"Stop failed: {str(e)}"}

    def status(self):
        """Get current recording status"""
        return {
            "ok": True,
            "recording": self.running,
            "mode": self.recording_mode,
            "file": self.last_file if self.running else None,
            "stats": self.recording_stats.copy() if self.running else {},
            "audio_device_busy": self.audio_device_busy
        }


# Create global recorder instance
rec = RecordingManager()


def get_recording_status():
    """Get recording status (for API)"""
    return rec.status()
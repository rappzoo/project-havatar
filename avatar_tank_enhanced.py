#!/usr/bin/env python3
import cv2
from flask import Flask, Response, request, jsonify, send_file
from flask_socketio import SocketIO, emit
import subprocess, shutil
from subprocess import PIPE
import threading
import time
import serial
import json
import tempfile
import os
import datetime
from pathlib import Path
import numpy as np
import re
import glob

# WebRTC imports - made optional to prevent startup failures
WEBRTC_AVAILABLE = False
try:
    import asyncio
    from aiortc import RTCPeerConnection, RTCSessionDescription, MediaStreamTrack
    from aiortc.contrib.media import MediaPlayer
    WEBRTC_AVAILABLE = True
    print("[WebRTC] aiortc available - WebRTC audio streaming enabled")
except ImportError as e:
    print(f"[WebRTC] aiortc not available - using WebSocket fallback only: {e}")
    print("[WebRTC] To install: pip install aiortc")
    # Define dummy classes to prevent NameError
    class RTCPeerConnection: pass
    class RTCSessionDescription: pass
    class MediaStreamTrack: pass
    class MediaPlayer: pass

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Folders
Path("snapshots").mkdir(exist_ok=True)
Path("recordings").mkdir(exist_ok=True)
Path("sounds").mkdir(exist_ok=True)

# ============== ENHANCED DEVICE AUTO-DETECTION ==============
class DeviceDetector:
    def __init__(self):
        self.detected_devices = {
            'camera': None,
            'microphone': None,
            'speaker': None,
            'motor_controller': None
        }
        self.scan_devices()
    
    def scan_devices(self):
        print("[Enhanced Detection] Scanning for devices...")
        self._scan_cameras()
        self._scan_audio_devices()
        self._scan_serial_devices()
        self._select_best_devices()
    
    def _scan_cameras(self):
        self.cameras = []
        # Test video devices
        for device_path in ['/dev/video0', '/dev/video1', '/dev/video2']:
            if os.path.exists(device_path):
                try:
                    cap = cv2.VideoCapture(device_path, cv2.CAP_V4L2)
                    if cap.isOpened():
                        ret, frame = cap.read()
                        if ret and frame is not None:
                            # Test MJPEG support
                            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M','J','P','G'))
                            mjpeg_support = cap.get(cv2.CAP_PROP_FOURCC) == cv2.VideoWriter_fourcc('M','J','P','G')
                            
                            self.cameras.append({
                                'path': device_path,
                                'name': f"Camera {device_path}",
                                'mjpeg_support': mjpeg_support,
                                'working': True
                            })
                            print(f"[Camera] Found working camera: {device_path} (MJPEG: {mjpeg_support})")
                        cap.release()
                except Exception as e:
                    print(f"[Camera] {device_path} failed: {e}")
    
    def _scan_audio_devices(self):
        self.audio_input = []
        self.audio_output = []
        
        # Scan input devices
        try:
            result = subprocess.run(['arecord', '-l'], capture_output=True, text=True)
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    match = re.search(r'card\s+(\d+):\s*([^,]+).*device\s+(\d+):\s*([^,]+)', line)
                    if match:
                        card, card_name, device, device_name = match.groups()
                        alsa_device = f"plughw:{card},{device}"
                        
                        # Prioritize USB devices
                        priority = 1 if 'usb' in card_name.lower() or 'pnp' in card_name.lower() else 0
                        
                        self.audio_input.append({
                            'path': alsa_device,
                            'name': f"{card_name.strip()} - {device_name.strip()}",
                            'priority': priority,
                            'card': card,
                            'device': device
                        })
        except Exception as e:
            print(f"[Audio] Input scan failed: {e}")
        
        # Scan output devices
        try:
            result = subprocess.run(['aplay', '-l'], capture_output=True, text=True)
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    match = re.search(r'card\s+(\d+):\s*([^,]+).*device\s+(\d+):\s*([^,]+)', line)
                    if match:
                        card, card_name, device, device_name = match.groups()
                        alsa_device = f"plughw:{card},{device}"
                        
                        # Prioritize USB devices
                        priority = 1 if 'usb' in card_name.lower() or 'uacdemo' in card_name.lower() else 0
                        
                        self.audio_output.append({
                            'path': alsa_device,
                            'name': f"{card_name.strip()} - {device_name.strip()}",
                            'priority': priority,
                            'card': card,
                            'device': device
                        })
        except Exception as e:
            print(f"[Audio] Output scan failed: {e}")
    
    def _scan_serial_devices(self):
        self.serial_ports = []
        serial_devices = glob.glob('/dev/ttyUSB*') + glob.glob('/dev/ttyACM*')
        
        for device_path in serial_devices:
            try:
                # Test for motor controller
                controller_type = self._test_motor_controller(device_path)
                priority = 1 if controller_type != 'unknown' else 0
                
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
        try:
            with serial.Serial(device_path, 115200, timeout=1) as ser:
                time.sleep(0.5)
                ser.reset_input_buffer()
                
                # Test for ESP32 controller
                ser.write(b'STATUS\n')
                time.sleep(0.2)
                response = ser.read_all().decode('utf-8', 'ignore')
                
                if 'voltage' in response.lower() or 'battery' in response.lower():
                    return 'esp32_motor_controller'
                elif response.strip():
                    return 'generic_controller'
                    
        except Exception:
            pass
        return 'unknown'
    
    def _select_best_devices(self):
        # Select best camera (prefer MJPEG support)
        if self.cameras:
            mjpeg_cameras = [c for c in self.cameras if c['mjpeg_support']]
            self.detected_devices['camera'] = mjpeg_cameras[0] if mjpeg_cameras else self.cameras[0]
        
        # Select best microphone (prefer USB)
        if self.audio_input:
            sorted_mics = sorted(self.audio_input, key=lambda x: x['priority'], reverse=True)
            self.detected_devices['microphone'] = sorted_mics[0]
        
        # Select best speaker (prefer USB)
        if self.audio_output:
            sorted_speakers = sorted(self.audio_output, key=lambda x: x['priority'], reverse=True)
            self.detected_devices['speaker'] = sorted_speakers[0]
        
        # Select best motor controller
        if self.serial_ports:
            sorted_controllers = sorted(self.serial_ports, key=lambda x: x['priority'], reverse=True)
            self.detected_devices['motor_controller'] = sorted_controllers[0]
    
    def get_device_config(self):
        return {
            'camera_device': self.detected_devices['camera']['path'] if self.detected_devices['camera'] else '/dev/video0',
            'mic_device': self.detected_devices['microphone']['path'] if self.detected_devices['microphone'] else 'default',
            'speaker_device': self.detected_devices['speaker']['path'] if self.detected_devices['speaker'] else 'default',
            'motor_port': self.detected_devices['motor_controller']['path'] if self.detected_devices['motor_controller'] else '/dev/ttyUSB0'
        }
    
    def print_detection_summary(self):
        print("\n" + "="*60)
        print("ENHANCED AVATAR TANK - DEVICE DETECTION")
        print("="*60)
        
        for device_type, device in self.detected_devices.items():
            if device:
                print(f"  {device_type.upper()}: {device['name']} ({device['path']})")
            else:
                print(f"  {device_type.upper()}: NOT FOUND")
        print("="*60)

# Initialize device detection
device_detector = DeviceDetector()
device_detector.print_detection_summary()
device_config = device_detector.get_device_config()

# Use detected devices
CAMERA_DEVICE = device_config['camera_device']
MIC_PLUG = device_config['mic_device']
SPK_PLUG = device_config['speaker_device']
MOTOR_PORT = device_config['motor_port']

print(f"\n[Enhanced System] Using:")
print(f"  Camera: {CAMERA_DEVICE}")
print(f"  Microphone: {MIC_PLUG}")
print(f"  Speaker: {SPK_PLUG}")
print(f"  Motor: {MOTOR_PORT}")

# Override environment variables for compatibility
os.environ['AV_MIC'] = MIC_PLUG
os.environ['AV_SPK'] = SPK_PLUG

# ============== CAMERA SETTINGS (Enhanced) ==============
current_resolution = "720p"
camera_settings = {
    "480p": {"width": 640, "height": 480, "fps": 30},
    "720p": {"width": 1280, "height": 720, "fps": 15},
    "1080p": {"width": 1920, "height": 1080, "fps": 10}
}

# ============== Camera with Auto-Detection ==============
class DummyCamera:
    def __init__(self):
        self.frame = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.putText(self.frame, "NO CAMERA SIGNAL", (140, 240),
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        cv2.rectangle(self.frame, (50, 50), (590, 430), (0, 255, 255), 2)
    def read(self):
        temp = self.frame.copy()
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        cv2.putText(temp, ts, (250, 280), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,255,0), 1)
        return True, temp
    def release(self): pass
    def set(self, prop, val): return True
    def get(self, prop):
        if prop==cv2.CAP_PROP_FRAME_WIDTH:  return 640
        if prop==cv2.CAP_PROP_FRAME_HEIGHT: return 480
        if prop==cv2.CAP_PROP_FPS:          return 30
        return 0
    def isOpened(self): return True

camera = None
camera_device = None

def find_working_camera():
    # Use detected camera first, then fallback with improved detection
    devices = [CAMERA_DEVICE] + ['/dev/video0','/dev/video1','/dev/video2','/dev/video3']
    
    # First try direct device paths
    for dev in devices:
        if isinstance(dev, str) and not os.path.exists(dev): 
            continue
        print(f"[Camera] Trying {dev}")
        try:
            # Try V4L2 first for better Pi Camera compatibility
            cap = cv2.VideoCapture(dev, cv2.CAP_V4L2)
            if cap.isOpened():
                # Set a reasonable resolution first
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                cap.set(cv2.CAP_PROP_FPS, 15)
                
                ret, fr = cap.read()
                if ret and fr is not None and fr.size > 0:
                    print(f"[Camera] ✓ {dev} (V4L2)")
                    return cap, dev
                cap.release()
            
            # If V4L2 failed, try default backend
            cap = cv2.VideoCapture(dev)
            if cap.isOpened():
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                cap.set(cv2.CAP_PROP_FPS, 15)
                
                ret, fr = cap.read()
                if ret and fr is not None and fr.size > 0:
                    print(f"[Camera] ✓ {dev} (default)")
                    return cap, dev
                cap.release()
        except Exception as e:
            print(f"[Camera] {dev} failed: {e}")
    
    # Try numeric indices as last resort
    for idx in [0, 1, 2, 3]:
        print(f"[Camera] Trying index {idx}")
        try:
            cap = cv2.VideoCapture(idx)
            if cap.isOpened():
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                cap.set(cv2.CAP_PROP_FPS, 15)
                
                ret, fr = cap.read()
                if ret and fr is not None and fr.size > 0:
                    print(f"[Camera] ✓ index {idx}")
                    return cap, idx
                cap.release()
        except Exception as e:
            print(f"[Camera] index {idx} failed: {e}")
    
    print("[Camera] No working camera found")
    return None, None

def init_camera():
    global camera, camera_device
    if camera and not isinstance(camera, DummyCamera):
        try: camera.release()
        except: pass
    new_cam, dev = find_working_camera()
    if not new_cam:
        print("[Camera] Using dummy camera")
        camera = DummyCamera(); camera_device="dummy"; return False
    camera = new_cam; camera_device = dev
    try:
        camera.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M','J','P','G'))
        s = camera_settings[current_resolution]
        camera.set(cv2.CAP_PROP_FRAME_WIDTH,  s["width"])
        camera.set(cv2.CAP_PROP_FRAME_HEIGHT, s["height"])
        camera.set(cv2.CAP_PROP_FPS,          s["fps"])
        aw = camera.get(cv2.CAP_PROP_FRAME_WIDTH)
        ah = camera.get(cv2.CAP_PROP_FRAME_HEIGHT)
        af = camera.get(cv2.CAP_PROP_FPS)
        print(f"[Camera] {aw}x{ah}@{af} initialized")
        return True
    except Exception as e:
        print("[Camera] config error:", e)
        return False

init_camera()

# ============== Motors with Auto-Detection ==============
class MotorController:
    def __init__(self, port=MOTOR_PORT):
        self.ser=None; self.port=port
        self.lock=threading.Lock()
        self.battery_voltage=12.0
        self.connect()
    def connect(self):
        try:
            # Try detected port first, then fallbacks
            ports = [self.port, '/dev/ttyUSB0','/dev/ttyUSB1','/dev/ttyACM0','/dev/ttyACM1']
            for p in ports:
                try:
                    if os.path.exists(p):
                        print(f"[Motor] Try {p}")
                        if self.ser: self.ser.close()
                        self.ser = serial.Serial(p,115200,timeout=0.5)
                        time.sleep(2); self.ser.read_all()
                        print(f"[Motor] ✓ {p}"); self.port=p; return True
                except: continue
            print("[Motor] No serial port found")
            return False
        except Exception as e:
            print("[Motor] connect error:", e); return False
    def send_command(self, cmd):
        with self.lock:
            if not self.ser and not self.connect():
                return {"ok":False,"msg":"no motor connection"}
            try:
                self.ser.write((cmd+'\n').encode()); time.sleep(0.05)
                resp=""; t0=time.time()
                while time.time()-t0<0.5:
                    if self.ser.in_waiting:
                        data=self.ser.read_all().decode('utf-8','ignore'); resp+=data
                        for line in resp.split('\n'):
                            line=line.strip()
                            if line.startswith('{') and line.endswith('}'):
                                try:
                                    j=json.loads(line)
                                    if 'voltage' in j: self.battery_voltage=j['voltage']
                                    return j
                                except: pass
                    time.sleep(0.01)
                return {"ok":True,"msg":"sent","raw":resp}
            except Exception as e:
                self.ser=None; return {"ok":False,"msg":str(e)}
    def move(self,l,r):
        l=max(-255,min(255,int(l))); r=max(-255,min(255,int(r)))
        return self.send_command(f"PWM {l} {r}")
    def stop(self): return self.send_command("STOP")
    def get_battery(self):
        if not self.ser: return {"voltage":12.0,"percentage":75}
        return {"voltage":self.battery_voltage,"percentage":max(0, min(100, (self.battery_voltage-10.0)*20))}

motors = MotorController()

# ============== Keep all your existing TTS, recording, audio, and other classes unchanged ==============
# [Include all the rest of your original code - PiperTTS, PipeRecorder, audio functions, etc.]

# Copy the rest of your original avatar_tank_audio.py from the PiperTTS class onwards...
class PiperTTS:
    def __init__(self):
        self.languages = {
            'en': {'name': 'English', 'dir': '/home/havatar/piper/models/en'},
            'ro': {'name': 'Română',  'dir': '/home/havatar/piper/models/ro'},
            'de': {'name': 'Deutsch', 'dir': '/home/havatar/piper/models/de'},
        }
        self.current_language='en'
        self.bin, self.kind = self._find_piper_bin()  # ('/path/to/piper-cli', 'cli') or ('/path/to/piper', 'piper') or (None,None)

    def _find_piper_bin(self):
        # prefer piper-cli, then piper
        cand = [
            os.path.expanduser("~/piper/bin/piper-cli"),
            "/usr/local/bin/piper-cli", "/usr/bin/piper-cli",
            os.path.expanduser("~/piper/bin/piper"),
            "/usr/local/bin/piper", "/usr/bin/piper",
        ]
        for c in cand:
            if os.path.exists(c):
                return (c, "cli" if c.endswith("piper-cli") else "piper")
        # also try PATH
        for name in ["piper-cli","piper"]:
            w = shutil.which(name)
            if w: return (w, "cli" if name=="piper-cli" else "piper")
        return (None, None)

    def _find_model_pair(self, lang_dir):
        onnx = sorted(glob.glob(os.path.join(lang_dir, "*.onnx")))
        js   = sorted(glob.glob(os.path.join(lang_dir, "*.json")))
        return (onnx[0], js[0]) if onnx and js else (None, None)

    def _find_model_single(self, lang_dir):
        onnx = sorted(glob.glob(os.path.join(lang_dir, "*.onnx")))
        return onnx[0] if onnx else None

    def status(self):
        return {
            "ok": bool(self.bin),
            "binary": self.bin,
            "kind": self.kind,
            "lang": self.current_language
        }

    def speak(self, text, language=None):
        text = (text or "").strip()
        if not text:
            return {"ok": False, "msg": "empty text"}
        if language: self.current_language = language
        if self.current_language not in self.languages:
            return {"ok": False, "msg": f"unsupported lang '{self.current_language}'"}

        lang_dir = self.languages[self.current_language]['dir']
        # 1) Piper CLI?
        if self.bin and self.kind=="cli":
            model, cfg = self._find_model_pair(lang_dir)
            if not model or not cfg:
                return {"ok": False, "msg": f"no Piper model/cfg in {lang_dir}"}
            outwav = "/tmp/tts.wav"
            try:
                p = subprocess.run(
                    [self.bin, "--model", model, "--config", cfg, "--output_file", outwav],
                    input=(text+"\n"), text=True,
                    stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=False
                )
                if p.returncode!=0 or not os.path.exists(outwav) or os.path.getsize(outwav)<1000:
                    return {"ok": False, "msg": (p.stderr.decode() if hasattr(p.stderr,'decode') else p.stderr) or "piper-cli failed"}
                # play
                q = subprocess.run(["aplay","-q","-D", SPK_PLUG, outwav], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
                os.unlink(outwav)
                if q.returncode!=0:
                    return {"ok": False, "msg": f"aplay error: {q.stderr.strip()}"}
                return {"ok": True, "msg": f"Spoken ({self.languages[self.current_language]['name']})"}
            except Exception as e:
                return {"ok": False, "msg": f"tts error: {e}"}

        # 2) Piper (no config file needed)
        if self.bin and self.kind=="piper":
            model = self._find_model_single(lang_dir)
            if not model:
                return {"ok": False, "msg": f"no Piper model in {lang_dir}"}
            outwav = "/tmp/tts.wav"
            try:
                p = subprocess.run(
                    [self.bin, "--model", model, "--output_file", outwav],
                    input=(text+"\n"), text=True,
                    stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=False
                )
                if p.returncode!=0 or not os.path.exists(outwav) or os.path.getsize(outwav)<1000:
                    return {"ok": False, "msg": (p.stderr.decode() if hasattr(p.stderr,'decode') else p.stderr) or "piper failed"}
                q = subprocess.run(["aplay","-q","-D", SPK_PLUG, outwav], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
                os.unlink(outwav)
                if q.returncode!=0:
                    return {"ok": False, "msg": f"aplay error: {q.stderr.strip()}"}
                return {"ok": True, "msg": f"Spoken ({self.languages[self.current_language]['name']})"}
            except Exception as e:
                return {"ok": False, "msg": f"tts error: {e}"}

        # 3) Fallback: espeak-ng -> aplay
        try:
            es = subprocess.Popen(["espeak-ng","-v","en-us","-s","170","--stdout", text], stdout=subprocess.PIPE)
            ap = subprocess.Popen(["aplay","-q","-D", SPK_PLUG], stdin=es.stdout, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=False)
            es.stdout.close()
            ap.wait(timeout=20); es.wait(timeout=20)
            if ap.returncode!=0:
                return {"ok": False, "msg": f"espeak/aplay error: {ap.stderr.read().decode('utf-8','ignore') if ap.stderr else 'fail'}"}
            return {"ok": True, "msg": "Spoken (espeak-ng fallback)"}
        except Exception as e:
            return {"ok": False, "msg": f"no TTS engines available: {e}"}

tts = PiperTTS()

# ============== Shared frame buffer for streaming + recording ==============
_last_bgr = None
_last_sz = (0,0)
_last_lock = threading.Lock()

def generate_frames():
    global _last_bgr, _last_sz, camera
    frame_count=0; fps_start=time.time()
    while True:
        if camera is None:
            init_camera(); time.sleep(1); continue
        try:
            ret, frame = camera.read()
            if not ret or frame is None:
                print("[Video] read failed, reinit..."); init_camera(); time.sleep(1); continue

            h,w = frame.shape[:2]
            # Remove all OpenCV text overlays - info is now shown in UI info bar

            with _last_lock:
                _last_bgr = frame.copy()
                _last_sz  = (w,h)

            _, buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buf.tobytes() + b'\r\n')
            frame_count += 1
        except Exception as e:
            print("[Video] error:", e); time.sleep(1)

# ============== Recording via pipe (no second /dev/video open) ==============
class PipeRecorder:
    def __init__(self):
        self.proc=None
        self.thread=None
        self.running=False
        self.lock=threading.Lock()
        self.last_file=None

    def is_recording(self): return self.running and self.proc and self.proc.poll() is None

    def _spawn_ffmpeg(self, w,h,fps,out,a_bitrate="96k"):
        # Use a separate microphone instance for recording to avoid conflicts
        # Try to use a different ALSA device or add buffer settings
        rec_mic_device = MIC_PLUG if MIC_PLUG.startswith('plughw:') else f"plughw:{MIC_PLUG.split(':')[-1] if ':' in MIC_PLUG else '0,0'}"
        
        cmd = [
            "ffmpeg","-hide_banner","-loglevel","warning","-nostdin",
            "-f","rawvideo","-pix_fmt","bgr24","-s",f"{w}x{h}","-r",str(fps),"-i","-",
            # Enhanced audio capture settings to avoid conflicts
            "-thread_queue_size","2048","-f","alsa","-channels","1","-sample_rate","44100",
            "-buffer_size","8192","-i",rec_mic_device,
            "-c:v","libx264","-preset","veryfast","-crf","23","-pix_fmt","yuv420p",
            "-c:a","aac","-b:a",a_bitrate,"-ar","44100","-ac","1",
            "-shortest","-movflags","+faststart",
            out
        ]
        logf = open(os.path.join("recordings","ffmpeg_record.log"),"ab",buffering=0)
        return subprocess.Popen(cmd, stdin=PIPE, stdout=logf, stderr=logf)

    def _writer(self, fps, w, h):
        frame_period = 1.0/float(fps or 15)
        next_t = time.time()
        while self.running and (_last_bgr is None):
            time.sleep(0.01)
        while self.running:
            with _last_lock:
                fr = None if _last_bgr is None else _last_bgr.copy()
            if fr is not None and self.proc and self.proc.stdin:
                try: self.proc.stdin.write(fr.tobytes())
                except BrokenPipeError: break
            next_t += frame_period
            time.sleep(max(0, next_t - time.time()))
        try:
            if self.proc and self.proc.stdin: self.proc.stdin.close()
        except: pass

    def start(self, a_bitrate="96k"):
        with self.lock:
            if self.is_recording():
                return {"ok":True,"msg":"already recording","file":self.last_file}
            s = camera_settings.get(current_resolution, {"width":1280,"height":720,"fps":15})
            w,h,fps = s["width"], s["height"], s["fps"]
            with _last_lock:
                if _last_sz != (0,0): w,h = _last_sz
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            out = os.path.join("recordings", f"rec_{ts}.mp4")
            self.proc = self._spawn_ffmpeg(w,h,fps,out,a_bitrate=a_bitrate)
            self.running=True; self.last_file=out
            self.thread = threading.Thread(target=self._writer, args=(fps,w,h), daemon=True)
            self.thread.start()
            return {"ok":True,"msg":"recording started","file":out}

    def stop(self):
        with self.lock:
            if not self.running:
                return {"ok":True,"msg":"not recording","file":self.last_file}
            self.running=False
            try:
                if self.thread: self.thread.join(timeout=3)
            except: pass
            try:
                if self.proc and self.proc.poll() is None:
                    self.proc.terminate()
                    try: self.proc.wait(timeout=5)
                    except subprocess.TimeoutExpired: self.proc.kill()
            finally:
                self.proc=None
            return {"ok":True,"msg":"recording stopped","file":self.last_file}

    def status(self):
        return {"ok":True,"recording":self.is_recording(),"file":self.last_file}

rec = PipeRecorder()

# ============== ALSA volume/mute helpers (same endpoints you tested) ==============
def _parse_aplay_l():
    try:
        out = subprocess.run(["aplay","-l"], capture_output=True, text=True).stdout
    except Exception:
        return []
    rx = re.compile(r"card\s+(\d+):\s*([^\[]+)\[.*?\],\s*device\s+(\d+):\s*([^\[]+)\[", re.I)
    devs=[]
    for line in out.splitlines():
        m=rx.search(line)
        if m:
            card=int(m.group(1)); cardname=m.group(2).strip()
            dev=int(m.group(3));  devname=m.group(4).strip()
            devs.append({"card":card,"device":dev,"name":f"{cardname} {devname}"})
    return devs

def _amixer_controls(card_str):
    # card_str like "plughw:1,0" -> card index 1
    m=re.search(r":(\d+),", card_str)
    card = m.group(1) if m else "0"
    try:
        p=subprocess.run(["amixer","-c",card,"scontrols"],capture_output=True,text=True)
        if p.returncode!=0: return []
        return [line.split("'")[1] for line in p.stdout.splitlines() if "Simple mixer control" in line and "'" in line]
    except: return []
def _pick_playback_ctrl():
    prefs=["Speaker","PCM","Master","Playback"]; cs=_amixer_controls(SPK_PLUG)
    for n in prefs:
        if n in cs: return n
    return cs[0] if cs else None
def _pick_capture_ctrl():
    prefs=["Mic","Capture","Input"]; cs=_amixer_controls(MIC_PLUG)
    for n in prefs:
        if n in cs: return n
    return cs[0] if cs else None
def _set_volume(card_str,ctrl,pct,mute=None):
    m=re.search(r":(\d+),", card_str); card = m.group(1) if m else "0"
    if ctrl is None: return {"ok":False,"msg":f"no control on card {card}"}
    args=["amixer","-c",card,"-M","sset",ctrl]
    if pct is not None: args.append(f"{max(0,min(100,int(pct)))}%")
    if mute is True: args.append("mute")
    elif mute is False: args.append("unmute")
    p=subprocess.run(args,capture_output=True,text=True)
    if p.returncode!=0: return {"ok":False,"msg":p.stderr.strip() or "amixer failed"}
    return {"ok":True,"msg":"ok"}
def _get_volume(card_str,ctrl):
    m=re.search(r":(\d+),", card_str); card = m.group(1) if m else "0"
    if ctrl is None: return {"ok":False,"msg":f"no control on card {card}"}
    p=subprocess.run(["amixer","-c",card,"sget",ctrl],capture_output=True,text=True)
    if p.returncode!=0: return {"ok":False,"msg":p.stderr.strip() or "amixer failed"}
    m2=re.search(r"\[(\d{1,3})%\]", p.stdout); vol=int(m2.group(1)) if m2 else None
    muted="off" in p.stdout.lower()
    return {"ok":True,"control":ctrl,"volume":vol,"muted":muted}

# ============== Mic streaming (AAC/ADTS) ==============
def _ffmpeg_mic_proc():
    cmd = [
        "ffmpeg","-hide_banner","-loglevel","error","-nostdin",
        "-thread_queue_size","64",  # Minimal queue for ultra-low latency
        "-f","alsa","-i",MIC_PLUG,
        "-ac","1","-ar","16000",  # 16kHz optimal for voice
        "-c:a","pcm_u8",  # Fastest codec
        "-f","wav","-fflags","+nobuffer+flush_packets+discardcorrupt",
        "-flags","low_delay","-avoid_negative_ts","disabled",
        "-max_delay","0","-buffer_size","256",  # Ultra-small buffer
        "-probesize","32","-analyzeduration","0",
        "-use_wallclock_as_timestamps","1",
        "-"
    ]
    return subprocess.Popen(cmd, stdout=PIPE, stderr=subprocess.DEVNULL, bufsize=0)

# ============== Prediction service ==============
class SimplePredict:
    def __init__(self, dict_dir="/home/havatar/dicts"):
        self.dict_dir = dict_dir
        self.words = []
        self.reload()

    def reload(self):
        self.words.clear()
        try:
            os.makedirs(self.dict_dir, exist_ok=True)
            
            # Load words from the specific words.txt file first
            words_file = os.path.join(self.dict_dir, "words.txt")
            if os.path.exists(words_file):
                try:
                    with open(words_file, "r", encoding="utf-8", errors="ignore") as f:
                        for line in f:
                            w = line.strip()
                            if w:
                                self.words.append(w)
                    print(f"[Predict] loaded {len(self.words)} words from words.txt")
                except Exception as e:
                    print(f"[Predict] failed to load words.txt: {e}")
            
            # Load additional words from other dictionary files
            for fn in glob.glob(os.path.join(self.dict_dir, "*.txt")):
                if os.path.basename(fn) == "words.txt":
                    continue  # Already loaded
                try:
                    with open(fn, "r", encoding="utf-8", errors="ignore") as f:
                        for line in f:
                            w = line.strip()
                            if w:
                                self.words.append(w)
                    # Special logging for custom words file
                    if os.path.basename(fn) == "custom_words.txt":
                        print(f"[Predict] loaded custom learned words from {fn}")
                except Exception as e:
                    print("[Predict] failed to load", fn, e)
            
            # Remove duplicates and sort
            self.words = sorted(set(self.words))
            print(f"[Predict] total {len(self.words)} unique words loaded")
            
            # Add some common words if dictionary is empty
            if not self.words:
                self.words = ["hello", "help", "please", "thank", "you", "yes", "no", "stop", "go", "forward", "back", "left", "right", "battery", "camera", "audio", "video", "record", "snapshot", "move", "motor", "system", "status", "reboot", "volume", "microphone", "speaker"]
                print(f"[Predict] using fallback words: {len(self.words)} words")
                
        except Exception as e:
            print(f"[Predict] reload error: {e}")
            self.words = ["error", "loading", "words"]  # Minimal fallback

    def suggest(self, prefix, limit=50):
        if not prefix:
            return []
        
        # Extract just the last word being typed for word-only prediction
        prefix_parts = prefix.strip().split()
        if not prefix_parts:
            return []
        
        # Get only the last word for prediction (ignore preceding text)
        current_word = prefix_parts[-1].lower()
        
        matches = []
        
        # Enhanced diacritics support
        import unicodedata
        def normalize_text(text):
            # Remove diacritics but keep original structure
            normalized = ''.join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn')
            return normalized.lower()
        
        def text_similarity(word, query):
            """Calculate text similarity for better Romanian matching"""
            word_norm = normalize_text(word)
            query_norm = normalize_text(query)
            
            # Exact match gets highest score
            if word.lower().startswith(query.lower()):
                return 100
            # Normalized match gets high score
            elif word_norm.startswith(query_norm):
                return 90
            # Contains match gets medium score
            elif query.lower() in word.lower():
                return 70
            # Normalized contains gets lower score
            elif query_norm in word_norm:
                return 60
            else:
                return 0
        
        # Score and collect all potential matches
        word_scores = []
        for word in self.words:
            score = text_similarity(word, current_word)
            if score > 0:
                word_scores.append((score, word))
        
        # Sort by score (highest first) and extract words
        word_scores.sort(key=lambda x: x[0], reverse=True)
        
        # Return only individual words (no phrase building)
        for score, word in word_scores[:limit]:
            matches.append(word)
            
        return matches[:limit]

    def add_words_from_text(self, text):
        """Extract and save new words from typed text"""
        if not text or len(text.strip()) < 2:
            return 0  # Skip very short text
        
        try:
            # Clean and extract words
            import re
            # Remove punctuation and split into words
            words = re.findall(r'\b[a-zA-ZăâîșțĂÂÎȘȚ]+\b', text.lower())
            
            new_words = []
            for word in words:
                # Only save words that are 2+ characters and not already in dictionary
                if len(word) >= 2 and word not in self.words:
                    new_words.append(word)
                    self.words.append(word)
            
            # Save new words to the custom words file
            if new_words:
                custom_words_file = os.path.join(self.dict_dir, "custom_words.txt")
                with open(custom_words_file, "a", encoding="utf-8") as f:
                    for word in new_words:
                        f.write(word + "\n")
                
                # Resort the words list for better prediction performance
                self.words = sorted(set(self.words))
                print(f"[Predict] Learned {len(new_words)} new words: {', '.join(new_words[:5])}{'...' if len(new_words) > 5 else ''}")
                return len(new_words)
        except Exception as e:
            print(f"[Predict] Error learning words: {e}")
        
        return 0

_predict = SimplePredict()

# ------------- Routes -------------
@app.route('/video')
def video(): return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/set_resolution', methods=['POST'])
def set_resolution():
    global current_resolution
    data=request.get_json() or {}
    r=data.get('resolution','720p')
    if r in camera_settings:
        current_resolution=r; init_camera()
        return jsonify({"ok":True,"resolution":current_resolution})
    return jsonify({"ok":False,"msg":"Invalid resolution"})

@app.route('/camera_status')
def camera_status():
    return jsonify({"ok":camera is not None,"device":camera_device if camera else None,
                    "is_dummy": isinstance(camera, DummyCamera),"resolution":current_resolution})

@app.route('/speak', methods=['POST'])
def speak():
    d=request.get_json() or {}; text=d.get('text',''); lang=d.get('language')
    if not text: return jsonify({"ok":False,"msg":"No text provided"})
    
    # Learn new words from the text for future predictions
    try:
        learned_count = _predict.add_words_from_text(text)
        if learned_count > 0:
            print(f"[TTS] Learned {learned_count} new words for predictions")
    except Exception as e:
        print(f"[TTS] Word learning error: {e}")
    
    # Proceed with text-to-speech
    result = tts.speak(text, lang)
    return jsonify(result)

@app.route('/set_language', methods=['POST'])
def set_language():
    d=request.get_json() or {}; lang=d.get('language','en')
    if lang in tts.languages:
        tts.current_language=lang
        return jsonify({"ok":True,"language":lang,"name":tts.languages[lang]['name']})
    return jsonify({"ok":False,"msg":"Invalid language"})

@app.route('/tts_status')
def tts_status(): return jsonify(tts.status())

@app.route('/motor/<direction>', methods=['POST'])
def motor_control(direction):
    d=request.get_json() or {}; sp=int(d.get('speed',150))
    if direction=='forward':  res=motors.move(sp,sp)
    elif direction=='backward':res=motors.move(-sp,-sp)
    elif direction=='left':    res=motors.move(-sp,sp)
    elif direction=='right':   res=motors.move(sp,-sp)
    elif direction=='stop':    res=motors.stop()
    else: return jsonify({"ok":False,"msg":"Invalid direction"})
    return jsonify(res)

@app.route('/battery')
def battery_status(): return jsonify(motors.get_battery())

@app.route('/system_status')
def system_status():
    return jsonify({
        "camera":{"ok":camera is not None,"device":camera_device,"is_dummy":isinstance(camera,DummyCamera)},
        "motors":{"ok":motors.ser is not None,"port":motors.port if motors.ser else None},
        "tts": tts.status(),
        "audio": {"mic": MIC_PLUG, "speaker": SPK_PLUG},
        "battery":motors.get_battery()
    })

@app.route('/snapshot', methods=['POST'])
def take_snapshot():
    try:
        if camera is None: return jsonify({"ok":False,"msg":"Camera not initialized"})
        ret, fr = camera.read()
        if ret and fr is not None:
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            fn = f"snapshots/avatar_tank_{ts}.jpg"; cv2.imwrite(fn, fr)
            return jsonify({"ok":True,"filename":fn})
        return jsonify({"ok":False,"msg":"Failed to capture frame"})
    except Exception as e:
        return jsonify({"ok":False,"msg":str(e)})

@app.route('/play_sound/<int:sound_id>', methods=['POST'])
def play_sound(sound_id):
    try:
        idx = (sound_id % 10) + 1
        # Look for files in ./sounds: sound{idx}.* or {idx}.*
        exts = ['mp3','wav','ogg','flac','m4a','aac','opus']
        candidates = []
        import glob
        for stem in (f"sound{idx}", f"{idx}", f"Sound{idx}"):
            for ext in exts:
                candidates += glob.glob(os.path.join('sounds', f'{stem}.{ext}'))
        chosen = candidates[0] if candidates else None
        if chosen and os.path.exists(chosen):
            # Decode with ffmpeg to WAV (48k/2ch) then play on your ALSA device
            import tempfile, subprocess
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as t:
                out = t.name
            r = subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-i',chosen,
                                '-ar','48000','-ac','2','-f','wav','-acodec','pcm_s16le','-y',out],
                               stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
            if r.returncode != 0:
                try: os.unlink(out)
                except: pass
                return jsonify({'ok':False,'msg':'Decode failed: '+(r.stderr.strip()[-200:] if r.stderr else 'ffmpeg error')})
            r2 = subprocess.run(['aplay','-D', SPK_PLUG, out], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
            try: os.unlink(out)
            except: pass
            if r2.returncode==0:
                return jsonify({'ok':True,'msg':'Played file: '+os.path.basename(chosen)})
            return jsonify({'ok':False,'msg':'Playback failed: '+(r2.stderr.strip() or 'aplay error')})
        # Fallback: generate the old beep
        freqs=[220,262,294,330,349,392,440,494,523,587]
        f=freqs[sound_id%10]
        import tempfile, subprocess
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as t:
            wav=t.name
        cmd=['ffmpeg','-f','lavfi','-i',f'sine=frequency={f}:duration=0.5',
             '-ar','48000','-ac','2','-f','wav','-acodec','pcm_s16le','-y',wav]
        r=subprocess.run(cmd,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        if r.returncode==0:
            rr=subprocess.run(['aplay','-D',SPK_PLUG,wav],capture_output=True,text=True)
            try: os.unlink(wav)
            except: pass
            if rr.returncode==0: return jsonify({'ok':True,'msg':'Beep '+str(sound_id+1)})
            return jsonify({'ok':False,'msg':'Beep playback failed: '+(rr.stderr.strip() or 'aplay error')})
        return jsonify({'ok':False,'msg':'Beep generation failed'})
    except Exception as e:
        return jsonify({'ok':False,'msg':str(e)})

@app.route('/audio/status')
def audio_status():
    return jsonify({"ok":True,"speaker":_get_volume(SPK_PLUG,_pick_playback_ctrl()),"mic":_get_volume(MIC_PLUG,_pick_capture_ctrl()),"devices":{"speaker":SPK_PLUG,"mic":MIC_PLUG}})

@app.route('/audio/set_volume', methods=['POST'])
def audio_set_volume():
    d=request.get_json() or {}; which=d.get('type','speaker'); pct=d.get('volume'); mute=d.get('mute')
    if which=='speaker': res=_set_volume(SPK_PLUG,_pick_playback_ctrl(),pct,mute)
    elif which=='mic':   res=_set_volume(MIC_PLUG,_pick_capture_ctrl(),pct,mute)
    else: return jsonify({"ok":False,"msg":"type must be 'speaker' or 'mic'"})
    return jsonify(res)

@app.route('/audio/volume')
def audio_volume():
    return jsonify({"ok":True,"speaker":_get_volume(SPK_PLUG,_pick_playback_ctrl()),"mic":_get_volume(MIC_PLUG,_pick_capture_ctrl())})

@app.route('/audio/devices')
def audio_devices():
    return jsonify({
        "mic_detected": _parse_arecord_l(),
        "spk_detected": _parse_aplay_l(),
        "MIC_PLUG": MIC_PLUG,
        "SPK_PLUG": SPK_PLUG,
        "override_hint": "export AV_MIC='plughw:CARD,DEV' AV_SPK='plughw:CARD,DEV' before starting the app to force"
    })

# ============== WebRTC Audio Streaming with aiortc ==============
# WebRTC peer connections storage
webrtc_peers = {}
webrtc_lock = threading.Lock()

if WEBRTC_AVAILABLE:
    class AudioStreamTrack(MediaStreamTrack):
        """
        A custom audio track that captures from ALSA device
        """
        kind = "audio"
        
        def __init__(self, device=MIC_PLUG):
            super().__init__()
            self.player = None
            self.audio_track = None
            self.device = device
            
            # Try multiple approaches to create working MediaPlayer
            self._setup_media_player()
        
        def _setup_media_player(self):
            """Try multiple approaches to setup MediaPlayer with ALSA"""
            approaches = [
                # Approach 1: Direct ALSA device
                lambda: self._try_direct_alsa(),
                # Approach 2: Use 'default' ALSA device
                lambda: self._try_default_alsa(),
                # Approach 3: Use pulse audio if available
                lambda: self._try_pulse_audio(),
                # Approach 4: Use ffmpeg directly with ALSA
                lambda: self._try_ffmpeg_alsa()
            ]
            
            for i, approach in enumerate(approaches, 1):
                try:
                    print(f"[WebRTC] Trying audio setup approach {i}...")
                    if approach():
                        print(f"[WebRTC] Audio setup approach {i} successful")
                        return
                except Exception as e:
                    print(f"[WebRTC] Audio setup approach {i} failed: {e}")
            
            print("[WebRTC] All audio setup approaches failed")
        
        def _try_direct_alsa(self):
            """Try using the detected ALSA device directly"""
            options = {
                'sample_rate': '16000',
                'channels': '1',
                'sample_format': 's16le'
            }
            
            try:
                # For aiortc MediaPlayer, we need to format the device as a proper input
                if self.device and self.device != 'default':
                    # Convert plughw:X,Y to proper ALSA format for aiortc
                    device_input = f"alsa={self.device}"
                    print(f"[WebRTC] Trying direct ALSA with: {device_input}")
                    self.player = MediaPlayer(device_input, options=options)
                else:
                    # Use default ALSA device
                    print(f"[WebRTC] Trying direct ALSA with: alsa=default")
                    self.player = MediaPlayer("alsa=default", options=options)
                
                if self.player and hasattr(self.player, 'audio') and self.player.audio:
                    self.audio_track = self.player.audio
                    print(f"[WebRTC] Direct ALSA setup successful")
                    return True
                else:
                    print(f"[WebRTC] Direct ALSA player created but no audio track")
                    return False
            except Exception as e:
                print(f"[WebRTC] Direct ALSA failed: {e}")
                return False
        
        def _try_default_alsa(self):
            """Try using default ALSA device"""
            try:
                options = {
                    'sample_rate': '16000',
                    'channels': '1'
                }
                
                print(f"[WebRTC] Trying default ALSA device")
                self.player = MediaPlayer("alsa=default", options=options)
                if self.player and hasattr(self.player, 'audio') and self.player.audio:
                    self.audio_track = self.player.audio
                    print(f"[WebRTC] Default ALSA setup successful")
                    return True
                else:
                    print(f"[WebRTC] Default ALSA player created but no audio track")
                    return False
            except Exception as e:
                print(f"[WebRTC] Default ALSA failed: {e}")
                return False
        
        def _try_pulse_audio(self):
            """Try using PulseAudio if available"""
            try:
                options = {
                    'sample_rate': '16000',
                    'channels': '1'
                }
                
                print(f"[WebRTC] Trying PulseAudio")
                self.player = MediaPlayer("pulse", format="pulse", options=options)
                if self.player and hasattr(self.player, 'audio') and self.player.audio:
                    self.audio_track = self.player.audio
                    print(f"[WebRTC] PulseAudio setup successful")
                    return True
                else:
                    print(f"[WebRTC] PulseAudio player created but no audio track")
                    return False
            except Exception as e:
                print(f"[WebRTC] PulseAudio failed: {e}")
                return False
        
        def _try_ffmpeg_alsa(self):
            """Try using FFmpeg with specific ALSA parameters"""
            options = {
                'f': 'alsa',
                'ar': '16000',
                'ac': '1',
                'sample_fmt': 's16'
            }
            
            # Try with specific device first, then default
            devices_to_try = []
            if self.device and self.device != 'default':
                devices_to_try.append(self.device)
            devices_to_try.extend(['default', 'plughw:0,0', 'hw:0,0'])
            
            for device in devices_to_try:
                try:
                    self.player = MediaPlayer(device, format='alsa', options=options)
                    if self.player and hasattr(self.player, 'audio'):
                        self.audio_track = self.player.audio
                        print(f"[WebRTC] FFmpeg ALSA setup successful with device: {device}")
                        return True
                except Exception as e:
                    print(f"[WebRTC] FFmpeg ALSA failed with device {device}: {e}")
                    continue
            
            return False
        
        async def recv(self):
            """Receive audio frame from the media player"""
            if self.audio_track:
                try:
                    frame = await self.audio_track.recv()
                    if frame:
                        print(f"[WebRTC] Audio frame received: {frame.format}, {frame.sample_rate}Hz")
                        return frame
                    else:
                        print(f"[WebRTC] Audio track returned None frame")
                except Exception as e:
                    print(f"[WebRTC] Audio recv error: {e}")
                    # Try to recreate player on error once
                    if not hasattr(self, '_recreation_attempted'):
                        self._recreation_attempted = True
                        print(f"[WebRTC] Attempting to recreate MediaPlayer...")
                        self._setup_media_player()
                        # Try again after recreation
                        try:
                            if self.audio_track:
                                frame = await self.audio_track.recv()
                                if frame:
                                    return frame
                        except Exception as e2:
                            print(f"[WebRTC] Retry after recreation failed: {e2}")
            
            # Fallback: Generate silent audio frames to keep WebRTC connection alive
            return self._generate_silent_frame()
        
        def _generate_silent_frame(self):
            """Generate a silent audio frame as fallback"""
            try:
                import numpy as np
                from av import AudioFrame
                
                # Generate 20ms of silence at 16kHz (320 samples)
                samples = np.zeros(320, dtype=np.int16)
                frame = AudioFrame.from_ndarray(samples.reshape(1, -1), format='s16', layout='mono')
                frame.sample_rate = 16000
                frame.pts = getattr(self, '_frame_count', 0) * 320
                self._frame_count = getattr(self, '_frame_count', 0) + 1
                
                # Add some debug info periodically
                if self._frame_count % 100 == 0:  # Every 2 seconds
                    print(f"[WebRTC] Generated {self._frame_count} silent frames (MediaPlayer not working)")
                
                return frame
            except Exception as e:
                print(f"[WebRTC] Error generating silent frame: {e}")
                return None
        
        def stop(self):
            """Stop the audio track and cleanup"""
            try:
                if self.audio_track:
                    self.audio_track = None
                if self.player:
                    # Safely close the player
                    if hasattr(self.player, 'close'):
                        try:
                            # Run any cleanup in event loop if needed
                            import asyncio
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            loop.run_until_complete(self.player.close())
                            loop.close()
                        except:
                            pass
                    self.player = None
                print("[WebRTC] AudioStreamTrack stopped")
            except Exception as e:
                print(f"[WebRTC] Error stopping AudioStreamTrack: {e}")
else:
    # Dummy class when WebRTC is not available
    class AudioStreamTrack:
        def __init__(self, device=None):
            pass

# Conditional WebRTC routes - only available if aiortc is installed
if WEBRTC_AVAILABLE:
    @app.route('/webrtc/offer', methods=['POST'])
    def webrtc_offer():
        """
        Handle WebRTC offer for audio streaming
        """
        try:
            data = request.get_json()
            if not data or 'sdp' not in data or 'type' not in data:
                return jsonify({'ok': False, 'error': 'Invalid offer data'})
            
            offer = RTCSessionDescription(sdp=data['sdp'], type=data['type'])
            
            # Create new peer connection
            pc = RTCPeerConnection()
            peer_id = f"audio_{len(webrtc_peers)}_{int(time.time())}"
            
            with webrtc_lock:
                webrtc_peers[peer_id] = pc
            
            # Add audio track
            try:
                audio_track = AudioStreamTrack()
                pc.addTrack(audio_track)
                print(f"[WebRTC] Audio track added for peer {peer_id}")
            except Exception as e:
                print(f"[WebRTC] Failed to add audio track: {e}")
                # Continue without audio track - let WebRTC handle the negotiation
            
            @pc.on("connectionstatechange")
            async def on_connectionstatechange():
                print(f"[WebRTC] Connection state: {pc.connectionState}")
                if pc.connectionState == "closed":
                    with webrtc_lock:
                        webrtc_peers.pop(peer_id, None)
            
            # Handle offer using thread-safe approach
            def handle_offer_sync():
                try:
                    # Use asyncio.run() which handles event loop creation properly
                    async def process_offer():
                        await pc.setRemoteDescription(offer)
                        answer = await pc.createAnswer()
                        await pc.setLocalDescription(answer)
                        return {
                            'sdp': pc.localDescription.sdp,
                            'type': pc.localDescription.type
                        }
                    
                    # Run the async function in a proper event loop
                    import asyncio
                    try:
                        # Try to get existing loop
                        loop = asyncio.get_running_loop()
                        # If we're in an existing loop, we need to run in a thread
                        import concurrent.futures
                        with concurrent.futures.ThreadPoolExecutor() as executor:
                            future = executor.submit(asyncio.run, process_offer())
                            return future.result(timeout=10)
                    except RuntimeError:
                        # No running loop, safe to use asyncio.run
                        return asyncio.run(process_offer())
                        
                except Exception as e:
                    print(f"[WebRTC] Offer processing error: {e}")
                    raise
            
            # Execute the offer handling
            answer_data = handle_offer_sync()
            
            print(f"[WebRTC] Offer processed successfully for peer {peer_id}")
            return jsonify({
                'ok': True,
                'answer': answer_data,
                'peer_id': peer_id
            })
            
        except Exception as e:
            print(f"[WebRTC] Offer error: {e}")
            # Clean up on error
            try:
                with webrtc_lock:
                    if 'peer_id' in locals():
                        webrtc_peers.pop(peer_id, None)
            except:
                pass
            return jsonify({'ok': False, 'error': str(e)})

    @app.route('/webrtc/close/<peer_id>', methods=['POST'])
    def webrtc_close(peer_id):
        """
        Close WebRTC connection
        """
        try:
            with webrtc_lock:
                pc = webrtc_peers.pop(peer_id, None)
            
            if pc:
                # Stop all tracks before closing connection
                try:
                    for sender in pc.getSenders():
                        if sender.track:
                            if hasattr(sender.track, 'stop'):
                                sender.track.stop()
                except Exception as e:
                    print(f"[WebRTC] Error stopping tracks: {e}")
                
                # Close connection using thread-safe approach
                def close_connection_sync():
                    try:
                        async def process_close():
                            await pc.close()
                        
                        import asyncio
                        try:
                            # Try to get existing loop
                            loop = asyncio.get_running_loop()
                            # If we're in an existing loop, run in a thread
                            import concurrent.futures
                            with concurrent.futures.ThreadPoolExecutor() as executor:
                                future = executor.submit(asyncio.run, process_close())
                                future.result(timeout=5)
                        except RuntimeError:
                            # No running loop, safe to use asyncio.run
                            asyncio.run(process_close())
                            
                    except Exception as e:
                        print(f"[WebRTC] Close processing error: {e}")
                
                close_connection_sync()
                print(f"[WebRTC] Connection {peer_id} closed and cleaned up")
            
            return jsonify({'ok': True, 'msg': 'Connection closed'})
        except Exception as e:
            print(f"[WebRTC] Error closing connection {peer_id}: {e}")
            return jsonify({'ok': False, 'error': str(e)})
else:
    # Dummy WebRTC routes when aiortc is not available
    @app.route('/webrtc/offer', methods=['POST'])
    def webrtc_offer():
        return jsonify({'ok': False, 'error': 'WebRTC not available - aiortc not installed'})
    
    @app.route('/webrtc/close/<peer_id>', methods=['POST'])
    def webrtc_close(peer_id):
        return jsonify({'ok': False, 'error': 'WebRTC not available - aiortc not installed'})

# Simple WebSocket fallback for browsers that don't support WebRTC properly
websocket_active = False
websocket_process = None

@socketio.on('start_simple_audio')
def handle_start_simple_audio():
    global websocket_active, websocket_process
    
    if websocket_active:
        emit('audio_status', {'status': 'already_active'})
        return
    
    try:
        websocket_active = True
        
        # Ultra-simple, robust audio streaming
        cmd = [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin",
            "-f", "alsa", "-i", MIC_PLUG,
            "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
            "-f", "wav", "-"
        ]
        
        websocket_process = subprocess.Popen(cmd, stdout=PIPE, stderr=subprocess.DEVNULL, bufsize=1024)
        
        def audio_worker():
            try:
                while websocket_active and websocket_process:
                    chunk = websocket_process.stdout.read(1024)
                    if not chunk:
                        break
                    # Send binary data via WebSocket
                    socketio.emit('audio_data', chunk, room=request.sid)
            except Exception as e:
                print(f"[SimpleAudio] Error: {e}")
            finally:
                if websocket_process:
                    try:
                        websocket_process.terminate()
                    except:
                        pass
        
        thread = threading.Thread(target=audio_worker, daemon=True)
        thread.start()
        
        emit('audio_status', {'status': 'started', 'format': 'pcm_16khz'})
        print(f"[SimpleAudio] Started for client {request.sid}")
        
    except Exception as e:
        websocket_active = False
        emit('audio_status', {'status': 'error', 'message': str(e)})
        print(f"[SimpleAudio] Error: {e}")

@socketio.on('stop_simple_audio')
def handle_stop_simple_audio():
    global websocket_active, websocket_process
    
    try:
        websocket_active = False
        
        if websocket_process:
            try:
                websocket_process.terminate()
                websocket_process.wait(timeout=2)
            except:
                try:
                    websocket_process.kill()
                except:
                    pass
            websocket_process = None
        
        emit('audio_status', {'status': 'stopped'})
        print(f"[SimpleAudio] Stopped for client {request.sid}")
        
    except Exception as e:
        emit('audio_status', {'status': 'error', 'message': str(e)})
        print(f"[SimpleAudio] Error: {e}")

@socketio.on('disconnect')
def handle_disconnect():
    global websocket_active
    if websocket_active:
        handle_stop_simple_audio()
    print(f"[WebSocket] Client {request.sid} disconnected")

@app.route('/mic_test')
def mic_test():
    # ffmpeg tends to be more robust than arecord across formats
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as t: out=t.name
    cmd=["ffmpeg","-hide_banner","-loglevel","warning","-f","alsa","-i",MIC_PLUG,"-t","2","-ac","1","-ar","44100","-f","wav","-y",out]
    p=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    if p.returncode!=0 or not os.path.exists(out) or os.path.getsize(out)<1000:
        try: os.unlink(out)
        except: pass
        return jsonify({"ok":False,"msg":p.stderr.strip() or "ffmpeg mic capture failed"})
    return send_file(out, as_attachment=True, download_name="mic_test.wav")

# ---- recording endpoints (pipe from live frames) ----
@app.route('/start_recording', methods=['POST'])
def start_recording():
    d=request.get_json() or {}; abr=d.get("audio_bitrate","96k")
    return jsonify(rec.start(a_bitrate=abr))

@app.route('/stop_recording', methods=['POST'])
def stop_recording(): return jsonify(rec.stop())

@app.route('/recording_status')
def recording_status(): return jsonify(rec.status())

# ---- prediction endpoints ----
@app.route("/predict")
def predict_endpoint():
    q = request.args.get("q", "", type=str)[:200]
    limit = max(1, min(200, request.args.get("limit", 50, type=int)))
    res = _predict.suggest(q, limit)
    return jsonify({"ok": True, "q": q, "count": len(res), "items": res})

@app.route("/predict/reload", methods=["POST"])
def predict_reload():
    _predict.reload()
    return jsonify({"ok": True, "count": len(_predict.words)})

@app.route("/predict/learn", methods=["POST"])
def predict_learn():
    """Manually add words from text to the prediction dictionary"""
    d = request.get_json() or {}
    text = d.get('text', '')
    if not text:
        return jsonify({"ok": False, "msg": "No text provided"})
    
    learned_count = _predict.add_words_from_text(text)
    return jsonify({"ok": True, "learned": learned_count, "total_words": len(_predict.words)})

@app.route("/predict/learned")
def predict_learned():
    """Get the list of custom learned words"""
    try:
        custom_words_file = os.path.join(_predict.dict_dir, "custom_words.txt")
        learned_words = []
        if os.path.exists(custom_words_file):
            with open(custom_words_file, "r", encoding="utf-8") as f:
                learned_words = [line.strip() for line in f if line.strip()]
        
        return jsonify({"ok": True, "learned_words": learned_words, "count": len(learned_words)})
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)})

# ---- system control ----
@app.route('/system/reboot', methods=['POST'])
def system_reboot():
    try:
        # Log the reboot request
        print("[System] Reboot requested via web interface")
        # Execute reboot with a small delay to allow response to be sent
        import threading
        def delayed_reboot():
            time.sleep(2)
            subprocess.run(['sudo', 'reboot'], check=False)
        threading.Thread(target=delayed_reboot, daemon=True).start()
        return jsonify({"ok": True, "msg": "System reboot initiated"})
    except Exception as e:
        return jsonify({"ok": False, "msg": f"Reboot failed: {e}"})

@app.route('/')
def index():
    return """<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Avatar Tank - Freedom Interface</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.2/socket.io.js"></script>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&display=swap');
    *{box-sizing:border-box;margin:0;padding:0}
    body{
      font-family:'Orbitron','Courier New',monospace;
      background:linear-gradient(135deg,#1a1a1a 0%,#2d2d2d 25%,#404040 50%,#2d2d2d 75%,#1a1a1a 100%);
      color:#cccccc;min-height:100vh;overflow-x:auto;
      background-attachment:fixed;
      position:relative;
    }
    body::before{
      content:'';position:fixed;top:0;left:0;width:100%;height:100%;
      background:radial-gradient(circle at 20% 20%, rgba(255,140,0,0.05) 0%, transparent 50%),
                 radial-gradient(circle at 80% 80%, rgba(255,165,0,0.05) 0%, transparent 50%),
                 radial-gradient(circle at 40% 60%, rgba(128,128,128,0.03) 0%, transparent 50%);
      pointer-events:none;z-index:-1;
    }
    .container{
      display:grid;
      grid-template-areas:
        "tts tts tts"
        "motor video audio"
        "sound video audio"
        "log log log";
      grid-template-columns:280px 1fr 340px;
      grid-template-rows:80px 1fr auto 70px;
      gap:15px;padding:15px;min-height:100vh;
    }
    .panel{
      background:linear-gradient(145deg,rgba(45,45,45,0.95),rgba(60,60,60,0.95));
      border:2px solid;
      border-image:linear-gradient(45deg,#ff8c00,#808080,#ffa500,#696969) 1;
      border-radius:16px;padding:16px;
      box-shadow:0 0 25px rgba(255,140,0,.3),inset 0 0 15px rgba(128,128,128,.05);
      position:relative;backdrop-filter:blur(5px);
    }
    .panel::before{
      content:'';position:absolute;inset:-3px;
      background:linear-gradient(45deg,#ff8c00,#808080,#ffa500,#696969);
      border-radius:16px;z-index:-1;opacity:.15;filter:blur(10px);
      animation:glow 3s ease-in-out infinite alternate;
    }
    @keyframes glow{0%{opacity:.15;filter:blur(10px)}100%{opacity:.25;filter:blur(12px)}}
    .tts{
      grid-area:tts;display:flex;align-items:center;gap:12px;
      background:linear-gradient(145deg,rgba(20,20,50,0.95),rgba(30,30,60,0.95));
    }
    .tts input{
      flex:1;background:rgba(20,20,20,0.8);border:2px solid #ff8c00;
      color:#cccccc;padding:12px;border-radius:10px;font:inherit;
      box-shadow:inset 0 0 10px rgba(255,140,0,.2);transition:.3s;
    }
    .tts input:focus{box-shadow:inset 0 0 15px rgba(255,140,0,.4),0 0 10px rgba(255,140,0,.3);outline:none}
    .pills{display:flex;gap:8px;flex-wrap:wrap}
    .pill{
      background:linear-gradient(145deg,#555,#666);border:1px solid #ff8c00;
      color:#cccccc;padding:6px 12px;border-radius:18px;cursor:pointer;
      font-size:11px;transition:.2s;box-shadow:0 2px 5px rgba(0,0,0,.3);
    }
    .pill:hover{background:#ff8c00;color:#000;transform:translateY(-1px);box-shadow:0 4px 10px rgba(255,140,0,.4)}
    .diacritic-pill {
      background:#444;border-color:#ff8c00;color:#ff8c00;font-weight:bold;
      font-size:16px;padding:6px 12px;min-width:32px;text-align:center;
    }
    .diacritic-pill:hover {
      background:#ff8c00;color:#000;border-color:#ffaa00;
    }
    .btn{
      background:linear-gradient(145deg,#4a4a4a,#2a2a2a);
      border:2px solid #ff8c00;color:#cccccc;padding:10px 14px;
      border-radius:10px;cursor:pointer;font:inherit;transition:.3s;
      box-shadow:0 2px 8px rgba(0,0,0,.3);
    }
    .btn:hover{
      background:#ff8c00;color:#000;box-shadow:0 0 15px #ff8c00;
      transform:translateY(-2px);
    }
    .btn-orange{border-color:#ff6600;color:#ff6600;font-weight:bold}
    .btn-orange:hover{background:#ff6600;color:#000;box-shadow:0 0 15px #ff6600}
    .lang{display:flex;border:2px solid #ff8c00;border-radius:10px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.3)}
    .lang button{background:#555;border:none;color:#cccccc;padding:10px 14px;cursor:pointer;flex:1;transition:.2s}
    .lang .active{background:#ff8c00;color:#000;font-weight:bold}
    .video{
      grid-area:video;text-align:center;position:relative;
      background:linear-gradient(145deg,rgba(30,30,30,0.95),rgba(40,40,40,0.95));
    }
    .video img{
      width:100%;max-width:920px;border-radius:12px;
      border:3px solid #ff8c00;box-shadow:0 0 20px rgba(255,140,0,.4);
    }
    .video-info-bar{
      display:flex;justify-content:space-between;align-items:center;
      background:rgba(0,0,0,0.8);border:1px solid #ff8c00;
      border-radius:8px;padding:8px 12px;margin:10px auto 0 auto;
      font-size:11px;flex-wrap:wrap;gap:15px;
      max-width:920px;width:100%;box-sizing:border-box;
    }
    .info-item{
      display:flex;align-items:center;gap:4px;
      min-width:fit-content;
    }
    .info-label{
      color:#808080;font-weight:bold;
    }
    .video-overlay{
      position:absolute;top:15px;left:15px;right:15px;
      display:flex;justify-content:space-between;align-items:flex-start;
      pointer-events:none;z-index:10;
    }
    .bandwidth-indicator{
      background:rgba(0,0,0,0.85);border:1px solid #ff8c00;
      border-radius:8px;padding:6px 10px;font-size:11px;
      display:flex;align-items:center;gap:6px;
      box-shadow:0 2px 8px rgba(0,0,0,.5);
    }
    .bandwidth-bar{
      width:50px;height:6px;background:#333;border-radius:3px;overflow:hidden;
    }
    .bandwidth-fill{
      height:100%;background:linear-gradient(90deg,#ff4444,#ffaa00,#44ff44);
      transition:width .5s;border-radius:3px;
    }
    .datetime-display{
      background:rgba(0,0,0,0.85);border:1px solid #808080;
      border-radius:8px;padding:6px 10px;font-size:11px;text-align:right;
      box-shadow:0 2px 8px rgba(0,0,0,.5);
    }
    .motor{
      grid-area:motor;
      background:linear-gradient(145deg,rgba(20,40,20,0.95),rgba(30,60,30,0.95));
    }
    .grid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;margin:15px 0}
    .mbtn{
      background:linear-gradient(145deg,#2a2a2a,#1a1a1a);
      border:3px solid #00ff00;color:#00ff00;padding:16px;
      border-radius:12px;cursor:pointer;font-size:20px;font-weight:bold;
      transition:.3s;box-shadow:0 3px 10px rgba(0,0,0,.4);
    }
    .mbtn:hover{
      background:#00ff00;color:#000;box-shadow:0 0 15px #00ff00;
      transform:translateY(-2px);
    }
    .stop{border-color:#f00!important;color:#f00!important}
    .stop:hover{background:#f00!important;color:#fff!important;box-shadow:0 0 15px #f00!important}
    .led{display:inline-block;width:12px;height:12px;border-radius:50%;margin-left:8px;animation:pulse 2s infinite}
    @keyframes pulse{0%,100%{opacity:1}50%{opacity:.5}}
    .ok{background:#0f0;box-shadow:0 0 8px #0f0}
    .warn{background:#ff0;box-shadow:0 0 8px #ff0}
    .err{background:#f00;box-shadow:0 0 8px #f00}
    .audio{
      grid-area:audio;
      background:linear-gradient(145deg,rgba(40,20,40,0.95),rgba(60,30,60,0.95));
    }
    .group{margin:15px 0;padding:12px;border:1px solid #444;border-radius:10px;background:rgba(0,0,0,.2)}
    .group h4{color:#ff6600;margin-bottom:10px;font-weight:bold;text-shadow:0 0 5px #ff6600}
    .slider{
      width:100%;background:#555;-webkit-appearance:none;
      height:10px;border-radius:5px;outline:none;
      box-shadow:inset 0 0 5px rgba(0,0,0,.5);
    }
    .slider::-webkit-slider-thumb{
      -webkit-appearance:none;appearance:none;width:20px;height:20px;
      border-radius:50%;background:#ff8c00;cursor:pointer;
      box-shadow:0 0 10px rgba(255,140,0,.5);
    }
    .vu{
      width:100%;height:24px;background:#000;border:2px solid #ff8c00;
      border-radius:6px;margin:10px 0;overflow:hidden;
      box-shadow:inset 0 0 10px rgba(0,0,0,.5);
    }
    .vubar{
      height:100%;background:linear-gradient(90deg,#44ff44,#ffaa00,#ff4444);
      border-radius:4px;transition:width .1s;position:relative;
    }
    .vubar::after{
      content:'';position:absolute;top:0;left:0;right:0;bottom:0;
      background:linear-gradient(90deg,transparent 0%,rgba(255,255,255,.2) 50%,transparent 100%);
      animation:sweep 2s infinite;
    }
    @keyframes sweep{0%{transform:translateX(-100%)}100%{transform:translateX(100%)}}}
    .sound{
      grid-area:sound;
      background:linear-gradient(145deg,rgba(40,30,20,0.95),rgba(60,45,30,0.95));
    }
    .soundgrid{display:grid;grid-template-columns:1fr 1fr;gap:8px}
    .sbtn{
      background:linear-gradient(145deg,#333,#444);border:2px solid #ff6600;
      color:#ff6600;padding:10px;border-radius:8px;cursor:pointer;
      font-size:12px;transition:.2s;box-shadow:0 2px 5px rgba(0,0,0,.3);
    }
    .sbtn:hover{background:#ff6600;color:#000;transform:translateY(-1px);box-shadow:0 4px 10px rgba(255,102,0,.4)}
    .log{
      grid-area:log;background:rgba(0,0,0,0.9);border:2px solid #808080;
      border-radius:10px;padding:12px;font-size:12px;overflow-y:auto;
      max-height:60px;font-family:'Courier New',monospace;
      box-shadow:inset 0 0 10px rgba(128,128,128,.2);color:#cccccc;
    }
    .res{display:flex;gap:8px;margin:10px 0}
    .res .r{
      background:#555;border:2px solid #ff8c00;color:#cccccc;
      padding:6px 12px;border-radius:6px;cursor:pointer;font-size:11px;
      transition:.2s;box-shadow:0 2px 5px rgba(0,0,0,.3);
    }
    .res .active{background:#ff8c00;color:#000;font-weight:bold}
    .res .r:hover{transform:translateY(-1px);box-shadow:0 4px 8px rgba(255,140,0,.3)}
    .row{display:flex;justify-content:space-between;align-items:center;gap:10px}
    .bat{display:flex;align-items:center;gap:12px;margin:12px 0}
    .batbar{
      flex:1;height:18px;background:#333;border:2px solid #ff8c00;
      border-radius:10px;overflow:hidden;box-shadow:inset 0 0 5px rgba(0,0,0,.5);
    }
    .batfill{
      height:100%;border-radius:8px;transition:width .5s,background .5s;
      box-shadow:0 0 10px currentColor;
    }
    h3{text-shadow:0 0 10px currentColor;margin-bottom:10px;font-weight:bold}
  </style>
</head>
<body>
<div class="container">
  <div class="panel tts">
  <div id="recent" class="pills" style="margin-bottom:5px;display:none">
    <div class="pill" onclick="pick(recentPhrases[0])" id="recent1" style="background:#444;border-color:#888"></div>
    <div class="pill" onclick="pick(recentPhrases[1])" id="recent2" style="background:#444;border-color:#888"></div>
  </div>
  <div id="predictions" class="pills" style="flex-wrap:wrap;margin-bottom:8px;display:none"></div>
  <div id="diacritics" class="pills" style="flex-wrap:wrap;margin-bottom:8px;display:none">
    <div class="pill diacritic-pill" onclick="insertDiacritic('ă')">ă</div>
    <div class="pill diacritic-pill" onclick="insertDiacritic('â')">â</div>
    <div class="pill diacritic-pill" onclick="insertDiacritic('î')">î</div>
    <div class="pill diacritic-pill" onclick="insertDiacritic('ș')">ș</div>
    <div class="pill diacritic-pill" onclick="insertDiacritic('ț')">ț</div>
  </div>
    <div style="display:flex;gap:10px;align-items:center;flex:1">
      <input id="tts" placeholder="Type message to speak..." oninput="predictText(this.value)" onkeydown="handleTTSKeydown(event)" style="flex:1" />
      <button class="btn" onclick="clearText()" style="padding:8px;border-color:#ff6600;color:#ff6600" title="Clear text">✕</button>
    </div>
    <button class="btn btn-orange" onclick="speak()">🗣 Speak</button>
    <div class="lang">
      <button id="len" class="active" onclick="setLang('en')">EN</button>
      <button id="lro" onclick="setLang('ro')">RO</button>
      <button id="lde" onclick="setLang('de')">DE</button>
    </div>
  </div>

  <div class="panel motor">
    <h3>🎮 Motor <span id="mled" class="led warn"></span></h3>
    <div class="grid">
      <div></div> <button class="mbtn" onmousedown="go('forward')" onmouseup="stopM()" onmouseleave="stopM()">▲</button> <div></div>
      <button class="mbtn" onmousedown="go('left')" onmouseup="stopM()" onmouseleave="stopM()">◀</button>
      <button class="mbtn stop" onclick="estop()">⬛</button>
      <button class="mbtn" onmousedown="go('right')" onmouseup="stopM()" onmouseleave="stopM()">▶</button>
      <div></div> <button class="mbtn" onmousedown="go('backward')" onmouseup="stopM()" onmouseleave="stopM()">▼</button> <div></div>
    </div>
    <div class="row">
      <span>Speed:</span>
      <input id="spd" type="range" class="slider" min="50" max="255" value="150" oninput="document.getElementById('spdv').textContent=this.value" />
      <span id="spdv" style="min-width:40px;color:#ff6600;font-weight:bold">150</span>
    </div>
    <div class="bat">
      <span>🔋</span>
      <div class="batbar"><div id="batf" class="batfill" style="width:75%;background:#0f0"></div></div>
      <span id="batp">75%</span>
    </div>
  </div>

  <div class="panel video">
    <img id="vid" src="/video" alt="Video feed" />
    <div class="video-info-bar">
      <div class="info-item">
        <span class="info-label">📡 Bandwidth:</span>
        <span id="bwtext">-- KB/s</span>
      </div>
      <div class="info-item">
        <span class="info-label">📊 Total:</span>
        <span id="total-data">0 MB</span>
      </div>
      <div class="info-item">
        <span class="info-label">⏰</span>
        <div id="datetime">Loading...</div>
      </div>
      <div class="info-item">
        <span class="info-label">📹</span>
        <span id="resolution-display">720p</span>
      </div>
      <div class="info-item">
        <span class="info-label">📊 FPS:</span>
        <span id="fps">--</span>
      </div>
      <div class="info-item">
        <span class="info-label">🔋</span>
        <span id="battery-display">75%</span>
      </div>
    </div>
    <div style="margin-top:8px">
      <span id="cstat" style="font-size:12px;color:#0f0">Camera: Initializing</span>
      <span id="uptime" style="margin-left:15px;font-size:10px;opacity:0.8">Uptime: 00:00:00</span>
    </div>
  </div>

  <div class="panel audio">
    <h3>🎬 Media</h3>
    <div class="group">
      <h4>📹 Resolution</h4>
      <div class="res">
        <button id="r480p" class="r" onclick="setRes('480p')">480p</button>
        <button id="r720p" class="r active" onclick="setRes('720p')">720p</button>
        <button id="r1080p" class="r" onclick="setRes('1080p')">1080p</button>
      </div>
      <div class="row" style="gap:6px;flex-wrap:wrap">
        <button class="btn" onclick="snap()">📸 Snapshot</button>
        <button class="btn" onclick="statusAll()">🔍 System</button>
        <button class="btn" onclick="recStart()">⚪ Start Rec</button>
        <button class="btn" onclick="recStop()">⏸ Stop Rec</button>
        <button class="btn" onclick="rebootSystem()" style="border-color:#ff0000;color:#ff0000">⚡ Reboot</button>
      </div>
    </div>

    <div class="group">
      <h4>🎤 Microphone</h4>
      <div class="vu"><div id="vu" class="vubar" style="width:0%"></div></div>
      <div class="row" style="flex-wrap:wrap;gap:8px">
        <button id="micbtn" class="btn" onclick="toggleMicrophone()" style="font-size:12px;flex:1">🎤 Start Audio</button>
        <button class="btn" onclick="testMic()" style="font-size:11px">🔬 Test</button>
      </div>
      <div class="row" style="margin-top:8px">
        <span id="mic-status" style="font-size:10px;color:#808080;flex:1">Ready</span>
        <span id="audio-quality" style="font-size:10px;color:#44ff44">WebRTC Ready</span>
      </div>
      <audio id="audio-playback" autoplay style="display:none"></audio>
    </div>

    <div class="group">
      <h4>🔊 Speaker</h4>
      <input id="vol" type="range" class="slider" min="0" max="100" value="70" oninput="setVol(this.value)" />
      <div class="row">
        <span>Volume: <span id="volv">70%</span></span>
        <button id="mutebtn" class="btn" onclick="toggleMute()">🔊</button>
      </div>
    </div>
  </div>

  <div class="panel sound">
    <h3>🎵 Sounds</h3>
    <div class="soundgrid">
      <button class="sbtn" onclick="beep(0)">🎵 1</button><button class="sbtn" onclick="beep(1)">🎵 2</button>
      <button class="sbtn" onclick="beep(2)">🎵 3</button><button class="sbtn" onclick="beep(3)">🎵 4</button>
      <button class="sbtn" onclick="beep(4)">🎵 5</button><button class="sbtn" onclick="beep(5)">🎵 6</button>
      <button class="sbtn" onclick="beep(6)">🎵 7</button><button class="sbtn" onclick="beep(7)">🎵 8</button>
      <button class="sbtn" onclick="beep(8)">🎵 9</button><button class="sbtn" onclick="beep(9)">🎵 10</button>
    </div>
  </div>

  <div id="log" class="panel log">Avatar Tank Interface ready</div>
</div>

<script>
console.log('Loading JavaScript...');

// Essential utility functions - defined first
const sid = function(id) {
  const element = document.getElementById(id);
  if (!element) console.warn('Element not found:', id);
  return element;
};

const log = function(m) { 
  const logEl = document.getElementById('log');
  if (logEl) logEl.textContent = '[' + new Date().toLocaleTimeString() + '] ' + m; 
  console.log(m);
};

let lang = 'en';
let predictionTimeout = null;
let recentPhrases = [];
let startTime = Date.now();
let frameCount = 0;
let lastFrameTime = Date.now();
let currentFPS = 0;
let bandwidthSamples = [];
let vuMeterActive = false;
let totalDataUsed = 0; // Cumulative data usage in KB
let lastBandwidthUpdate = Date.now();

// Enhanced monitoring functions
function updateDateTime() {
  try {
    const now = new Date();
    const timeStr = now.toLocaleTimeString('en-GB', {hour12: false}); // 24-hour format
    const dateStr = now.toLocaleDateString('en-GB'); // DD/MM/YYYY format
    const datetimeEl = sid('datetime');
    if (datetimeEl) {
      datetimeEl.innerHTML = `${timeStr}<br><small>${dateStr}</small>`;
    }
    
    // Update uptime
    const uptimeEl = sid('uptime');
    if (uptimeEl) {
      const uptime = Date.now() - startTime;
      const hours = Math.floor(uptime / 3600000);
      const minutes = Math.floor((uptime % 3600000) / 60000);
      const seconds = Math.floor((uptime % 60000) / 1000);
      uptimeEl.textContent = `Uptime: ${hours.toString().padStart(2,'0')}:${minutes.toString().padStart(2,'0')}:${seconds.toString().padStart(2,'0')}`;
    }
  } catch (e) {
    console.error('DateTime update error:', e);
  }
}

function updateBandwidth() {
  try {
    const vid = sid('vid');
    const now = Date.now();
    
    if (vid && vid.naturalWidth > 0) {
      frameCount++;
      const timeDiff = now - lastFrameTime;
      
      if (timeDiff > 1000) { // Update every second
        currentFPS = frameCount / (timeDiff / 1000);
        frameCount = 0;
        lastFrameTime = now;
        
        const fpsEl = sid('fps');
        if (fpsEl) {
          fpsEl.textContent = `FPS: ${currentFPS.toFixed(1)}`;
        }
        
        // Simulate bandwidth based on FPS and resolution
        const resolution = document.querySelector('.res .active')?.textContent || '720p';
        const resMultiplier = {'480p': 0.5, '720p': 1.0, '1080p': 2.0}[resolution] || 1.0;
        const estimatedBandwidth = currentFPS * resMultiplier * 0.1; // Rough estimate
        
        bandwidthSamples.push(estimatedBandwidth);
        if (bandwidthSamples.length > 10) bandwidthSamples.shift();
        
        const avgBandwidth = bandwidthSamples.reduce((a, b) => a + b, 0) / bandwidthSamples.length;
        updateBandwidthDisplay(avgBandwidth);
      }
    }
  } catch (e) {
    console.error('Bandwidth update error:', e);
  }
}

function updateBandwidthDisplay(bandwidth) {
  try {
    const bwText = sid('bwtext');
    const now = Date.now();
    
    if (bwText) {
      // Convert to KB/s (rough estimation based on resolution and FPS)
      const resolution = document.querySelector('.res .active')?.textContent || '720p';
      const resMultiplier = {'480p': 0.8, '720p': 1.5, '1080p': 3.2}[resolution] || 1.5;
      const kbps = Math.round(bandwidth * resMultiplier * 100); // Estimate KB/s
      
      bwText.textContent = `${kbps} KB/s`;
      
      // Calculate cumulative data usage
      const timeDiff = (now - lastBandwidthUpdate) / 1000; // seconds
      if (timeDiff > 0) {
        totalDataUsed += (kbps * timeDiff); // KB
        lastBandwidthUpdate = now;
        
        // Update total data display
        const totalDataEl = sid('total-data');
        if (totalDataEl) {
          const totalMB = totalDataUsed / 1024;
          if (totalMB >= 1024) {
            const totalGB = totalMB / 1024;
            totalDataEl.textContent = `${totalGB.toFixed(2)} GB`;
            totalDataEl.style.color = totalGB > 2 ? '#ff4444' : (totalGB > 1 ? '#ffaa00' : '#44ff44');
          } else {
            totalDataEl.textContent = `${totalMB.toFixed(1)} MB`;
            totalDataEl.style.color = totalMB > 500 ? '#ffaa00' : '#44ff44';
          }
        }
      }
      
      // Color coding optimized for 4G modem usage (green = low/efficient, red = high/wasteful)
      if (kbps < 400) {
        bwText.style.color = '#44ff44'; // Green - Low bandwidth (good for 4G data conservation)
      } else if (kbps < 800) {
        bwText.style.color = '#ffaa00'; // Orange - Medium bandwidth  
      } else {
        bwText.style.color = '#ff4444'; // Red - High bandwidth (bad for 4G data usage)
      }
    }
    
    // Update resolution display
    const resDisplay = sid('resolution-display');
    if (resDisplay) {
      const activeRes = document.querySelector('.res .active')?.textContent || '720p';
      resDisplay.textContent = activeRes;
    }
    
    // Update battery display
    const batteryDisplay = sid('battery-display');
    if (batteryDisplay) {
      fetch('/battery')
        .then(response => response.json())
        .then(data => {
          if (data.percentage !== undefined) {
            batteryDisplay.textContent = `${Math.round(data.percentage)}%`;
            if (data.percentage > 50) {
              batteryDisplay.style.color = '#44ff44';
            } else if (data.percentage > 20) {
              batteryDisplay.style.color = '#ffaa00';
            } else {
              batteryDisplay.style.color = '#ff4444';
            }
          }
        })
        .catch(e => console.error('Battery update error:', e));
    }
  } catch (e) {
    console.error('Bandwidth display error:', e);
  }
}

function enhancedVUMeter() {
  try {
    const vuBar = sid('vu');
    if (!vuBar) return; // Exit if VU bar not found
    
    // Directly get element without logging warning - 'mica' element may not exist
    const micAudio = document.getElementById('mica');
    // Only proceed with audio-based VU meter if micAudio element exists
    if (vuMeterActive && micAudio && !micAudio.paused) {
      // Create a more realistic VU meter simulation
      const baseLevel = 20 + Math.random() * 30;
      const spike = Math.random() > 0.8 ? Math.random() * 40 : 0;
      const level = Math.min(100, baseLevel + spike);
      
      vuBar.style.width = `${level}%`;
      
      // Add color coding based on level
      if (level > 80) {
        vuBar.style.boxShadow = '0 0 15px #ff0000';
      } else if (level > 60) {
        vuBar.style.boxShadow = '0 0 10px #ffff00';
      } else {
        vuBar.style.boxShadow = '0 0 5px #00ff00';
      }
    } else {
      // Show inactive VU meter
      vuBar.style.width = '0%';
      vuBar.style.boxShadow = 'none';
    }
  } catch (e) {
    // Silently handle errors to prevent console spam
  }
}
function clearText() {
  try {
    const input = document.getElementById('tts');
    if (input) {
      input.value = '';
      input.focus();
      // Hide predictions when clearing
      const predictions = document.getElementById('predictions');
      if (predictions) predictions.style.display = 'none';
      log('Text cleared');
    }
  } catch (e) {
    console.error('Clear text error:', e);
  }
}

function pick(t) { 
  const input = document.getElementById('tts');
  if (input) {
    const currentText = input.value;
    const words = currentText.trim().split(/\s+/);
    
    if (words.length > 0 && currentText.trim().length > 0) {
      // Replace the last word being typed
      words[words.length - 1] = t;
      input.value = words.join(' ');
    } else {
      // If empty or only whitespace, just set the word
      input.value = t;
    }
    
    // Add a space after the word for continued typing
    input.value += ' ';
    input.focus();
    
    // Hide predictions when selecting
    const predictions = document.getElementById('predictions');
    if (predictions) predictions.style.display = 'none';
  }
}
function updateRecentPhrases(phrase) {
  if (!phrase || phrase.length < 3) return;
  recentPhrases = recentPhrases.filter(p => p !== phrase);
  recentPhrases.unshift(phrase);
  recentPhrases = recentPhrases.slice(0, 2);
  
  const recentDiv = document.getElementById('recent');
  const recent1 = document.getElementById('recent1');
  const recent2 = document.getElementById('recent2');
  
  if (recentPhrases.length > 0) {
    recent1.textContent = recentPhrases[0];
    recent1.style.display = 'inline-block';
    if (recentPhrases.length > 1) {
      recent2.textContent = recentPhrases[1];
      recent2.style.display = 'inline-block';
    } else {
      recent2.style.display = 'none';
    }
    recentDiv.style.display = 'flex';
  } else {
    recentDiv.style.display = 'none';
  }
}

async function predictText(query) {
  clearTimeout(predictionTimeout);
  const predictions = document.getElementById('predictions');
  
  if (!query || query.length < 1) {
    if (predictions) predictions.style.display = 'none';
    return;
  }
  
  predictionTimeout = setTimeout(async () => {
    try {
      const response = await fetch('/predict?q=' + encodeURIComponent(query) + '&limit=3');
      const data = await response.json();
      
      if (data.ok && data.items && data.items.length > 0 && predictions) {
        predictions.innerHTML = '';
        data.items.forEach(function(item) {
          const pill = document.createElement('div');
          pill.className = 'pill';
          pill.textContent = item;
          pill.onclick = function() { 
            pick(item); 
            predictions.style.display = 'none';
          };
          predictions.appendChild(pill);
        });
        predictions.style.display = 'flex';
        console.log('Showing', data.items.length, 'predictions');
      } else {
        if (predictions) predictions.style.display = 'none';
        console.log('No predictions found for:', query);
      }
    } catch (e) {
      console.error('Prediction error:', e);
      if (predictions) predictions.style.display = 'none';
    }
  }, 200); // Reduced timeout for faster response
}

function handleTTSKeydown(event) {
  if (event.key === 'Enter') {
    event.preventDefault();
    speak();
  }
  if (event.key === 'Escape') {
    const predictions = document.getElementById('predictions');
    if (predictions) predictions.style.display = 'none';
  }
}
async function speak() {
  try {
    const textEl = document.getElementById('tts');
    if (!textEl) return;
    const text = textEl.value.trim(); 
    if (!text) return;
    
    log('Speaking...');
    const r = await fetch('/speak', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({text: text, language: lang})
    });
    const j = await r.json(); 
    
    if (j.ok) {
      // Add to recent phrases when successfully spoken
      updateRecentPhrases(text);
      log('Speech: ' + j.msg);
    } else {
      log('Speech error: ' + j.msg);
    }
  } catch (e) {
    log('Speak error: ' + e.message);
  }
}

async function setLang(l) {
  try {
    lang = l;
    ['len', 'lro', 'lde'].forEach(function(id) {
      const el = sid(id);
      if (el) el.classList.remove('active');
    });
    const mapping = {'en': 'len', 'ro': 'lro', 'de': 'lde'};
    const activeEl = sid(mapping[l]);
    if (activeEl) activeEl.classList.add('active');
    
    // Show/hide Romanian diacritics pills
    const diacriticsEl = sid('diacritics');
    if (diacriticsEl) {
      diacriticsEl.style.display = (l === 'ro') ? 'flex' : 'none';
    }
    
    await fetch('/set_language', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({language: l})
    });
    
    log(`Language: ${l.toUpperCase()}${l === 'ro' ? ' (diacritics available)' : ''}`);
  } catch (e) {
    log('Set language error: ' + e.message);
  }
}

// Function to insert diacritics at cursor position
function insertDiacritic(char) {
  try {
    const input = sid('tts');
    if (!input) return;
    
    const start = input.selectionStart;
    const end = input.selectionEnd;
    const text = input.value;
    
    // Insert the diacritic at cursor position
    input.value = text.substring(0, start) + char + text.substring(end);
    
    // Move cursor after the inserted character
    input.setSelectionRange(start + 1, start + 1);
    input.focus();
    
    // Trigger prediction update
    predictText(input.value);
    
    log(`Inserted: ${char}`);
  } catch (e) {
    log('Insert diacritic error: ' + e.message);
  }
}

let moving = false;
let cur = null;

async function mcmd(dir, speed) { 
  try {
    const led = sid('mled');
    if (led) led.className = 'led warn'; // Show working state
    
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 3000); // 3 second timeout
    
    const r = await fetch('/motor/' + dir, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({speed: parseInt(speed)}),
      signal: controller.signal
    });
    
    clearTimeout(timeoutId);
    const j = await r.json(); 
    
    if (led) {
      led.className = 'led ' + (j.ok ? 'ok' : 'err');
    }
    
    if (!j.ok) {
      console.warn('Motor command failed:', j.msg);
    }
  } catch (e) { 
    const led = sid('mled');
    if (led) led.className = 'led err';
    if (e.name !== 'AbortError') {
      console.error('Motor error:', e);
      log('Motor error: ' + e.message);
    }
  } 
}

function go(d) { 
  if (moving && cur === d) return; 
  moving = true; 
  cur = d; 
  const speedEl = sid('spd');
  const speed = speedEl ? speedEl.value : 150;
  mcmd(d, speed); 
  log('Move ' + d); 
}

function stopM() { 
  if (!moving) return; 
  moving = false; 
  cur = null; 
  const speedEl = sid('spd');
  const speed = speedEl ? speedEl.value : 150;
  mcmd('stop', speed); 
  log('Stop'); 
}

function estop() { 
  moving = false; 
  cur = null; 
  const speedEl = sid('spd');
  const speed = speedEl ? speedEl.value : 150;
  mcmd('stop', speed); 
  log('EMERGENCY STOP'); 
}

async function setRes(r) {
  try {
    log('Set resolution ' + r + '...');
    const res = await fetch('/set_resolution', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({resolution: r})
    });
    const j = await res.json();
    if (j.ok) {
      ['r480p', 'r720p', 'r1080p'].forEach(function(id) {
        const el = sid(id);
        if (el) el.classList.remove('active');
      });
      const activeEl = sid('r' + r);
      if (activeEl) activeEl.classList.add('active');
      
      setTimeout(function() { 
        const v = sid('vid'); 
        if (v) {
          const s = v.src; 
          v.src = ''; 
          v.src = s + '?t=' + Date.now(); 
        }
      }, 800);
      log('Resolution changed to ' + r);
    } else { 
      log('Resolution change failed: ' + j.msg); 
    }
  } catch (e) {
    log('Set resolution error: ' + e.message);
  }
}

async function snap() {
  try {
    log('Snapshot...');
    const r = await fetch('/snapshot', {method: 'POST'});
    const j = await r.json(); 
    log(j.ok ? ('Saved -> ' + j.filename) : ('Snapshot error: ' + j.msg));
  } catch (e) {
    log('Snapshot error: ' + e.message);
  }
}

async function statusAll() {
  try {
    const r = await fetch('/system_status'); 
    const s = await r.json();
    const cs = s.camera;
    const el = sid('cstat');
    if (el) {
      if (cs.is_dummy) { 
        el.textContent = 'Camera: DUMMY (no physical camera)'; 
        el.style.color = '#ff0'; 
      } else if (cs.ok) { 
        el.textContent = 'Camera: ' + cs.device; 
        el.style.color = '#0f0'; 
      } else { 
        el.textContent = 'Camera: not available'; 
        el.style.color = '#f00'; 
      }
    }
    const led = sid('mled');
    if (led) led.className = 'led ' + (s.motors.ok ? 'ok' : 'err');
    
    log('System: ' + (cs.ok ? 'CAM-OK ' : 'CAM-ERR ') + (s.motors.ok ? 'MOT-OK ' : 'MOT-ERR ') + (s.tts.ok ? 'TTS-OK' : 'TTS-ERR'));
  } catch (e) {
    log('Status error: ' + e.message);
  }
}

async function recStart() { 
  try {
    log('Recording start...'); 
    const r = await fetch('/start_recording', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({audio_bitrate: '96k'})
    }); 
    const j = await r.json(); 
    log(j.ok ? ('Recording -> ' + j.file) : ('Rec error: ' + j.msg)); 
  } catch (e) {
    log('Recording start error: ' + e.message);
  }
}

async function recStop() { 
  try {
    log('Recording stop...'); 
    const r = await fetch('/stop_recording', {method: 'POST'}); 
    const j = await r.json(); 
    log(j.ok ? ('Stopped. Last -> ' + (j.file || 'n/a')) : ('Stop error: ' + j.msg)); 
  } catch (e) {
    log('Recording stop error: ' + e.message);
  }
}

// Enhanced audio streaming variables
let audioActive = false;
let webrtcPeer = null;
let webrtcPeerId = null;
let audioContext = null;
let audioWorklet = null;

function initWebSocket() {
  try {
    if (socket && socket.connected) return socket;
    
    console.log('Initializing WebSocket connection...');
    
    socket = io({
      timeout: 10000,
      reconnection: true,
      reconnectionAttempts: 5,
      reconnectionDelay: 1000,
      transports: ['websocket', 'polling']
    });
    
    socket.on('connect', function() {
      console.log('WebSocket connected successfully');
      updateMicStatus('WebSocket ready');
    });
    
    socket.on('connect_error', function(error) {
      console.error('WebSocket connection error:', error);
      updateMicStatus('WebSocket connect error');
    });
    
    socket.on('disconnect', function(reason) {
      console.log('WebSocket disconnected:', reason);
      audioActive = false;
      updateMicButton();
      updateMicStatus('WebSocket disconnected');
    });
    
    socket.on('audio_status', function(data) {
      console.log('Audio status:', data);
      if (data.status === 'error') {
        updateMicStatus('Audio error: ' + (data.message || 'Unknown'));
        audioActive = false;
        updateMicButton();
      } else {
        updateMicStatus(data.status || 'Unknown status');
      }
    });
    
    socket.on('audio_data', function(data) {
      // Handle raw audio data from WebSocket fallback
      if (audioActive && audioContext) {
        try {
          playAudioChunk(data);
        } catch (e) {
          console.error('Audio playback error:', e);
        }
      }
    });
    
    return socket;
  } catch (e) {
    console.error('WebSocket init error:', e);
    updateMicStatus('WebSocket init failed: ' + e.message);
    return null;
  }
}

async function initWebRTC() {
  try {
    // Check if WebRTC is supported in browser
    if (!window.RTCPeerConnection) {
      throw new Error('WebRTC not supported in browser');
    }
    
    // Check if server supports WebRTC
    const testResponse = await fetch('/webrtc/offer', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ test: true })
    });
    
    if (!testResponse.ok) {
      throw new Error('WebRTC not available on server');
    }
    
    updateMicStatus('Setting up WebRTC...');
    
    // Create peer connection
    webrtcPeer = new RTCPeerConnection({
      iceServers: [{ urls: 'stun:stun.l.google.com:19302' }]
    });
    
    // Handle incoming audio stream
    webrtcPeer.ontrack = function(event) {
      console.log('Received WebRTC audio track');
      const audioEl = document.getElementById('audio-playback');
      if (audioEl && event.streams[0]) {
        audioEl.srcObject = event.streams[0];
        updateMicStatus('WebRTC audio active');
        updateAudioQuality('WebRTC Active');
      }
    };
    
    webrtcPeer.onconnectionstatechange = function() {
      console.log('WebRTC connection state:', webrtcPeer.connectionState);
      updateMicStatus('WebRTC: ' + webrtcPeer.connectionState);
      
      if (webrtcPeer.connectionState === 'connected') {
        updateAudioQuality('WebRTC Connected');
        console.log('WebRTC connection established successfully');
      } else if (webrtcPeer.connectionState === 'disconnected') {
        console.log('WebRTC connection disconnected');
        updateAudioQuality('WebRTC Disconnected');
      } else if (webrtcPeer.connectionState === 'failed') {
        console.log('WebRTC connection failed - will fallback to WebSocket');
        updateAudioQuality('WebRTC Failed');
        audioActive = false;
        updateMicButton();
        // Automatically try WebSocket fallback
        setTimeout(async () => {
          console.log('Auto-fallback to WebSocket audio...');
          updateAudioQuality('WebSocket Mode');
          const success = await startWebSocketAudio();
          if (success) {
            audioActive = true;
            vuMeterActive = true;
            updateMicStatus('Audio streaming active (WebSocket fallback)');
            updateMicButton();
          }
        }, 1000);
      }
    };
    
    // Add ICE connection state monitoring
    webrtcPeer.oniceconnectionstatechange = function() {
      console.log('ICE connection state:', webrtcPeer.iceConnectionState);
      if (webrtcPeer.iceConnectionState === 'failed') {
        console.log('ICE connection failed - this may cause WebRTC failure');
      } else if (webrtcPeer.iceConnectionState === 'connected') {
        console.log('ICE connection established successfully');
      }
    };
    
    // Add data channel error monitoring
    webrtcPeer.onicegatheringstatechange = function() {
      console.log('ICE gathering state:', webrtcPeer.iceGatheringState);
    };
    
    // Create offer
    const offer = await webrtcPeer.createOffer({ offerToReceiveAudio: true });
    await webrtcPeer.setLocalDescription(offer);
    
    // Send offer to server
    const response = await fetch('/webrtc/offer', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        sdp: offer.sdp,
        type: offer.type
      })
    });
    
    const result = await response.json();
    if (result.ok) {
      webrtcPeerId = result.peer_id;
      const answer = new RTCSessionDescription(result.answer);
      await webrtcPeer.setRemoteDescription(answer);
      updateMicStatus('WebRTC connected');
      return true;
    } else {
      throw new Error(result.error || 'WebRTC setup failed');
    }
    
  } catch (e) {
    console.error('WebRTC init error:', e);
    updateMicStatus('WebRTC failed: ' + e.message);
    return false;
  }
}

async function startWebSocketAudio() {
  try {
    if (!socket) {
      socket = initWebSocket();
      if (!socket) throw new Error('WebSocket init failed');
    }
    
    // Initialize audio context for playback
    if (!audioContext) {
      audioContext = new (window.AudioContext || window.webkitAudioContext)();
    }
    
    socket.emit('start_simple_audio');
    updateMicStatus('Starting WebSocket audio...');
    return true;
  } catch (e) {
    console.error('WebSocket audio error:', e);
    updateMicStatus('WebSocket audio failed: ' + e.message);
    return false;
  }
}

function playAudioChunk(audioData) {
  // Simple audio playback for WebSocket fallback
  try {
    if (audioContext && audioData) {
      // This is a simplified implementation
      // In a full implementation, you'd properly decode the PCM data
      console.log('Playing audio chunk:', audioData.length, 'bytes');
    }
  } catch (e) {
    console.error('Audio chunk playback error:', e);
  }
}

async function toggleMicrophone() {
  try {
    if (audioActive) {
      // Stop audio streaming
      audioActive = false;
      
      if (webrtcPeer && webrtcPeerId) {
        await fetch(`/webrtc/close/${webrtcPeerId}`, { method: 'POST' });
        webrtcPeer.close();
        webrtcPeer = null;
        webrtcPeerId = null;
      }
      
      if (socket) {
        socket.emit('stop_simple_audio');
      }
      
      updateMicStatus('Audio stopped');
      updateAudioQuality('Ready');
      vuMeterActive = false;
      
    } else {
      // Start audio streaming
      updateMicStatus('Starting audio...');
      
      let success = false;
      
      // Try WebRTC first (best quality)
      if (window.RTCPeerConnection) {
        try {
          success = await initWebRTC();
          if (success) {
            updateAudioQuality('WebRTC Mode');
          }
        } catch (e) {
          console.error('WebRTC initialization failed:', e);
          updateMicStatus('WebRTC failed, trying WebSocket...');
        }
      }
      
      // Fallback to WebSocket
      if (!success) {
        updateAudioQuality('WebSocket Mode');
        success = await startWebSocketAudio();
      }
      
      if (success) {
        audioActive = true;
        vuMeterActive = true;
        updateMicStatus('Audio streaming active');
      } else {
        updateMicStatus('Failed to start audio');
        updateAudioQuality('Error');
      }
    }
    
    updateMicButton();
    
  } catch (e) {
    console.error('Toggle microphone error:', e);
    updateMicStatus('Error: ' + e.message);
    audioActive = false;
    updateMicButton();
  }
}

function updateMicButton() {
  const btn = document.getElementById('micbtn');
  if (btn) {
    if (audioActive) {
      btn.textContent = '🔴 Stop Audio';
      btn.style.background = '#ff4444';
      btn.style.color = '#fff';
    } else {
      btn.textContent = '🎤 Start Audio';
      btn.style.background = '';
      btn.style.color = '';
    }
  }
}

function updateMicStatus(status) {
  const statusEl = document.getElementById('mic-status');
  if (statusEl) {
    statusEl.textContent = status;
  }
  console.log('Mic status:', status);
}

function updateAudioQuality(quality) {
  const qualityEl = document.getElementById('audio-quality');
  if (qualityEl) {
    qualityEl.textContent = quality;
    // Color coding based on quality
    if (quality.includes('WebRTC')) {
      qualityEl.style.color = '#44ff44';  // Green for WebRTC
    } else if (quality.includes('WebSocket')) {
      qualityEl.style.color = '#ffaa00';  // Orange for WebSocket
    } else if (quality.includes('Error') || quality.includes('Failed')) {
      qualityEl.style.color = '#ff4444';  // Red for errors
    } else {
      qualityEl.style.color = '#808080';  // Gray for ready/unknown
    }
  }
}

async function testMic() {
  try {
    log('Testing microphone...');
    const response = await fetch('/mic_test');
    if (response.ok) {
      log('Mic test completed - check downloaded file');
      // Trigger download
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'mic_test.wav';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    } else {
      log('Mic test failed');
    }
  } catch (e) {
    log('Mic test error: ' + e.message);
  }
}

let muted = false;
let socketConnected = false;

// Initialize Socket.IO connection
function initializeSocket() {
  try {
    socket = io();
    
    socket.on('connect', function() {
      socketConnected = true;
      console.log('Socket.IO connected:', socket.id);
      log('WebSocket connected - All systems ready');
    });
    
    socket.on('disconnect', function() {
      socketConnected = false;
      console.log('Socket.IO disconnected');
      log('WebSocket disconnected - Reconnecting...');
    });
    
    socket.on('connect_error', function(error) {
      console.error('Socket.IO connection error:', error);
      log('WebSocket connection failed: ' + error.message);
    });
    
    socket.on('audio_status', function(data) {
      console.log('Audio status:', data);
      if (data.status === 'started') {
        vuMeterActive = true;
        log('Audio streaming started');
      } else if (data.status === 'stopped') {
        vuMeterActive = false;
        log('Audio streaming stopped');
      } else if (data.status === 'error') {
        vuMeterActive = false;
        log('Audio error: ' + (data.message || 'unknown'));
      }
    });
    
  } catch (e) {
    console.error('Socket.IO initialization failed:', e);
    log('WebSocket initialization failed: ' + e.message);
  }
}

async function setVol(v) { 
  try {
    const volEl = sid('volv');
    if (volEl) volEl.textContent = v + '%'; 
    await fetch('/audio/set_volume', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({type: 'speaker', volume: parseInt(v)})
    }); 
  } catch (e) {
    log('Set volume error: ' + e.message);
  } 
}

async function toggleMute() {
  try {
    muted = !muted; 
    const btn = sid('mutebtn'); 
    const sl = sid('vol');
    if (btn && sl) {
      if (muted) { 
        btn.textContent = '🔇'; 
        btn.style.background = '#f00'; 
        sl.disabled = true; 
        await fetch('/audio/set_volume', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({type: 'speaker', mute: true})
        }); 
      } else { 
        btn.textContent = '🔊'; 
        btn.style.background = ''; 
        sl.disabled = false; 
        await fetch('/audio/set_volume', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({type: 'speaker', volume: parseInt(sl.value), mute: false})
        }); 
      }
    }
  } catch (e) {
    log('Toggle mute error: ' + e.message);
  }
}

async function beep(i) { 
  try {
    const r = await fetch('/play_sound/' + i, {method: 'POST'}); 
    const j = await r.json(); 
    log(j.ok ? j.msg : ('Sound error: ' + j.msg)); 
  } catch (e) {
    log('Beep error: ' + e.message);
  }
}

async function rebootSystem() {
  try {
    if (!confirm('REBOOT SYSTEM? This will restart the entire device. Are you sure?')) return;
    log('Initiating system reboot...');
    const r = await fetch('/system/reboot', {method: 'POST'});
    const j = await r.json();
    if (j.ok) {
      log('Reboot command sent successfully');
      setTimeout(function() { log('System should be rebooting now...'); }, 3000);
    } else {
      log('Reboot failed: ' + j.msg);
    }
  } catch (e) {
    log('Reboot request failed: ' + e.message);
  }
}

async function batt() {
  try {
    const r = await fetch('/battery'); 
    const b = await r.json();
    const f = sid('batf'); 
    const p = sid('batp');
    if (f && p) {
      f.style.width = b.percentage + '%'; 
      p.textContent = b.percentage.toFixed(0) + '%';
      if (b.percentage > 50) f.style.background = '#0f0'; 
      else if (b.percentage > 20) f.style.background = '#ff0'; 
      else f.style.background = '#f00';
    }
  } catch (e) {
    console.error('Battery update error:', e);
  }
}

const down = {};
document.addEventListener('keydown', function(e) {
  try {
    // Don't trigger motor controls if user is typing in any input field
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.isContentEditable) return;
    
    if (down[e.key]) return; 
    down[e.key] = true;
    switch (e.key.toLowerCase()) {
      case 'w': go('forward'); e.preventDefault(); break;
      case 's': go('backward'); e.preventDefault(); break;
      case 'a': go('left'); e.preventDefault(); break;
      case 'd': go('right'); e.preventDefault(); break;
      case ' ': estop(); e.preventDefault(); break;
    }
  } catch (e) {
    console.error('Keydown error:', e);
  }
});

document.addEventListener('keyup', function(e) {
  try {
    // Don't trigger motor controls if user is typing in any input field
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.isContentEditable) return;
    
    if (!down[e.key]) return; 
    down[e.key] = false;
    if (['w', 's', 'a', 'd'].includes(e.key.toLowerCase())) stopM();
  } catch (e) {
    console.error('Keyup error:', e);
  }
});

function init() {
  try {
    log('Initializing Avatar Tank Enhanced System...');
    
    // Initialize Socket.IO connection first
    initializeSocket();
    
    setLang('en'); 
    batt(); 
    setInterval(batt, 5000); 
    statusAll(); 
    setInterval(statusAll, 30000);
    
    // Enhanced monitoring systems
    updateDateTime();
    setInterval(updateDateTime, 1000);
    
    setInterval(updateBandwidth, 100); // More frequent bandwidth updates
    setInterval(enhancedVUMeter, 50); // Smooth VU meter updates
    
    // Video stream monitoring
    setInterval(function() { 
      const v = sid('vid'); 
      if (v && v.naturalWidth === 0) { 
        v.src = v.src.split('?')[0] + '?t=' + Date.now(); 
      } 
    }, 10000);
    
    // Test prediction system after a short delay
    setTimeout(function() {
      fetch('/predict?q=test&limit=5')
        .then(function(response) { return response.json(); })
        .then(function(data) {
          console.log('Prediction system test:', data);
          if (!data.ok) {
            log('Prediction system not working: ' + (data.msg || 'unknown error'));
          } else {
            log('Prediction system active with ' + (data.count || 0) + ' words');
          }
        })
        .catch(function(e) {
          console.error('Prediction test failed:', e);
          log('Prediction test failed: ' + e.message);
        });
    }, 2000);
    
    // Test basic connectivity
    setTimeout(function() {
      fetch('/system_status')
        .then(function(response) { return response.json(); })
        .then(function(data) {
          console.log('System status:', data);
          const camera = data.camera ? (data.camera.is_dummy ? 'Dummy' : 'Working') : 'Failed';
          const motors = data.motors ? (data.motors.ok ? 'Connected' : 'Failed') : 'Failed';
          const tts = data.tts ? (data.tts.ok ? 'Ready' : 'Failed') : 'Failed';
          log(`Systems: Camera=${camera}, Motors=${motors}, TTS=${tts}`);
        })
        .catch(function(e) {
          console.error('System status failed:', e);
          log('System status check failed: ' + e.message);
        });
    }, 3000);
    
    // Initialize VU meter as inactive
    vuMeterActive = false;
    
    log('All systems initialized successfully');
  } catch (e) {
    console.error('Init error:', e);
    log('Initialization failed: ' + e.message);
  }
}

document.addEventListener('DOMContentLoaded', init);
console.log('JavaScript loaded successfully');
</script>
</body>
</html>"""

# --- keep server alive ---
if __name__ == '__main__':
    try:
        print("Avatar Tank - Backend ready")
        print("Speaker:", SPK_PLUG)
        print("Mic    :", MIC_PLUG)
        print("TTS    :", tts.status())
        print("WebRTC :", "Available" if WEBRTC_AVAILABLE else "Not available")
        print("Camera :", "Working" if camera and not isinstance(camera, DummyCamera) else "Dummy/Failed")
    except Exception as e:
        print(f"Startup info error: {e}")
    
    # Force SocketIO production server with proper configuration
    try:
        print("Starting SocketIO production server...")
        # Import check
        import simple_websocket
        print("✓ simple-websocket available")
        
        # Start with explicit configuration (removed problematic logger config)
        socketio.run(
            app, 
            host='0.0.0.0', 
            port=5000, 
            debug=False, 
            allow_unsafe_werkzeug=True,
            use_reloader=False,
            log_output=False
        )
    except ImportError as e:
        print(f"SocketIO dependency missing: {e}")
        print("Falling back to Flask development server...")
        app.run(host='0.0.0.0', port=5000, debug=False)
    except Exception as e:
        print(f"SocketIO server failed: {e}")
        print("Falling back to Flask development server...")
        app.run(host='0.0.0.0', port=5000, debug=False)

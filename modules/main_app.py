#!/usr/bin/env python3
"""
Main application module for Avatar Tank system.
Coordinates all subsystems and provides the web interface.
"""

import os
import sys
import json
import tempfile
import time
import threading
import subprocess
import datetime
import cv2
from pathlib import Path
from flask import Flask, Response, request, jsonify, send_file
from flask_socketio import SocketIO


# Ensure all modules can be imported
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Import all modules with error handling
print("[MainApp] Loading Avatar Tank modules...")

try:
    from modules.device_detector import device_detector, device_config, CAMERA_DEVICE, MIC_PLUG, SPK_PLUG, MOTOR_PORT
    print("[MainApp] ✓ Device detector loaded")
except ImportError as e:
    print(f"[MainApp] ✗ Device detector failed: {e}")
    # Fallback values
    CAMERA_DEVICE = '/dev/video0'
    MIC_PLUG = 'default'
    SPK_PLUG = 'default'
    MOTOR_PORT = '/dev/ttyUSB0'

try:
    from modules.camera import (camera_manager, camera_settings, current_resolution, 
                               generate_frames, init_camera, get_camera_status, 
                               set_camera_resolution, take_snapshot)
    print("[MainApp] ✓ Camera module loaded")
except ImportError as e:
    print(f"[MainApp] ✗ Camera module failed: {e}")
    # Create dummy functions
    def generate_frames():
        while True:
            yield b'--frame\r\nContent-Type: image/jpeg\r\n\r\nDUMMY\r\n'
            time.sleep(0.1)
    def get_camera_status():
        return {"ok": False, "msg": "Camera module not loaded"}
    def set_camera_resolution(res):
        return False
    def take_snapshot():
        return {"ok": False, "msg": "Camera module not loaded"}
    camera_settings = {"720p": {"width": 1280, "height": 720, "fps": 15}}
    current_resolution = "720p"

try:
    from modules.motor_controller import motors, get_motor_status
    print("[MainApp] ✓ Motor controller loaded")
except ImportError as e:
    print(f"[MainApp] ✗ Motor controller failed: {e}")
    # Create dummy motor controller
    class DummyMotors:
        def move(self, l, r): return {"ok": False, "msg": "Motor module not loaded"}
        def stop(self): return {"ok": False, "msg": "Motor module not loaded"}
        def get_battery(self): return {"voltage": 12.0, "percentage": 75}
    motors = DummyMotors()
    def get_motor_status(): return {"connected": False}

try:
    from modules.tts import tts
    print("[MainApp] ✓ TTS module loaded")
except ImportError as e:
    print(f"[MainApp] ✗ TTS module failed: {e}")
    # Create dummy TTS
    class DummyTTS:
        def speak(self, text, lang=None): return {"ok": False, "msg": "TTS module not loaded"}
        def status(self): return {"ok": False, "msg": "TTS module not loaded"}
        languages = {'en': {'name': 'English'}}
        current_language = 'en'
    tts = DummyTTS()

try:
    from modules.recorder import rec, get_recording_status
    print("[MainApp] ✓ Recorder module loaded")
except ImportError as e:
    print(f"[MainApp] ✗ Recorder module failed: {e}")
    # Create dummy recorder
    class DummyRecorder:
        def start(self, a_bitrate="96k"): return {"ok": False, "msg": "Recorder module not loaded"}
        def stop(self): return {"ok": False, "msg": "Recorder module not loaded"}
        def status(self): return {"ok": False, "recording": False}
    rec = DummyRecorder()
    def get_recording_status(): return {"ok": False, "recording": False}

try:
    from modules.audio_utils import _get_volume, _set_volume, _pick_playback_ctrl, _pick_capture_ctrl
    print("[MainApp] ✓ Audio utils loaded")
except ImportError as e:
    print(f"[MainApp] ✗ Audio utils failed: {e}")
    # Create dummy functions
    def _get_volume(device, ctrl): return {"ok": False, "volume": 50, "muted": False}
    def _set_volume(device, ctrl, vol, mute=None): return {"ok": False, "msg": "Audio utils not loaded"}
    def _pick_playback_ctrl(): return "Master"
    def _pick_capture_ctrl(): return "Capture"

try:
    from modules.predictor import _predict
    print("[MainApp] ✓ Predictor module loaded")
except ImportError as e:
    print(f"[MainApp] ✗ Predictor module failed: {e}")
    # Create dummy predictor
    class DummyPredict:
        def suggest(self, prefix, limit=50): return []
        def add_words_from_text(self, text): return 0
        def reload(self): pass
        words = []
    _predict = DummyPredict()

try:
    from modules.audio_streamer import (handle_start_simple_audio, handle_stop_simple_audio, 
                                       handle_test_audio_tone, handle_disconnect as audio_disconnect,
                                       get_audio_streaming_status)
    print("[MainApp] ✓ Audio streamer loaded")
    audio_streamer_available = True
    print(f"[MainApp] Audio streamer available: {audio_streamer_available}")
except ImportError as e:
    print(f"[MainApp] ✗ Audio streamer failed: {e}")
    audio_streamer_available = False
    def handle_start_simple_audio(): pass
    def handle_stop_simple_audio(): pass
    def handle_test_audio_tone(): pass
    def audio_disconnect(): pass
    def get_audio_streaming_status(): return {"active": False}


# Create Flask app with proper configuration
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload

# Configure SocketIO with better settings for Raspberry Pi
socketio = SocketIO(
    app, 
    cors_allowed_origins="*", 
    async_mode='threading',
    ping_timeout=60,
    ping_interval=25,
    max_http_buffer_size=1000000
)

# Ensure required directories exist
Path("snapshots").mkdir(exist_ok=True)
Path("recordings").mkdir(exist_ok=True)
Path("sounds").mkdir(exist_ok=True)

# Application state
app_state = {
    'startup_time': time.time(),
    'clients_connected': 0,
    'total_requests': 0,
    'audio_streaming_clients': set()
}


# ============== WebSocket Event Handlers ==============
@socketio.on('connect')
def handle_connect():
    app_state['clients_connected'] += 1
    print(f"[WebSocket] Client connected: {request.sid} (total: {app_state['clients_connected']})")

@socketio.on('disconnect')
def handle_disconnect():
    app_state['clients_connected'] -= 1
    
    # Clean up audio streaming for this client
    if request.sid in app_state['audio_streaming_clients']:
        app_state['audio_streaming_clients'].discard(request.sid)
        if audio_streamer_available:
            audio_disconnect()
    
    print(f"[WebSocket] Client disconnected: {request.sid} (total: {app_state['clients_connected']})")

@socketio.on('start_simple_audio')
def handle_start_simple_audio_event():
    print("[WebSocket] start_simple_audio event received")
    if audio_streamer_available:
        app_state['audio_streaming_clients'].add(request.sid)
        handle_start_simple_audio()
    else:
        socketio.emit('audio_status', {'status': 'error', 'message': 'Audio streamer not available'})

@socketio.on('stop_simple_audio')
def handle_stop_simple_audio_event():
    print("[WebSocket] stop_simple_audio event received")
    if audio_streamer_available:
        app_state['audio_streaming_clients'].discard(request.sid)
        handle_stop_simple_audio()
    else:
        socketio.emit('audio_status', {'status': 'error', 'message': 'Audio streamer not available'})

@socketio.on('test_audio_tone')
def handle_test_audio_tone_event():
    if audio_streamer_available:
        handle_test_audio_tone()
    else:
        socketio.emit('audio_status', {'status': 'error', 'message': 'Audio streamer not available'})


# ============== HTTP Routes ==============

@app.before_request
def before_request():
    app_state['total_requests'] += 1

@app.route('/')
def index():
    """Serve the main HTML interface"""
    try:
        # Try to serve from static directory first
        static_file = os.path.join('static', 'index.html')
        if os.path.exists(static_file):
            with open(static_file, 'r', encoding='utf-8') as f:
                return f.read()
        
        # Fallback to module directory
        module_static = os.path.join(os.path.dirname(__file__), '..', 'static', 'index.html')
        if os.path.exists(module_static):
            with open(module_static, 'r', encoding='utf-8') as f:
                return f.read()
        
        # Last resort - minimal interface
        return """
        <!DOCTYPE html>
        <html>
        <head><title>Avatar Tank</title></head>
        <body>
            <h1>Avatar Tank Control Interface</h1>
            <p>HTML interface not found. System is running but web interface is not available.</p>
            <p>Available endpoints:</p>
            <ul>
                <li><a href="/video">/video</a> - Video stream</li>
                <li><a href="/system_status">/system_status</a> - System status (JSON)</li>
                <li><a href="/battery">/battery</a> - Battery status (JSON)</li>
            </ul>
        </body>
        </html>
        """
    except Exception as e:
        return f"<h1>Error loading interface</h1><p>{str(e)}</p>"

# Video streaming
@app.route('/video')
def video():
    """Video stream endpoint"""
    try:
        return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')
    except Exception as e:
        print(f"[MainApp] Video stream error: {e}")
        # Return a simple error image
        def error_frame():
            while True:
                yield b'--frame\r\nContent-Type: text/plain\r\n\r\nVideo Error\r\n'
                time.sleep(1)
        return Response(error_frame(), mimetype='multipart/x-mixed-replace; boundary=frame')

# Camera control
@app.route('/set_resolution', methods=['POST'])
def set_resolution():
    """Set camera resolution"""
    try:
        data = request.get_json() or {}
        resolution = data.get('resolution', '720p')
        
        print(f"[MainApp] Set resolution request: {resolution}")
        
        if resolution in camera_settings:
            success = set_camera_resolution(resolution)
            actual_resolution = current_resolution  # Get the actual current resolution
            print(f"[MainApp] Resolution set {'successful' if success else 'failed'}, current: {actual_resolution}")
            return jsonify({"ok": success, "resolution": actual_resolution})
        else:
            return jsonify({"ok": False, "msg": "Invalid resolution"})
    except Exception as e:
        print(f"[MainApp] Set resolution error: {e}")
        return jsonify({"ok": False, "msg": str(e)})

@app.route('/camera_status')
def camera_status():
    """Get camera status"""
    try:
        return jsonify(get_camera_status())
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)})

@app.route('/snapshot', methods=['POST'])
def snapshot():
    """Take a snapshot"""
    try:
        result = take_snapshot()
        return jsonify(result)
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)})

# Motor control
@app.route('/motor/<direction>', methods=['POST'])
def motor_control(direction):
    """Control motors"""
    try:
        data = request.get_json() or {}
        speed = int(data.get('speed', 150))
        
        if direction == 'forward':
            result = motors.move(speed, speed)
        elif direction == 'backward':
            result = motors.move(-speed, -speed)
        elif direction == 'left':
            result = motors.move(-speed, speed)
        elif direction == 'right':
            result = motors.move(speed, -speed)
        elif direction == 'stop':
            result = motors.stop()
        else:
            return jsonify({"ok": False, "msg": "Invalid direction"})
        
        return jsonify(result)
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)})

@app.route('/motor/reconnect', methods=['POST'])
def motor_reconnect():
    """Reconnect to motor controller"""
    try:
        result = motors.reconnect()
        return jsonify({"ok": result, "msg": "Reconnection attempted"})
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)})

@app.route('/battery')
def battery_status():
    """Get battery status"""
    try:
        return jsonify(motors.get_battery())
    except Exception as e:
        return jsonify({"voltage": 12.0, "percentage": 75, "error": str(e)})

# Text-to-Speech
@app.route('/speak', methods=['POST'])
def speak():
    """Text-to-speech endpoint"""
    try:
        data = request.get_json() or {}
        text = data.get('text', '')
        language = data.get('language')
        
        if not text:
            return jsonify({"ok": False, "msg": "No text provided"})
        
        # Learn new words for prediction
        try:
            learned_count = _predict.add_words_from_text(text)
            if learned_count > 0:
                print(f"[MainApp] Learned {learned_count} new words for predictions")
        except Exception as e:
            print(f"[MainApp] Word learning error: {e}")
        
        # Speak the text
        result = tts.speak(text, language)
        return jsonify(result)
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)})

@app.route('/set_language', methods=['POST'])
def set_language():
    """Set TTS language"""
    try:
        data = request.get_json() or {}
        language = data.get('language', 'en')
        
        if language in tts.languages:
            tts.current_language = language
            return jsonify({
                "ok": True,
                "language": language,
                "name": tts.languages[language]['name']
            })
        else:
            return jsonify({"ok": False, "msg": "Invalid language"})
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)})

@app.route('/tts_status')
def tts_status():
    """Get TTS status"""
    try:
        return jsonify(tts.status())
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)})

# Audio control
@app.route('/audio/status')
def audio_status():
    """Get audio system status"""
    try:
        return jsonify({
            "ok": True,
            "speaker": _get_volume(SPK_PLUG, _pick_playback_ctrl()),
            "mic": _get_volume(MIC_PLUG, _pick_capture_ctrl()),
            "devices": {"speaker": SPK_PLUG, "mic": MIC_PLUG},
            "streaming": get_audio_streaming_status()
        })
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)})

@app.route('/audio/set_volume', methods=['POST'])
def audio_set_volume():
    """Set audio volume"""
    try:
        data = request.get_json() or {}
        device_type = data.get('type', 'speaker')
        volume = data.get('volume')
        mute = data.get('mute')
        
        if device_type == 'speaker':
            result = _set_volume(SPK_PLUG, _pick_playback_ctrl(), volume, mute)
        elif device_type == 'mic':
            result = _set_volume(MIC_PLUG, _pick_capture_ctrl(), volume, mute)
        else:
            return jsonify({"ok": False, "msg": "type must be 'speaker' or 'mic'"})
        
        return jsonify(result)
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)})

@app.route('/audio/volume')
def audio_volume():
    """Get current audio volumes"""
    try:
        return jsonify({
            "ok": True,
            "speaker": _get_volume(SPK_PLUG, _pick_playback_ctrl()),
            "mic": _get_volume(MIC_PLUG, _pick_capture_ctrl())
        })
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)})

@app.route('/audio/devices')
def audio_devices():
    """Get available audio devices"""
    try:
        return jsonify({
            "mic_detected": getattr(device_detector, 'audio_input', []),
            "spk_detected": getattr(device_detector, 'audio_output', []),
            "MIC_PLUG": MIC_PLUG,
            "SPK_PLUG": SPK_PLUG,
            "override_hint": "Set AV_MIC and AV_SPK environment variables to override"
        })
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)})

# Sound playback
@app.route('/play_sound/<int:sound_id>', methods=['POST'])
def play_sound(sound_id):
    """Play sound effects"""
    try:
        idx = (sound_id % 10) + 1
        exts = ['mp3', 'wav', 'ogg', 'flac', 'm4a', 'aac', 'opus']
        candidates = []
        
        # Look for sound files
        for stem in (f"sound{idx}", f"{idx}", f"Sound{idx}"):
            for ext in exts:
                candidates.extend(Path('sounds').glob(f'{stem}.{ext}'))
        
        if candidates:
            chosen = str(candidates[0])
            
            # Convert to WAV and play
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                temp_wav = temp_file.name
            
            # Convert with ffmpeg
            convert_result = subprocess.run([
                'ffmpeg', '-hide_banner', '-loglevel', 'error', '-i', chosen,
                '-ar', '48000', '-ac', '2', '-f', 'wav', '-acodec', 'pcm_s16le', 
                '-y', temp_wav
            ], capture_output=True, text=True)
            
            if convert_result.returncode != 0:
                os.unlink(temp_wav)
                return jsonify({
                    'ok': False, 
                    'msg': f'Decode failed: {convert_result.stderr[:200]}'
                })
            
            # Play with aplay
            play_result = subprocess.run([
                'aplay', '-D', SPK_PLUG, temp_wav
            ], capture_output=True, text=True)
            
            os.unlink(temp_wav)
            
            if play_result.returncode == 0:
                return jsonify({
                    'ok': True, 
                    'msg': f'Played file: {Path(chosen).name}'
                })
            else:
                return jsonify({
                    'ok': False, 
                    'msg': f'Playback failed: {play_result.stderr}'
                })
        
        # Fallback: generate beep tone
        frequencies = [220, 262, 294, 330, 349, 392, 440, 494, 523, 587]
        frequency = frequencies[sound_id % 10]
        
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
            temp_wav = temp_file.name
        
        # Generate tone with ffmpeg
        tone_result = subprocess.run([
            'ffmpeg', '-f', 'lavfi', '-i', f'sine=frequency={frequency}:duration=0.5',
            '-ar', '48000', '-ac', '2', '-f', 'wav', '-acodec', 'pcm_s16le',
            '-y', temp_wav
        ], capture_output=True, text=True)
        
        if tone_result.returncode == 0:
            play_result = subprocess.run([
                'aplay', '-D', SPK_PLUG, temp_wav
            ], capture_output=True, text=True)
            
            os.unlink(temp_wav)
            
            if play_result.returncode == 0:
                return jsonify({'ok': True, 'msg': f'Beep {sound_id + 1}'})
            else:
                return jsonify({
                    'ok': False, 
                    'msg': f'Beep playback failed: {play_result.stderr}'
                })
        
        os.unlink(temp_wav)
        return jsonify({'ok': False, 'msg': 'Beep generation failed'})
        
    except Exception as e:
        return jsonify({'ok': False, 'msg': str(e)})

# Recording
@app.route('/start_recording', methods=['POST'])
def start_recording():
    """Start video recording"""
    try:
        data = request.get_json() or {}
        audio_bitrate = data.get("audio_bitrate", "96k")
        result = rec.start(a_bitrate=audio_bitrate)
        return jsonify(result)
    except Exception as e:
        print(f"[MainApp] Start recording failed: {e}")
        return jsonify({"ok": False, "msg": f"Recording failed: {str(e)}"}), 500

@app.route('/stop_recording', methods=['POST'])
def stop_recording():
    """Stop video recording"""
    try:
        return jsonify(rec.stop())
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)})

@app.route('/recording_status')
def recording_status():
    """Get recording status"""
    try:
        return jsonify(rec.status())
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)})

# Microphone testing
@app.route('/mic_test')
def mic_test():
    """Test microphone and download recording"""
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
            output_file = temp_file.name
        
        # Record 2 seconds of audio
        cmd = [
            "ffmpeg", "-hide_banner", "-loglevel", "warning",
            "-f", "alsa", "-i", MIC_PLUG, "-t", "2",
            "-ac", "1", "-ar", "44100", "-f", "wav", "-y", output_file
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0 or not os.path.exists(output_file) or os.path.getsize(output_file) < 1000:
            try:
                os.unlink(output_file)
            except:
                pass
            return jsonify({
                "ok": False, 
                "msg": result.stderr.strip() or "ffmpeg mic capture failed"
            })
        
        return send_file(output_file, as_attachment=True, download_name="mic_test.wav")
        
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)})

# Text prediction
@app.route("/predict")
def predict_endpoint():
    """Text prediction endpoint"""
    try:
        query = request.args.get("q", "", type=str)[:200]
        limit = max(1, min(200, request.args.get("limit", 50, type=int)))
        results = _predict.suggest(query, limit)
        return jsonify({"ok": True, "q": query, "count": len(results), "items": results})
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)})

@app.route("/predict/reload", methods=["POST"])
def predict_reload():
    """Reload prediction dictionary"""
    try:
        _predict.reload()
        return jsonify({"ok": True, "count": len(_predict.words)})
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)})

@app.route("/predict/learn", methods=["POST"])
def predict_learn():
    """Learn words from text"""
    try:
        data = request.get_json() or {}
        text = data.get('text', '')
        
        if not text:
            return jsonify({"ok": False, "msg": "No text provided"})
        
        learned_count = _predict.add_words_from_text(text)
        return jsonify({
            "ok": True, 
            "learned": learned_count, 
            "total_words": len(_predict.words)
        })
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)})

# System status and control
@app.route('/system_status')
def system_status():
    """Get comprehensive system status"""
    try:
        camera_status = get_camera_status()
        motor_status = get_motor_status()
        tts_status_data = tts.status()
        
        return jsonify({
            "camera": camera_status,
            "motors": motor_status,
            "tts": tts_status_data,
            "audio": {"mic": MIC_PLUG, "speaker": SPK_PLUG},
            "battery": motors.get_battery(),
            "app_state": {
                "uptime": time.time() - app_state['startup_time'],
                "clients_connected": app_state['clients_connected'],
                "total_requests": app_state['total_requests'],
                "audio_streaming_active": len(app_state['audio_streaming_clients']) > 0
            }
        })
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)})

@app.route('/system/reboot', methods=['POST'])
def system_reboot():
    """Reboot the system"""
    try:
        print("[MainApp] Reboot requested via web interface")
        
        def delayed_reboot():
            time.sleep(2)
            subprocess.run(['sudo', 'reboot'], check=False)
        
        threading.Thread(target=delayed_reboot, daemon=True).start()
        return jsonify({"ok": True, "msg": "System reboot initiated"})
    except Exception as e:
        return jsonify({"ok": False, "msg": f"Reboot failed: {e}"})

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({"ok": False, "msg": "Endpoint not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"ok": False, "msg": "Internal server error"}), 500

@app.errorhandler(Exception)
def handle_exception(e):
    print(f"[MainApp] Unhandled exception: {e}")
    return jsonify({"ok": False, "msg": "Server error"}), 500


# ============== Application Lifecycle ==============

def print_startup_info():
    """Print startup information"""
    print("\n" + "="*60)
    print("AVATAR TANK SYSTEM - STARTUP COMPLETE")
    print("="*60)
    print(f"Speaker: {SPK_PLUG}")
    print(f"Microphone: {MIC_PLUG}")
    print(f"Camera: {CAMERA_DEVICE}")
    print(f"Motor: {MOTOR_PORT}")
    print(f"TTS Status: {tts.status()}")
    print(f"Camera Status: {get_camera_status()}")
    print(f"Motor Status: {get_motor_status()}")
    print("="*60)
    print("Web interface available at: http://localhost:5000")
    print("="*60)

def cleanup_on_shutdown():
    """Clean up resources on shutdown"""
    print("[MainApp] Shutting down...")
    
    try:
        # Stop any active recordings
        if hasattr(rec, 'stop'):
            rec.stop()
    except:
        pass
    
    try:
        # Stop motors
        motors.stop()
    except:
        pass
    
    print("[MainApp] Cleanup complete")

# Register cleanup handler
import atexit
atexit.register(cleanup_on_shutdown)


# ============== Main Application Entry Point ==============

if __name__ == '__main__':
    try:
        print_startup_info()
        
        # Start SocketIO server with production settings
        print("[MainApp] Starting SocketIO server...")
        
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
        print(f"[MainApp] SocketIO dependency missing: {e}")
        print("[MainApp] Falling back to Flask development server...")
        app.run(host='0.0.0.0', port=5000, debug=False)
        
    except Exception as e:
        print(f"[MainApp] Server failed to start: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        cleanup_on_shutdown()
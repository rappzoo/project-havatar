#!/usr/bin/env python3
"""
Audio streaming module for Avatar Tank system.
Handles WebSocket audio streaming with proper resource management.
"""

import subprocess
import threading
import base64
import time
import signal
import os
import sys
from subprocess import PIPE
from flask import request
from typing import Optional


# Try to get device detector - handle import gracefully
try:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)
    
    from modules.device_detector import device_detector, MIC_PLUG
    print(f"[AudioStreamer] Using detected microphone: {MIC_PLUG}")
except ImportError as e:
    print(f"[AudioStreamer] Warning: Could not import device detector ({e}), using fallback")
    MIC_PLUG = 'default'


# Global variable for socketio - will be set by main_app
socketio = None


class AudioStreamer:
    """Enhanced audio streamer with better process management"""
    
    def __init__(self):
        self.active = False
        self.process: Optional[subprocess.Popen] = None
        self.worker_thread: Optional[threading.Thread] = None
        self.lock = threading.Lock()
        self.client_sessions = set()  # Track active client sessions
        self.stats = {
            'chunks_sent': 0,
            'bytes_sent': 0,
            'errors': 0,
            'start_time': None
        }
        
    def start_streaming(self, client_id: str = None) -> dict:
        """Start audio streaming for a client"""
        with self.lock:
            # Add client to session tracking
            if client_id:
                self.client_sessions.add(client_id)
            
            if self.active:
                if socketio:
                    socketio.emit('audio_status', {'status': 'already_active'}, room=client_id)
                return {'status': 'already_active'}
            
            try:
                self.active = True
                self.stats['start_time'] = time.time()
                self.stats['chunks_sent'] = 0
                self.stats['bytes_sent'] = 0
                self.stats['errors'] = 0
                
                # Start FFmpeg process
                success = self._start_ffmpeg_process()
                
                if not success:
                    self.active = False
                    if socketio:
                        socketio.emit('audio_status', {'status': 'error', 'message': 'Failed to start audio capture'}, room=client_id)
                    return {'status': 'error', 'message': 'Failed to start audio capture'}
                
                # Start worker thread
                self.worker_thread = threading.Thread(target=self._audio_worker, daemon=True)
                self.worker_thread.start()
                
                if socketio:
                    socketio.emit('audio_status', {'status': 'started', 'format': 'pcm_s16le_22050_mono'}, room=client_id)
                print(f"[AudioStreamer] Started for client {client_id or 'unknown'}")
                
                return {'status': 'started'}
                
            except Exception as e:
                self.active = False
                error_msg = f"Audio streaming failed: {str(e)}"
                if socketio:
                    socketio.emit('audio_status', {'status': 'error', 'message': error_msg}, room=client_id)
                print(f"[AudioStreamer] Error: {e}")
                return {'status': 'error', 'message': error_msg}
    
    def _start_ffmpeg_process(self) -> bool:
        """Start the FFmpeg process for audio capture"""
        try:
            print(f"[AudioStreamer] Starting FFmpeg with microphone: {MIC_PLUG}")
            
            # Test microphone device first
            if not self._test_microphone_device():
                print(f"[AudioStreamer] Warning: Microphone test failed for {MIC_PLUG}")
                # Continue anyway - might still work
            
            # Improved FFmpeg command with better audio quality settings
            cmd = [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin",
                "-f", "alsa", "-i", MIC_PLUG,
                "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "1",  # Increased sample rate to 44.1kHz
                "-af", "highpass=f=100,lowpass=f=7000",  # Add filters to reduce noise
                "-f", "s16le", "-"  # Raw PCM output to stdout
            ]
            
            print(f"[AudioStreamer] FFmpeg command: {' '.join(cmd)}")
            
            # Start process with proper error handling
            self.process = subprocess.Popen(
                cmd,
                stdout=PIPE,
                stderr=PIPE,
                bufsize=0,  # No buffering for real-time audio
                preexec_fn=os.setsid  # Create new process group for clean termination
            )
            
            # Give FFmpeg a moment to start and check if it's still running
            time.sleep(0.2)
            
            if self.process.poll() is not None:
                # Process exited immediately - capture error
                stderr_output = self.process.stderr.read().decode('utf-8')
                print(f"[AudioStreamer] FFmpeg failed immediately: {stderr_output}")
                return False
            
            print(f"[AudioStreamer] FFmpeg started successfully with PID {self.process.pid}")
            return True
            
        except Exception as e:
            print(f"[AudioStreamer] Failed to start FFmpeg: {e}")
            return False
    
    def _test_microphone_device(self) -> bool:
        """Test if the microphone device is accessible"""
        try:
            # Quick test with arecord
            test_cmd = ["arecord", "-D", MIC_PLUG, "-f", "cd", "-d", "1", "-q", "/dev/null"]
            result = subprocess.run(test_cmd, capture_output=True, timeout=2)
            return result.returncode == 0
        except Exception as e:
            print(f"[AudioStreamer] Microphone test failed: {e}")
            return False
    
    def _audio_worker(self):
        """Worker thread that reads audio data and sends via WebSocket"""
        try:
            chunk_size = 8192  # Increased chunk size for smoother streaming
            chunk_count = 0
            empty_chunk_count = 0
            last_stats_time = time.time()
            
            print("[AudioStreamer] Audio worker started")
            
            while self.active and self.process:
                try:
                    # Check if FFmpeg process is still running
                    if self.process.poll() is not None:
                        stderr_output = self.process.stderr.read().decode('utf-8')
                        if stderr_output:
                            print(f"[AudioStreamer] FFmpeg exited with error: {stderr_output}")
                        else:
                            print("[AudioStreamer] FFmpeg process exited normally")
                        break
                    
                    # Read audio chunk
                    chunk = self.process.stdout.read(chunk_size)
                    
                    if not chunk:
                        empty_chunk_count += 1
                        if empty_chunk_count > 50:  # Too many empty reads
                            print("[AudioStreamer] Too many empty reads, stopping")
                            break
                        time.sleep(0.01)  # Increased pause for empty reads
                        continue
                    
                    empty_chunk_count = 0  # Reset on successful read
                    chunk_count += 1
                    
                    # Update statistics
                    self.stats['chunks_sent'] += 1
                    self.stats['bytes_sent'] += len(chunk)
                    
                    # Encode and send chunk
                    chunk_b64 = base64.b64encode(chunk).decode('ascii')
                    
                    # Send to all connected clients
                    if socketio:
                        for client_id in list(self.client_sessions):  # Use list copy to avoid modification during iteration
                            try:
                                socketio.emit('audio_data', {
                                    'data': chunk_b64,
                                    'format': 'pcm_s16le_44100_mono'  # Updated format
                                }, room=client_id)
                            except Exception as e:
                                print(f"[AudioStreamer] Error sending to client {client_id}: {e}")
                                self.client_sessions.discard(client_id)  # Remove problematic client
                    
                    # Periodic stats logging
                    current_time = time.time()
                    if current_time - last_stats_time > 5.0:  # Every 5 seconds
                        duration = current_time - self.stats['start_time']
                        avg_chunks_per_sec = self.stats['chunks_sent'] / duration if duration > 0 else 0
                        print(f"[AudioStreamer] Stats: {self.stats['chunks_sent']} chunks, "
                              f"{self.stats['bytes_sent']/1024:.1f}KB, "
                              f"{avg_chunks_per_sec:.1f} chunks/sec")
                        last_stats_time = current_time
                    
                    # Adjusted pause to prevent overwhelming the WebSocket while maintaining smooth streaming
                    if chunk_count % 3 == 0:  # Reduced frequency of pauses
                        time.sleep(0.01)  # Increased pause duration
                        
                except Exception as e:
                    self.stats['errors'] += 1
                    print(f"[AudioStreamer] Worker error: {e}")
                    
                    # Break on repeated errors
                    if self.stats['errors'] > 10:
                        print("[AudioStreamer] Too many errors, stopping")
                        break
                    
                    time.sleep(0.01)  # Brief recovery pause
                    
        except Exception as e:
            print(f"[AudioStreamer] Audio worker exception: {e}")
        finally:
            print("[AudioStreamer] Audio worker stopped")
            self._cleanup_process(from_worker_thread=True)
    
    def stop_streaming(self, client_id: str = None) -> dict:
        """Stop audio streaming"""
        with self.lock:
            # Remove client from session tracking
            if client_id:
                self.client_sessions.discard(client_id)
            
            # Only stop if no other clients are active
            if len(self.client_sessions) > 0:
                return {'status': 'other_clients_active'}
            
            if not self.active:
                if socketio:
                    socketio.emit('audio_status', {'status': 'not_active'}, room=client_id)
                return {'status': 'not_active'}
            
            try:
                self.active = False
                self._cleanup_process()
                
                if socketio:
                    socketio.emit('audio_status', {'status': 'stopped'}, room=client_id)
                print(f"[AudioStreamer] Stopped for client {client_id or 'unknown'}")
                
                # Print final statistics
                if self.stats['start_time']:
                    duration = time.time() - self.stats['start_time']
                    print(f"[AudioStreamer] Session stats: {duration:.1f}s, "
                          f"{self.stats['chunks_sent']} chunks, "
                          f"{self.stats['bytes_sent']/1024:.1f}KB, "
                          f"{self.stats['errors']} errors")
                
                return {'status': 'stopped'}
                
            except Exception as e:
                error_msg = f"Error stopping audio: {str(e)}"
                if socketio:
                    socketio.emit('audio_status', {'status': 'error', 'message': error_msg}, room=client_id)
                print(f"[AudioStreamer] Stop error: {e}")
                return {'status': 'error', 'message': error_msg}
    
    def _cleanup_process(self, from_worker_thread=False):
        """Clean up the FFmpeg process"""
        if self.process:
            try:
                # First try gentle termination
                if self.process.poll() is None:  # Still running
                    self.process.terminate()
                    
                    # Wait briefly for graceful shutdown
                    try:
                        self.process.wait(timeout=2)
                        print("[AudioStreamer] FFmpeg terminated gracefully")
                    except subprocess.TimeoutExpired:
                        # Force kill if necessary
                        print("[AudioStreamer] Force killing FFmpeg")
                        self.process.kill()
                        self.process.wait()
                
            except Exception as e:
                print(f"[AudioStreamer] Process cleanup error: {e}")
            finally:
                self.process = None
        
        # Wait for worker thread to finish (but not if called from the worker thread itself)
        if not from_worker_thread and self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=1)
    
    def handle_client_disconnect(self, client_id: str):
        """Handle client disconnection"""
        with self.lock:
            if client_id in self.client_sessions:
                self.client_sessions.discard(client_id)
                print(f"[AudioStreamer] Client {client_id} disconnected")
                
                # Stop streaming if no clients left
                if len(self.client_sessions) == 0 and self.active:
                    print("[AudioStreamer] No clients left, stopping streaming")
                    self.active = False
                    self._cleanup_process()
    
    def get_status(self) -> dict:
        """Get streaming status"""
        return {
            'active': self.active,
            'clients': len(self.client_sessions),
            'stats': self.stats.copy(),
            'process_running': self.process is not None and self.process.poll() is None
        }
    
    def generate_test_tone(self, frequency: float = 440.0, duration: float = 2.0):
        """Generate a test tone for audio testing"""
        import math
        import struct
        
        try:
            print(f"[AudioStreamer] Generating {frequency}Hz test tone for {duration}s")
            
            sample_rate = 22050
            samples_per_chunk = 2048
            total_samples = int(sample_rate * duration)
            
            for i in range(0, total_samples, samples_per_chunk):
                chunk_samples = min(samples_per_chunk, total_samples - i)
                samples = []
                
                for j in range(chunk_samples):
                    t = (i + j) / sample_rate
                    sample = int(32767 * 0.3 * math.sin(2 * math.pi * frequency * t))  # 30% volume
                    samples.append(sample)
                
                # Convert to bytes
                chunk_bytes = b''.join(struct.pack('<h', sample) for sample in samples)
                chunk_b64 = base64.b64encode(chunk_bytes).decode('ascii')
                
                # Send to all connected clients
                if socketio:
                    for client_id in self.client_sessions:
                        socketio.emit('audio_data', {
                            'data': chunk_b64,
                            'format': 'pcm_s16le_22050_mono'
                        }, room=client_id)
                
                time.sleep(0.05)  # 50ms between chunks
            
            print("[AudioStreamer] Test tone generation completed")
            
        except Exception as e:
            print(f"[AudioStreamer] Test tone error: {e}")
            if socketio:
                for client_id in self.client_sessions:
                    socketio.emit('audio_status', {'status': 'error', 'message': f'Test tone failed: {e}'}, room=client_id)


# Global audio streamer instance
print("[AudioStreamer] Creating global audio streamer instance")
audio_streamer = AudioStreamer()

# WebSocket event handlers
def handle_start_simple_audio():
    """Handle start audio streaming request"""
    return audio_streamer.start_streaming(request.sid)

def handle_stop_simple_audio():
    """Handle stop audio streaming request"""
    return audio_streamer.stop_streaming(request.sid)

def handle_test_audio_tone():
    """Handle test audio tone request"""
    audio_streamer.generate_test_tone()

def handle_disconnect():
    """Handle client disconnection"""
    audio_streamer.handle_client_disconnect(request.sid)

def get_audio_streaming_status():
    """Get audio streaming status"""
    return audio_streamer.get_status()

# Export compatibility functions
def is_audio_streaming():
    """Check if audio streaming is active"""
    return audio_streamer.active

def set_socketio_instance(sockio):
    """Set the socketio instance - called by main_app"""
    global socketio
    socketio = sockio

print("[AudioStreamer] Module initialized")
# Analiza Integrării MediaMTX în Proiectul Havatar

## Prezentare Generală MediaMTX

[MediaMTX](https://github.com/bluenviron/mediamtx) este un server media real-time, gata de utilizare și fără dependențe, care permite publicarea, citirea, proxy-ul, înregistrarea și redarea fluxurilor video și audio. A fost conceput ca un "router media" care rutează fluxurile media de la un capăt la altul.

### Caracteristici Principale MediaMTX
- **Protocoale Multiple**: SRT, WebRTC, RTSP, RTMP, HLS, MPEG-TS, RTP
- **Conversie Automată**: Fluxurile sunt convertite automat dintr-un protocol în altul
- **Înregistrare**: Salvare pe disc în format fMP4 sau MPEG-TS
- **Autentificare**: Suport pentru autentificare internă, HTTP sau JWT
- **Proxy și Forward**: Redirecționarea fluxurilor către alte servere
- **API de Control**: Control prin API REST
- **Hot Reloading**: Reîncărcarea configurației fără deconectarea clienților
- **Metrici**: Monitorizare prin metrici compatibile cu Prometheus
- **Cross-platform**: Linux, Windows, macOS, fără dependențe

## 🎯 Analiza Compatibilității cu Havatar

### Situația Actuală în Havatar

#### **Streaming Video Actual**
```
Camera USB → V4L2 → OpenCV → MJPEG → HTTP Stream → Browser
```
- **Latență**: ~200-500ms
- **Calitate**: JPEG quality 85
- **Limitări**: Un singur client, bandwidth fix, fără adaptabilitate

#### **Streaming Audio Actual**
```
Microfon USB → ALSA → FFmpeg → PCM → WebSocket → Browser
```
- **Latență**: ~300-500ms
- **Format**: PCM 16-bit 44.1kHz
- **Limitări**: Unidirecțional, bandwidth mare, fără compresie

### 🚀 Beneficiile Integrării MediaMTX

#### **1. Îmbunătățiri Video Streaming**

##### **A. Latență Redusă cu WebRTC**
```
Camera USB → V4L2 → MediaMTX → WebRTC → Browser
```
- **Latență**: Sub 200ms (îmbunătățire de 2-3x)
- **Adaptabilitate**: Bitrate adaptiv în funcție de conexiune
- **Multi-client**: Suport pentru multiple vizualizări simultane
- **Codec**: H.264 hardware encoding pe Pi 5

##### **B. Streaming Profesional cu RTSP**
```
Camera USB → V4L2 → MediaMTX → RTSP → Client Profesional
```
- **Compatibilitate**: VLC, OBS Studio, aplicații mobile RTSP
- **Calitate**: Streaming de înaltă calitate fără degradare
- **Înregistrare**: Înregistrare directă în MediaMTX
- **Monitoring**: Acces la metrici detaliate

#### **2. Audio Bidirectional Îmbunătățit**

##### **A. Înlocuirea WebSocket Audio cu WebRTC**
```
Microfon ↔ MediaMTX ↔ WebRTC ↔ Browser (bidirectional)
```
- **Avantaje**:
  - Audio bidirectional nativ
  - Compresie Opus pentru bandwidth redus
  - Sincronizare perfectă cu video
  - Latență sub 150ms

##### **B. Alternativa la Mumble**
MediaMTX poate înlocui planul de implementare Mumble cu o soluție mai simplă și integrată:
```
Client Web → MediaMTX WebRTC → Robot (audio bidirectional)
```

#### **3. Arhitectură Simplificată**

##### **Înainte (Complexă)**
```
┌─────────────┐    ┌──────────────┐    ┌─────────────┐
│ Client Web  │    │ Raspberry Pi │    │    ESP32    │
│             │    │              │    │             │
│ Video MJPEG │◄───┤ OpenCV       │    │             │
│ Audio WS    │◄───┤ FFmpeg       │    │             │
│ Commands    │────┤ Flask API    │────┤ Serial      │
└─────────────┘    └──────────────┘    └─────────────┘
```

##### **După (Simplificată cu MediaMTX)**
```
┌─────────────┐    ┌──────────────┐    ┌─────────────┐
│ Client Web  │    │ Raspberry Pi │    │    ESP32    │
│             │    │              │    │             │
│ WebRTC A/V  │◄───┤ MediaMTX     │    │             │
│ Commands    │────┤ Flask API    │────┤ Serial      │
└─────────────┘    └──────────────┘    └─────────────┘
```

## 🛠️ Implementarea Propusă

### **Faza 1: Integrarea de Bază**

#### **A. Instalarea MediaMTX pe Raspberry Pi**
```bash
# Download MediaMTX pentru ARM64
wget https://github.com/bluenviron/mediamtx/releases/latest/download/mediamtx_v1.14.0_linux_arm64v8.tar.gz
tar -xzf mediamtx_v1.14.0_linux_arm64v8.tar.gz
sudo mv mediamtx /usr/local/bin/
sudo chmod +x /usr/local/bin/mediamtx
```

#### **B. Configurarea MediaMTX**
```yaml
# /etc/mediamtx.yml
# Configurare optimizată pentru Havatar

# General settings
logLevel: info
logDestinations: [stdout]
logFile: /var/log/mediamtx.log

# API settings
api: yes
apiAddress: 127.0.0.1:9997

# Metrics
metrics: yes
metricsAddress: 127.0.0.1:9998

# WebRTC settings
webrtc: yes
webrtcAddress: :8889
webrtcEncryption: no  # Pentru rețea locală
webrtcICEServers:
  - url: stun:stun.l.google.com:19302

# RTSP settings
rtsp: yes
rtspAddress: :8554

# HLS settings (pentru mobile)
hls: yes
hlsAddress: :8888
hlsEncryption: no

# Path pentru camera principală
paths:
  havatar_camera:
    source: publisher
    publishUser: havatar
    publishPass: robot123
    
    # WebRTC specific
    webrtcDisable: no
    
    # RTSP specific  
    rtspDisable: no
    
    # HLS pentru mobile
    hlsDisable: no
    hlsSegmentCount: 3
    hlsSegmentDuration: 1s
    
    # Recording
    record: no  # Controlat prin API
    recordPath: /home/pi/recordings/%path/%Y-%m-%d_%H-%M-%S.mp4
```

#### **C. Modificarea Modulului Camera**
```python
# modules/camera_mediamtx.py
import subprocess
import requests
import json
from typing import Optional

class MediaMTXCameraManager:
    def __init__(self):
        self.mediamtx_api = "http://127.0.0.1:9997/v3"
        self.stream_name = "havatar_camera"
        self.ffmpeg_process: Optional[subprocess.Popen] = None
        
    def start_streaming(self):
        """Pornește streaming-ul către MediaMTX"""
        try:
            # Comandă FFmpeg optimizată pentru MediaMTX
            cmd = [
                'ffmpeg', '-hide_banner', '-loglevel', 'error',
                '-f', 'v4l2', '-i', CAMERA_DEVICE,
                '-c:v', 'libx264', '-preset', 'ultrafast', '-tune', 'zerolatency',
                '-pix_fmt', 'yuv420p', '-g', '30', '-keyint_min', '30',
                '-b:v', '1000k', '-maxrate', '1200k', '-bufsize', '2000k',
                '-f', 'rtsp', f'rtsp://havatar:robot123@127.0.0.1:8554/{self.stream_name}'
            ]
            
            self.ffmpeg_process = subprocess.Popen(cmd)
            print(f"[MediaMTX] Started streaming to {self.stream_name}")
            return True
            
        except Exception as e:
            print(f"[MediaMTX] Failed to start streaming: {e}")
            return False
    
    def stop_streaming(self):
        """Oprește streaming-ul"""
        if self.ffmpeg_process:
            self.ffmpeg_process.terminate()
            self.ffmpeg_process = None
    
    def start_recording(self, filename: str = None):
        """Pornește înregistrarea prin MediaMTX API"""
        try:
            response = requests.post(
                f"{self.mediamtx_api}/config/paths/{self.stream_name}/record/start"
            )
            return response.status_code == 200
        except Exception as e:
            print(f"[MediaMTX] Recording start failed: {e}")
            return False
    
    def stop_recording(self):
        """Oprește înregistrarea"""
        try:
            response = requests.post(
                f"{self.mediamtx_api}/config/paths/{self.stream_name}/record/stop"
            )
            return response.status_code == 200
        except Exception as e:
            print(f"[MediaMTX] Recording stop failed: {e}")
            return False
    
    def get_stream_stats(self):
        """Obține statistici stream"""
        try:
            response = requests.get(f"{self.mediamtx_api}/paths/list")
            if response.status_code == 200:
                data = response.json()
                for path in data.get('items', []):
                    if path['name'] == self.stream_name:
                        return {
                            'active': True,
                            'readers': len(path.get('readers', [])),
                            'bytes_sent': path.get('bytesSent', 0),
                            'bytes_received': path.get('bytesReceived', 0)
                        }
            return {'active': False}
        except Exception as e:
            print(f"[MediaMTX] Stats error: {e}")
            return {'active': False, 'error': str(e)}
```

### **Faza 2: Integrarea Audio Bidirectional**

#### **A. Configurarea Audio în MediaMTX**
```yaml
# Adăugare în mediamtx.yml
paths:
  havatar_audio:
    source: publisher
    publishUser: havatar
    publishPass: robot123
    
    # Doar WebRTC pentru audio bidirectional
    webrtcDisable: no
    rtspDisable: yes
    hlsDisable: yes
```

#### **B. Modulul Audio MediaMTX**
```python
# modules/audio_mediamtx.py
class MediaMTXAudioManager:
    def __init__(self):
        self.stream_name = "havatar_audio"
        self.ffmpeg_input: Optional[subprocess.Popen] = None
        self.ffmpeg_output: Optional[subprocess.Popen] = None
    
    def start_audio_streaming(self):
        """Pornește streaming audio bidirectional"""
        try:
            # Input: Microfon → MediaMTX
            input_cmd = [
                'ffmpeg', '-hide_banner', '-loglevel', 'error',
                '-f', 'alsa', '-i', MIC_PLUG,
                '-c:a', 'opus', '-b:a', '64k', '-ar', '48000', '-ac', '1',
                '-f', 'rtsp', f'rtsp://havatar:robot123@127.0.0.1:8554/{self.stream_name}'
            ]
            
            self.ffmpeg_input = subprocess.Popen(input_cmd)
            
            # Output: MediaMTX → Difuzor (pentru audio primit)
            # Implementare prin WebRTC JavaScript în browser
            
            return True
            
        except Exception as e:
            print(f"[MediaMTX Audio] Failed to start: {e}")
            return False
```

### **Faza 3: Frontend WebRTC**

#### **A. JavaScript Client WebRTC**
```javascript
// static/mediamtx-client.js
class MediaMTXClient {
    constructor() {
        this.pc = null;
        this.videoElement = document.getElementById('robot-video');
        this.audioElement = document.getElementById('robot-audio');
        this.localStream = null;
    }
    
    async connect() {
        try {
            // Configurare WebRTC
            this.pc = new RTCPeerConnection({
                iceServers: [{ urls: 'stun:stun.l.google.com:19302' }]
            });
            
            // Primire stream video/audio de la robot
            this.pc.ontrack = (event) => {
                const [stream] = event.streams;
                const track = event.track;
                
                if (track.kind === 'video') {
                    this.videoElement.srcObject = stream;
                } else if (track.kind === 'audio') {
                    this.audioElement.srcObject = stream;
                }
            };
            
            // Trimitere audio către robot (pentru comunicare bidirectională)
            this.localStream = await navigator.mediaDevices.getUserMedia({
                audio: true,
                video: false
            });
            
            this.localStream.getTracks().forEach(track => {
                this.pc.addTrack(track, this.localStream);
            });
            
            // Conectare la MediaMTX WebRTC endpoint
            await this.connectToMediaMTX();
            
        } catch (error) {
            console.error('[MediaMTX] Connection failed:', error);
        }
    }
    
    async connectToMediaMTX() {
        // Implementare specifică pentru MediaMTX WebRTC signaling
        // Vezi documentația MediaMTX pentru detalii complete
        
        const response = await fetch('/api/mediamtx/webrtc/whep', {
            method: 'POST',
            headers: { 'Content-Type': 'application/sdp' },
            body: await this.pc.createOffer()
        });
        
        const answer = await response.text();
        await this.pc.setRemoteDescription({
            type: 'answer',
            sdp: answer
        });
    }
}
```

## 📊 Comparația Performanțelor

### **Latența (ms)**
| Funcționalitate | Actual | Cu MediaMTX | Îmbunătățire |
|-----------------|--------|-------------|--------------|
| Video Streaming | 300-500 | 150-250 | **50%** |
| Audio Streaming | 300-500 | 100-200 | **60%** |
| Audio Bidirectional | N/A | 150-250 | **Nou** |

### **Bandwidth (Mbps)**
| Calitate | Actual MJPEG | MediaMTX H.264 | Economie |
|----------|--------------|----------------|----------|
| 720p | 3-5 Mbps | 1-2 Mbps | **60%** |
| 480p | 2-3 Mbps | 0.5-1 Mbps | **70%** |
| Audio | 1.4 Mbps (PCM) | 0.064 Mbps (Opus) | **95%** |

### **Funcționalități Noi**
- ✅ **Multi-client**: Vizualizare simultană de pe multiple dispozitive
- ✅ **Audio bidirectional**: Comunicare vocală în timp real
- ✅ **Adaptabilitate**: Calitate adaptivă la bandwidth
- ✅ **Compatibilitate**: Acces prin aplicații RTSP profesionale
- ✅ **Înregistrare îmbunătățită**: Control prin API, multiple formate
- ✅ **Monitoring**: Metrici detaliate și statistici în timp real

## 🎯 Recomandări de Implementare

### **Prioritatea 1: Video WebRTC (Săptămâna 1-2)**
1. Instalarea și configurarea MediaMTX
2. Modificarea modulului camera pentru streaming RTSP
3. Implementarea client-ului WebRTC în frontend
4. Testing și optimizarea latenței

### **Prioritatea 2: Audio Bidirectional (Săptămâna 3-4)**
1. Configurarea audio streaming în MediaMTX
2. Implementarea audio bidirectional în browser
3. Integrarea cu sistemul TTS existent
4. Testing calitate audio și sincronizare

### **Prioritatea 3: Funcționalități Avansate (Săptămâna 5-6)**
1. Multi-client support și management sesiuni
2. Înregistrare îmbunătățită prin MediaMTX
3. Monitoring și metrici integrate
4. Optimizări pentru 4G și mobile

## 💡 Concluzie

**MediaMTX este o soluție excelentă pentru Havatar** care poate rezolva majoritatea limitărilor actuale:

### **Beneficii Majore:**
- **Latență redusă cu 50-60%** prin WebRTC
- **Bandwidth redus cu 60-95%** prin codecuri moderne
- **Audio bidirectional nativ** (înlocuiește planul Mumble)
- **Arhitectură simplificată** (mai puține componente)
- **Compatibilitate extinsă** (RTSP, WebRTC, HLS)
- **Scalabilitate** (multi-client support)

### **Integrarea Graduală:**
MediaMTX poate fi integrat treptat, păstrând funcționalitatea existentă ca fallback. Aceasta permite testarea și optimizarea fără întreruperea serviciului actual.

### **Compatibilitate cu Planurile Existente:**
MediaMTX se integrează perfect cu arhitectura server-centralizată propusă în `docs/propunere.md`, oferind o alternativă mai simplă și mai eficientă la componentele WebRTC și Mumble planificate.

**Recomandare finală**: Implementarea MediaMTX este o îmbunătățire semnificativă care va transforma Havatar într-un sistem de teleprezență profesional, cu latență minimă și funcționalități avansate, ideal pentru utilizatorii cu mobilitate redusă.

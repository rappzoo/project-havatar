# Fluxurile de Comunicare în Proiectul Havatar

## Prezentare Generală

Proiectul Havatar este un robot tank controlat de la distanță, construit pe Raspberry Pi 5 și ESP32, destinat prezenței la distanță pentru persoanele cu mobilitate redusă (ALS). Sistemul folosește multiple fluxuri de comunicare pentru video, audio și control motor.

## 🎤 Fluxurile de Comunicare Vocală

### Direcțiile Comunicării Audio

#### 1. **Captarea Audio (Microfon → Raspberry Pi)**
- **Sursă**: Microfon USB (SF-558) conectat la Raspberry Pi 5
- **Configurare**: `plughw:0,0` (detectat automat)
- **Procesare**: FFmpeg pentru captarea și encodarea audio

#### 2. **Streaming Audio în Timp Real (Pi → Client Web)**
Sistemul implementează **streaming audio prin WebSocket**:

##### **Modul Actual Implementat (⚡ WebSocket Realtime)**
```
Microfon USB → ALSA → FFmpeg (PCM s16le 44.1kHz) → WebSocket → Browser Client
```
- **Codec**: PCM raw 16-bit little-endian
- **Sample Rate**: 44.1kHz mono pentru calitate audio optimă
- **Latență**: Sub 500ms prin WebSocket
- **Transport**: WebSocket cu SocketIO pentru latență minimă
- **Filtrare**: Highpass (100Hz) și Lowpass (7kHz) pentru reducerea zgomotului
- **Buffer**: Chunk size 8192 bytes pentru streaming fluid
- **Encoding**: Base64 pentru transport prin WebSocket

#### 3. **Audio Bidirectional cu Mumble (PLANIFICAT)**
```
Client Mumble ←→ Server Mumble (Pi) ←→ Dispozitive Audio USB
```
- **Status**: 🚧 **ÎN DEZVOLTARE** - Vezi propunerea tehnică din `docs/propunere.md`
- **Arhitectură Planificată**: Server Mumble (Murmur) pe Raspberry Pi 5
- **Client Planificat**: Mumble headless controlat prin web interface
- **Protocol Planificat**: Opus codec pentru calitate optimă
- **Control Planificat**: API REST pentru connect/disconnect/mute
- **Avantaje Planificate**: Audio full-duplex, latență foarte mică

**Nota**: Funcționalitatea Mumble este prezentă în versiunea monolitică de backup dar nu în arhitectura modulară actuală. Implementarea completă este planificată în migrarea către arhitectura server-centralizată.

#### 4. **Text-to-Speech (TTS)**
```
Text Input (Web UI) → Piper TTS → Difuzor USB → Mediu Fizic
```
- **Engine**: Piper TTS cu suport pentru română și engleză
- **Output**: Difuzor USB (`plughw:3,0`)
- **Caracteristici**: Suport diacritice românești (ă, â, î, ș, ț)

### Direcțiile de Comunicare

1. **Unidirecțional (Pi → Client)** - ✅ **IMPLEMENTAT**:
   - Streaming microfon în timp real prin WebSocket
   - Feedback audio din mediul robotului cu filtrare zgomot

2. **Unidirecțional (Client → Pi)** - ✅ **IMPLEMENTAT**:
   - Comenzi TTS pentru comunicare vocală
   - Text convertit în vorbire locală cu suport Piper
   - Predicție de text pentru input rapid

3. **Bidirectional (Client ↔ Pi)** - 🚧 **PLANIFICAT**:
   - Mumble pentru conversații în timp real (în dezvoltare)
   - Control complet prin web interface (parțial implementat)

## 📹 Fluxurile Video

### Arhitectura Video

#### 1. **Captura Video**
```
Camera USB Ultra-Wide → V4L2 (/dev/video0) → OpenCV → Frame Buffer
```
- **Driver**: V4L2 (Video4Linux2)
- **Format**: MJPEG pentru performanță optimă
- **Rezoluții**: 320p (15fps), 480p (20fps), 720p (10fps)
- **Detectare**: Auto-detectare capabilități cameră

#### 2. **Streaming Video Live**
```
OpenCV Frame Buffer → JPEG Encoding → HTTP MJPEG Stream → Browser Client
```
- **Codec**: MJPEG pentru latență mică
- **Calitate**: JPEG quality 85 pentru balans calitate/bandwidth
- **Buffer**: Shared frame buffer pentru streaming + recording
- **Recuperare**: Auto-reconnect la eșecuri cameră

#### 3. **Recording Video**
```
Frame Buffer → FFmpeg → MP4 (H.264) → Stocare Locală
```
- **Codec**: H.264 pentru compresie eficientă
- **Audio**: Sincronizat cu microfonul
- **Stocare**: Director `recordings/`
- **Trigger**: Buton record în web interface

#### 4. **Snapshots**
```
Frame Buffer → JPEG → Stocare Locală (snapshots/)
```
- **Format**: JPEG de înaltă calitate
- **Timestamp**: Automat în numele fișierului
- **Acces**: Download direct prin web interface

### Caracteristici Video

- **Rezoluție Adaptivă**: Schimbare dinamică fără restart
- **Monitoring Bandwidth**: Contorizare trafic în timp real
- **Recuperare Robustă**: Reinițializare automată la crash-uri
- **Optimizare 4G**: Codec și calitate optimizate pentru conexiuni mobile

## ⚙️ Comunicarea cu Motoarele

### Arhitectura Control Motor

#### 1. **Fluxul de Comandă**
```
Web UI (WASD/Butoane) → Flask API → Serial (USB) → ESP32 → Motoare DC
```

#### 2. **Protocolul Serial**
- **Port**: `/dev/ttyUSB0` (auto-detectat)
- **Baudrate**: 115200
- **Protocol**: Comenzi text + răspunsuri JSON

#### 3. **Comenzile Motor**
```
Raspberry Pi → ESP32:
- "PWM <left> <right>" (valori -255 la +255)
- "STOP" (oprire imediată)
- "STATUS" (interogare stare)

ESP32 → Raspberry Pi:
- {"ok": true, "voltage": 12.4, "current": 2.1}
- {"ok": false, "error": "motor_fault"}
```

#### 4. **Tipurile de Mișcare**
- **Înainte**: PWM pozitiv pe ambele motoare
- **Înapoi**: PWM negativ pe ambele motoare  
- **Stânga**: Motor stâng negativ, motor drept pozitiv
- **Dreapta**: Motor stâng pozitiv, motor drept negativ
- **Oprire**: PWM 0 pe ambele motoare

#### 5. **Monitorizarea Bateriei**
```
INA219 (ESP32) → Voltage/Current → Serial → Raspberry Pi → Web UI
```
- **Senzor**: INA219 pentru monitorizare precisă
- **Parametri**: Tensiune, curent, putere
- **Frecvență**: Update la fiecare comandă motor
- **Display**: Indicator vizual în web interface

### Caracteristici Siguranță

- **Dead-man's Switch**: Motoarele se opresc când se eliberează comenzile
- **Auto-detectare Port**: Testare automată `/dev/ttyUSB*` și `/dev/ttyACM*`
- **Timeout**: Comenzile expiră automat pentru siguranță
- **Limitare Viteză**: PWM limitat la -255/+255
- **Recovery**: Reconectare automată la pierderea conexiunii seriale

## 🌐 Rolul ZeroTier VPN

### Ce este ZeroTier?

ZeroTier este o soluție de rețea definită prin software (SDN) care creează o rețea privată virtuală (VPN) între dispozitive, indiferent de locația lor geografică.

### Beneficiile pentru Havatar

#### 1. **Acces Remote Securizat**
```
Client (Laptop/Telefon) ←→ ZeroTier Network ←→ Raspberry Pi 5 (Robot)
```
- **Criptare**: End-to-end encryption pentru toate comunicațiile
- **Autentificare**: ID-uri criptografice unice pentru fiecare dispozitiv
- **Acces**: Controlul robotului de oriunde în lume

#### 2. **Conectivitate Directă P2P**
- **Latență Redusă**: Comunicare directă între dispozitive
- **Bypass NAT**: Funcționează prin firewall-uri și NAT
- **Optimizare Rută**: Găsește cea mai eficientă cale de comunicare

#### 3. **Compatibilitate 4G/Mobile**
```
Robot (4G Modem) ←→ ZeroTier Cloud ←→ Client (WiFi/4G)
```
- **Mobilitate**: Robotul poate fi controlat în mișcare
- **Redundanță**: WiFi + 4G pentru conectivitate continuă
- **Roaming**: Schimbarea rețelelor fără întrerupere

#### 4. **Configurare Simplă**
- **Zero Configuration**: Nu necesită configurări complexe de rețea
- **Auto-Discovery**: Dispozitivele se găsesc automat în rețea
- **Management Central**: Control prin ZeroTier Central dashboard

#### 5. **Avantaje pentru ALS/Mobilitate Redusă**
- **Acces Permanent**: Control 24/7 al robotului de acasă
- **Independență**: Nu depinde de configurări IT complexe
- **Fiabilitate**: Conexiune stabilă pentru monitorizare continuă
- **Securitate**: Protecție împotriva accesului neautorizat

### Implementarea în Proiect

1. **Configurare Externă**: ZeroTier se configurează separat de aplicația principală
2. **Transparență**: Aplicația Flask funcționează normal prin ZeroTier
3. **Portabilitate**: Robotul poate fi mutat fără reconfigurări
4. **Scalabilitate**: Suport pentru multiple dispozitive client

## 📊 Diagrama Fluxurilor Complete

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Client Web    │    │  Raspberry Pi 5  │    │     ESP32       │
│  (Browser/App)  │    │   (Controller)   │    │ (Motor Control) │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │                       │
         │ ◄─── ZeroTier VPN ───► │                       │
         │                       │                       │
    ┌────▼────┐              ┌───▼───┐               ┌───▼───┐
    │ Video   │              │OpenCV │               │Serial │
    │ MJPEG   │ ◄────────────┤Camera │               │ USB   │
    │ Stream  │              │ V4L2  │               │115200 │
    └─────────┘              └───────┘               └───┬───┘
                                 │                       │
    ┌─────────┐              ┌───▼───┐               ┌───▼───┐
    │ Audio   │              │FFmpeg │               │ DC    │
    │WebSocket│ ◄────────────┤ ALSA  │               │Motors │
    │PCM 44kHz│              │ Mic   │               │ 520   │
    └─────────┘              └───────┘               └───────┘
         │                       │
    ┌────▼────┐              ┌───▼───┐
    │ Mumble  │ ◄────────────┤Mumble │
    │(Future) │              │(Plan) │
    └─────────┘              └───────┘
         │                       │
    ┌────▼────┐              ┌───▼───┐
    │Commands │ ────────────►│ Flask │
    │WASD/GUI │              │  API  │
    └─────────┘              └───────┘
```

## 🔧 Configurarea și Optimizarea

### Configurare Automată
- **Device Detection**: Auto-detectare cameră, microfon, difuzor, port serial
- **Configurare Salvată**: `avatar_tank_config.json` pentru persistență
- **Fallback**: Configurări default la eșecul detectării

### Optimizări pentru 4G
- **Bandwidth Monitoring**: Contorizare trafic în timp real
- **Codec Selection**: Opus pentru audio, MJPEG pentru video
- **Buffer Management**: Buffere mici pentru latență redusă
- **Quality Adaptation**: Rezoluție adaptivă la bandwidth

### Monitorizare și Diagnostice
- **Status Real-time**: Baterie, rețea, dispozitive
- **Error Recovery**: Reconectare automată la eșecuri
- **Logging**: Diagnostice detaliate pentru depanare
- **Health Checks**: Verificări periodice ale sistemului

---

## 📋 Actualizări Documentație

**Ultima actualizare**: Decembrie 2024

### Modificări Recente
- ✅ **Corectat**: Descrierea audio streaming-ului pentru a reflecta implementarea reală (WebSocket PCM în loc de 3 moduri separate)
- ✅ **Clarificat**: Statusul funcționalității Mumble (planificată, nu implementată în modulele actuale)
- ✅ **Actualizat**: Diagramele pentru a reflecta arhitectura modulară actuală
- ✅ **Adăugat**: Statusuri clare (✅ IMPLEMENTAT / 🚧 PLANIFICAT) pentru toate funcționalitățile

### Verificare Conformitate
Documentația a fost verificată împotriva codului sursă din arhitectura modulară (decembrie 2024) pentru acuratețe tehnică.

---

*Documentația descrie fluxurile complete de comunicare în proiectul Havatar, optimizat pentru controlul la distanță prin ZeroTier VPN și conexiuni 4G mobile. Actualizată pentru a reflecta implementarea reală din arhitectura modulară.*

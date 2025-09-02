# Changelog - Proiectul Havatar

Toate schimbările importante ale proiectului sunt documentate în acest fișier.

## [2.0.0] - Decembrie 2024 - Refactorizarea Modulară

### 🎯 Schimbări Majore
- **Arhitectură Modulară Completă**: Refactorizarea întregului cod într-o structură modulară
- **Launcher Enhanced**: Sistem complet de verificări și diagnostice la pornire
- **Audio Streaming Multi-Modal**: Trei moduri de streaming audio (Standard/Optimized/Realtime)
- **Predicție de Text**: Sistem inteligent de sugerare cuvinte pentru TTS
- **Documentație Avansată**: Documentație completă a fluxurilor și propuneri tehnice

### ✨ Funcționalități Noi

#### Core Modules
- `modules/main_app.py` - Aplicația principală Flask coordinator
- `modules/device_detector.py` - Detectarea automată a dispozitivelor hardware
- `modules/camera.py` - Management cameră și streaming
- `modules/motor_controller.py` - Comunicația ESP32 și controlul motoarelor
- `modules/tts.py` - Text-to-Speech cu suport Piper
- `modules/recorder.py` - Funcționalitatea de înregistrare video/audio
- `modules/audio_utils.py` - Utilitare pentru managementul dispozitivelor audio
- `modules/predictor.py` - Sistemul de predicție și sugerare de cuvinte
- `modules/audio_streamer.py` - Streaming audio prin WebSocket

#### Enhanced Launcher (`avatar_tank_enhanced.py`)
- Verificări complete ale sistemului și dependențelor
- Testarea modulelor și diagnostice
- Verificarea permisiunilor și grupurilor utilizator
- Setup automat al mediului Python
- Monitoring în timp real al stării sistemului
- Suport pentru variabile de mediu override (AV_CAMERA, AV_MIC, AV_SPK, AV_MOTOR)

#### Audio Streaming Îmbunătățit
- **Standard Mode**: AAC cu calitate bună pentru toate browserele
- **Optimized Mode**: Opus 16kbps pentru bandwidth redus cu 50%
- **Realtime Mode**: PCM prin WebSocket pentru latență sub 500ms
- Fallback automat la HTTP dacă WebSocket eșuează

#### Text Prediction System
- Învățare automată din textul introdus în TTS
- Sugerări rapide de cuvinte pentru utilizatori cu mobilitate redusă
- Dicționare extensibile pentru română și engleză
- API REST pentru integrare cu interfața web

### 🔧 Îmbunătățiri Tehnice

#### Robustețea Sistemului
- Module dummy pentru funcționarea continuă la eșecuri hardware
- Gestionarea robustă a erorilor cu mesaje descriptive
- Auto-reconnect pentru toate conexiunile (cameră, serial, audio)
- Verificări de sănătate periodice pentru toate componentele

#### Device Detection Enhanced
- Auto-detectarea camerelor USB cu testare capabilități
- Detectarea automată a dispozitivelor audio (microfon/difuzor)
- Scanarea porturilor seriale pentru ESP32
- Configurare persistentă în `avatar_tank_config.json`
- Fallback la configurări default

#### ESP32 Firmware
- Monitorizarea bateriei cu INA219 pentru măsurători precise
- Comunicație serială robustă cu Raspberry Pi
- Heartbeat și raportare status în timp real
- Suport pentru comenzi PWM și control motoare

### 📚 Documentație Nouă

#### Documentație Tehnică Avansată
- **`docs/fluxuri.md`** - Documentația completă a fluxurilor de comunicare
  - Fluxuri audio (3 moduri de streaming)
  - Arhitectura video cu OpenCV și V4L2
  - Comunicarea cu motoarele prin ESP32
  - Integrarea ZeroTier VPN pentru acces remote
  
- **`docs/propunere.md`** - Propunerea tehnică pentru arhitectura server-centralizată
  - Migrarea de la P2P la server centralizat
  - Optimizarea latenței pentru control în timp real
  - WebRTC pentru streaming video
  - Mumble pentru audio bidirectional
  - Plan de implementare detaliat cu costuri

#### Ghiduri de Dezvoltare
- **`MODULAR_REFACTOR_SUMMARY.md`** - Rezumatul refactorizării
- **`MODULES_README.md`** - Ghidul de utilizare al modulelor
- **`module_examples.py`** - Exemple de utilizare a modulelor individuale

### 🛠️ Schimbări în Development

#### Project Structure
```
Structura nouă modulară:
├── modules/                    # Core modules (NEW!)
├── static/                    # Web interface files
├── docs/                      # Enhanced documentation (NEW!)
├── esp_firmware/              # ESP32 firmware
├── backup/                    # Backup versions (NEW!)
├── MODULAR_REFACTOR_SUMMARY.md # Refactoring docs (NEW!)
├── MODULES_README.md          # Module guide (NEW!)
├── module_examples.py         # Usage examples (NEW!)
└── CHANGELOG.md              # This file (NEW!)
```

#### Dependencies
- Menținute dependențele minime în `requirements.txt`
- Suport pentru import opțional cu fallback
- Compatibilitate cu Python 3.8+

### 🔄 Backward Compatibility
- Launcher-ul `avatar_tank_enhanced.py` menține compatibilitatea
- Configurația `avatar_tank_config.json` rămâne aceeași
- API-ul web menține toate endpoint-urile existente
- Interfața web funcționează identic pentru utilizatori

### 🚀 Performance Improvements
- Streaming audio optimizat cu 50% mai puțin bandwidth în modul Optimized
- Latență redusă sub 500ms în modul Realtime
- Predicția de text pentru input mai rapid
- Diagnostice de sistem pentru depanare rapidă

### 🛡️ Security & Reliability
- Verificări de permisiuni pentru dispozitive
- Gestionarea robustă a erorilor cu recuperare automată
- Logging detaliat pentru diagnostice
- Fallback la configurări sigure

## [1.0.0] - Versiunea Inițială Monolitică

### Funcționalități de Bază
- Control tank prin WASD și butoane web
- Streaming video live prin OpenCV
- Streaming audio prin FFmpeg
- Comunicație serială cu ESP32
- Text-to-Speech cu suport pentru română
- Înregistrare video/audio sincronizată
- Monitorizarea bateriei
- Acces remote prin ZeroTier VPN

---

*Pentru informații detaliate despre fiecare schimbare, consultă documentația din directorul `docs/`.*

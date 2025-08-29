# Proiectul "Havatar" - Un Robot Tank de Prezență Remotă

---

## Despre Ce Vorbim Aici, Dragii Mei

Să vă spun o poveste, o poveste despre cum se face un robot adevărat, nu vreo jucărie de plastic din magazinele chinezești. Aici avem de-a face cu **"Havatar"** - un robot tank controlat remote care nu e o glumă de-a copiilor, ci o creație serioasă pentru oameni serioși.

### Pentru Cine E Făcut Acest Minunat Proiect

Dragii mei, acest robot nu e pentru toată lumea. E gândit special pentru utilizatori cu **ALS** (Scleroză Laterală Amiotrofică), care au nevoie să controleze totul cu ochii - prin eye-gaze tracking și tastatură/mouse de la distanță. Nu e despre gadget-uri fancy, e despre **independență și demnitate**.

## Inima Tehnicii - Hardware-ul Care Contează

### Șasiul și Mișcarea
- **Bază tank cu șenile de 30 cm** - pentru că mersul pe roți e pentru amatori
- **2 motoare DC 520 cu encodere** - să știi mereu unde ești și cu ce viteză mergi
- **Controller ESP32** (Waveshare) care se ocupă de motoare și monitorizarea bateriei

### Creierul Operațiunii
- **Raspberry Pi 5 (8GB)** - nu-ți face economii la procesor când vine vorba de viață
- Poate boota de pe SD sau SSD (când se rezolvă problemele de alimentare, că nu-s toate perfecte în viață)

### Ochii și Urechile
- **Cameră web USB ultrawide** - să vezi tot ce se întâmplă
- **Microfon USB (SF-558)** - să auzi mediul înconjurător
- **Suport TTS** pentru feedback audio

### Energia și Conectivitatea
- **Baterie LiPo 12V** monitorizată prin INA219
- **Ethernet, WiFi și modem 4G** - pentru că izolarea nu e o opțiune
- **ZeroTier VPN** pentru acces securizat de oriunde

## Arhitectura Software - Cum Funcționează Totul

### Pe Raspberry Pi 5

**Flask Web Server** - centrul de comandă:
- Interfață web principală
- API pentru toate comenzile (mișcare, viteză, poze, audio, TTS)
- Comunicație serială cu ESP32
- Monitorizarea tuturor serviciilor

**MJPG-Streamer** pentru video live cu latență mică

**FFmpeg** pentru:
- Înregistrări video+audio sincronizate
- Streaming audio live de la microfon

**ZeroTier** pentru acces remote securizat

### Pe ESP32
- Control motoare DC cu feedback de la encodere
- Monitorizare baterie prin INA219
- Comunicație serială cu Pi-ul
- Pregătit pentru extensii (servo, IMU, etc.)

## Interfața Web - Controlul Intuitiv

### Feed Camera Live
Stream video în timp real cu:
- Rezoluție selectabilă
- Reconectare automată
- Optimizat pentru eye-gaze control

### Controlul Mișcării
- **WASD pe tastatură** sau butoane on-screen
- **"Hold-to-move"** - te miști doar cât ții apăsat (siguranță maximă)
- **Slider de viteză** 0-100% pentru control fin

### Monitorizare și Feedback
- Tensiune baterie în timp real
- Contor bandă și timp de funcționare
- Rezoluție și FPS curent
- Status toate serviciile

### Funcții Multimedia
- **Snapshots** instant
- **Înregistrări video+audio** stocate local
- **Buton "Listen"** pentru audio live din mediu
- **TTS input** pentru a face robotul să "vorbească"

## Siguranța - Pentru Că Viața Nu E Joacă

- Motoarele se mișcă **DOAR** cât timp ții apăsată comanda
- Port serial detectat automat prin ID unic
- Toate comenzile și statusurile vizibile în UI
- Gestionarea erorilor pentru cameră, serial, microfon

## Ce Merge Deja (Și Merge Bine)

✅ **Control mișcare** (hold-to-move, viteză, stop)  
✅ **Monitorizare baterie** în timp real  
✅ **Video live** prin MJPG-Streamer  
✅ **Audio "listen" și TTS**  
✅ **Snapshots și înregistrări**  
✅ **Acces remote securizat**  
✅ **Interfață web completă**  

## Ce Mai Urmează

🔧 **Îmbunătățiri streaming audio** (latență/calitate)  
🔧 **Boot direct de pe SSD** (când se rezolvă problemele de alimentare)  
🔧 **Date IMU/heading de la ESP32**  
🔧 **Control servo pentru tilt cameră**  
🔧 **Output speaker pentru TTS**  
🔧 **Optimizări UI pentru mobile/touch**  

## Provocările Rezolvate (Pentru Că Nimic Nu E Perfect)

- **Nume dispozitive audio instabile** - rezolvat prin "default:CARD=SF558"
- **Probleme alimentare SSD** - în curs de rezolvare
- **Sincronizare video/audio** - îmbunătățită prin FFmpeg
- **Startup automat** - toate serviciile critice pornesc automat

---

## Concluzia Danutzei

Nu e doar un robot - e **libertate** pentru cei care au nevoie de ea cel mai mult. Și asta, copii dragi, asta înseamnă cu adevărat să faci tehnologie care contează.

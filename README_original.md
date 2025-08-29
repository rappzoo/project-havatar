Project Overview: “havatar”
A remotely controlled, Raspberry Pi 5 + ESP32-powered tracked robot (“tank”) for remote presence, designed for hands-free control and rich sensory feedback.
Primary user:
You (with ALS), controlled by eye-gaze and keyboard/mouse from a remote laptop, optimized for quick commands and feedback.



Hardware Platform
Chassis: 30 cm tank-style tracked base (mecanum possible in future)


Motors: 2x 520 DC motors with encoders


Motor Controller: ESP32-based robot board (Waveshare), dual motor control + battery monitor, serial bus support


Main Computer: Raspberry Pi 5 (8GB), can boot from SD or SSD


Camera: USB ultrawide webcam


Audio: USB microphone (SF-558), future support for TTS speakers


Power: 12V LiPo battery (monitored by INA219 on ESP32)


Network: Wired Ethernet, WiFi, and 4G modem support (long-range via ZeroTier VPN)


Optional: HDMI for local display/messages, future LIDAR/I2C/OLED support



Software Architecture
On Raspberry Pi 5d:
Flask-based Web Server (app.py)


Hosts the main web UI


Runs and monitors MJPG-Streamer for video feed


Provides API for all commands (movement, speed, snapshots, audio, TTS)


Handles serial communication with ESP32 for motor and battery feedback


MJPG-Streamer


Streams the USB camera live (low-latency, user-selectable resolution)


FFmpeg


Records synchronized audio + video clips on command


Streams live audio from USB mic


Audio


“Listen” button for real-time microphone stream


Text-to-speech (TTS) output (speak text remotely)


ZeroTier


Secure remote access for control from anywhere (4G fallback)


Startup Scripts


MJPG-Streamer, Flask server, etc., start automatically on boot


On ESP32 Board:
Handles:


DC motor control with encoder feedback (speed + direction)


Battery voltage/current monitoring via INA219


Serial feedback: Sends battery readings to Pi


Receives movement/speed commands over serial from Pi


Ready for expansion: servo, IMU, etc.



Web UI Features (index.html)
Live Camera Feed:


View from the robot in near real-time (selectable resolution, auto reconnect)


Movement Controls:


WASD keyboard and on-screen “hold-to-move” buttons (press/hold = move, release = stop)


Speed slider (0–100%) for smooth driving


Monitor:
Bandwidth and bandwidth counter from uptime
Time and date .
Resolution and fps.


Live voltage reading from the robot displayed on the UI


Snapshot and Video Recording:


Snap a picture or record video+audio clips (stored on Pi, with feedback)


Audio:


“Listen” button streams robot’s mic live to your browser (for hearing environment)


TTS input to make robot speak (future: text appears on HDMI display as well)


Responsive UI:


Designed for eye-gaze, minimal clicks, quick response



Safety and Reliability
Motors only move while key/button is held


Serial port is detected by unique ID (no wrong port)


All commands and status feedback are visible in the web UI


Error handling: Missing camera, serial, or microphone is detected and logged



Notable Challenges (Handled/Outstanding)
Audio device names change: Now set by “default:CARD=SF558”


SSD power issues: (Currently troubleshooting—see last messages)


Video/Audio sync: Improved via FFmpeg recipes, with ongoing tweaks for best latency vs. quality


Automatic startup: All critical services set to auto-start (with logs for diagnosis)



What’s Ready / What’s Next
Almost Ready/Stable:
Drive control (hold-to-move, speed, stop)


Battery monitoring


Live video (via MJPG-Streamer)


Audio “listen” and TTS


Snapshots and video+audio recording


Remote secure access (ZeroTier)


Web UI for all commands


In progress / Possible to add next:
More reliable audio streaming (latency/quality tweaks)


Direct SSD boot and storage (when power issues resolved)


Feedback of IMU/heading data from ESP32


Add servo/camera tilt control


Speaker output for TTS


Mobile/touch-friendly UI tweaks

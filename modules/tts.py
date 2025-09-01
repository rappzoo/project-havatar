#!/usr/bin/env python3
"""
Text-to-Speech module for Avatar Tank system.
Handles speech synthesis using Piper or fallback engines.
"""

import subprocess
import shutil
import os
import glob
from modules.device_detector import SPK_PLUG


class PiperTTS:
    def __init__(self):
        self.languages = {
            'en': {'name': 'English', 'dir': '/home/havatar/piper/models/en'},
            'ro': {'name': 'Română',  'dir': '/home/havatar/piper/models/ro'},
            'de': {'name': 'Deutsch', 'dir': '/home/havatar/piper/models/de'},
        }
        self.current_language='en'
        self.bin, self.kind = self._find_piper_bin()

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
#!/usr/bin/env python3
"""
Audio utilities module for Avatar Tank system.
Handles volume control, audio device management, and audio streaming.
"""

import subprocess
import re
import os
from modules.device_detector import MIC_PLUG, SPK_PLUG


# ============== ALSA volume/mute helpers ==============
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
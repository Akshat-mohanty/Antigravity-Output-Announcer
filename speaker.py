#!/usr/bin/env python3
import sys
import os
import re
import asyncio
import subprocess

PID_FILE = "/tmp/agy_voice_reader.pid"
AUDIO_FILE = "/tmp/agy_speech.mp3"
CANCEL_FILE = "/tmp/agy_voice_cancelled"
CONFIG_FILE = os.path.join(PLUGIN_DIR, "config.json")

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                import json
                return json.load(f)
        except Exception:
            pass
    return {}

def is_cancelled():
    return os.path.exists(CANCEL_FILE)

def ensure_monitor():
    bin_dir = os.path.join(PLUGIN_DIR, "bin")
    mute_bin = os.path.join(bin_dir, "voice_mute_monitor")
    mute_src = os.path.join(bin_dir, "voice_mute_monitor.swift")
    if not os.path.exists(mute_bin) and os.path.exists(mute_src):
        try:
            subprocess.run(["swiftc", "-O", mute_src, "-o", mute_bin], capture_output=True, timeout=10.0)
        except Exception:
            pass
    if os.path.exists(mute_bin):
        return mute_bin
    ctrl_bin = os.path.join(bin_dir, "voice_ctrl_monitor")
    return ctrl_bin if os.path.exists(ctrl_bin) else None

def start_monitor():
    mon_bin = ensure_monitor()
    if not mon_bin or not os.path.exists(mon_bin):
        return None
    try:
        if os.path.exists(CANCEL_FILE):
            os.remove(CANCEL_FILE)
        cfg = load_config()
        mute_key = cfg.get("mute_key", "control")
        return subprocess.Popen(
            [mon_bin, "--parent", str(os.getpid()), "--key", str(mute_key)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True
        )
    except Exception:
        return None

def stop_monitor(proc):
    if proc:
        try:
            if proc.poll() is None:
                proc.terminate()
                proc.wait(timeout=0.5)
        except Exception:
            pass

def clean_speech_text(text):
    text = re.sub(r"\[\[slnc\s*\d+\]\]", ", ", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r",\s*,+", ", ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

async def generate_neural_speech(text, voice, out_path, rate="+1%", pitch="+0Hz"):
    import edge_tts
    clean = clean_speech_text(text)
    communicate = edge_tts.Communicate(clean, voice, rate=rate, pitch=pitch)
    await communicate.save(out_path)

def speak_neural(text, voice="en-US-AvaMultilingualNeural", volume=1.3, rate="+1%"):
    monitor = start_monitor()
    try:
        if is_cancelled():
            return False
        asyncio.run(generate_neural_speech(text, voice, AUDIO_FILE, rate=rate))
        if is_cancelled():
            return False
        if os.path.exists(AUDIO_FILE) and os.path.getsize(AUDIO_FILE) > 100:
            vol_str = str(min(max(volume, 0.5), 2.5))
            proc = subprocess.Popen(
                ["afplay", "-v", vol_str, AUDIO_FILE],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            with open(PID_FILE, "w") as f:
                f.write(str(proc.pid))
            proc.wait()
            if is_cancelled():
                return False
            return True
    except Exception:
        pass
    finally:
        stop_monitor(monitor)
    return False

def speak_system(text, voice="Samantha", rate=200):
    monitor = start_monitor()
    try:
        if is_cancelled():
            return False
        say_cmd = ["say"]
        if voice:
            say_cmd.extend(["-v", voice])
        if rate:
            say_cmd.extend(["-r", str(rate)])
        say_cmd.append(clean_speech_text(text))
        proc = subprocess.Popen(
            say_cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        with open(PID_FILE, "w") as f:
            f.write(str(proc.pid))
        proc.wait()
        if is_cancelled():
            return False
        return True
    except Exception:
        return False
    finally:
        stop_monitor(monitor)

def main():
    if len(sys.argv) < 2:
        return
    text = sys.argv[1]
    voice = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] else "en-US-AvaMultilingualNeural"
    engine = sys.argv[3] if len(sys.argv) > 3 and sys.argv[3] else "neural"
    rate = sys.argv[4] if len(sys.argv) > 4 and sys.argv[4] else "+1%"
    
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))

    if engine == "neural":
        ok = speak_neural(text, voice=voice, rate=rate)
        if not ok and not is_cancelled():
            speak_system(text, voice="Samantha")
    else:
        speak_system(text, voice=voice)

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
import sys
import os
import re
import asyncio
import subprocess

PID_FILE = "/tmp/agy_voice_reader.pid"
AUDIO_FILE = "/tmp/agy_speech.mp3"
CANCEL_FILE = "/tmp/agy_voice_cancelled"
PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
MONITOR_BIN = os.path.join(PLUGIN_DIR, "bin", "voice_ctrl_monitor")

def is_cancelled():
    return os.path.exists(CANCEL_FILE)

def start_monitor():
    if not os.path.exists(MONITOR_BIN):
        swift_src = os.path.join(PLUGIN_DIR, "bin", "voice_ctrl_monitor.swift")
        if os.path.exists(swift_src):
            try:
                subprocess.run(["swiftc", "-O", swift_src, "-o", MONITOR_BIN], capture_output=True, timeout=10.0)
            except Exception:
                pass
    if os.path.exists(MONITOR_BIN):
        try:
            if os.path.exists(CANCEL_FILE):
                os.remove(CANCEL_FILE)
            return subprocess.Popen(
                [MONITOR_BIN, "--parent", str(os.getpid())],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True
            )
        except Exception:
            pass
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

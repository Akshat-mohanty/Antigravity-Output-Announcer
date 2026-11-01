#!/usr/bin/env python3
import sys
import os
import glob
import time
import json
import fcntl
import asyncio
import subprocess

PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
QUEUE_DIR = "/tmp/agy_voice_queue"
LOCK_FILE = "/tmp/agy_voice_queue.lock"
PID_FILE = "/tmp/agy_voice_reader.pid"
LOG_FILE = "/tmp/agy_voice_worker.log"
CANCEL_FILE = "/tmp/agy_voice_cancelled"
MONITOR_BIN = os.path.join(PLUGIN_DIR, "bin", "voice_ctrl_monitor")

os.makedirs(QUEUE_DIR, exist_ok=True)

def log(msg):
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except Exception:
        pass

def is_cancelled():
    return os.path.exists(CANCEL_FILE)

def ensure_monitor():
    if not os.path.exists(MONITOR_BIN):
        swift_src = os.path.join(PLUGIN_DIR, "bin", "voice_ctrl_monitor.swift")
        if os.path.exists(swift_src):
            try:
                subprocess.run(["swiftc", "-O", swift_src, "-o", MONITOR_BIN], capture_output=True, timeout=10.0)
            except Exception:
                pass
    return os.path.exists(MONITOR_BIN)

def start_monitor():
    if not ensure_monitor():
        return None
    try:
        if os.path.exists(CANCEL_FILE):
            os.remove(CANCEL_FILE)
        return subprocess.Popen(
            [MONITOR_BIN, "--parent", str(os.getpid())],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True
        )
    except Exception as e:
        log(f"Failed to start ctrl monitor: {e}")
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
    import re
    if not text:
        return ""
    text = re.sub(r"\[\[slnc\s*\d+\]\]", ", ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    # Strip markdown syntax
    text = re.sub(r"\*{3,}([^*]+)\*{3,}", r"\1", text)
    text = re.sub(r"\*{2}([^*]+)\*{2}", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    text = re.sub(r"_{3,}([^_]+)_{3,}", r"\1", text)
    text = re.sub(r"_{2}([^_]+)_{2}", r"\1", text)
    text = re.sub(r"`+([^`]+)`+", r"\1", text)
    # CRITICAL: Eliminate ALL remaining asterisks so TTS never speaks "star" or "asterisk"
    text = text.replace("*", "")
    text = re.sub(r"[•◦▪▫‣⁃·~\\|`#]", " ", text)
    # Replace snake_case underscores with spaces
    text = re.sub(r"(?<=\w)_(?=\w)", " ", text)
    text = text.replace("_", " ")
    text = re.sub(r"[,;]\s*[,;]+", ",", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

async def generate_neural_speech(text, voice, out_path, rate="+1%"):
    import edge_tts
    clean = clean_speech_text(text)
    communicate = edge_tts.Communicate(clean, voice, rate=rate)
    await asyncio.wait_for(communicate.save(out_path), timeout=15.0)

def play_job(job):
    job_id = job.get("id", "job")
    job_time = job.get("timestamp", 0)
    text = job.get("text", "")
    voice = job.get("voice", "en-US-AvaNeural")
    engine = job.get("engine", "neural")
    rate = job.get("rate", "+1%")
    volume = job.get("volume", 1.3)

    if not text:
        return

    # Check if cancelled before starting work
    if is_cancelled():
        log(f"Job {job_id} skipped: Cancelled by user.")
        return

    # If job has been sitting in queue for more than 10 minutes, discard it
    if job_time and (time.time() - job_time) > 600:
        log(f"Dropping stale queued job {job_id} (age {time.time() - job_time:.1f}s)")
        return

    audio_path = f"/tmp/agy_speech_{job_id}.mp3"
    played = False

    if engine == "neural":
        for attempt in range(2):
            if is_cancelled():
                break
            try:
                asyncio.run(generate_neural_speech(text, voice, audio_path, rate=rate))
                if is_cancelled():
                    break
                if os.path.exists(audio_path) and os.path.getsize(audio_path) > 100:
                    vol_str = str(min(max(volume, 0.5), 2.5))
                    proc = subprocess.Popen(
                        ["afplay", "-v", vol_str, audio_path],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                    with open(PID_FILE, "w") as f:
                        f.write(str(proc.pid))
                    proc.wait()
                    if is_cancelled():
                        log("Playback stopped by Control key.")
                        break
                    played = True
                    log(f"Successfully played neural speech with {voice}")
                    break
            except Exception as e:
                log(f"Neural attempt {attempt+1} failed: {e}")
                time.sleep(0.3)

    if not played and not is_cancelled():
        log("Falling back to local speech engine.")
        clean = clean_speech_text(text)
        say_cmd = ["say", "-v", "Samantha", clean]
        try:
            proc = subprocess.Popen(
                say_cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            with open(PID_FILE, "w") as f:
                f.write(str(proc.pid))
            proc.wait()
            if is_cancelled():
                log("Playback stopped by Control key.")
        except Exception as e:
            log(f"Fallback say failed: {e}")

    if os.path.exists(audio_path):
        try:
            os.remove(audio_path)
        except Exception:
            pass

    time.sleep(0.3)

def main():
    try:
        lock_fd = open(LOCK_FILE, "w")
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (BlockingIOError, OSError):
        return

    monitor_proc = None
    idle_count = 0
    try:
        while True:
            if is_cancelled():
                log("Worker detected cancellation signal; clearing pending queue.")
                for f in glob.glob(os.path.join(QUEUE_DIR, "*.json")):
                    try:
                        os.remove(f)
                    except Exception:
                        pass
                break

            files = sorted(glob.glob(os.path.join(QUEUE_DIR, "*.json")))
            if not files:
                if monitor_proc:
                    stop_monitor(monitor_proc)
                    monitor_proc = None
                time.sleep(0.4)
                idle_count += 1
                if idle_count > 7:
                    break
                continue

            # Active jobs found: start key listener if not already running
            if monitor_proc is None or monitor_proc.poll() is not None:
                monitor_proc = start_monitor()

            idle_count = 0
            job_file = files[0]

            try:
                with open(job_file, "r", encoding="utf-8") as f:
                    job = json.load(f)
            except Exception:
                job = None

            try:
                os.remove(job_file)
            except Exception:
                pass

            if job:
                play_job(job)

    finally:
        if monitor_proc:
            stop_monitor(monitor_proc)
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            lock_fd.close()
        except Exception:
            pass
        if os.path.exists(PID_FILE):
            try:
                os.remove(PID_FILE)
            except Exception:
                pass
        if os.path.exists(CANCEL_FILE):
            try:
                os.remove(CANCEL_FILE)
            except Exception:
                pass

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
import sys
import os
import time
import json
import re
import urllib.request
import subprocess

PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = "/tmp/agy_yt_tasteandtours.json"
PID_FILE = "/tmp/agy_yt_tracker.pid"
LOG_FILE = "/tmp/agy_yt_tracker.log"
QUEUE_DIR = "/tmp/agy_voice_queue"
WORKER_SCRIPT = os.path.join(PLUGIN_DIR, "queue_worker.py")

CHANNEL_HANDLE = "@tasteandtours"
CHANNEL_URL = f"https://www.youtube.com/{CHANNEL_HANDLE}"
CHANNEL_NAME = "Taste and Tours"

CONFIG_FILE = os.path.join(PLUGIN_DIR, "config.json")

def get_user_name():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f).get("user_name", "")
        except Exception:
            pass
    return ""

def log(msg):
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except Exception:
        pass

def enqueue_speech(text):
    os.makedirs(QUEUE_DIR, exist_ok=True)
    import uuid
    job_id = f"{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}"
    job_path = os.path.join(QUEUE_DIR, f"{job_id}.json")
    job_data = {
        "id": job_id,
        "timestamp": time.time(),
        "text": text,
        "voice": "en-US-AvaNeural",
        "engine": "neural",
        "rate": "+1%",
        "volume": 1.3
    }
    with open(job_path, "w", encoding="utf-8") as f:
        json.dump(job_data, f)

    cmd = ["/usr/bin/caffeinate", "-i", "-s", "-m", sys.executable, WORKER_SCRIPT]
    try:
        subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            start_new_session=True
        )
    except Exception as e:
        log(f"Error spawning worker: {e}")

def show_notification(title, message):
    safe_msg = message.replace('\\', '\\\\').replace('"', '\\"')
    safe_title = title.replace('\\', '\\\\').replace('"', '\\"')
    scpt = f'display notification "{safe_msg}" with title "{safe_title}" sound name "default"'
    try:
        subprocess.Popen(["osascript", "-e", scpt], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

def fetch_subscriber_count():
    req = urllib.request.Request(
        CHANNEL_URL,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9"
        }
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        html = resp.read().decode("utf-8", errors="ignore")
    
    m = re.search(r"var ytInitialData\s*=\s*({.+?});</script>", html)
    if m:
        data_str = m.group(1)
        # Look for "content": "79 subscribers" or accessibilityLabel
        sub_m = re.search(r"\"content\":\s*\"([\d,]+)\s+subscribers\"", data_str)
        if not sub_m:
            sub_m = re.search(r"\"accessibilityLabel\":\s*\"([\d,]+)\s+subscribers\"", data_str)
        if sub_m:
            num_str = sub_m.group(1).replace(",", "").strip()
            return int(num_str)
    
    # Fallback regex on HTML directly
    sub_m = re.search(r"\"([\d,]+)\s+subscribers\"", html)
    if sub_m:
        return int(sub_m.group(1).replace(",", "").strip())

    return None

def run_loop(poll_interval=60):
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))

    log(f"Starting YouTube subscriber monitor for {CHANNEL_HANDLE} (interval: {poll_interval}s)")

    # Load previous count if exists
    last_count = None
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                saved = json.load(f)
                last_count = saved.get("count")
        except Exception:
            pass

    # Initial probe
    try:
        init_count = fetch_subscriber_count()
        if init_count is not None:
            if last_count is None:
                last_count = init_count
                with open(STATE_FILE, "w") as f:
                    json.dump({"count": init_count, "updated_at": time.time()}, f)
                log(f"Initialized baseline subscriber count: {init_count}")
    except Exception as e:
        log(f"Initial fetch error: {e}")

    while True:
        try:
            time.sleep(poll_interval)
            current = fetch_subscriber_count()
            if current is not None:
                if last_count is not None and current > last_count:
                    delta = current - last_count
                    log(f"Subscriber increase detected! {last_count} -> {current} (+{delta})")
                    msg = f"Subscriber increased to {current}."
                    notif_body = f"Subscriber increased to {current}"

                    enqueue_speech(msg)
                    show_notification("YouTube Subscriber Alert", notif_body)

                last_count = current
                with open(STATE_FILE, "w") as f:
                    json.dump({"count": current, "updated_at": time.time()}, f)
            else:
                log("Fetch returned None, skipping cycle.")
        except Exception as e:
            log(f"Polling loop exception: {e}")

def main():
    args = sys.argv[1:]
    cmd = args[0] if args else "status"

    if cmd == "status":
        count = None
        updated = None
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, "r") as f:
                    d = json.load(f)
                    count = d.get("count")
                    updated = d.get("updated_at")
            except Exception:
                pass
        
        is_running = False
        pid = None
        if os.path.exists(PID_FILE):
            try:
                with open(PID_FILE, "r") as f:
                    pid = int(f.read().strip())
                os.kill(pid, 0)
                is_running = True
            except Exception:
                pass

        print(f"YouTube Channel:    {CHANNEL_NAME} ({CHANNEL_HANDLE})")
        print(f"Tracking Status:    {'● Active (PID ' + str(pid) + ')' if is_running else '○ Inactive'}")
        print(f"Current Count:      {count if count is not None else 'Not yet fetched'} subscribers")
        if updated:
            print(f"Last Checked:       {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(updated))}")
        return

    elif cmd == "start":
        if os.path.exists(PID_FILE):
            try:
                with open(PID_FILE, "r") as f:
                    pid = int(f.read().strip())
                os.kill(pid, 0)
                print(f"Monitor already running (PID {pid}).")
                return
            except Exception:
                pass

        interval = int(args[1]) if len(args) > 1 and args[1].isdigit() else 60
        proc = subprocess.Popen(
            [sys.executable, __file__, "run", str(interval)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            start_new_session=True
        )
        print(f"✓ Started background subscriber tracker for {CHANNEL_HANDLE} (PID {proc.pid}, interval: {interval}s).")

    elif cmd == "stop":
        if os.path.exists(PID_FILE):
            try:
                with open(PID_FILE, "r") as f:
                    pid = int(f.read().strip())
                os.kill(pid, 15)
                print(f"✓ Stopped tracker (PID {pid}).")
            except Exception as e:
                print(f"Tracker process not running: {e}")
            try:
                os.remove(PID_FILE)
            except Exception:
                pass
        else:
            print("Tracker is not running.")

    elif cmd == "run":
        interval = int(args[1]) if len(args) > 1 and args[1].isdigit() else 60
        run_loop(interval)

    elif cmd == "check":
        print(f"Fetching live count for {CHANNEL_HANDLE}...")
        c = fetch_subscriber_count()
        print(f"Live Subscriber Count: {c}")

if __name__ == "__main__":
    main()

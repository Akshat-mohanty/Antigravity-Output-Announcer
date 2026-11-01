#!/usr/bin/env python3
import sys
import os
import json
import time
import uuid
import re
import datetime
import subprocess

PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(PLUGIN_DIR, "config.json")
STATE_FILE = "/tmp/agy_voice_reader_state.json"
QUEUE_DIR = "/tmp/agy_voice_queue"
WORKER_SCRIPT = os.path.join(PLUGIN_DIR, "queue_worker.py")
HOOK_LOG_FILE = "/tmp/agy_voice_reader.log"

os.makedirs(QUEUE_DIR, exist_ok=True)

def log(msg):
    try:
        with open(HOOK_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except Exception:
        pass

def load_config():
    defaults = {
        "enabled": True,
        "user_name": "",
        "mode": "smart",              # "smart", "headline", "full"
        "engine": "neural",           # "neural" or "system"
        "voice": "en-US-AvaNeural",   # Fast, ultra-smooth Ava neural voice
        "rate": "+1%",
        "max_words": 60,
        "volume_boost": 1.3,
        "announce_tab": True,
        "announce_tools": False,
        "notification": True
    }
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                defaults.update(cfg)
        except Exception:
            pass
    return defaults

def ensure_find_tab_bar_bin():
    bin_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bin")
    os.makedirs(bin_dir, exist_ok=True)
    bar_bin = os.path.join(bin_dir, "find_tab_bar")
    if not os.path.exists(bar_bin):
        swift_src = """import Cocoa
import CoreGraphics

let options = CGWindowListOption(arrayLiteral: .excludeDesktopElements, .optionOnScreenOnly)
if let list = CGWindowListCopyWindowInfo(options, kCGNullWindowID) as? [[String: Any]] {
    for w in list {
        if let owner = w[kCGWindowOwnerName as String] as? String, owner == "Terminal" {
            let bounds = w[kCGWindowBounds as String] as? [String: Any] ?? [:]
            if bounds["Height"] as? Int == 68 {
                print(w[kCGWindowNumber as String] ?? 0)
                exit(0)
            }
        }
    }
}
print(0)
"""
        src_path = os.path.join(bin_dir, "find_tab_bar.swift")
        try:
            with open(src_path, "w") as f:
                f.write(swift_src)
            subprocess.run(["swiftc", "-O", src_path, "-o", bar_bin], capture_output=True, timeout=10.0)
        except Exception:
            pass
        finally:
            if os.path.exists(src_path):
                try:
                    os.remove(src_path)
                except OSError:
                    pass
    return bar_bin

def ensure_voice_ctrl_monitor_bin():
    bin_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bin")
    monitor_bin = os.path.join(bin_dir, "voice_ctrl_monitor")
    swift_src = os.path.join(bin_dir, "voice_ctrl_monitor.swift")
    if not os.path.exists(monitor_bin) and os.path.exists(swift_src):
        try:
            subprocess.run(["swiftc", "-O", swift_src, "-o", monitor_bin], capture_output=True, timeout=10.0)
        except Exception:
            pass
    return monitor_bin


def get_terminal_visual_tab(dev_tty):
    """
    Determines the physical visual tab position (1-based left-to-right) in Apple Terminal.app.
    Works dynamically when tabs are dragged or rearranged by sampling the active tab pill
    brightness across the horizontal segments of the tab bar.
    """
    cache_path = "/tmp/agy_terminal_tab_cache.json"
    tab_cache = {}
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r") as f:
                tab_cache = json.load(f)
        except Exception:
            tab_cache = {}

    scpt = """
    tell application "Terminal"
        set out to ""
        try
            set fId to id of front window
            set out to out & (fId as text) & linefeed
        on error
            set out to out & "0" & linefeed
        end try
        repeat with w in windows
            try
                set out to out & (id of w as text) & ":" & (tty of tab 1 of w as text) & linefeed
            end try
        end repeat
        return out
    end tell
    """
    try:
        res = subprocess.run(["osascript", "-e", scpt], capture_output=True, text=True, timeout=1.5)
        lines = [l.strip() for l in res.stdout.strip().splitlines() if l.strip()]
        if not lines:
            return tab_cache.get(dev_tty)

        front_wid = int(lines[0]) if lines[0].isdigit() else 0
        my_wid = None
        tab_wids = []
        for l in lines[1:]:
            parts = l.split(":")
            if len(parts) >= 2:
                try:
                    wid = int(parts[0])
                    tty = parts[1]
                    tab_wids.append(wid)
                    if tty == dev_tty:
                        my_wid = wid
                except ValueError:
                    pass

        if not my_wid:
            return tab_cache.get(dev_tty)

        num_tabs = len(tab_wids)
        if num_tabs <= 1:
            return 1

        need_restore = (front_wid != 0 and my_wid != front_wid)
        if need_restore:
            subprocess.run(["osascript", "-e", f'tell application "Terminal" to set index of window id {my_wid} to 1'], capture_output=True, timeout=1.0)
            time.sleep(0.06)

        bar_bin = ensure_find_tab_bar_bin()
        detected_tab = None
        if os.path.exists(bar_bin):
            bar_res = subprocess.run([bar_bin], capture_output=True, text=True, timeout=0.5)
            bar_id = bar_res.stdout.strip()
            if bar_id.isdigit() and int(bar_id) > 0:
                capture_path = f"/tmp/agy_bar_{my_wid}.png"
                cap = subprocess.run(["screencapture", "-x", f"-l{bar_id}", capture_path], capture_output=True, timeout=1.0)
                if cap.returncode == 0 and os.path.exists(capture_path):
                    try:
                        from PIL import Image
                        im = Image.open(capture_path)
                        w, h = im.size
                        if w > 0 and h >= 50:
                            pixels = [sum(im.getpixel((x, 50))[:3]) / 3 for x in range(w)]
                            seg_len = w // num_tabs
                            if seg_len > 0:
                                qs = [sum(pixels[i * seg_len : (i + 1) * seg_len]) / seg_len for i in range(num_tabs)]
                                detected_tab = qs.index(max(qs)) + 1
                    except Exception as e:
                        log(f"Error analyzing tab bar image: {e}")
                    finally:
                        try:
                            os.remove(capture_path)
                        except OSError:
                            pass

        if need_restore:
            subprocess.run(["osascript", "-e", f'tell application "Terminal" to set index of window id {front_wid} to 1'], capture_output=True, timeout=1.0)

        if detected_tab is not None and 1 <= detected_tab <= num_tabs:
            tab_cache[dev_tty] = detected_tab
            try:
                with open(cache_path, "w") as f:
                    json.dump(tab_cache, f)
            except Exception:
                pass
            return detected_tab

        if dev_tty in tab_cache:
            return tab_cache[dev_tty]

    except Exception as e:
        log(f"Visual tab detection error: {e}")

    return tab_cache.get(dev_tty)


def get_tab_number():
    """
    Returns the stable 1-based tab/window number in Terminal.app / iTerm2.
    Matches the natural visual tab order (Tab 1, Tab 2, Tab 3...) dynamically left-to-right.
    """
    curr = os.getppid()
    tty_str = ""
    for _ in range(6):
        res = subprocess.run(["ps", "-o", "ppid=,tty=,comm=", "-p", str(curr)], capture_output=True, text=True)
        out = res.stdout.strip()
        if not out:
            break
        parts = out.split(None, 2)
        if len(parts) >= 2:
            p_ppid = parts[0]
            p_tty = parts[1]
            comm = parts[2] if len(parts) > 2 else ""
            if "agy" in comm or "antigravity" in comm:
                tty_str = p_tty
                break
            if not tty_str and p_tty != "?" and p_tty:
                tty_str = p_tty
            try:
                curr = int(p_ppid)
            except ValueError:
                break
        else:
            break

    if not tty_str:
        tty_str = subprocess.run(["ps", "-o", "tty=", "-p", str(os.getppid())], capture_output=True, text=True).stdout.strip()

    if not tty_str or tty_str == "?":
        return 1

    dev_tty = "/dev/" + tty_str if not tty_str.startswith("/dev/") else tty_str

    # Strategy 1: Terminal.app visual tab position (dynamically tracks physical left-to-right tab order on reorder)
    visual_tab = get_terminal_visual_tab(dev_tty)
    if visual_tab is not None and visual_tab > 0:
        return visual_tab

    # Fallback for Terminal.app: Query all windows and tabs
    scpt_term = """
    tell application "Terminal"
        set ttyMap to ""
        repeat with w in windows
            set wId to id of w
            try
                set tList to tabs of w
                repeat with j from 1 to count of tList
                    set t to item j of tList
                    set ttyMap to ttyMap & (wId as text) & ":" & (j as text) & ":" & (tty of t) & linefeed
                end repeat
            end try
        end repeat
        return ttyMap
    end tell
    """
    try:
        res = subprocess.run(["osascript", "-e", scpt_term], capture_output=True, text=True, timeout=1.5)
        lines = [l.strip() for l in res.stdout.strip().splitlines() if l.strip()]
        entries = []
        for line in lines:
            parts = line.split(":")
            if len(parts) >= 3:
                try:
                    entries.append((int(parts[0]), int(parts[1]), parts[2]))
                except ValueError:
                    pass
        if entries:
            entries.sort(key=lambda x: (x[0], x[1]))
            for idx, (_, _, t_tty) in enumerate(entries, 1):
                if t_tty == dev_tty:
                    return idx
    except Exception as e:
        log(f"Terminal tab lookup error: {e}")

    # Strategy 2: iTerm2 AppleScript
    scpt_iterm = """
    tell application "iTerm"
        set ttyMap to ""
        repeat with w in windows
            set wId to id of w
            set tList to tabs of w
            repeat with j from 1 to count of tList
                set t to item j of tList
                repeat with s in sessions of t
                    set ttyMap to ttyMap & (wId as text) & ":" & (j as text) & ":" & (tty of s) & linefeed
                end repeat
            end repeat
        end repeat
        return ttyMap
    end tell
    """
    try:
        res = subprocess.run(["osascript", "-e", scpt_iterm], capture_output=True, text=True, timeout=2.5)
        lines = [l.strip() for l in res.stdout.strip().splitlines() if l.strip()]
        entries = []
        for line in lines:
            parts = line.split(":")
            if len(parts) >= 3:
                try:
                    entries.append((int(parts[0]), int(parts[1]), parts[2]))
                except ValueError:
                    pass
        if entries:
            entries.sort(key=lambda x: (x[0], x[1]))
            for idx, (_, _, t_tty) in enumerate(entries, 1):
                if t_tty == dev_tty:
                    return idx
    except Exception:
        pass

    # Strategy 3: Shell elapsed time (ps fallback)
    try:
        res = subprocess.run(["ps", "-eo", "tty=,etime=,comm="], capture_output=True, text=True, timeout=2.0)
        candidates = []
        for line in res.stdout.splitlines():
            parts = line.strip().split(None, 2)
            if len(parts) >= 3:
                p_tty, p_etime, p_comm = parts[0], parts[1], parts[2]
                if p_comm in ("-zsh", "-bash", "zsh", "bash", "login"):
                    t_full = "/dev/" + p_tty if not p_tty.startswith("/dev/") else p_tty
                    candidates.append((p_etime, t_full))
        seen = {}
        for etime, t_full in candidates:
            if t_full not in seen:
                seen[t_full] = etime

        def parse_etime(s):
            days = 0
            if "-" in s:
                d_str, s = s.split("-", 1)
                days = int(d_str)
            segs = [int(x) for x in s.split(":")]
            if len(segs) == 3:
                return days * 86400 + segs[0] * 3600 + segs[1] * 60 + segs[2]
            elif len(segs) == 2:
                return days * 86400 + segs[0] * 60 + segs[1]
            return days * 86400 + segs[0]

        sorted_ttys = sorted(seen.keys(), key=lambda t: parse_etime(seen[t]), reverse=True)
        if dev_tty in sorted_ttys:
            return sorted_ttys.index(dev_tty) + 1
    except Exception as e:
        log(f"Fallback tab lookup error: {e}")

    return 1

def enqueue_speech(text, voice, engine, rate, volume):
    ensure_voice_ctrl_monitor_bin()
    job_id = f"{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}"
    job_path = os.path.join(QUEUE_DIR, f"{job_id}.json")
    job_data = {
        "id": job_id,
        "timestamp": time.time(),
        "text": text,
        "voice": voice,
        "engine": engine,
        "rate": rate,
        "volume": volume
    }
    with open(job_path, "w", encoding="utf-8") as f:
        json.dump(job_data, f)

    caffeinate_bin = "/usr/bin/caffeinate"
    if os.path.exists(caffeinate_bin):
        cmd = [caffeinate_bin, "-i", "-s", "-m", sys.executable, WORKER_SCRIPT]
    else:
        cmd = [sys.executable, WORKER_SCRIPT]

    try:
        subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            start_new_session=True
        )
        log(f"Enqueued job {job_id}.")
    except Exception as e:
        log(f"Error spawning worker: {e}")

def clean_file_paths(text):
    return re.sub(r"/(?:[a-zA-Z0-9._-]+/)+([a-zA-Z0-9._-]+)", r"\1", text)

def strip_markdown(text):
    if not text:
        return ""
    # Strip HTML tags
    text = re.sub(r"<[^>]+>", " ", text)
    # Strip URLs
    text = re.sub(r"https?://\S+", "", text)
    # Strip markdown links [label](url) -> label
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    # Strip standalone file:// links in parens
    text = re.sub(r"\(file://[^)]+\)", "", text)
    # Strip inline code backticks `code` -> code
    text = re.sub(r"`+([^`]+)`+", r"\1", text)
    text = re.sub(r"`+", "", text)
    # Strip bold / italic markdown combinations
    text = re.sub(r"\*{3,}([^*]+)\*{3,}", r"\1", text)
    text = re.sub(r"\*{2}([^*]+)\*{2}", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    text = re.sub(r"_{3,}([^_]+)_{3,}", r"\1", text)
    text = re.sub(r"_{2}([^_]+)_{2}", r"\1", text)
    # Strip headers # Header
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s+#{1,6}\s+", " ", text)
    # Strip blockquotes >
    text = re.sub(r"^>\s+", "", text, flags=re.MULTILINE)
    # Strip bullet point markers at start of lines
    text = re.sub(r"^[\*\-\+•◦▪▫‣⁃·]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\d+\.\s+", "", text, flags=re.MULTILINE)
    # CRITICAL: Eliminate ALL remaining asterisks so TTS never speaks "star" or "asterisk"
    text = text.replace("*", "")
    # Strip bullet characters, tildes, backslashes, pipes
    text = re.sub(r"[•◦▪▫‣⁃·~\\|]", " ", text)
    # Replace snake_case underscores with space so it sounds natural (e.g. read_output -> read output)
    text = re.sub(r"(?<=\w)_(?=\w)", " ", text)
    text = text.replace("_", " ")
    # Clean file paths to basenames
    text = clean_file_paths(text)
    # Clean up double punctuation and spacing
    text = re.sub(r"[,;]\s*[,;]+", ",", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def extract_smart_summary(raw_text, user_name="", ws_label="", tab_num=None, mode="smart"):
    if not raw_text:
        return ""

    # 1. Detect if there is a pending question or call to action for the user
    question = ""
    lines = [l.strip() for l in raw_text.split("\n") if l.strip()]
    if lines:
        last_few = lines[-3:] if len(lines) >= 3 else lines
        for chunk in reversed(last_few):
            if "?" in chunk or any(chunk.lower().startswith(p) for p in [
                "please ", "let me know", "would you like", "should i ", "do you want", "which option", "shall i"
            ]):
                sentences = re.split(r"(?<=[.!?])\s+", chunk)
                for s in reversed(sentences):
                    s_clean = s.strip()
                    if "?" in s_clean or any(s_clean.lower().startswith(p) for p in [
                        "please ", "let me know", "would you like", "should i ", "do you want", "which option", "shall i"
                    ]):
                        question = strip_markdown(s_clean)
                        break
            if question:
                break

    # 2. Clean out code blocks and raw markdown tables
    cleaned_body = re.sub(r"```[\s\S]*?```", "", raw_text)
    cleaned_body = re.sub(r"\|[^\n]+\|\n", "", cleaned_body)
    cleaned_body = re.sub(r"<[^>]+>", "", cleaned_body)

    # 3. Filter out bullet points to get direct prose output
    prose_body = re.sub(r"^\s*(?:[\*\-\+•◦▪▫‣⁃·]|\d+\.)\s+.*$", "", cleaned_body, flags=re.MULTILINE)
    paras = [p.strip() for p in prose_body.split("\n\n") if p.strip()]

    lead_text = ""
    for p in paras:
        without_heading = re.sub(r"^#{1,6}\s+.*$", "", p, flags=re.MULTILINE).strip()
        if without_heading and len(without_heading.split()) >= 3:
            lead_text = without_heading
            break

    # If the output was solely bullet points with no prose, take only the primary action
    if not lead_text:
        bullet_lines = re.findall(r"^\s*(?:[\*\-\+•◦▪▫‣⁃·]|\d+\.)\s+(.+)$", cleaned_body, flags=re.MULTILINE)
        if bullet_lines:
            lead_text = bullet_lines[0].strip()
        elif paras:
            lead_text = paras[0]

    lead_clean = strip_markdown(lead_text)
    lead_clean = re.sub(r"^(Sure|Certainly|Okay|Alright|Here is the summary|Here are the results)[,.!:]\s*", "", lead_clean, flags=re.IGNORECASE)

    # 4. Extract 1 to 2 core sentences (direct conversational output, no bullet recitation)
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", lead_clean) if s.strip()]
    if mode == "headline":
        core_lead = sentences[0] if sentences else ""
    else:
        core_lead = " ".join(sentences[:2]) if len(sentences) >= 2 else (sentences[0] if sentences else "")

    if not core_lead:
        return ""

    loc_parts = []
    if tab_num:
        loc_parts.append(f"tab {tab_num}")
    if ws_label:
        loc_parts.append(ws_label)

    loc_str = " ".join(loc_parts)

    if loc_str:
        intro = f"In {loc_str}, "
    else:
        intro = ""

    parts = [intro + core_lead]

    # Include any question asking the user for input
    if question and question.lower() not in core_lead.lower():
        parts.append(question)

    return " ".join(parts)

def get_current_turn_output(transcript_path):
    if not transcript_path:
        return None, None

    dir_name = os.path.dirname(transcript_path)
    full_path = os.path.join(dir_name, "transcript_full.jsonl")

    lines = []
    for _ in range(3):
        if os.path.exists(transcript_path):
            try:
                with open(transcript_path, "r", encoding="utf-8", errors="replace") as f:
                    lines = f.readlines()
                if lines:
                    break
            except Exception:
                pass
        time.sleep(0.1)

    if not lines:
        return None, None

    steps = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            steps.append(json.loads(line))
        except Exception:
            continue

    if not steps:
        return None, None

    last_user_idx = -1
    last_user_step_idx = -1
    for i, s in enumerate(steps):
        if s.get("type") == "USER_INPUT":
            last_user_idx = i
            last_user_step_idx = s.get("step_index", -1)

    if last_user_idx < 0:
        log("No USER_INPUT found in transcript.")
        return None, None

    turn_steps = steps[last_user_idx:]
    now = datetime.datetime.now(datetime.timezone.utc)

    for step in reversed(turn_steps):
        step_type = step.get("type")
        step_idx = step.get("step_index", -1)
        
        if step_idx <= last_user_step_idx:
            continue

        if step_type == "PLANNER_RESPONSE":
            content = step.get("content")
            
            ts_str = step.get("created_at", "")
            if ts_str:
                try:
                    dt = datetime.datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    age_seconds = (now - dt).total_seconds()
                    # Only skip if the output is older than 30 minutes (from a past historical session)
                    if age_seconds > 1800:
                        log(f"Step {step_idx} is from a past session ({age_seconds:.1f}s old). Skipping.")
                        return None, None
                except Exception:
                    pass

            if step.get("truncated_fields") and "content" in step["truncated_fields"]:
                if os.path.exists(full_path):
                    try:
                        with open(full_path, "r", encoding="utf-8", errors="replace") as ff:
                            for fline in ff:
                                fstep = json.loads(fline)
                                if fstep.get("step_index") == step_idx:
                                    content = fstep.get("content")
                                    break
                    except Exception:
                        pass

            if content and content.strip():
                return step_idx, content.strip()

    return None, None

def get_latest_step_idx_from_transcript(transcript_path):
    if not transcript_path or not os.path.exists(transcript_path):
        return None
    try:
        with open(transcript_path, "r", encoding="utf-8", errors="replace") as f:
            for line in reversed(f.readlines()):
                line = line.strip()
                if line:
                    data = json.loads(line)
                    if "step_index" in data:
                        return data["step_index"]
    except Exception:
        pass
    return None

def read_last_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_state(state):
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f)
    except Exception:
        pass

def main():
    try:
        raw_input = sys.stdin.read()
        payload = json.loads(raw_input) if raw_input.strip() else {}
    except Exception:
        payload = {}

    config = load_config()

    if not config.get("enabled", True):
        log("Voice reader disabled in config.")
        print(json.dumps({}))
        return

    term_reason = payload.get("terminationReason", "")
    if term_reason == "USER_CANCELED":
        log("Turn canceled by user.")
        print(json.dumps({}))
        return

    conv_id = payload.get("conversationId", "default")
    transcript_path = payload.get("transcriptPath", "")
    workspace_paths = payload.get("workspacePaths", [])

    log(f"Hook fired: conv_id={conv_id}, reason={term_reason}")

    step_idx, raw_content = get_current_turn_output(transcript_path)

    if not raw_content:
        if payload.get("error"):
            raw_content = f"Error: {payload['error']}"
            t_idx = get_latest_step_idx_from_transcript(transcript_path)
            step_idx = t_idx if t_idx is not None else 0
        else:
            log("No active turn model output found. Silence maintained.")
            print(json.dumps({}))
            return

    state = read_last_state()
    last_spoken_step = state.get(conv_id, -1)
    # Self-healing safeguard: if state previously stored a Unix timestamp (from earlier bug > 1,000,000), ignore it
    if not isinstance(last_spoken_step, (int, float)) or last_spoken_step > 1_000_000:
        last_spoken_step = -1

    if step_idx is not None and step_idx <= last_spoken_step:
        log(f"Step {step_idx} <= {last_spoken_step} already spoken. Skipping.")
        print(json.dumps({}))
        return

    if step_idx is not None:
        state[conv_id] = step_idx
        save_state(state)

    tab_num = get_tab_number() if config.get("announce_tab", True) else None

    ws_label = ""
    if workspace_paths and config.get("announce_tab", True):
        ws_name = os.path.basename(os.path.normpath(workspace_paths[0]))
        if ws_name and ws_name != os.path.expanduser("~") and ws_name != "akshatmohanty":
            ws_label = ws_name

    user_name = config.get("user_name", "")
    mode = config.get("mode", "smart")

    if mode in ("smart", "headline"):
        final_speech = extract_smart_summary(raw_content, user_name=user_name, ws_label=ws_label, tab_num=tab_num, mode=mode)
    else:
        cleaned = strip_markdown(raw_content)
        words = cleaned.split()
        max_words = config.get("max_words", 100)
        intro_parts = [f"tab {tab_num}"] if tab_num else []
        if ws_label:
            intro_parts.append(ws_label)
        loc = f"in {' '.join(intro_parts)}, " if intro_parts else ""
        intro = f"{loc.capitalize()}" if loc else ""
        if max_words > 0 and len(words) > max_words:
            final_speech = intro + " ".join(words[:max_words]) + "... Details continue in terminal."
        else:
            final_speech = intro + cleaned

    if not final_speech:
        log("Final speech empty after extraction.")
        print(json.dumps({}))
        return

    log(f"Speaking current turn: '{final_speech[:90]}...'")

    if config.get("notification", True):
        tag_parts = []
        if tab_num:
            tag_parts.append(f"Tab {tab_num}")
        if ws_label:
            tag_parts.append(ws_label)
        notif_sub = " - ".join(tag_parts)
        notif_title = f"agy ({notif_sub})" if notif_sub else "Antigravity"
        plain_notif = final_speech[:140].strip()
        safe_msg = plain_notif.replace('\\', '\\\\').replace('"', '\\"')
        safe_title = notif_title.replace('\\', '\\\\').replace('"', '\\"')
        apple_script = f'display notification "{safe_msg}" with title "{safe_title}"'
        try:
            subprocess.Popen(
                ["osascript", "-e", apple_script],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
                start_new_session=True
            )
        except Exception:
            pass

    voice = config.get("voice", "en-US-AvaNeural")
    engine = config.get("engine", "neural")
    rate = config.get("rate", "+1%")
    volume = config.get("volume_boost", 1.3)

    enqueue_speech(final_speech, voice, engine, rate, volume)

    print(json.dumps({}))

if __name__ == "__main__":
    main()

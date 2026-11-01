#!/usr/bin/env python3
"""
Antigravity Output Announcer - Modern Web GUI Server
Provides an aesthetic local dashboard to control voice reading, pause/run state,
mute keys, voice settings, and live speech logs.
"""

import sys
import os
import json
import glob
import time
import subprocess
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
import socket

PORT = 48123
PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(PLUGIN_DIR, "config.json")
QUEUE_DIR = "/tmp/agy_voice_queue"
PID_FILE = "/tmp/agy_voice_reader.pid"
CANCEL_FILE = "/tmp/agy_voice_cancelled"
HOOK_LOG_FILE = "/tmp/agy_voice_reader.log"
WORKER_LOG_FILE = "/tmp/agy_voice_worker.log"
WORKER_SCRIPT = os.path.join(PLUGIN_DIR, "queue_worker.py")

DEFAULT_CONFIG = {
    "enabled": True,
    "paused": False,
    "mute_key": "control",
    "user_name": "",
    "mode": "smart",
    "engine": "neural",
    "voice": "en-US-AvaNeural",
    "rate": "+1%",
    "max_words": 60,
    "volume_boost": 1.3,
    "announce_tab": True,
    "announce_tools": False,
    "notification": True
}

def load_config():
    cfg = dict(DEFAULT_CONFIG)
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg.update(json.load(f))
        except Exception:
            pass
    return cfg

def save_config(cfg):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
        # Also sync to installed plugin config if running from repository
        home_cfg = os.path.expanduser("~/.gemini/config/plugins/voice-reader/config.json")
        if os.path.abspath(CONFIG_PATH) != os.path.abspath(home_cfg):
            try:
                os.makedirs(os.path.dirname(home_cfg), exist_ok=True)
                with open(home_cfg, "w", encoding="utf-8") as f:
                    json.dump(cfg, f, indent=2)
            except Exception:
                pass
        return True
    except Exception:
        return False

def is_audio_playing():
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE, "r") as f:
                pid = int(f.read().strip())
            # Check if PID exists
            os.kill(pid, 0)
            return True
        except (ValueError, OSError):
            pass
    # Also check if afplay or say is running
    res = subprocess.run(["pgrep", "-x", "afplay"], capture_output=True)
    if res.returncode == 0:
        return True
    res_say = subprocess.run(["pgrep", "-x", "say"], capture_output=True)
    return res_say.returncode == 0

def stop_all_speech():
    for f in glob.glob(os.path.join(QUEUE_DIR, "*.json")):
        try:
            os.remove(f)
        except Exception:
            pass
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE, "r") as f:
                pid = int(f.read().strip())
            os.kill(pid, 15)
        except Exception:
            pass
        try:
            os.remove(PID_FILE)
        except Exception:
            pass
    try:
        with open(CANCEL_FILE, "w") as f:
            f.write(str(time.time()))
    except Exception:
        pass
    subprocess.run(["killall", "-9", "afplay", "say", "voice_ctrl_monitor", "voice_fn_monitor", "voice_mute_monitor"], stderr=subprocess.DEVNULL)

def enqueue_test(text=None):
    cfg = load_config()
    os.makedirs(QUEUE_DIR, exist_ok=True)
    import uuid
    job_id = f"{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}"
    job_path = os.path.join(QUEUE_DIR, f"{job_id}.json")
    
    phrase = text if text and text.strip() else f"Testing Antigravity Output Announcer with {cfg.get('voice', 'Ava')}. Press your mute key anytime to silence me."
    
    job_data = {
        "id": job_id,
        "timestamp": time.time(),
        "text": phrase,
        "voice": cfg.get("voice", "en-US-AvaNeural"),
        "engine": cfg.get("engine", "neural"),
        "rate": cfg.get("rate", "+1%"),
        "volume": cfg.get("volume_boost", 1.3)
    }
    with open(job_path, "w", encoding="utf-8") as f:
        json.dump(job_data, f)

    caffeinate_bin = "/usr/bin/caffeinate"
    cmd = [caffeinate_bin, "-i", "-s", "-m", sys.executable, WORKER_SCRIPT] if os.path.exists(caffeinate_bin) else [sys.executable, WORKER_SCRIPT]
    subprocess.Popen(
        cmd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
        start_new_session=True
    )

def read_recent_logs(max_lines=25):
    lines = []
    if os.path.exists(HOOK_LOG_FILE):
        try:
            with open(HOOK_LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
                raw = f.readlines()
                for l in raw[-max_lines:]:
                    l_str = l.strip()
                    if l_str:
                        lines.append(l_str)
        except Exception:
            pass
    return lines

HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Antigravity Output Announcer</title>
  <style>
    :root {
      --bg-base: #0b0e14;
      --bg-surface: #121721;
      --bg-surface-elevated: #18202d;
      --bg-surface-hover: #1f293a;
      --border-subtle: rgba(255, 255, 255, 0.08);
      --border-focus: rgba(56, 189, 248, 0.4);
      --text-primary: #f1f5f9;
      --text-secondary: #94a3b8;
      --text-muted: #64748b;
      --accent-emerald: #10b981;
      --accent-emerald-glow: rgba(16, 185, 129, 0.2);
      --accent-amber: #f59e0b;
      --accent-amber-glow: rgba(245, 158, 11, 0.2);
      --accent-rose: #f43f5e;
      --accent-cyan: #38bdf8;
      --accent-indigo: #6366f1;
      --radius-sm: 8px;
      --radius-md: 12px;
      --radius-lg: 16px;
      --radius-full: 9999px;
      --font-stack: -apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", "Segoe UI", Roboto, Helvetica, sans-serif;
      --font-mono: "SF Mono", Menlo, Monaco, Consolas, monospace;
    }

    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }

    ::selection {
      background: rgba(56, 189, 248, 0.3);
      color: #fff;
    }

    ::-webkit-scrollbar {
      width: 6px;
      height: 6px;
    }
    ::-webkit-scrollbar-track {
      background: transparent;
    }
    ::-webkit-scrollbar-thumb {
      background: rgba(255, 255, 255, 0.15);
      border-radius: 3px;
    }
    ::-webkit-scrollbar-thumb:hover {
      background: rgba(255, 255, 255, 0.25);
    }

    body {
      background-color: var(--bg-base);
      color: var(--text-primary);
      font-family: var(--font-stack);
      -webkit-font-smoothing: antialiased;
      -moz-osx-font-smoothing: grayscale;
      line-height: 1.5;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
    }

    /* Top Navigation Shell */
    header {
      background: rgba(18, 23, 33, 0.85);
      backdrop-filter: blur(20px);
      -webkit-backdrop-filter: blur(20px);
      border-bottom: 1px solid var(--border-subtle);
      position: sticky;
      top: 0;
      z-index: 50;
    }

    .header-inner {
      max-width: 1100px;
      margin: 0 auto;
      padding: 16px 24px;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }

    .brand {
      display: flex;
      align-items: center;
      gap: 12px;
    }

    .brand-icon {
      width: 36px;
      height: 36px;
      border-radius: var(--radius-sm);
      background: linear-gradient(135deg, #1e293b, #0f172a);
      border: 1px solid var(--border-subtle);
      display: flex;
      align-items: center;
      justify-content: center;
      color: var(--accent-cyan);
    }

    .brand-title {
      font-size: 17px;
      font-weight: 600;
      letter-spacing: -0.015em;
      color: var(--text-primary);
    }

    .brand-sub {
      font-size: 12px;
      color: var(--text-muted);
      font-weight: 400;
    }

    .header-actions {
      display: flex;
      align-items: center;
      gap: 12px;
    }

    .live-badge {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 6px 12px;
      border-radius: var(--radius-full);
      font-size: 12px;
      font-weight: 500;
      border: 1px solid var(--border-subtle);
      background: var(--bg-surface-elevated);
      transition: all 0.2s ease;
    }

    .live-badge.running {
      border-color: rgba(16, 185, 129, 0.3);
      color: #34d399;
      background: rgba(16, 185, 129, 0.1);
    }

    .live-badge.paused {
      border-color: rgba(245, 158, 11, 0.3);
      color: #fbbf24;
      background: rgba(245, 158, 11, 0.1);
    }

    .live-pulse {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: currentColor;
      box-shadow: 0 0 10px currentColor;
      animation: pulse 2s infinite ease-in-out;
    }

    @keyframes pulse {
      0%, 100% { opacity: 1; transform: scale(1); }
      50% { opacity: 0.4; transform: scale(0.85); }
    }

    /* Main Container */
    main {
      flex: 1;
      max-width: 1100px;
      width: 100%;
      margin: 0 auto;
      padding: 32px 24px;
      display: flex;
      flex-direction: column;
      gap: 28px;
    }

    /* Hero Controller Banner (Pause / Run) */
    .hero-controller {
      background: var(--bg-surface);
      border: 1px solid var(--border-subtle);
      border-radius: var(--radius-lg);
      padding: 24px 28px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 20px;
      position: relative;
      overflow: hidden;
      box-shadow: 0 8px 24px rgba(0, 0, 0, 0.25);
    }

    .hero-controller::before {
      content: "";
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      height: 3px;
      background: var(--accent-emerald);
      transition: background 0.3s ease;
    }

    .hero-controller.paused-mode::before {
      background: var(--accent-amber);
    }

    .hero-details {
      display: flex;
      flex-direction: column;
      gap: 6px;
    }

    .hero-status-title {
      font-size: 20px;
      font-weight: 600;
      letter-spacing: -0.02em;
      display: flex;
      align-items: center;
      gap: 10px;
    }

    .hero-status-desc {
      font-size: 14px;
      color: var(--text-secondary);
      max-width: 620px;
    }

    .hero-actions {
      display: flex;
      align-items: center;
      gap: 12px;
      flex-shrink: 0;
    }

    /* Buttons */
    .btn {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      font-family: inherit;
      font-size: 14px;
      font-weight: 500;
      padding: 10px 18px;
      border-radius: var(--radius-sm);
      border: 1px solid transparent;
      cursor: pointer;
      transition: all 0.15s ease;
      text-decoration: none;
      user-select: none;
    }

    .btn:active {
      transform: scale(0.98);
    }

    .btn-hero {
      padding: 12px 22px;
      font-size: 15px;
      font-weight: 600;
    }

    .btn-run {
      background: #059669;
      color: #ffffff;
      box-shadow: 0 4px 14px rgba(5, 150, 105, 0.35);
    }
    .btn-run:hover {
      background: #10b981;
    }

    .btn-pause {
      background: #d97706;
      color: #ffffff;
      box-shadow: 0 4px 14px rgba(217, 119, 6, 0.35);
    }
    .btn-pause:hover {
      background: #f59e0b;
    }

    .btn-stop {
      background: rgba(244, 63, 94, 0.12);
      border-color: rgba(244, 63, 94, 0.3);
      color: #fda4af;
    }
    .btn-stop:hover {
      background: rgba(244, 63, 94, 0.2);
      border-color: rgba(244, 63, 94, 0.5);
      color: #fff;
    }

    .btn-secondary {
      background: var(--bg-surface-elevated);
      border-color: var(--border-subtle);
      color: var(--text-primary);
    }
    .btn-secondary:hover {
      background: var(--bg-surface-hover);
      border-color: rgba(255, 255, 255, 0.15);
    }

    /* Grid Layout */
    .dashboard-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 24px;
    }

    @media (max-width: 860px) {
      .dashboard-grid {
        grid-template-columns: 1fr;
      }
      .hero-controller {
        flex-direction: column;
        align-items: flex-start;
      }
      .hero-actions {
        width: 100%;
        justify-content: flex-start;
      }
    }

    /* Section Panels */
    .panel {
      background: var(--bg-surface);
      border: 1px solid var(--border-subtle);
      border-radius: var(--radius-md);
      padding: 24px;
      display: flex;
      flex-direction: column;
      gap: 20px;
    }

    .panel-header {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 12px;
    }

    .panel-heading {
      font-size: 16px;
      font-weight: 600;
      letter-spacing: -0.015em;
      color: var(--text-primary);
    }

    .panel-sub {
      font-size: 13px;
      color: var(--text-secondary);
      margin-top: 4px;
    }

    /* Keyboard Silence Selector */
    .keys-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
      gap: 10px;
    }

    .key-btn {
      background: var(--bg-surface-elevated);
      border: 1px solid var(--border-subtle);
      border-radius: var(--radius-sm);
      padding: 14px 12px;
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 6px;
      cursor: pointer;
      transition: all 0.15s ease;
      position: relative;
    }

    .key-btn:hover {
      background: var(--bg-surface-hover);
      border-color: rgba(255, 255, 255, 0.16);
    }

    .key-btn.active {
      background: rgba(56, 189, 248, 0.08);
      border-color: var(--accent-cyan);
      box-shadow: 0 0 0 1px var(--accent-cyan), 0 4px 12px rgba(56, 189, 248, 0.15);
    }

    .keycap {
      font-family: var(--font-mono);
      font-size: 13px;
      font-weight: 600;
      background: #0f141c;
      border: 1px solid rgba(255, 255, 255, 0.12);
      border-bottom: 2px solid rgba(255, 255, 255, 0.22);
      border-radius: 6px;
      padding: 4px 8px;
      color: var(--text-primary);
      min-width: 48px;
      text-align: center;
    }

    .key-btn.active .keycap {
      background: rgba(56, 189, 248, 0.15);
      border-color: var(--accent-cyan);
      color: #e0f2fe;
    }

    .key-title {
      font-size: 12px;
      font-weight: 500;
      color: var(--text-secondary);
    }

    .key-btn.active .key-title {
      color: var(--accent-cyan);
    }

    /* Form Elements */
    .form-group {
      display: flex;
      flex-direction: column;
      gap: 8px;
    }

    .form-label {
      font-size: 13px;
      font-weight: 500;
      color: var(--text-secondary);
      display: flex;
      justify-content: space-between;
      align-items: center;
    }

    .form-val {
      font-family: var(--font-mono);
      font-size: 12px;
      color: var(--accent-cyan);
    }

    select, input[type="text"] {
      background: var(--bg-surface-elevated);
      border: 1px solid var(--border-subtle);
      border-radius: var(--radius-sm);
      color: var(--text-primary);
      font-family: inherit;
      font-size: 14px;
      padding: 10px 14px;
      outline: none;
      transition: border-color 0.15s ease;
      width: 100%;
    }

    select:focus, input[type="text"]:focus {
      border-color: var(--accent-cyan);
      box-shadow: 0 0 0 1px var(--accent-cyan);
    }

    /* Sliders */
    input[type="range"] {
      -webkit-appearance: none;
      width: 100%;
      height: 6px;
      border-radius: 3px;
      background: var(--bg-surface-hover);
      outline: none;
    }

    input[type="range"]::-webkit-slider-thumb {
      -webkit-appearance: none;
      width: 18px;
      height: 18px;
      border-radius: 50%;
      background: var(--accent-cyan);
      cursor: pointer;
      box-shadow: 0 2px 6px rgba(0, 0, 0, 0.3);
      transition: transform 0.1s ease;
    }

    input[type="range"]::-webkit-slider-thumb:hover {
      transform: scale(1.15);
    }

    /* Switch Toggles */
    .toggle-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 10px 0;
      border-bottom: 1px solid rgba(255, 255, 255, 0.05);
    }

    .toggle-row:last-child {
      border-bottom: none;
    }

    .toggle-info {
      display: flex;
      flex-direction: column;
      gap: 2px;
    }

    .toggle-title {
      font-size: 13.5px;
      font-weight: 500;
      color: var(--text-primary);
    }

    .toggle-desc {
      font-size: 12px;
      color: var(--text-muted);
    }

    .switch {
      position: relative;
      display: inline-block;
      width: 44px;
      height: 24px;
      flex-shrink: 0;
    }

    .switch input {
      opacity: 0;
      width: 0;
      height: 0;
    }

    .slider {
      position: absolute;
      cursor: pointer;
      top: 0; left: 0; right: 0; bottom: 0;
      background-color: var(--bg-surface-hover);
      border: 1px solid var(--border-subtle);
      transition: .2s;
      border-radius: 24px;
    }

    .slider:before {
      position: absolute;
      content: "";
      height: 18px;
      width: 18px;
      left: 2px;
      bottom: 2px;
      background-color: white;
      transition: .2s;
      border-radius: 50%;
    }

    input:checked + .slider {
      background-color: #0284c7;
      border-color: var(--accent-cyan);
    }

    input:checked + .slider:before {
      transform: translateX(20px);
    }

    /* Live Terminal Console Log */
    .console-panel {
      background: #080b10;
      border: 1px solid var(--border-subtle);
      border-radius: var(--radius-md);
      padding: 20px;
      font-family: var(--font-mono);
      font-size: 12px;
      display: flex;
      flex-direction: column;
      gap: 12px;
    }

    .console-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      border-bottom: 1px solid rgba(255, 255, 255, 0.06);
      padding-bottom: 10px;
    }

    .console-title {
      color: var(--text-secondary);
      font-weight: 500;
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .console-body {
      max-height: 200px;
      overflow-y: auto;
      display: flex;
      flex-direction: column;
      gap: 6px;
      color: #94a3b8;
    }

    .log-line {
      line-height: 1.6;
      word-break: break-all;
    }

    .log-line .ts {
      color: #475569;
    }

    .log-line.highlight {
      color: #38bdf8;
    }

    /* Sound Wave Animation */
    .sound-waves {
      display: flex;
      align-items: center;
      gap: 3px;
      height: 16px;
    }

    .wave-bar {
      width: 3px;
      background: var(--accent-cyan);
      border-radius: 1px;
      animation: sound-bounce 1s infinite ease-in-out;
    }

    .wave-bar:nth-child(1) { height: 6px; animation-delay: 0.1s; }
    .wave-bar:nth-child(2) { height: 14px; animation-delay: 0.3s; }
    .wave-bar:nth-child(3) { height: 8px; animation-delay: 0.2s; }
    .wave-bar:nth-child(4) { height: 16px; animation-delay: 0.4s; }

    @keyframes sound-bounce {
      0%, 100% { transform: scaleY(0.4); }
      50% { transform: scaleY(1); }
    }

    /* Toast Notification */
    #toast {
      position: fixed;
      bottom: 24px;
      right: 24px;
      background: #1e293b;
      border: 1px solid rgba(255, 255, 255, 0.15);
      color: #fff;
      padding: 12px 20px;
      border-radius: var(--radius-sm);
      font-size: 13.5px;
      box-shadow: 0 10px 25px rgba(0, 0, 0, 0.4);
      transform: translateY(100px);
      opacity: 0;
      transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
      z-index: 100;
      display: flex;
      align-items: center;
      gap: 10px;
    }

    #toast.show {
      transform: translateY(0);
      opacity: 1;
    }
  </style>
</head>
<body>

  <header>
    <div class="header-inner">
      <div class="brand">
        <div class="brand-icon">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/>
            <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
            <line x1="12" x2="12" y1="19" y2="22"/>
          </svg>
        </div>
        <div>
          <div class="brand-title">Antigravity Output Announcer</div>
          <div class="brand-sub">Neural Audio & Terminal Speech Control</div>
        </div>
      </div>

      <div class="header-actions">
        <div id="liveStatusBadge" class="live-badge running">
          <span class="live-pulse"></span>
          <span id="liveStatusText">Running</span>
        </div>
        <button id="btnStopAudio" class="btn btn-stop" title="Stop current speech and purge queue">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
            <rect x="4" y="4" width="16" height="16" rx="2"/>
          </svg>
          Stop Audio
        </button>
      </div>
    </div>
  </header>

  <main>
    <!-- Hero Script Runner & Pause Controller -->
    <div id="heroController" class="hero-controller">
      <div class="hero-details">
        <div id="heroStatusTitle" class="hero-status-title">
          <span id="heroStatusIcon">⚡</span>
          <span id="heroStatusHeadline">Voice Announcer is Active</span>
        </div>
        <div id="heroStatusDesc" class="hero-status-desc">
          The background hook automatically intercepts completed Antigravity CLI turns, extracts smart takeaways, and reads them aloud.
        </div>
      </div>

      <div class="hero-actions">
        <button id="btnTogglePause" class="btn btn-hero btn-pause">
          <span id="toggleIcon">⏸</span>
          <span id="toggleText">Pause Script</span>
        </button>
      </div>
    </div>

    <!-- Main Grid: Mute Key & Synthesis Settings -->
    <div class="dashboard-grid">
      <!-- Section 1: Dynamic Mute Key Selector -->
      <div class="panel">
        <div class="panel-header">
          <div>
            <div class="panel-heading">Hardware Silence Key</div>
            <div class="panel-sub">Press this key anytime while speech is playing to immediately terminate audio.</div>
          </div>
        </div>

        <div class="keys-grid">
          <div class="key-btn" data-key="control">
            <div class="keycap">Ctrl ⌃</div>
            <div class="key-title">Control</div>
          </div>
          <div class="key-btn" data-key="escape">
            <div class="keycap">Esc</div>
            <div class="key-title">Escape</div>
          </div>
          <div class="key-btn" data-key="fn">
            <div class="keycap">Fn 🌐</div>
            <div class="key-title">Function</div>
          </div>
          <div class="key-btn" data-key="option">
            <div class="keycap">⌥ Alt</div>
            <div class="key-title">Option</div>
          </div>
          <div class="key-btn" data-key="command">
            <div class="keycap">⌘ Cmd</div>
            <div class="key-title">Command</div>
          </div>
          <div class="key-btn" data-key="space">
            <div class="keycap">Space ␣</div>
            <div class="key-title">Spacebar</div>
          </div>
          <div class="key-btn" data-key="shift">
            <div class="keycap">⇧ Shift</div>
            <div class="key-title">Shift</div>
          </div>
        </div>

        <div style="font-size: 12.5px; color: var(--text-muted); background: var(--bg-surface-elevated); padding: 12px 14px; border-radius: var(--radius-sm); border: 1px solid var(--border-subtle); display: flex; gap: 8px;">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="flex-shrink: 0; margin-top: 1px; color: var(--accent-cyan);">
            <circle cx="12" cy="12" r="10"/>
            <line x1="12" y1="16" x2="12" y2="12"/>
            <line x1="12" y1="8" x2="12.01" y2="8"/>
          </svg>
          <span>Selection saves instantly. The native low-latency monitor runs in the background and catches modifier changes at hardware level.</span>
        </div>
      </div>

      <!-- Section 2: Voice & Neural Audio -->
      <div class="panel">
        <div class="panel-header">
          <div>
            <div class="panel-heading">Voice & Audio Profile</div>
            <div class="panel-sub">Select neural speaker model, conversational mode, and playback rates.</div>
          </div>
        </div>

        <div class="form-group">
          <label class="form-label">Speaker Voice</label>
          <select id="selectVoice">
            <option value="en-US-AvaNeural">Ava Neural (Fast, expressive, natural - Recommended)</option>
            <option value="en-US-EmmaNeural">Emma Neural (Friendly, conversational)</option>
            <option value="en-US-AnaNeural">Ana Neural (Youthful American)</option>
            <option value="en-US-JennyNeural">Jenny Neural (Professional, clear)</option>
            <option value="Samantha">Samantha (macOS Offline System Voice)</option>
          </select>
        </div>

        <div class="form-group">
          <label class="form-label">Reading Mode</label>
          <select id="selectMode">
            <option value="smart">Smart Takeaway (1-2 sentences + pending question)</option>
            <option value="headline">Headline (Ultra-concise single sentence)</option>
            <option value="full">Full Output (Continuous cleaned reading)</option>
          </select>
        </div>

        <div class="form-group">
          <div class="form-label">
            <span>Speech Speed</span>
            <span id="rateLabel" class="form-val">+1%</span>
          </div>
          <input type="range" id="rateSlider" min="-15" max="30" step="1" value="1">
        </div>

        <div class="form-group">
          <div class="form-label">
            <span>Volume Boost</span>
            <span id="volumeLabel" class="form-val">1.3x</span>
          </div>
          <input type="range" id="volumeSlider" min="0.5" max="2.0" step="0.1" value="1.3">
        </div>
      </div>
    </div>

    <!-- Section 3: Announcer Features & Test Audio -->
    <div class="dashboard-grid">
      <div class="panel">
        <div class="panel-heading">Behaviors & Features</div>

        <div class="toggle-row">
          <div class="toggle-info">
            <div class="toggle-title">Announce Terminal Tab & Workspace</div>
            <div class="toggle-desc">Prefixes speech with the originating tab and folder name (e.g. "In tab 2 project")</div>
          </div>
          <label class="switch">
            <input type="checkbox" id="toggleTabAnnounce" checked>
            <span class="slider"></span>
          </label>
        </div>

        <div class="toggle-row">
          <div class="toggle-info">
            <div class="toggle-title">macOS Desktop Notifications</div>
            <div class="toggle-desc">Displays a banner notification alongside the spoken summary</div>
          </div>
          <label class="switch">
            <input type="checkbox" id="toggleNotification" checked>
            <span class="slider"></span>
          </label>
        </div>

        <div class="form-group" style="margin-top: 8px;">
          <label class="form-label">Personal Address Name</label>
          <input type="text" id="inputUserName" placeholder="Optional (e.g. Adrien, Akshat)">
        </div>
      </div>

      <!-- Test Audio Panel -->
      <div class="panel">
        <div class="panel-heading">Test Speech Output</div>
        <div class="panel-sub">Play a sample announcement using your active voice and rate settings.</div>

        <div class="form-group" style="flex: 1;">
          <input type="text" id="inputTestPhrase" value="Antigravity output announcer is active. Press your mute key to test immediate silence.">
        </div>

        <div style="display: flex; gap: 10px;">
          <button id="btnPlayTest" class="btn btn-secondary" style="flex: 1;">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor">
              <polygon points="5 3 19 12 5 21 5 3"/>
            </svg>
            Play Test Voice
          </button>
        </div>
      </div>
    </div>

    <!-- Section 4: Live Activity Log Console -->
    <div class="console-panel">
      <div class="console-header">
        <div class="console-title">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="4 17 10 11 4 5"/>
            <line x1="12" y1="19" x2="20" y2="19"/>
          </svg>
          Live Activity & Output Log
        </div>
        <div id="playingWaveContainer" style="display: none;">
          <div class="sound-waves">
            <div class="wave-bar"></div>
            <div class="wave-bar"></div>
            <div class="wave-bar"></div>
            <div class="wave-bar"></div>
          </div>
        </div>
      </div>
      <div id="consoleBody" class="console-body">
        <div class="log-line"><span class="ts">[Ready]</span> Listening for Antigravity turn completions...</div>
      </div>
    </div>
  </main>

  <div id="toast">
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#34d399" stroke-width="2">
      <polyline points="20 6 9 17 4 12"/>
    </svg>
    <span id="toastMsg">Settings updated successfully</span>
  </div>

  <script>
    let state = {
      paused: false,
      mute_key: 'control',
      config: {},
      is_speaking: false
    };

    function showToast(msg) {
      const toast = document.getElementById('toast');
      document.getElementById('toastMsg').innerText = msg;
      toast.classList.add('show');
      setTimeout(() => toast.classList.remove('show'), 2600);
    }

    async function fetchStatus() {
      try {
        const res = await fetch('/api/status');
        const data = await res.json();
        updateUI(data);
      } catch (e) {
        console.error("Status fetch error:", e);
      }
    }

    function updateUI(data) {
      state = data;
      const cfg = data.config || {};

      // 1. Paused / Running State
      const isPaused = Boolean(cfg.paused);
      const isSpeaking = Boolean(data.is_speaking);

      const hero = document.getElementById('heroController');
      const badge = document.getElementById('liveStatusBadge');
      const badgeText = document.getElementById('liveStatusText');
      const btnToggle = document.getElementById('btnTogglePause');
      const toggleText = document.getElementById('toggleText');
      const toggleIcon = document.getElementById('toggleIcon');
      const heroHeadline = document.getElementById('heroStatusHeadline');
      const heroDesc = document.getElementById('heroStatusDesc');

      if (isPaused) {
        hero.classList.add('paused-mode');
        badge.className = 'live-badge paused';
        badgeText.innerText = 'Paused';
        btnToggle.className = 'btn btn-hero btn-run';
        toggleIcon.innerText = '▶';
        toggleText.innerText = 'Run Script';
        heroHeadline.innerText = 'Voice Announcer is Paused';
        heroDesc.innerText = 'The announcer is currently paused. Completed terminal tasks will not trigger spoken voice announcements.';
      } else {
        hero.classList.remove('paused-mode');
        badge.className = isSpeaking ? 'live-badge running' : 'live-badge running';
        badgeText.innerText = isSpeaking ? 'Speaking...' : 'Running';
        btnToggle.className = 'btn btn-hero btn-pause';
        toggleIcon.innerText = '⏸';
        toggleText.innerText = 'Pause Script';
        heroHeadline.innerText = 'Voice Announcer is Running';
        heroDesc.innerText = 'The background hook automatically intercepts completed Antigravity CLI turns, extracts smart takeaways, and reads them aloud.';
      }

      // Audio waveform indicator
      const wave = document.getElementById('playingWaveContainer');
      wave.style.display = isSpeaking ? 'block' : 'none';

      // 2. Active Mute Key Selector
      const activeKey = (cfg.mute_key || 'control').toLowerCase();
      document.querySelectorAll('.key-btn').forEach(btn => {
        const k = btn.getAttribute('data-key');
        if (k === activeKey || (k === 'control' && activeKey === 'ctrl')) {
          btn.classList.add('active');
        } else {
          btn.classList.remove('active');
        }
      });

      // 3. Form Controls (only if not currently focused by user)
      if (document.activeElement !== document.getElementById('selectVoice')) {
        document.getElementById('selectVoice').value = cfg.voice || 'en-US-AvaNeural';
      }
      if (document.activeElement !== document.getElementById('selectMode')) {
        document.getElementById('selectMode').value = cfg.mode || 'smart';
      }
      if (document.activeElement !== document.getElementById('rateSlider')) {
        const rVal = parseInt(cfg.rate) || 1;
        document.getElementById('rateSlider').value = rVal;
        document.getElementById('rateLabel').innerText = (rVal >= 0 ? '+' : '') + rVal + '%';
      }
      if (document.activeElement !== document.getElementById('volumeSlider')) {
        const vVal = parseFloat(cfg.volume_boost) || 1.3;
        document.getElementById('volumeSlider').value = vVal;
        document.getElementById('volumeLabel').innerText = vVal.toFixed(1) + 'x';
      }
      document.getElementById('toggleTabAnnounce').checked = cfg.announce_tab !== false;
      document.getElementById('toggleNotification').checked = cfg.notification !== false;
      if (document.activeElement !== document.getElementById('inputUserName')) {
        document.getElementById('inputUserName').value = cfg.user_name || '';
      }

      // 4. Console Logs
      if (data.recent_logs && data.recent_logs.length > 0) {
        const consoleBody = document.getElementById('consoleBody');
        consoleBody.innerHTML = '';
        data.recent_logs.forEach(line => {
          const div = document.createElement('div');
          div.className = 'log-line';
          if (line.includes('Speaking current turn') || line.includes('Mute key')) {
            div.classList.add('highlight');
          }
          div.textContent = line;
          consoleBody.appendChild(div);
        });
        consoleBody.scrollTop = consoleBody.scrollHeight;
      }
    }

    // Toggle Pause/Run Button
    document.getElementById('btnTogglePause').addEventListener('click', async () => {
      try {
        const res = await fetch('/api/toggle_pause', { method: 'POST' });
        const resData = await res.json();
        showToast(resData.paused ? 'Voice Announcer Paused' : 'Voice Announcer Running');
        fetchStatus();
      } catch (e) {
        console.error(e);
      }
    });

    // Mute Key Selection
    document.querySelectorAll('.key-btn').forEach(btn => {
      btn.addEventListener('click', async () => {
        const key = btn.getAttribute('data-key');
        try {
          await fetch('/api/set_mute_key', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mute_key: key })
          });
          showToast(`Silence shortcut updated to ${key.toUpperCase()}`);
          fetchStatus();
        } catch (e) {
          console.error(e);
        }
      });
    });

    // Stop Audio Button
    document.getElementById('btnStopAudio').addEventListener('click', async () => {
      try {
        await fetch('/api/stop', { method: 'POST' });
        showToast('Playback stopped and queue cleared');
        fetchStatus();
      } catch (e) {
        console.error(e);
      }
    });

    // Save Config Helper
    async function saveFormConfig() {
      const payload = {
        voice: document.getElementById('selectVoice').value,
        mode: document.getElementById('selectMode').value,
        rate: (parseInt(document.getElementById('rateSlider').value) >= 0 ? '+' : '') + document.getElementById('rateSlider').value + '%',
        volume_boost: parseFloat(document.getElementById('volumeSlider').value),
        announce_tab: document.getElementById('toggleTabAnnounce').checked,
        notification: document.getElementById('toggleNotification').checked,
        user_name: document.getElementById('inputUserName').value.trim()
      };
      try {
        await fetch('/api/update_config', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        showToast('Settings saved');
        fetchStatus();
      } catch (e) {
        console.error(e);
      }
    }

    // Input listeners
    document.getElementById('selectVoice').addEventListener('change', saveFormConfig);
    document.getElementById('selectMode').addEventListener('change', saveFormConfig);
    document.getElementById('toggleTabAnnounce').addEventListener('change', saveFormConfig);
    document.getElementById('toggleNotification').addEventListener('change', saveFormConfig);
    document.getElementById('inputUserName').addEventListener('blur', saveFormConfig);

    document.getElementById('rateSlider').addEventListener('input', (e) => {
      const v = parseInt(e.target.value);
      document.getElementById('rateLabel').innerText = (v >= 0 ? '+' : '') + v + '%';
    });
    document.getElementById('rateSlider').addEventListener('change', saveFormConfig);

    document.getElementById('volumeSlider').addEventListener('input', (e) => {
      document.getElementById('volumeLabel').innerText = parseFloat(e.target.value).toFixed(1) + 'x';
    });
    document.getElementById('volumeSlider').addEventListener('change', saveFormConfig);

    // Play Test
    document.getElementById('btnPlayTest').addEventListener('click', async () => {
      const phrase = document.getElementById('inputTestPhrase').value;
      try {
        await fetch('/api/test', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text: phrase })
        });
        showToast('Playing test audio...');
        fetchStatus();
      } catch (e) {
        console.error(e);
      }
    });

    // Initial load & polling loop (every 1.5s)
    fetchStatus();
    setInterval(fetchStatus, 1500);
  </script>
</body>
</html>
"""

class AnnouncerHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Silence default stderr spam
        pass

    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        if url.path == "/" or url.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode("utf-8"))
        elif url.path == "/api/status":
            cfg = load_config()
            data = {
                "config": cfg,
                "paused": cfg.get("paused", False),
                "mute_key": cfg.get("mute_key", "control"),
                "is_speaking": is_audio_playing(),
                "recent_logs": read_recent_logs(20)
            }
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(data).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        url = urllib.parse.urlparse(self.path)
        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len).decode("utf-8") if content_len > 0 else "{}"
        try:
            payload = json.loads(body) if body.strip() else {}
        except Exception:
            payload = {}

        if url.path == "/api/toggle_pause":
            cfg = load_config()
            cur_paused = cfg.get("paused", False)
            new_paused = not cur_paused
            cfg["paused"] = new_paused
            save_config(cfg)
            if new_paused:
                stop_all_speech()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": True, "paused": new_paused}).encode("utf-8"))

        elif url.path == "/api/set_mute_key":
            key = payload.get("mute_key", "control")
            cfg = load_config()
            cfg["mute_key"] = key
            save_config(cfg)
            # Re-compile / ensure monitor if needed
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": True, "mute_key": key}).encode("utf-8"))

        elif url.path == "/api/update_config":
            cfg = load_config()
            for k in ["voice", "mode", "rate", "volume_boost", "announce_tab", "notification", "user_name"]:
                if k in payload:
                    cfg[k] = payload[k]
            save_config(cfg)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": True}).encode("utf-8"))

        elif url.path == "/api/stop":
            stop_all_speech()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": True}).encode("utf-8"))

        elif url.path == "/api/test":
            txt = payload.get("text")
            enqueue_test(txt)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": True}).encode("utf-8"))

        else:
            self.send_response(404)
            self.end_headers()

def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

def start_server(port=PORT, open_browser=True):
    if is_port_in_use(port):
        if open_browser:
            subprocess.run(["open", f"http://127.0.0.1:{port}"])
        print(f"Announcer UI already running at http://127.0.0.1:{port}")
        return

    server = HTTPServer(('127.0.0.1', port), AnnouncerHandler)
    url = f"http://127.0.0.1:{port}"
    print(f"Antigravity Announcer UI running at {url}")
    if open_browser:
        subprocess.run(["open", url])
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

if __name__ == "__main__":
    should_open = "--no-open" not in sys.argv
    start_server(open_browser=should_open)

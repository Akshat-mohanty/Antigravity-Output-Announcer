# Antigravity Output Announcer 🎙️

An intelligent, non-blocking voice announcer and reader plugin for the [Antigravity](https://github.com/google-deepmind) CLI (`agy`).

Whenever any terminal tab running `agy` completes a task, this plugin automatically summarizes the response and reads it aloud using ultra-smooth neural text-to-speech, complete with native tab awareness and an instant keyboard interrupt shortcut.

---

## ✨ Features

- **🗣️ Natural Neural TTS**: Uses high-quality neural voice models (e.g. `Ava Neural`, `Emma Neural`) via `edge-tts` with seamless fallback to macOS system voices (`say`).
- **🧠 Smart Output Extraction**:
  - Cleans Markdown formatting, backticks, asterisks, URLs, and code blocks.
  - Strips bullet recitation to deliver concise, natural-sounding conversational summaries (1–2 key sentences plus any call-to-action or question).
- **🛑 Instant Silence Key (Control `Ctrl` / `⌃`)**:
  - Press the **Control** key anytime while speech is playing to instantly kill audio playback and discard queued speech.
  - Built with a native Swift background monitor (`voice_ctrl_monitor`) utilizing low-latency macOS `CGEvent` taps.
- **📑 Multi-Tab & Workspace Awareness**:
  - Dynamically detects the visual physical tab order (left-to-right) in Apple Terminal or iTerm2.
  - Prefixes speech with the source tab and project name (e.g., *"In tab 2 backend: ..."*).
- **🔔 Desktop Notifications**:
  - Displays macOS banner notifications matching the spoken announcement.
- **⚡ Non-Blocking Queue**:
  - Queues speech requests asynchronously via a background worker (`queue_worker.py`) backed by macOS `caffeinate`, ensuring `agy` runs at full speed without waiting on audio.

---

## 🚀 Installation

### 1. Clone & Run the Installer

```bash
git clone https://github.com/Akshat-mohanty/Antigravity-Output-Announcer.git
cd Antigravity-Output-Announcer
./install.sh
```

The installer will:
1. Install Python dependencies (`edge-tts`, `Pillow`).
2. Copy plugin files to `~/.gemini/config/plugins/voice-reader`.
3. Precompile native Swift event monitors (`voice_ctrl_monitor`, `voice_fn_monitor`, `find_tab_bar`).
4. Install the `agy-voice` CLI utility into `~/.local/bin/`.

Ensure `~/.local/bin` is in your `$PATH`.

---

## 🎮 CLI Control (`agy-voice`)

Manage voice reading settings anytime using the included `agy-voice` tool:

```bash
# Check current status, voice, speed, and pending queue
agy-voice status

# Stop active audio immediately & clear queue
agy-voice stop

# Enable or disable speech announcements
agy-voice on
agy-voice off

# Switch reading modes (smart = concise summary, headline = 1 sentence, full = full text)
agy-voice mode smart

# Change voice (available presets: ava, emma, ana, samantha)
agy-voice voice ava

# Adjust speech speed
agy-voice speed +5%

# Adjust volume boost (0.5 to 2.0)
agy-voice vol 1.3

# Toggle announcing tab/workspace name
agy-voice tab on

# Toggle desktop banner notifications
agy-voice notify on

# Play a test phrase
agy-voice test "Antigravity voice reader is working."
```

---

## ⌨️ Silence Shortcut

Whenever audio is playing:
- **Press `Control` (`Ctrl` / `⌃`)**: Instantly silences speech playback and purges pending audio from the queue.

---

## 📁 Repository Structure

```
Antigravity-Output-Announcer/
├── bin/
│   ├── agy-voice               # CLI controller command
│   ├── voice_ctrl_monitor.swift# Native Swift monitor for Control key press
│   ├── voice_fn_monitor.swift  # Native Swift monitor for Fn key press
│   └── find_tab_bar.swift      # Terminal tab visual position detection
├── hooks.json                  # Antigravity lifecycle hook definition (Stop event)
├── plugin.json                 # Antigravity plugin manifest
├── config.json                 # Default configuration parameters
├── read_output.py              # Main hook script: transcript parsing & text cleaning
├── queue_worker.py             # Asynchronous speech playback queue worker
├── speaker.py                  # TTS audio generation and playback engine
├── youtube_tracker.py          # Bonus background channel subscriber tracker
├── install.sh                  # One-step installer script
├── requirements.txt            # Python dependencies
└── README.md
```

---

## ⚙️ Configuration (`config.json`)

Located at `~/.gemini/config/plugins/voice-reader/config.json`:

```json
{
  "enabled": true,
  "user_name": "",
  "mode": "smart",
  "engine": "neural",
  "voice": "en-US-AvaNeural",
  "rate": "+1%",
  "max_words": 60,
  "volume_boost": 1.3,
  "announce_tab": true,
  "announce_tools": false,
  "notification": true
}
```

---

## 📄 License

MIT License. Feel free to use and modify!

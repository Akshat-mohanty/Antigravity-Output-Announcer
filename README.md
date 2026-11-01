# Antigravity Output Announcer 🎙️

An intelligent, non-blocking voice announcer and reader plugin for the [Antigravity](https://github.com/google-deepmind) CLI (`agy`).

Whenever any terminal tab running `agy` completes a task, this plugin automatically summarizes the response and reads it aloud using ultra-smooth neural text-to-speech, complete with native tab awareness, an aesthetic desktop control dashboard, and a configurable instant keyboard interrupt key.

---

## ✨ Features

- **🎨 Aesthetic Desktop GUI Dashboard**:
  - Clean, dark-mode control interface inspired by modern macOS design aesthetics.
  - Live state badge with audio waveforms and real-time activity log stream.
  - Instant one-click **Pause Script / Run Script** hero controller.
  - Interactive tactile **Silence Shortcut Key** selector (`Ctrl`, `Esc`, `Fn`, `Alt`, `Cmd`, `Space`, `Shift`).
  - Real-time voice model preview, speech speed, and volume boost controls.
- **🗣️ Natural Neural TTS**: High-quality neural voice models (e.g. `Ava Neural`, `Emma Neural`, `Ana Neural`) via `edge-tts` with seamless fallback to macOS system voices (`say`).
- **🧠 Smart Output Extraction**:
  - Cleans Markdown formatting, backticks, asterisks, URLs, and code blocks.
  - Strips bullet recitation to deliver concise, natural-sounding conversational summaries (1–2 key sentences plus any call-to-action or question).
- **🛑 Configurable Mute Key**:
  - Choose your preferred silence trigger: **Control (`Ctrl` / `⌃`)**, **Escape (`Esc`)**, **Function (`Fn` / 🌐)**, **Option (`Alt` / `⌥`)**, **Command (`Cmd` / `⌘`)**, **Space**, or **Shift**.
  - Built with a native Swift background monitor (`voice_mute_monitor`) utilizing low-latency macOS `CGEvent` taps and hardware polling.
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
2. Copy plugin files and the GUI server to `~/.gemini/config/plugins/voice-reader`.
3. Precompile native Swift event monitors (`voice_mute_monitor`, `voice_ctrl_monitor`, `voice_fn_monitor`, `find_tab_bar`).
4. Install the `agy-voice` CLI utility into `~/.local/bin/`.

Ensure `~/.local/bin` is in your `$PATH`.

---

## 🖥️ Launching the Aesthetic GUI

Open the desktop dashboard anytime with:

```bash
agy-voice gui
```

Or run directly:

```bash
python3 ui_server.py
```

This launches the web dashboard at `http://127.0.0.1:48123` with:
- **Pause / Run Toggle**: Instantly pause the script so terminal outputs stay silent, or resume active reading.
- **Silence Shortcut Selector**: Switch between `Control`, `Escape`, `Function`, `Option`, `Command`, `Space`, or `Shift`.
- **Live Voice & Rate Sliders**: Adjust speech speed (`-15%` to `+30%`) and volume boost (`0.5x` to `2.0x`).
- **Live Activity Console**: Streams recent speech timestamps and detected tabs.

---

## 🎮 CLI Controls (`agy-voice`)

Manage voice reading settings anytime from your terminal:

```bash
# Open the graphical user interface
agy-voice gui

# Check current status, pause state, mute key, and pending queue
agy-voice status

# Pause or Resume the announcer
agy-voice pause
agy-voice run

# Change the audio muting key
agy-voice key esc          # Set to Escape
agy-voice key ctrl         # Set to Control
agy-voice key fn           # Set to Function key
agy-voice key alt          # Set to Option / Alt
agy-voice key cmd          # Set to Command
agy-voice key space        # Set to Spacebar

# Stop active audio immediately & clear queue
agy-voice stop

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

## 📁 Repository Structure

```
Antigravity-Output-Announcer/
├── ui_server.py                # Aesthetic local web GUI dashboard & REST API
├── bin/
│   ├── agy-voice               # CLI controller command
│   ├── voice_mute_monitor.swift# Native Swift configurable mute key monitor
│   ├── voice_ctrl_monitor.swift# Native Swift monitor for Control key press
│   ├── voice_fn_monitor.swift  # Native Swift monitor for Fn key press
│   └── find_tab_bar.swift      # Terminal tab visual position detection
├── hooks.json                  # Antigravity lifecycle hook definition (Stop event)
├── plugin.json                 # Antigravity plugin manifest
├── config.json                 # Configuration parameters (paused, mute_key, voice)
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
  "paused": false,
  "mute_key": "control",
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

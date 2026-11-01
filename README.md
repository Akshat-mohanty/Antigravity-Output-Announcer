# Antigravity Output Announcer 🎙️

An intelligent, non-blocking voice announcer plugin for the [Antigravity](https://github.com/google-deepmind) CLI (`agy`).

Whenever any terminal tab running `agy` completes a task, this plugin automatically summarizes the response and reads it aloud using ultra-smooth neural text-to-speech, complete with native tab awareness and a customizable instant keyboard silence shortcut.

---

## ✨ Features

- **🗣️ Natural Neural TTS**: Uses high-quality neural voice models (e.g. `Ava Neural`, `Emma Neural`, `Ana Neural`) via `edge-tts` with seamless fallback to macOS system voices (`say`).
- **🧠 Smart Output Summaries**:
  - Automatically cleans Markdown, backticks, asterisks, URLs, and code blocks.
  - Strips bullet recitation to deliver concise, natural-sounding conversational summaries (1–2 key sentences plus any call-to-action or question).
- **🛑 Customizable Silence Button**:
  - Set your preferred keyboard key to immediately silence audio and clear pending queue items.
  - Supported keys: **Control (`ctrl`)**, **Function (`fn` / 🌐)**, **Escape (`esc`)**, **Option (`alt`)**, **Command (`cmd`)**, **Spacebar (`space`)**, or **Shift (`shift`)**.
  - Powered by a native Swift background monitor utilizing low-latency macOS `CGEvent` taps and hardware polling.
- **⏸️ Terminal Pause & Run Controls**:
  - Instantly pause the announcer when you want quiet without uninstalling or editing files.
  - Resume reading turns aloud with a single command.
- **📑 Multi-Tab & Workspace Awareness**:
  - Dynamically tracks the physical visual tab order (left-to-right) in Apple Terminal or iTerm2.
  - Prefixes speech with the source tab and project name (e.g., *"In tab 2 backend: ..."*).
- **🔔 Desktop Notifications**:
  - Displays macOS banner notifications matching the spoken announcement.
- **⚡ Non-Blocking Queue**:
  - Queues speech requests asynchronously via a background worker (`queue_worker.py`) backed by macOS `caffeinate`, ensuring `agy` runs at full speed without waiting on audio.

---

## 🚀 Terminal Setup Guide

Setting up Antigravity Output Announcer takes less than a minute through your terminal:

### Step 1: Clone the Repository

```bash
git clone https://github.com/Akshat-mohanty/Antigravity-Output-Announcer.git
cd Antigravity-Output-Announcer
```

### Step 2: Run the Installer

```bash
./install.sh
```

The script will automatically:
1. Install required Python packages (`edge-tts`, `Pillow`).
2. Install the plugin into `~/.gemini/config/plugins/voice-reader`.
3. Precompile native Swift helper binaries (`voice_mute_monitor`, `find_tab_bar`).
4. Install the `agy-voice` management command into `~/.local/bin/`.

> **Note**: Ensure `~/.local/bin` is in your `$PATH` (standard in macOS `.zshrc` / `.bashrc`):
> ```bash
> export PATH="$HOME/.local/bin:$PATH"
> ```

### Step 3: Verify Installation

Run:

```bash
agy-voice status
```

You should see:
```text
Antigravity Voice Reader Status:
  Script State:    ✓ Running
  Mute Audio Key:  CONTROL (press to silence)
  Voice:           en-US-AvaNeural
  Engine:          neural (ultra-realistic AI neural)
  Mode:            smart (smart = lead takeaway + next step)
  Speed:           +1%
  Volume Boost:    1.3x
  Queue Status:    0 item(s) pending
  Announce Tab:    ✓ Yes
  Notification:    ✓ Yes
```

---

## ⌨️ How to Change the Mute / Silence Key

You can change which keyboard button stops active speech at any time using:

```bash
agy-voice key <name>
```

### Supported Keys:

| Command | Key | Description |
|---|---|---|
| `agy-voice key ctrl` | **Control (`Ctrl` / `⌃`)** *(Default)* | Press Left or Right Control |
| `agy-voice key esc` | **Escape (`Esc`)** | Press Escape key |
| `agy-voice key fn` | **Function (`Fn` / 🌐)** | Press Fn / Globe or F-keys |
| `agy-voice key alt` | **Option / Alt (`⌥`)** | Press Left or Right Option |
| `agy-voice key cmd` | **Command (`⌘`)** | Press Command key |
| `agy-voice key space`| **Spacebar (`␣`)** | Tap Spacebar |
| `agy-voice key shift`| **Shift (`⇧`)** | Press Left or Right Shift |

### Check Current Key:

```bash
agy-voice key
# Output: Current mute key: ESC
```

Whenever audio is playing from an `agy` completion, simply press your chosen key to immediately terminate playback and clear the speech queue.

---

## ⏸️ How to Pause and Run the Script

When you are in a meeting or need silence, you can pause the script without disabling it:

### Pause Announcer:
```bash
agy-voice pause
```
*Output: `⏸ Voice announcer is now PAUSED. Completed turns will be silent.`*

### Resume / Run Announcer:
```bash
agy-voice run
```
*Output: `▶ Voice announcer is now RUNNING. Completed turns will be read aloud.`*

---

## 🎮 CLI Reference (`agy-voice`)

All configuration is managed directly via the `agy-voice` CLI tool:

```bash
# Check current settings, state, voice, and queue
agy-voice status

# Pause / Resume announcer
agy-voice pause
agy-voice run

# Change the audio silence key
agy-voice key esc
agy-voice key ctrl
agy-voice key fn

# Immediately stop playing audio & flush queue
agy-voice stop

# Choose a voice preset (ava, emma, ana, samantha)
agy-voice voice ava        # Ava Neural (Fast, expressive, natural)
agy-voice voice emma       # Emma Neural (Conversational)
agy-voice voice ana        # Ana Neural (Youthful American)
agy-voice voice samantha   # Samantha (macOS offline system voice)

# Change reading summary mode
agy-voice mode smart       # 1-2 core sentences + next step (Recommended)
agy-voice mode headline    # Ultra-concise single sentence
agy-voice mode full        # Direct cleaned output

# Adjust speech speed
agy-voice speed +5%        # Speed up (+0%, +5%, +10%, etc.)
agy-voice speed -5%        # Slow down

# Adjust volume boost
agy-voice vol 1.4          # 0.5 to 2.0 (Default: 1.3)

# Toggle tab/workspace announcement
agy-voice tab off          # Don't announce "In tab X project"
agy-voice tab on

# Toggle macOS banner notifications
agy-voice notify on
agy-voice notify off

# Personalize your name
agy-voice name Adrien

# Play a test announcement
agy-voice test "Antigravity voice reader is working."
```

---

## 📁 Repository Structure

```
Antigravity-Output-Announcer/
├── bin/
│   ├── agy-voice               # CLI controller command
│   ├── voice_mute_monitor.swift# Native Swift configurable mute key monitor
│   ├── voice_ctrl_monitor.swift# Native Swift monitor for Control key press
│   ├── voice_fn_monitor.swift  # Native Swift monitor for Fn key press
│   └── find_tab_bar.swift      # Terminal tab visual position detection
├── hooks.json                  # Antigravity lifecycle hook definition (Stop event)
├── plugin.json                 # Antigravity plugin manifest
├── config.json                 # Runtime configuration parameters
├── read_output.py              # Main hook script: transcript parsing & text cleaning
├── queue_worker.py             # Asynchronous speech playback queue worker
├── speaker.py                  # TTS audio generation and playback engine
├── youtube_tracker.py          # Bonus background channel subscriber tracker
├── install.sh                  # One-step terminal installer script
├── requirements.txt            # Python dependencies (edge-tts, Pillow)
└── README.md
```

---

## ⚙️ Configuration (`config.json`)

The active configuration file is located at `~/.gemini/config/plugins/voice-reader/config.json`:

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

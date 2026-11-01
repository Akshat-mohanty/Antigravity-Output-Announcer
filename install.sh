#!/usr/bin/env bash
set -e

PLUGIN_TARGET_DIR="$HOME/.gemini/config/plugins/voice-reader"
LOCAL_BIN_DIR="$HOME/.local/bin"

echo "=== Installing Antigravity Output Announcer ==="

# 1. Install Python dependencies
echo "-> Installing Python dependencies..."
python3 -m pip install -r "$(dirname "$0")/requirements.txt" --break-system-packages --quiet 2>/dev/null || python3 -m pip install -r "$(dirname "$0")/requirements.txt" --quiet 2>/dev/null || true

# 2. Ensure target plugin directory exists
echo "-> Setting up plugin directory at $PLUGIN_TARGET_DIR..."
mkdir -p "$PLUGIN_TARGET_DIR/bin"
mkdir -p "$LOCAL_BIN_DIR"

# 3. Copy files to plugin directory
REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
cp "$REPO_DIR/read_output.py" "$PLUGIN_TARGET_DIR/"
cp "$REPO_DIR/queue_worker.py" "$PLUGIN_TARGET_DIR/"
cp "$REPO_DIR/speaker.py" "$PLUGIN_TARGET_DIR/"
cp "$REPO_DIR/youtube_tracker.py" "$PLUGIN_TARGET_DIR/"
cp "$REPO_DIR/hooks.json" "$PLUGIN_TARGET_DIR/"
cp "$REPO_DIR/plugin.json" "$PLUGIN_TARGET_DIR/"

# Don't overwrite existing user config if present
if [ ! -f "$PLUGIN_TARGET_DIR/config.json" ]; then
    cp "$REPO_DIR/config.json" "$PLUGIN_TARGET_DIR/"
fi

# Copy bin source files
cp "$REPO_DIR/bin/"*.swift "$PLUGIN_TARGET_DIR/bin/"

# 4. Compile Swift helper binaries
echo "-> Compiling native Swift monitor binaries..."
if command -v swiftc &>/dev/null; then
    swiftc -O "$PLUGIN_TARGET_DIR/bin/voice_mute_monitor.swift" -o "$PLUGIN_TARGET_DIR/bin/voice_mute_monitor"
    swiftc -O "$PLUGIN_TARGET_DIR/bin/voice_ctrl_monitor.swift" -o "$PLUGIN_TARGET_DIR/bin/voice_ctrl_monitor"
    swiftc -O "$PLUGIN_TARGET_DIR/bin/voice_fn_monitor.swift" -o "$PLUGIN_TARGET_DIR/bin/voice_fn_monitor"
    swiftc -O "$PLUGIN_TARGET_DIR/bin/find_tab_bar.swift" -o "$PLUGIN_TARGET_DIR/bin/find_tab_bar"
else
    echo "Warning: swiftc not found. Helper binaries will be compiled on first run if swiftc is available."
fi

# 5. Install agy-voice CLI tool
echo "-> Linking agy-voice CLI into $LOCAL_BIN_DIR..."
cp "$REPO_DIR/bin/agy-voice" "$LOCAL_BIN_DIR/agy-voice"
chmod +x "$LOCAL_BIN_DIR/agy-voice"

echo ""
echo "✓ Installation complete!"
echo "Run 'agy-voice status' to verify settings."
echo "Use 'agy-voice key <name>' to set your mute button (ctrl, fn, esc, alt, cmd, space, shift)."

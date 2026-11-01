import Cocoa
import CoreGraphics
import Foundation

// MARK: - Mute Key Definitions
enum MuteKey: String {
    case control = "control"
    case ctrl = "ctrl"
    case fn = "fn"
    case function = "function"
    case escape = "escape"
    case esc = "esc"
    case option = "option"
    case alt = "alt"
    case command = "command"
    case cmd = "cmd"
    case shift = "shift"
    case space = "space"
    
    static func normalized(_ raw: String) -> MuteKey {
        switch raw.trimmingCharacters(in: .whitespacesAndNewlines).lowercased() {
        case "fn", "function", "globe": return .fn
        case "escape", "esc": return .escape
        case "option", "alt": return .option
        case "command", "cmd": return .command
        case "shift": return .shift
        case "space", "spacebar": return .space
        default: return .control
        }
    }
}

func loadConfiguredKey() -> MuteKey {
    let configPath = NSString(string: "~/.gemini/config/plugins/voice-reader/config.json").expandingTildeInPath
    if let data = try? Data(contentsOf: URL(fileURLWithPath: configPath)),
       let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
       let rawKey = json["mute_key"] as? String {
        return MuteKey.normalized(rawKey)
    }
    return .control
}

var activeKey: MuteKey = loadConfiguredKey()
var targetParentPid: pid_t = getppid()

// Parse CLI overrides
let args = CommandLine.arguments
for i in 0..<args.count {
    if args[i] == "--key" && i + 1 < args.count {
        activeKey = MuteKey.normalized(args[i + 1])
    } else if args[i] == "--parent" && i + 1 < args.count {
        if let p = Int32(args[i + 1]) {
            targetParentPid = p
        }
    }
}

var isStopping = false
let lock = NSLock()

func logWorker(_ message: String) {
    let formatter = DateFormatter()
    formatter.dateFormat = "yyyy-MM-dd HH:mm:ss"
    let dateStr = formatter.string(from: Date())
    let line = "[\(dateStr)] [MuteMonitor:\(activeKey.rawValue)] \(message)\n"
    if let data = line.data(using: .utf8),
       let handle = FileHandle(forWritingAtPath: "/tmp/agy_voice_worker.log") {
        handle.seekToEndOfFile()
        handle.write(data)
        handle.closeFile()
    }
}

func stopSpeech(reason: String) {
    lock.lock()
    if isStopping {
        lock.unlock()
        return
    }
    isStopping = true
    lock.unlock()

    logWorker("Mute key '\(activeKey.rawValue)' triggered (\(reason)). Stopping speech immediately.")

    // 1. Mark as cancelled
    FileManager.default.createFile(atPath: "/tmp/agy_voice_cancelled", contents: nil)

    // 2. Kill playback
    let killTask = Process()
    killTask.executableURL = URL(fileURLWithPath: "/usr/bin/killall")
    killTask.arguments = ["-9", "afplay", "say"]
    killTask.standardOutput = FileHandle.nullDevice
    killTask.standardError = FileHandle.nullDevice
    try? killTask.run()
    killTask.waitUntilExit()

    // 3. Clear queue
    let queueDir = "/tmp/agy_voice_queue"
    if let files = try? FileManager.default.contentsOfDirectory(atPath: queueDir) {
        for f in files where f.hasSuffix(".json") {
            try? FileManager.default.removeItem(atPath: "\(queueDir)/\(f)")
        }
    }

    // 4. Remove PID file
    try? FileManager.default.removeItem(atPath: "/tmp/agy_voice_reader.pid")

    exit(0)
}

func checkKeyCondition(flags: CGEventFlags, keycode: Int64) -> Bool {
    switch activeKey {
    case .control, .ctrl:
        return flags.contains(.maskControl) || keycode == 59 || keycode == 62
    case .fn, .function:
        let isFnFlag = flags.contains(.maskSecondaryFn)
        let isFnKey = (keycode == 63) || (122...131 ~= keycode) || (keycode == 96) || (keycode == 97)
        return isFnFlag || isFnKey
    case .escape, .esc:
        return keycode == 53
    case .option, .alt:
        return flags.contains(.maskAlternate) || keycode == 58 || keycode == 61
    case .command, .cmd:
        return flags.contains(.maskCommand) || keycode == 54 || keycode == 55
    case .shift:
        return flags.contains(.maskShift) || keycode == 56 || keycode == 60
    case .space:
        return keycode == 49
    }
}

func pollHardwareState() -> Bool {
    let flags = CGEventSource.flagsState(.hidSystemState)
    switch activeKey {
    case .control, .ctrl:
        return flags.contains(.maskControl) ||
               CGEventSource.keyState(.hidSystemState, key: 59) ||
               CGEventSource.keyState(.hidSystemState, key: 62)
    case .fn, .function:
        return flags.contains(.maskSecondaryFn) ||
               CGEventSource.keyState(.hidSystemState, key: 63)
    case .escape, .esc:
        return CGEventSource.keyState(.hidSystemState, key: 53)
    case .option, .alt:
        return flags.contains(.maskAlternate) ||
               CGEventSource.keyState(.hidSystemState, key: 58) ||
               CGEventSource.keyState(.hidSystemState, key: 61)
    case .command, .cmd:
        return flags.contains(.maskCommand) ||
               CGEventSource.keyState(.hidSystemState, key: 54) ||
               CGEventSource.keyState(.hidSystemState, key: 55)
    case .shift:
        return flags.contains(.maskShift) ||
               CGEventSource.keyState(.hidSystemState, key: 56) ||
               CGEventSource.keyState(.hidSystemState, key: 60)
    case .space:
        return CGEventSource.keyState(.hidSystemState, key: 49)
    }
}

// Method 1: CGEvent Tap
let mask = (1 << CGEventType.flagsChanged.rawValue) | (1 << CGEventType.keyDown.rawValue)
if let tap = CGEvent.tapCreate(
    tap: .cghidEventTap,
    place: .headInsertEventTap,
    options: .listenOnly,
    eventsOfInterest: CGEventMask(mask),
    callback: { (proxy, type, event, refcon) -> Unmanaged<CGEvent>? in
        let flags = event.flags
        let keycode = event.getIntegerValueField(.keyboardEventKeycode)
        if checkKeyCondition(flags: flags, keycode: keycode) {
            stopSpeech(reason: "Event tap detected key")
        }
        return Unmanaged.passUnretained(event)
    },
    userInfo: nil
) {
    let runLoopSource = CFMachPortCreateRunLoopSource(kCFAllocatorDefault, tap, 0)
    CFRunLoopAddSource(CFRunLoopGetCurrent(), runLoopSource, .commonModes)
    CGEvent.tapEnable(tap: tap, enable: true)
}

// Method 2: Fast Polling Fallback (every 30ms)
let pollTimer = Timer.scheduledTimer(withTimeInterval: 0.030, repeats: true) { _ in
    if pollHardwareState() {
        stopSpeech(reason: "Polled hardware state")
    }
}

// Parent Watchdog
let parentCheckTimer = Timer.scheduledTimer(withTimeInterval: 0.5, repeats: true) { _ in
    if kill(targetParentPid, 0) != 0 {
        exit(0)
    }
}

RunLoop.current.run()

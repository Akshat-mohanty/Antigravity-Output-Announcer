import Cocoa
import CoreGraphics
import Foundation

// MARK: - Keycodes for Function Keys
let functionKeyCodes: Set<Int64> = [
    63,  // fn / Globe key on Apple keyboards
    122, // F1
    120, // F2
    99,  // F3
    118, // F4
    96,  // F5
    97,  // F6
    98,  // F7
    100, // F8
    101, // F9
    109, // F10
    103, // F11
    111, // F12
    105, // F13
    107, // F14
    113, // F15
    106, // F16
    64,  // F17
    79,  // F18
    80,  // F19
    90   // F20
]

var isStopping = false
let lock = NSLock()

func logWorker(_ message: String) {
    let formatter = DateFormatter()
    formatter.dateFormat = "yyyy-MM-dd HH:mm:ss"
    let dateStr = formatter.string(from: Date())
    let line = "[\(dateStr)] [FnMonitor] \(message)\n"
    if let data = line.data(using: .utf8) {
        if let handle = FileHandle(forWritingAtPath: "/tmp/agy_voice_worker.log") {
            handle.seekToEndOfFile()
            handle.write(data)
            handle.closeFile()
        }
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

    logWorker("Function key detected (\(reason)). Stopping speech immediately.")

    // 1. Mark as cancelled so workers abort immediately
    FileManager.default.createFile(atPath: "/tmp/agy_voice_cancelled", contents: nil)

    // 2. Kill active audio playback processes
    let killTask = Process()
    killTask.executableURL = URL(fileURLWithPath: "/usr/bin/killall")
    killTask.arguments = ["-9", "afplay", "say"]
    killTask.standardOutput = FileHandle.nullDevice
    killTask.standardError = FileHandle.nullDevice
    try? killTask.run()
    killTask.waitUntilExit()

    // 3. Clear voice queue
    let queueDir = "/tmp/agy_voice_queue"
    if let files = try? FileManager.default.contentsOfDirectory(atPath: queueDir) {
        for f in files where f.hasSuffix(".json") {
            try? FileManager.default.removeItem(atPath: "\(queueDir)/\(f)")
        }
    }

    // 4. Remove active PID file
    try? FileManager.default.removeItem(atPath: "/tmp/agy_voice_reader.pid")

    exit(0)
}

// Check arguments: if parent PID was passed via argument, use it; otherwise use getppid()
var targetParentPid: pid_t = getppid()
let args = CommandLine.arguments
for i in 0..<args.count {
    if args[i] == "--parent" && i + 1 < args.count {
        if let p = Int32(args[i + 1]) {
            targetParentPid = p
        }
    }
}

// MARK: - Method 1: Global Event Tap
let mask = (1 << CGEventType.flagsChanged.rawValue) | (1 << CGEventType.keyDown.rawValue)
if let tap = CGEvent.tapCreate(
    tap: .cghidEventTap,
    place: .headInsertEventTap,
    options: .listenOnly,
    eventsOfInterest: CGEventMask(mask),
    callback: { (proxy, type, event, refcon) -> Unmanaged<CGEvent>? in
        let keycode = event.getIntegerValueField(.keyboardEventKeycode)

        if type == .flagsChanged {
            let flags = event.flags
            if keycode == 63 && flags.contains(.maskSecondaryFn) {
                stopSpeech(reason: "Fn/Globe key pressed")
            } else if flags.contains(.maskSecondaryFn) {
                stopSpeech(reason: "SecondaryFn flag active")
            }
        } else if type == .keyDown {
            if functionKeyCodes.contains(keycode) {
                stopSpeech(reason: "Function key code \(keycode) pressed")
            }
        }
        return Unmanaged.passUnretained(event)
    },
    userInfo: nil
) {
    let runLoopSource = CFMachPortCreateRunLoopSource(kCFAllocatorDefault, tap, 0)
    CFRunLoopAddSource(CFRunLoopGetCurrent(), runLoopSource, .commonModes)
    CGEvent.tapEnable(tap: tap, enable: true)
}

// MARK: - Method 2: Fast Polling Fallback (every 35ms)
let pollTimer = Timer.scheduledTimer(withTimeInterval: 0.035, repeats: true) { _ in
    let flags = CGEventSource.flagsState(.hidSystemState)
    if flags.contains(.maskSecondaryFn) {
        stopSpeech(reason: "Polled SecondaryFn flag")
        return
    }

    if CGEventSource.keyState(.hidSystemState, key: 63) {
        stopSpeech(reason: "Polled Fn keycode 63")
        return
    }

    for k in functionKeyCodes {
        if CGEventSource.keyState(.hidSystemState, key: CGKeyCode(k)) {
            stopSpeech(reason: "Polled Function keycode \(k)")
            return
        }
    }
}

// MARK: - Auto-exit when parent process exits
let parentCheckTimer = Timer.scheduledTimer(withTimeInterval: 0.5, repeats: true) { _ in
    if kill(targetParentPid, 0) != 0 {
        // Parent process no longer exists
        exit(0)
    }
}

RunLoop.current.run()

import Cocoa
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

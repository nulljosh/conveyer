// win.swift: find a program's windows and click inside one without moving the real mouse.
//   win list PID            every window of that process: id, layer, on-screen flag, x y w h, title
//   win click PID X Y       left click at a screen point, delivered to that process only (the cursor stays where it is)
// Build once: swiftc -O scripts/win.swift -o .gdt/win
import AppKit

let a = CommandLine.arguments
guard a.count >= 3, let pid = Int32(a[2]) else { print("usage: win list PID | win click PID X Y"); exit(1) }
if a[1] == "list" {
    let all = CGWindowListCopyWindowInfo([.optionAll], kCGNullWindowID) as? [[String: Any]] ?? []
    for w in all where (w[kCGWindowOwnerPID as String] as? Int32) == pid {
        let b = w[kCGWindowBounds as String] as? [String: Any] ?? [:]
        print(w[kCGWindowNumber as String] ?? 0, w[kCGWindowLayer as String] ?? 0, w[kCGWindowIsOnscreen as String] ?? 0,
              b["X"] ?? 0, b["Y"] ?? 0, b["Width"] ?? 0, b["Height"] ?? 0, w[kCGWindowName as String] ?? "")
    }
} else if a[1] == "click", a.count >= 5, let x = Double(a[3]), let y = Double(a[4]) {
    let p = CGPoint(x: x, y: y)
    for t in [CGEventType.leftMouseDown, .leftMouseUp] {
        guard let e = CGEvent(mouseEventSource: nil, mouseType: t, mouseCursorPosition: p, mouseButton: .left) else { exit(2) }
        e.postToPid(pid)
        usleep(80_000)
    }
}

import SwiftUI
import Darwin
import Carbon.HIToolbox

extension Status {
    /// The game reports ok even when a skill threw, so also read the message.
    var worked: Bool { ok && !message.contains("Exception") && !message.contains("Error occurred") }
}

struct Status: Decodable {
    let step: Int
    let skill: String
    let ok: Bool
    let message: String
    let updated_at: Double
}

struct Research: Decodable {
    let current: String
    let percent: Int
    let techs: Int
    let queue: [String]
    let labs: Int?
    let labs_working: Int?
    let moving: Bool?   // research progress changed in the last 90 s; labs flip faster than we sample

    /// "advanced-circuit" -> "Advanced circuit"
    static func nice(_ name: String) -> String {
        let t = name.replacingOccurrences(of: "-", with: " ")
        return t.prefix(1).uppercased() + t.dropFirst()
    }
}

struct Milestone: Identifiable {
    let id: Int
    let title: String
    let eta: String?
    let done: Bool

    /// Parses the "Real save run" checklist in roadmap.md. One source of truth: edit the roadmap, the menu bar follows.
    static func load(_ path: String) -> [Milestone] {
        guard let text = try? String(contentsOfFile: path, encoding: .utf8) else { return [] }
        var inSection = false
        var out: [Milestone] = []
        for line in text.split(separator: "\n", omittingEmptySubsequences: false) {
            if line.hasPrefix("## ") { inSection = line.hasPrefix("## Real save run"); continue }
            guard inSection else { continue }
            let t = line.trimmingCharacters(in: .whitespaces)
            let done = t.hasPrefix("- [x]")
            guard done || t.hasPrefix("- [ ]") else { continue }
            let body = String(t.dropFirst(6))
            let parts = body.components(separatedBy: " ETA ")
            let title = parts[0].components(separatedBy: ". ")[0].trimmingCharacters(in: CharacterSet(charactersIn: ". "))
            let eta = parts.count > 1 ? parts[1].trimmingCharacters(in: CharacterSet(charactersIn: ". ")) : nil
            out.append(Milestone(id: out.count, title: title, eta: eta, done: done))
        }
        return out
    }
}

@MainActor
final class StatusPoller: ObservableObject {
    @Published var status: Status?
    @Published var stale = false
    @Published var runnerAlive = true
    @Published var busy = false
    @Published var map: NSImage?
    @Published var research: Research?
    @Published var milestones: [Milestone] = []
    private var roadmapStamp: Date?
    private let roadmapPath = NSString(
        string: "~/Documents/Code/conveyer/roadmap.md"
    ).expandingTildeInPath
    private let researchPath = NSString(
        string: "~/Documents/Code/conveyer/research.json"
    ).expandingTildeInPath
    private var mapStamp: Date?
    private let mapPath = NSString(
        string: "~/Documents/Code/conveyer/preview.png"
    ).expandingTildeInPath
    /// preview.png with real ground painted under the sprites (scripts/terrain.py); falls back to the flat render.
    private let terrainPath = NSString(
        string: "~/Documents/Code/conveyer/preview_map.png"
    ).expandingTildeInPath

    private let statusPath = NSString(
        string: "~/Documents/Code/conveyer/status.json"
    ).expandingTildeInPath
    private let pidPath = NSString(
        string: "~/Documents/Code/conveyer/runner.pid"
    ).expandingTildeInPath
    private var autoRestartedAt: Date?

    /// `--demo stopped|failed|idle|nodata` overrides the real data so each state can be checked in a snapshot.
    func applyDemo(_ name: String) {
        switch name {
        case "stopped": runnerAlive = false
        case "failed": status = Status(step: 9, skill: "craft", ok: true, message: "Error occurred:\n Line 2: could not craft LogisticsSciencePack, missing 40 iron-plate", updated_at: Date().timeIntervalSince1970)
        case "idle": research = Research(current: "advanced-circuit", percent: 36, techs: 41, queue: ["advanced-circuit", "chemical-science-pack"], labs: 9, labs_working: 0, moving: false)
        case "nodata": status = nil; research = nil; milestones = []; map = nil
        default: break
        }
    }
    private let scriptsDir = NSString(
        string: "~/Documents/Code/conveyer/menubar"
    ).expandingTildeInPath

    /// Something is on screen: the popover is open or the live window is visible. Everything expensive keys off this.
    @Published var popoverShown = false { didSet { applyWatching() } }
    @Published var windowVisible = false { didSet { applyWatching() } }
    @Published var hudVisible = false   // the progress panel top left starts hidden; Ctrl+Option+H shows or hides it
    @Published var lastFrame: Date?
    let marker = MarkerModel()
    private var timer: Timer?
    private let watchPath = NSString(string: "~/Documents/Code/conveyer/.watching").expandingTildeInPath

    var watching: Bool { popoverShown || windowVisible }

    private func applyWatching() {
        timer?.invalidate()
        if watching {
            touchWatching()
            marker.start()
        } else {
            marker.stop()
        }
        // 1 s while someone looks (the heartbeat must stay under the 8 s the Python side tolerates), 5 s otherwise
        timer = Timer.scheduledTimer(withTimeInterval: watching ? 1 : 5, repeats: true) { _ in
            Task { @MainActor in self.poll() }
        }
    }

    private func touchWatching() {
        try? Data().write(to: URL(fileURLWithPath: watchPath))
    }

    init() {
        poll()
        applyWatching()
        Hotkey.register({ [weak self] in Task { @MainActor in self?.hudVisible.toggle() } }, pin: { Task { @MainActor in LiveWindow.togglePin() } })
        // `ConveyerMonitor --open-live` opens the live window; add `--fullscreen` for full screen
        if CommandLine.arguments.contains("--open-live") {
            DispatchQueue.main.asyncAfter(deadline: .now() + 1.5) {
                LiveWindow.show(self)
                if CommandLine.arguments.contains("--fullscreen") { DispatchQueue.main.asyncAfter(deadline: .now() + 0.8) { LiveWindow.window?.toggleFullScreen(nil) } }
            }
        }
    }

    func poll() {
        if watching { touchWatching() }
        if let data = FileManager.default.contents(atPath: statusPath),
           let decoded = try? JSONDecoder().decode(Status.self, from: data) {
            status = decoded
            stale = Date().timeIntervalSince1970 - decoded.updated_at > 120
        }
        loadMap()
        if let data = FileManager.default.contents(atPath: researchPath),
           let r = try? JSONDecoder().decode(Research.self, from: data) { research = r }
        loadRoadmap()
        checkLiveness()
    }

    private func loadRoadmap() {
        guard let m = (try? FileManager.default.attributesOfItem(atPath: roadmapPath))?[.modificationDate] as? Date,
              m != roadmapStamp else { return }
        roadmapStamp = m
        milestones = Milestone.load(roadmapPath)
    }

    /// The runner rewrites preview.png every ~8s while idle, non-atomically. Only keep a
    /// frame that decodes, and only remember its stamp then, so a half-written file is retried.
    private func loadMap() {
        let path = FileManager.default.fileExists(atPath: terrainPath) ? terrainPath : mapPath
        guard let m = (try? FileManager.default.attributesOfItem(atPath: path))?[.modificationDate] as? Date,
              m != mapStamp else { return }
        guard let img = NSImage(contentsOfFile: path), img.size.width > 0 else {
            FileHandle.standardError.write(Data("map: decode failed, will retry\n".utf8))
            return
        }
        mapStamp = m
        map = img
        lastFrame = m
        FileHandle.standardError.write(Data("map: loaded \(Int(img.size.width))x\(Int(img.size.height))\n".utf8))
    }

    /// True process liveness (kill(pid, 0)), not just "no recent status update" —
    /// a long smelt/harvest wait is a real gap, not a crash. Auto-restarts at most
    /// every 10 min: a runner that dies on boot (memory guard) must not respawn in a loop.
    private func checkLiveness() {
        // No pid file = stopped on purpose (Stop server) or killed by the memory guard.
        // Respawning either one just rebuilds the same balloon, so stay down.
        guard let pidText = try? String(contentsOfFile: pidPath, encoding: .utf8),
              let pid = pid_t(pidText.trimmingCharacters(in: .whitespacesAndNewlines))
        else { runnerAlive = false; return }
        let alive = Darwin.kill(pid, 0) == 0
        runnerAlive = alive
        if !alive && serverUp() {
            let now = Date()
            if autoRestartedAt == nil || now.timeIntervalSince(autoRestartedAt!) > 600 {
                autoRestartedAt = now
                run("restart_runner.sh")
            }
        }
    }

    /// RCON port open = a Factorio server is up. No server, no point restarting the runner.
    private func serverUp() -> Bool {
        let fd = socket(AF_INET, SOCK_STREAM, 0)
        guard fd >= 0 else { return false }
        defer { close(fd) }
        var addr = sockaddr_in()
        addr.sin_family = sa_family_t(AF_INET)
        addr.sin_port = in_port_t(27000).bigEndian
        addr.sin_addr.s_addr = inet_addr("127.0.0.1")
        return withUnsafePointer(to: &addr) {
            $0.withMemoryRebound(to: sockaddr.self, capacity: 1) {
                connect(fd, $0, socklen_t(MemoryLayout<sockaddr_in>.size)) == 0
            }
        }
    }

    func run(_ script: String) {
        busy = true
        let task = Process()
        task.executableURL = URL(fileURLWithPath: "/bin/bash")
        task.arguments = ["\(scriptsDir)/\(script)"]
        task.terminationHandler = { _ in
            Task { @MainActor in self.busy = false }
        }
        try? task.run()
    }
}

/// Ctrl+Option+H shows or hides the progress panel, Ctrl+Option+P pins the live window above everything or lets it drop back.
/// Carbon hot keys work from any app and need no Accessibility permission.
enum Hotkey {
    nonisolated(unsafe) static var actions: [UInt32: () -> Void] = [:]
    static func register(_ hud: @escaping () -> Void, pin: @escaping () -> Void) {
        actions = [1: hud, 2: pin]
        var spec = EventTypeSpec(eventClass: OSType(kEventClassKeyboard), eventKind: UInt32(kEventHotKeyPressed))
        InstallEventHandler(GetApplicationEventTarget(), { _, ev, _ in
            var id = EventHotKeyID()
            GetEventParameter(ev, EventParamName(kEventParamDirectObject), EventParamType(typeEventHotKeyID), nil, MemoryLayout<EventHotKeyID>.size, nil, &id)
            Hotkey.actions[id.id]?(); return noErr
        }, 1, &spec, nil, nil)
        for (code, id) in [(kVK_ANSI_H, UInt32(1)), (kVK_ANSI_P, UInt32(2))] {
            var ref: EventHotKeyRef?
            RegisterEventHotKey(UInt32(code), UInt32(controlKey | optionKey), EventHotKeyID(signature: 0x43564552, id: id), GetApplicationEventTarget(), 0, &ref)
        }
    }
}

/// The map and progress in a normal window you can move, resize and leave open next to the game.
@MainActor
enum LiveWindow {
    static var window: NSWindow?
    /// Always on top by default, so the live view stays visible next to whatever is being debugged. Remembered across launches.
    static var pinned: Bool {
        get { UserDefaults.standard.object(forKey: "livePinned") as? Bool ?? true }
        set { UserDefaults.standard.set(newValue, forKey: "livePinned"); window?.level = newValue ? .floating : .normal }
    }
    static func togglePin() { pinned.toggle() }
    static func show(_ poller: StatusPoller) {
        if let w = window { w.makeKeyAndOrderFront(nil); NSApp.activate(ignoringOtherApps: true); return }
        let w = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 760, height: 700),
                         styleMask: [.titled, .closable, .resizable, .miniaturizable], backing: .buffered, defer: false)
        w.title = "Conveyer live"
        w.appearance = NSAppearance(named: .darkAqua)
        w.backgroundColor = NSColor(white: 0.11, alpha: 1)
        w.isReleasedWhenClosed = false
        w.level = pinned ? .floating : .normal
        w.collectionBehavior = [.fullScreenPrimary, .fullScreenAuxiliary]  // without this the green button and toggleFullScreen do nothing
        w.contentView = NSHostingView(rootView: LiveView(poller: poller))
        w.center()
        window = w
        poller.windowVisible = true
        NSApp.setActivationPolicy(.regular)   // dock icon while the live window is open
        NSApp.applicationIconImage = NSImage(contentsOfFile: Bundle.main.path(forResource: "AppIcon", ofType: "icns") ?? "")
        NotificationCenter.default.addObserver(forName: NSWindow.didChangeOcclusionStateNotification, object: w, queue: .main) { _ in
            Task { @MainActor in poller.windowVisible = w.occlusionState.contains(.visible) }
        }
        NotificationCenter.default.addObserver(forName: NSWindow.willCloseNotification, object: w, queue: .main) { _ in
            Task { @MainActor in LiveWindow.window = nil; poller.windowVisible = false; NSApp.setActivationPolicy(.accessory) }
        }
        w.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }
}

/// Live position of the player, read from live.json (written ~5 times a second by scripts/livefeed.py while someone watches).
struct LiveFrame: Decodable { let cx: Double; let cy: Double; let w: Double; let h: Double; let ppt: Double }
struct LivePos: Decodable { let x: Double; let y: Double }

@MainActor
final class MarkerModel: ObservableObject {
    @Published var pos: CGPoint?
    @Published var shown: CGPoint?   // eased toward pos about 60 times a second: the marker and the camera follow this, so neither jumps
    private var ease: Timer?
    @Published var heading: Double = 90   // degrees, 0 = east, 90 = south (screen y grows down)
    @Published var moving = false
    @Published var step = 0
    @Published var frame: LiveFrame?
    @Published var dots: [[Double]] = []   // [x, y, code] per machine, from live_status.json: 0 working, 1 waiting, 2 stuck
    private var dotsStamp: Date?
    private let dotsPath = NSString(string: "~/Documents/Code/conveyer/live_status.json").expandingTildeInPath
    private var timer: Timer?
    private var frameStamp: Date?
    private let livePath = NSString(string: "~/Documents/Code/conveyer/live.json").expandingTildeInPath
    private let framePath = NSString(string: "~/Documents/Code/conveyer/frame.json").expandingTildeInPath

    func start() {
        guard timer == nil else { return }
        read()
        timer = Timer.scheduledTimer(withTimeInterval: 0.2, repeats: true) { _ in Task { @MainActor in self.read() } }
        ease = Timer.scheduledTimer(withTimeInterval: 1.0 / 60, repeats: true) { _ in Task { @MainActor in
            guard let p = self.pos else { return }
            guard let c = self.shown else { self.shown = p; return }
            let dx = p.x - c.x, dy = p.y - c.y
            if abs(dx) < 0.005 && abs(dy) < 0.005 { return }   // arrived: no redraws
            let d = (dx * dx + dy * dy).squareRoot(), k = min(0.12 * d, 1.0) / d   // 12% of the gap per frame, never faster than 60 tiles a second, so even a long trip glides
            self.shown = CGPoint(x: c.x + dx * k, y: c.y + dy * k)
        } }
    }
    func stop() { timer?.invalidate(); timer = nil; ease?.invalidate(); ease = nil }

    private func readDots() {
        guard let m = (try? FileManager.default.attributesOfItem(atPath: dotsPath))?[.modificationDate] as? Date, m != dotsStamp,
              let d = FileManager.default.contents(atPath: dotsPath),
              let j = try? JSONSerialization.jsonObject(with: d) as? [String: Any], let arr = j["d"] as? [[Double]] else { return }
        dotsStamp = m; dots = arr
    }

    private func read() {
        readDots()
        if let m = (try? FileManager.default.attributesOfItem(atPath: framePath))?[.modificationDate] as? Date, m != frameStamp,
           let d = FileManager.default.contents(atPath: framePath), let f = try? JSONDecoder().decode(LiveFrame.self, from: d) {
            frameStamp = m; frame = f
        }
        guard let d = FileManager.default.contents(atPath: livePath), let p = try? JSONDecoder().decode(LivePos.self, from: d) else { return }
        let np = CGPoint(x: p.x, y: p.y)
        guard np != pos else { if moving { moving = false }; return }   // publish only on change: idle costs no redraws
        if let o = pos { heading = atan2(np.y - o.y, np.x - o.x) * 180 / .pi }
        moving = pos != nil
        step += 1
        pos = np
    }
}

/// Machine status dots over the map: green pulses while working, amber waits for items, red is stuck. Drawn from live_status.json, so the view moves even when the map picture is old.
struct StatusDots: View {
    @ObservedObject var m: MarkerModel
    var body: some View {
        GeometryReader { g in
            if let f = m.frame, !m.dots.isEmpty {
                let s = max(g.size.width / f.w, g.size.height / f.h)
                TimelineView(.animation(minimumInterval: 1.0 / 10)) { ctx in
                    let t = ctx.date.timeIntervalSinceReferenceDate
                    Canvas { c, _ in
                        for (i, d) in m.dots.enumerated() where d.count == 3 {
                            let x = (g.size.width - f.w * s) / 2 + (f.w / 2 + (d[0] - f.cx) * f.ppt) * s
                            let y = (g.size.height - f.h * s) / 2 + (f.h / 2 + (d[1] - f.cy) * f.ppt) * s
                            let code = Int(d[2])
                            let pulse = code == 0 ? 0.55 + 0.45 * sin(t * 6 + Double(i)) : 1.0
                            let col: Color = code == 0 ? .green : (code == 1 ? .orange : .red)
                            let r: CGFloat = max(3, (code == 0 ? 4 : 5) * s)
                            c.fill(Path(ellipseIn: CGRect(x: x - r, y: y - r - 14 * s, width: 2 * r, height: 2 * r)), with: .color(col.opacity(pulse)))
                            c.stroke(Path(ellipseIn: CGRect(x: x - r, y: y - r - 14 * s, width: 2 * r, height: 2 * r)), with: .color(.black.opacity(0.6)), lineWidth: 1)
                        }
                    }
                }
            }
        }
        .allowsHitTesting(false)
    }
}

/// An original marker, not a game sprite: a pin with a heading wedge. It glides between position updates.
struct PlayerMarker: View {
    @ObservedObject var m: MarkerModel
    var body: some View {
        GeometryReader { g in
            if let p = m.shown, let f = m.frame {
                // same fill transform as the map image: scale to cover, centered
                let s = max(g.size.width / f.w, g.size.height / f.h)
                let x = (g.size.width - f.w * s) / 2 + (f.w / 2 + (p.x - f.cx) * f.ppt) * s
                let y = (g.size.height - f.h * s) / 2 + (f.h / 2 + (p.y - f.cy) * f.ppt) * s
                ZStack {
                    Circle().fill(Color.accentColor.opacity(m.moving ? 0.28 : 0.14)).frame(width: 30 * s, height: 30 * s)
                    if Engineer.available {
                        EngineerSprite(heading: m.heading, walking: m.moving, scale: s)
                    } else if m.moving {
                        // 12 fps walk cycle, only while he is actually moving; standing still has no timer at all
                        TimelineView(.animation(minimumInterval: 1.0 / 12)) { ctx in
                            HardHatFigure(heading: m.heading, phase: sin(ctx.date.timeIntervalSinceReferenceDate * 11), walking: true)
                        }
                    } else {
                        HardHatFigure(heading: m.heading, phase: 0, walking: false)
                    }
                }
                .position(x: x, y: y)
            }
        }
        .allowsHitTesting(false)
    }
}

/// The real Factorio engineer, cut from the game's own sprite sheets at runtime. build.sh copies them from the installed game into the app bundle
/// (never into git); without them the marker falls back to the hand-drawn hard hat below. 22 frames across, 8 directions down, north first, clockwise.
enum Engineer {
    static let run: CGImage? = load("engineer_running")
    static let idle: CGImage? = load("engineer_idle")
    private static func load(_ name: String) -> CGImage? {
        guard let p = Bundle.main.path(forResource: name, ofType: "png"), let img = NSImage(contentsOfFile: p) else { return nil }
        return img.cgImage(forProposedRect: nil, context: nil, hints: nil)
    }
    static var available: Bool { run != nil && idle != nil }
    /// One frame of the sheet: row by heading (0 = east, 90 = south on screen), column by frame.
    static func frame(_ sheet: CGImage, heading: Double, frame: Int, scale: CGFloat) -> NSImage {
        let cw = sheet.width / 22, ch = sheet.height / 8
        let a = (heading + 90).truncatingRemainder(dividingBy: 360), row = Int(((a < 0 ? a + 360 : a) + 22.5) / 45) % 8
        let rect = CGRect(x: (frame % 22) * cw, y: row * ch, width: cw, height: ch)
        let c = sheet.cropping(to: rect) ?? sheet
        return NSImage(cgImage: c, size: NSSize(width: CGFloat(cw) / 4 * scale, height: CGFloat(ch) / 4 * scale))   // sheets are 2x art for 32 px a tile; the map is 16 px a tile, then scaled to the window
    }
}

struct EngineerSprite: View {
    var heading: Double
    var walking: Bool
    var scale: CGFloat
    var body: some View {
        TimelineView(.animation(minimumInterval: 1.0 / 20)) { ctx in
            let i = walking ? Int(ctx.date.timeIntervalSinceReferenceDate * 22) % 22 : 0
            if let sheet = walking ? Engineer.run : Engineer.idle {
                Image(nsImage: Engineer.frame(sheet, heading: heading, frame: i, scale: scale)).interpolation(.high)
            }
        }
    }
}

/// An original little engineer seen from above: grey armor, a pack on the back, orange helmet with a visor that points the way it walks.
struct HardHatFigure: View {
    var heading: Double   // degrees, 0 = east
    var phase: Double     // -1...1 walk cycle, 0 when standing
    var walking: Bool
    private let glove = Color(red: 0.30, green: 0.31, blue: 0.33)
    var body: some View {
        ZStack {
            Ellipse().fill(Color.black.opacity(0.30)).frame(width: 24, height: 12).offset(y: 3)
            RoundedRectangle(cornerRadius: 2).fill(Color(red: 0.62, green: 0.40, blue: 0.14)).frame(width: 13, height: 9).offset(y: 8)  // pack
            Capsule().fill(Color(red: 0.50, green: 0.53, blue: 0.56)).frame(width: 24, height: 12)                                        // armor
            Capsule().stroke(Color(red: 0.28, green: 0.30, blue: 0.33), lineWidth: 1).frame(width: 24, height: 12)
            Ellipse().fill(Color(red: 0.20, green: 0.21, blue: 0.23)).frame(width: 6, height: 8).offset(x: -5, y: 9 + 4 * phase)         // feet step in turn
            Ellipse().fill(Color(red: 0.20, green: 0.21, blue: 0.23)).frame(width: 6, height: 8).offset(x: 5, y: 9 - 4 * phase)
            Circle().fill(glove).frame(width: 6, height: 6).offset(x: -13, y: -3.5 * phase)                                              // arms swing opposite the feet
            Circle().fill(glove).frame(width: 6, height: 6).offset(x: 13, y: 3.5 * phase)
            Circle().fill(Color(red: 0.96, green: 0.50, blue: 0.10)).frame(width: 14, height: 14)                                         // helmet
            Circle().fill(Color.white.opacity(0.30)).frame(width: 5, height: 5).offset(x: -2, y: 2)
            Capsule().fill(Color(red: 0.20, green: 0.22, blue: 0.25)).frame(width: 9, height: 4).offset(y: -8)                            // visor, points forward
        }
        .rotationEffect(.degrees(heading + 90))   // drawn facing north; north is heading -90
        .scaleEffect(1.0 + (walking ? 0.05 + 0.03 * abs(phase) : 0))   // small bob while walking
    }
}

struct Triangle: Shape {
    func path(in r: CGRect) -> Path {
        var p = Path(); p.move(to: CGPoint(x: r.midX, y: r.minY)); p.addLine(to: CGPoint(x: r.maxX, y: r.maxY)); p.addLine(to: CGPoint(x: r.minX, y: r.maxY)); p.closeSubpath(); return p
    }
}

/// Zooms the map layer and slides it so the player stays in the middle, clamped to the picture's edge. Only this view watches the eased position.
struct CameraRig<Content: View>: View {
    @ObservedObject var m: MarkerModel
    let size: CGSize
    let content: Content
    private let zoom: CGFloat = 1.7
    init(m: MarkerModel, size: CGSize, @ViewBuilder content: () -> Content) { self.m = m; self.size = size; self.content = content() }
    var body: some View {
        let o = offset()
        content.scaleEffect(zoom).offset(x: o.width, y: o.height)
    }
    private func offset() -> CGSize {
        guard let f = m.frame, let p = m.shown else { return .zero }
        let s0 = max(size.width / f.w, size.height / f.h)
        let qx = (p.x - f.cx) * f.ppt * s0, qy = (p.y - f.cy) * f.ppt * s0
        let mx = max(0, zoom * f.w * s0 / 2 - size.width / 2), my = max(0, zoom * f.h * s0 / 2 - size.height / 2)
        return CGSize(width: min(max(-zoom * qx, -mx), mx), height: min(max(-zoom * qy, -my), my))
    }
}

struct LiveView: View {
    @ObservedObject var poller: StatusPoller
    /// The map fills the whole window; the status bar floats on top of it so nothing is letterboxed.
    /// Follow camera: CameraRig re-renders at 60 fps on its own while this view (and the 4 MB map picture) stays still.
    var body: some View {
        GeometryReader { g in
            ZStack {
                Color(white: 0.11)
                CameraRig(m: poller.marker, size: g.size) {
                    ZStack {
                        if let map = poller.map {
                            Image(nsImage: map).resizable().interpolation(.high).scaledToFill().frame(width: g.size.width, height: g.size.height).clipped()
                        } else {
                            Text("Waiting for the first frame").foregroundStyle(.secondary)
                        }
                        StatusDots(m: poller.marker)
                        PlayerMarker(m: poller.marker)
                    }
                }
            }
            .clipped()
            .overlay(alignment: .topLeading) { if poller.hudVisible { hud } }
        }
        .frame(minWidth: 520, minHeight: 420)
        .ignoresSafeArea()
        .environment(\.colorScheme, .dark)
    }

    private var hud: some View {
        VStack(alignment: .leading, spacing: 5) {
            if let r = poller.research, !r.current.isEmpty {
                HStack(spacing: 8) {
                    Text(Research.nice(r.current)).font(.system(size: 14, weight: .semibold))
                    Spacer(minLength: 12)
                    Text("\(r.percent)%").font(.system(size: 14)).monospacedDigit()
                }
                GeometryReader { g in
                    ZStack(alignment: .leading) {
                        Capsule().fill(Color.white.opacity(0.22))
                        Capsule().fill(Color.accentColor).frame(width: g.size.width * CGFloat(min(max(r.percent, 0), 100)) / 100)
                    }
                }
                .frame(height: 5)
                if let labs = r.labs, let working = r.labs_working {
                    let stalled = working == 0 && r.moving != true
                    Text(stalled ? "Labs idle, waiting for packs" : "\(working) of \(labs) labs busy")
                        .font(.system(size: 12)).foregroundStyle(stalled ? Color.orange : Color.white.opacity(0.7))
                }
            }
            if let s = poller.status, s.skill != "?" {
                HStack(spacing: 5) {
                    Circle().fill(s.worked ? Color.green : Color.red).frame(width: 6, height: 6)
                    Text("Player is \(ConveyerMonitorApp.narrate(s.skill))").font(.system(size: 12)).foregroundStyle(.white.opacity(0.7))
                }
            }
        }
        .padding(12)
        .frame(width: 270, alignment: .leading)
        .background(.black.opacity(0.58), in: RoundedRectangle(cornerRadius: 10))
        .padding(12)
    }
}

@main
struct ConveyerMonitorApp: App {
    @StateObject private var poller = StatusPoller()

    /// `ConveyerMonitor --snapshot out.png` renders the popover to a PNG and exits, so the layout
    /// can be checked without opening the menu bar item.
    init() {
        let args = CommandLine.arguments
        guard let i = args.firstIndex(of: "--snapshot"), i + 1 < args.count else { return }
        let demoPoller = StatusPoller()
        if let d = args.firstIndex(of: "--demo"), d + 1 < args.count { demoPoller.applyDemo(args[d + 1]) }
        let live = args.contains("--live")  // --snapshot out.png --live renders the detached window instead of the popover
        let content: AnyView = live
            ? AnyView(LiveView(poller: demoPoller).frame(width: 760, height: 700).background(Color(white: 0.16)).environment(\.colorScheme, .dark))
            : AnyView(Self.popover(demoPoller).background(Color(white: 0.16)).environment(\.colorScheme, .dark))
        let renderer = ImageRenderer(content: content)
        renderer.scale = 2
        if let cg = renderer.cgImage {
            let rep = NSBitmapImageRep(cgImage: cg)
            try? rep.representation(using: .png, properties: [:])?.write(to: URL(fileURLWithPath: args[i + 1]))
        }
        exit(0)
    }

    var body: some Scene {
        MenuBarExtra {
            Self.popover(poller)
        } label: {
            Text(labelText)
                .font(.system(size: 12))
        }
        .menuBarExtraStyle(.window)
    }


    @ViewBuilder
    static func roadmap(_ all: [Milestone]) -> some View {
        let done = all.filter(\.done).count
        let open = all.filter { !$0.done }
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Text("Roadmap").font(.system(size: 12, weight: .semibold))
                Spacer()
                Text("\(open.count) left").font(.system(size: 11)).foregroundStyle(.secondary)
            }
            ForEach(Array(open.prefix(3).enumerated()), id: \.element.id) { i, m in
                HStack(alignment: .top, spacing: 7) {
                    Image(systemName: i == 0 ? "circle.inset.filled" : "circle")
                        .font(.system(size: 11))
                        .foregroundStyle(i == 0 ? Color.accentColor : Color.secondary)
                        .padding(.top, 1)
                    VStack(alignment: .leading, spacing: 1) {
                        Text(m.title)
                            .font(.system(size: 11, weight: i == 0 ? .semibold : .regular))
                            .lineLimit(2)
                            .fixedSize(horizontal: false, vertical: true)
                        if let eta = m.eta {
                            Text(eta).font(.system(size: 10)).foregroundStyle(.secondary)
                        }
                    }
                }
            }
            if open.count > 3 {
                Text("\(open.count - 3) more in roadmap.md").font(.system(size: 10)).foregroundStyle(.tertiary)
            }
        }
    }

    @MainActor
    static func popover(_ poller: StatusPoller) -> some View {
            VStack(alignment: .leading, spacing: 10) {
                if let map = poller.map {
                    Image(nsImage: map)
                        .resizable()
                        .interpolation(.high)
                        .scaledToFill()
                        .frame(width: 316, height: 220)
                        .clipShape(RoundedRectangle(cornerRadius: 6))
                    HStack {
                        Spacer()
                        Button { LiveWindow.show(poller) } label: {
                            Label("Open live view", systemImage: "macwindow.on.rectangle").font(.system(size: 11))
                        }
                    }
                }
                if poller.runnerAlive, let r = poller.research, !r.current.isEmpty {
                    VStack(alignment: .leading, spacing: 3) {
                        HStack {
                            Text("Researching \(Research.nice(r.current).lowercased())")
                                .font(.system(size: 12, weight: .semibold))
                            Spacer()
                            Text("\(r.percent)%").font(.system(size: 12))
                        }
                        GeometryReader { g in
                            ZStack(alignment: .leading) {
                                Capsule().fill(Color.secondary.opacity(0.25))
                                Capsule().fill(Color.accentColor)
                                    .frame(width: g.size.width * CGFloat(min(max(r.percent, 0), 100)) / 100)
                            }
                        }
                        .frame(height: 6)
                        if let labs = r.labs, let working = r.labs_working {
                            let stalled = working == 0 && r.moving != true
                            Label(stalled ? "Labs idle, waiting for science packs" : "Research moving, \(working) of \(labs) labs busy",
                                  systemImage: stalled ? "exclamationmark.circle.fill" : "checkmark.circle.fill")
                                .font(.system(size: 11))
                                .foregroundStyle(stalled ? Color.orange : Color.secondary)
                        }
                        let next = r.queue.dropFirst().first.map { Research.nice($0).lowercased() }
                        Text(next.map { "\(r.techs) techs done. Then \($0)" } ?? "\(r.techs) techs done")
                            .font(.system(size: 11))
                            .foregroundStyle(.secondary)
                    }
                }
                if !poller.milestones.isEmpty {
                    Self.roadmap(poller.milestones)
                }
                if !poller.runnerAlive {
                    Label("Stopped. It restarts on its own while the game is running.", systemImage: "stop.circle.fill")
                        .font(.system(size: 11))
                        .foregroundStyle(.red)
                } else if let s = poller.status, s.skill != "?" {
                    VStack(alignment: .leading, spacing: 3) {
                        HStack(spacing: 5) {
                            Circle().fill(s.worked ? Color.green : Color.red).frame(width: 7, height: 7)
                            Text("Player is \(Self.narrate(s.skill))")
                                .font(.system(size: 12, weight: .semibold))
                            Spacer()
                            if poller.stale {
                                Text("slow step").font(.system(size: 11)).foregroundStyle(.secondary)
                            }
                        }
                        if !s.worked {
                            Text(s.message.split(separator: "\n").map { $0.trimmingCharacters(in: .whitespaces) }.last(where: { !$0.isEmpty }) ?? s.message)
                                .font(.system(size: 11))
                                .foregroundStyle(.red)
                                .lineLimit(2)
                                .fixedSize(horizontal: false, vertical: true)
                        }
                    }
                } else {
                    Text("Starting up")
                        .font(.system(size: 12))
                        .foregroundStyle(.secondary)
                }

                Divider()

                Text("Controls")
                    .font(.system(size: 10, weight: .semibold))
                    .foregroundStyle(.secondary)

                VStack(spacing: 4) {
                    Self.controlButton(poller, "Restart", systemImage: "arrow.clockwise") {
                        poller.run("restart_runner.sh")
                    }
                    Self.controlButton(poller, "Restart game and player", systemImage: "arrow.triangle.2.circlepath") {
                        poller.run("restart_server.sh")
                    }
                    Self.controlButton(poller, "Stop everything", systemImage: "stop.circle") {
                        poller.run("stop_all.sh")
                    }
                }

                if poller.busy {
                    HStack(spacing: 5) {
                        ProgressView().controlSize(.small)
                        Text("Working").font(.system(size: 11)).foregroundStyle(.secondary)
                    }
                }

                Divider()
                Button("Quit") { NSApplication.shared.terminate(nil) }
                    .font(.system(size: 12))
            }
            .padding(12)
            .frame(width: 340)
            .onAppear { poller.popoverShown = true }
            .onDisappear { poller.popoverShown = false }
    }

    private var labelText: String {
        if !poller.runnerAlive { return "stopped" }
        if let r = poller.research, !r.current.isEmpty {
            return "\(Research.nice(r.current)) \(r.percent)%"
        }
        guard let s = poller.status, s.skill != "?" else { return "…" }
        let dot = s.worked ? "●" : "○"
        return "\(dot) \(Self.narrate(s.skill))"
    }

    /// Skill names as they'd be said out loud, matching how progress reads in
    /// chat ("smelting", "building a base") instead of the raw dispatch name.
    static func narrate(_ skill: String) -> String {
        switch skill {
        case "goto": return "walking"
        case "harvest": return "gathering resources"
        case "mine": return "placing drills"
        case "smelt": return "smelting"
        case "craft": return "crafting"
        case "place", "place_at", "place_inserter": return "building"
        case "feed", "collect", "pickup": return "moving items"
        case "auto_feed", "belt": return "automating"
        case "research", "research_progress": return "starting research"
        case "inspect", "peek", "nearby", "dropcheck", "find", "recipe": return "looking around"
        default: return skill
        }
    }

    @ViewBuilder
    private static func controlButton(_ poller: StatusPoller, _ title: String, systemImage: String, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            HStack {
                Image(systemName: systemImage).frame(width: 16)
                Text(title).font(.system(size: 12))
                Spacer()
            }
        }
        .buttonStyle(.plain)
        .disabled(poller.busy)
    }
}

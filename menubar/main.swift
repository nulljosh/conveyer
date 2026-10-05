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
    @Published var hudVisible = true   // the progress panel top left starts visible; Ctrl+Option+H shows or hides it
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
struct MiniMeta: Decodable { let x0: Double; let y0: Double; let w: Double; let h: Double }   // minimap.json: tile coords of the picture's top-left and the span it covers
struct HotbarSlot: Decodable { let name: String; let count: Int }
struct HotbarData: Decodable { let slots: [HotbarSlot] }
struct Event: Decodable { let t: Double; let kind: String; let text: String }
struct EventData: Decodable { let events: [Event] }
struct EngineerData: Decodable { let item: String; let t: Double; let label: String? }
struct CombatData: Decodable { let t: Double; let player: [Double]; let enemies: [[Double]]; let turrets: [[Double]] }  // enemies: [x,y,kind,size], turrets: [x,y,firing]
struct SiloData: Decodable { let x: Double; let y: Double; let parts: Int; let status: String; let launched: Int; let t: Double; let rocket: Int?; let rocket_status: String? }

/// The eased position, alone in its own object: it changes 60 times a second while the engineer walks, and only the camera, the marker and the minimap need it.
/// Every view that observed MarkerModel for it used to redraw at that rate (the hotbar decoding icons, the feed, the dots).
@MainActor
final class Glide: ObservableObject {
    @Published var shown: CGPoint?
}

@MainActor
final class MarkerModel: ObservableObject {
    @Published var pos: CGPoint?
    let glide = Glide()
    var shown: CGPoint? { get { glide.shown } set { glide.shown = newValue } }   // eased toward pos about 60 times a second: the marker and the camera follow this, so neither jumps
    private var ease: Timer?
    @Published var heading: Double = 90   // degrees, 0 = east, 90 = south (screen y grows down)
    @Published var moving = false
    @Published var step = 0
    @Published var frame: LiveFrame?
    @Published var dots: [[Double]] = []   // [x, y, code] per machine, from live_status.json: 0 working, 1 waiting, 2 stuck
    @Published var mini: NSImage?
    @Published var miniMeta: MiniMeta?
    @Published var hotbar: [HotbarSlot] = []
    @Published var events: [Event] = []
    @Published var engineer: EngineerData?
    @Published var combat: CombatData?
    @Published var silo: SiloData?
    private var miniStamp: Date?
    private let miniPath = NSString(string: "~/Documents/Code/conveyer/minimap.png").expandingTildeInPath
    private let miniMetaPath = NSString(string: "~/Documents/Code/conveyer/minimap.json").expandingTildeInPath
    private var dotsStamp: Date?
    private let dotsPath = NSString(string: "~/Documents/Code/conveyer/live_status.json").expandingTildeInPath
    private var timer: Timer?
    private var pollEvery = 0.2
    private var streamSource: DispatchSourceFileSystemObject?
    private let streamPath = NSString(string: "~/Documents/Code/conveyer/stream.json").expandingTildeInPath
    private var frameStamp: Date?
    private let livePath = NSString(string: "~/Documents/Code/conveyer/live.json").expandingTildeInPath
    private let framePath = NSString(string: "~/Documents/Code/conveyer/frame.json").expandingTildeInPath
    private var hotbarStamp: Date?
    private let hotbarPath = NSString(string: "~/Documents/Code/conveyer/hotbar.json").expandingTildeInPath
    private var eventsStamp: Date?
    private let eventsPath = NSString(string: "~/Documents/Code/conveyer/events.json").expandingTildeInPath
    private var engineerStamp: Date?
    private let engineerPath = NSString(string: "~/Documents/Code/conveyer/engineer.json").expandingTildeInPath
    private var combatStamp: Date?
    private let combatPath = NSString(string: "~/Documents/Code/conveyer/combat.json").expandingTildeInPath
    private var siloStamp: Date?
    private let siloPath = NSString(string: "~/Documents/Code/conveyer/silo.json").expandingTildeInPath

    func start() {
        guard timer == nil else { return }
        read()
        schedulePoll(0.2)
        watchStream()
    }
    func stop() { timer?.invalidate(); timer = nil; ease?.invalidate(); ease = nil; streamSource?.cancel(); streamSource = nil }

    private func schedulePoll(_ every: Double) {
        timer?.invalidate(); pollEvery = every
        timer = Timer.scheduledTimer(withTimeInterval: every, repeats: true) { _ in Task { @MainActor in self.read() } }
    }

    /// stream.py replaces stream.json atomically (rename), so the watch fires on every frame and is re-opened after each one.
    /// While stream.json is fresh the 0.2 s poll slows to 1 s and only covers the files stream.py does not write; without stream.py it stays at 0.2 s.
    private func watchStream() {
        streamSource?.cancel(); streamSource = nil
        let fd = open(streamPath, O_EVTONLY)
        guard fd >= 0 else { return }
        let src = DispatchSource.makeFileSystemObjectSource(fileDescriptor: fd, eventMask: [.write, .delete, .rename], queue: .main)
        src.setEventHandler { [weak self] in
            guard let self else { return }
            MainActor.assumeIsolated { self.read(); self.watchStream() }
        }
        src.setCancelHandler { close(fd) }
        streamSource = src; src.resume()
    }

    /// Glide the marker toward pos at 60 Hz, but only while it is not there yet.
    private func startEase() {
        guard ease == nil else { return }
        ease = Timer.scheduledTimer(withTimeInterval: 1.0 / 60, repeats: true) { _ in Task { @MainActor in
            guard let p = self.pos else { return }
            guard let c = self.shown else { self.shown = p; return }
            let dx = p.x - c.x, dy = p.y - c.y
            if abs(dx) < 0.005 && abs(dy) < 0.005 { self.ease?.invalidate(); self.ease = nil; return }   // arrived: the timer stops until the next move
            let d = (dx * dx + dy * dy).squareRoot(), k = min(0.12 * d, 1.0) / d   // 12% of the gap per frame, never faster than 60 tiles a second, so even a long trip glides
            self.shown = CGPoint(x: c.x + dx * k, y: c.y + dy * k)
        } }
    }

    private func readDots() {
        guard let m = (try? FileManager.default.attributesOfItem(atPath: dotsPath))?[.modificationDate] as? Date, m != dotsStamp,
              let d = FileManager.default.contents(atPath: dotsPath),
              let j = try? JSONSerialization.jsonObject(with: d) as? [String: Any], let arr = j["d"] as? [[Double]] else { return }
        dotsStamp = m; dots = arr
    }

    private func readMini() {
        let mod = (try? FileManager.default.attributesOfItem(atPath: miniMetaPath))?[.modificationDate] as? Date
        guard let m = mod, m != miniStamp else { return }
        let data = FileManager.default.contents(atPath: miniMetaPath)
        let meta = data.flatMap { try? JSONDecoder().decode(MiniMeta.self, from: $0) }
        let img = NSImage(contentsOfFile: miniPath)
        guard let meta, let img else { return }
        miniStamp = m; miniMeta = meta; mini = img
    }

    private func readHotbar() {
        guard let m = (try? FileManager.default.attributesOfItem(atPath: hotbarPath))?[.modificationDate] as? Date, m != hotbarStamp,
              let d = FileManager.default.contents(atPath: hotbarPath),
              let h = try? JSONDecoder().decode(HotbarData.self, from: d) else { return }
        hotbarStamp = m; hotbar = h.slots
    }

    private func readEvents() {
        guard let m = (try? FileManager.default.attributesOfItem(atPath: eventsPath))?[.modificationDate] as? Date, m != eventsStamp,
              let d = FileManager.default.contents(atPath: eventsPath),
              let e = try? JSONDecoder().decode(EventData.self, from: d) else { return }
        eventsStamp = m; events = e.events
    }

    private func readEngineer() {
        guard let m = (try? FileManager.default.attributesOfItem(atPath: engineerPath))?[.modificationDate] as? Date, m != engineerStamp,
              let d = FileManager.default.contents(atPath: engineerPath),
              let eng = try? JSONDecoder().decode(EngineerData.self, from: d) else { return }
        engineerStamp = m; engineer = eng
    }

    private func readCombat() {
        guard let m = (try? FileManager.default.attributesOfItem(atPath: combatPath))?[.modificationDate] as? Date, m != combatStamp,
              let d = FileManager.default.contents(atPath: combatPath),
              let c = try? JSONDecoder().decode(CombatData.self, from: d) else { return }
        let now = Date().timeIntervalSince1970
        guard now - c.t < 4 else { combat = nil; return }   // stale data: ignore
        combatStamp = m; combat = c
    }

    private func readSilo() {
        guard let m = (try? FileManager.default.attributesOfItem(atPath: siloPath))?[.modificationDate] as? Date, m != siloStamp,
              let d = FileManager.default.contents(atPath: siloPath),
              let s = try? JSONDecoder().decode(SiloData.self, from: d) else { return }
        let now = Date().timeIntervalSince1970
        guard now - s.t < 10 else { silo = nil; return }   // stale data: ignore
        siloStamp = m; silo = s
    }

    private func read() {
        let fresh = ((try? FileManager.default.attributesOfItem(atPath: streamPath))?[.modificationDate] as? Date).map { -$0.timeIntervalSinceNow < 2 } ?? false
        if timer != nil && fresh != (pollEvery > 0.5) { schedulePoll(fresh ? 1.0 : 0.2) }
        readDots()
        readMini()
        readHotbar()
        readEvents()
        readEngineer()
        readCombat()
        readSilo()
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
        startEase()
    }
}

/// Rocket silo: pad, launch pad, rocket, exhaust, progress, launch animation.
struct SiloLayer: View {
    @ObservedObject var m: MarkerModel
    @State private var launchStartTime: Double?

    static let siloClosedImg: NSImage? = {
        let path = NSString(string: "~/Documents/Code/conveyer/assets/silo/silo_closed.png").expandingTildeInPath
        return NSImage(contentsOfFile: path)
    }()

    static let siloOpenBackImg: NSImage? = {
        let path = NSString(string: "~/Documents/Code/conveyer/assets/silo/silo_open_back.png").expandingTildeInPath
        return NSImage(contentsOfFile: path)
    }()

    static let siloOpenFrontImg: NSImage? = {
        let path = NSString(string: "~/Documents/Code/conveyer/assets/silo/silo_open_front.png").expandingTildeInPath
        return NSImage(contentsOfFile: path)
    }()

    static let rocketImg: NSImage? = {
        let path = NSString(string: "~/Documents/Code/conveyer/assets/silo/rocket.png").expandingTildeInPath
        return NSImage(contentsOfFile: path)
    }()

    var body: some View {
        GeometryReader { g in
            if let f = m.frame, let silo = m.silo {
                let s = max(g.size.width / f.w, g.size.height / f.h)
                let cx = (g.size.width - f.w * s) / 2 + (f.w / 2 + (silo.x - f.cx) * f.ppt) * s
                let cy = (g.size.height - f.h * s) / 2 + (f.h / 2 + (silo.y - f.cy) * f.ppt) * s
                let tileSize = f.ppt * s
                let isLaunching = silo.status == "preparing_rocket_for_launch" || silo.status == "launching_rocket"

                ZStack {
                    let hasRocket = (silo.rocket ?? 0) == 1 || isLaunching

                    if !hasRocket {
                        if let img = SiloLayer.siloClosedImg {
                            Image(nsImage: img)
                                .interpolation(.high)
                                .frame(width: 22 * tileSize, height: 22 * tileSize)
                                .position(x: cx, y: cy)
                        }
                    } else {
                        if let img = SiloLayer.siloOpenBackImg {
                            Image(nsImage: img)
                                .interpolation(.high)
                                .frame(width: 22 * tileSize, height: 22 * tileSize)
                                .position(x: cx, y: cy)
                        }

                        if SiloLayer.rocketImg != nil {
                            if isLaunching {
                                TimelineView(.animation(minimumInterval: 1.0 / 30)) { ctx in
                                    RocketImageView(cx: cx, cy: cy, tileSize: tileSize, t: ctx.date.timeIntervalSinceReferenceDate, launchStart: launchStartTime ?? ctx.date.timeIntervalSinceReferenceDate)
                                }
                            } else {
                                RocketImageView(cx: cx, cy: cy, tileSize: tileSize, t: 0, launchStart: 0)
                            }
                        }

                        if let img = SiloLayer.siloOpenFrontImg {
                            Image(nsImage: img)
                                .interpolation(.high)
                                .frame(width: 22 * tileSize, height: 22 * tileSize)
                                .position(x: cx, y: cy)
                        }
                    }

                    if isLaunching {
                        TimelineView(.animation(minimumInterval: 1.0 / 30)) { ctx in
                            Canvas { canvas, _ in
                                drawAnimationEffects(cx: cx, cy: cy, tileSize: tileSize, silo: silo, t: ctx.date.timeIntervalSinceReferenceDate, launchStart: launchStartTime ?? ctx.date.timeIntervalSinceReferenceDate, canvas: canvas)
                            }
                        }
                        .onAppear {
                            if launchStartTime == nil {
                                launchStartTime = Date().timeIntervalSinceReferenceDate
                            }
                        }
                    } else {
                        Canvas { canvas, _ in
                            drawAnimationEffects(cx: cx, cy: cy, tileSize: tileSize, silo: silo, t: 0, launchStart: 0, canvas: canvas)
                        }
                    }

                    if (silo.rocket ?? 0) != 1 && silo.parts < 100 {
                        ProgressBarView(cx: cx, cy: cy, tileSize: tileSize, silo: silo)
                    }
                }
            }
        }
        .allowsHitTesting(false)
    }

    private func drawAnimationEffects(cx: CGFloat, cy: CGFloat, tileSize: CGFloat, silo: SiloData, t: Double, launchStart: Double, canvas: GraphicsContext) {
        let isLaunching = silo.status == "preparing_rocket_for_launch" || silo.status == "launching_rocket"
        guard isLaunching else { return }

        let elapsedTime = t - launchStart
        let riseProgress = min(elapsedTime / 12.0, 1.0)
        let easeProgress = riseProgress * riseProgress * (3 - 2 * riseProgress)
        let yOffset = easeProgress * 45.0 * tileSize

        // Flame teardrop under rocket
        let flameH = 3.0 * tileSize
        let flickerPhase = sin(t * 3.0 * .pi) * 0.5 + 0.5
        canvas.fill(Path { p in
            p.move(to: CGPoint(x: cx, y: cy + 0.5 * tileSize))
            p.addCurve(to: CGPoint(x: cx, y: cy + 0.5 * tileSize + flameH * flickerPhase),
                       control1: CGPoint(x: cx - 0.6 * tileSize * flickerPhase, y: cy + 0.3 * tileSize),
                       control2: CGPoint(x: cx - 0.5 * tileSize * flickerPhase, y: cy + 0.5 * tileSize + flameH * flickerPhase * 0.8))
            p.addCurve(to: CGPoint(x: cx, y: cy + 0.5 * tileSize),
                       control1: CGPoint(x: cx + 0.5 * tileSize * flickerPhase, y: cy + 0.5 * tileSize + flameH * flickerPhase * 0.8),
                       control2: CGPoint(x: cx + 0.6 * tileSize * flickerPhase, y: cy + 0.3 * tileSize))
        }, with: .color(Color(red: 1.0, green: 0.85, blue: 0.3).opacity(0.6)))

        // Smoke puffs
        for i in 0..<8 {
            let angle = Double(i) * 2.0 * .pi / 8.0
            let phaseShift = Double(i) / 8.0
            let smokeProg = (elapsedTime - phaseShift * 2.0).truncatingRemainder(dividingBy: 2.0) / 2.0
            guard smokeProg >= 0 else { continue }
            let smokeSize = 0.8 * tileSize * (1.0 - smokeProg)
            let smokeDist = smokeProg * 4.0 * tileSize
            let sx = cx + cos(angle) * smokeDist
            let sy = cy + 0.5 * tileSize + sin(angle) * smokeDist
            canvas.fill(Path(ellipseIn: CGRect(x: sx - smokeSize / 2, y: sy - smokeSize / 2, width: smokeSize, height: smokeSize)), with: .color(Color(red: 0.5, green: 0.5, blue: 0.5).opacity(0.4 * (1.0 - smokeProg))))
        }

        // Glow on pad
        let glowR = (5.0 + 6.0 * sin(t * 2.0 * .pi)) * tileSize
        canvas.fill(Path(ellipseIn: CGRect(x: cx - glowR, y: cy - glowR, width: glowR * 2, height: glowR * 2)), with: .color(Color(red: 1.0, green: 0.9, blue: 0.5).opacity(0.2)))

        // Flash ring (once at ignition)
        if elapsedTime < 0.3 {
            let flashR = 15.0 * tileSize * (elapsedTime / 0.3)
            canvas.stroke(Path(ellipseIn: CGRect(x: cx - flashR, y: cy - flashR, width: flashR * 2, height: flashR * 2)), with: .color(.white.opacity(0.4)), lineWidth: 2)
        }
    }
}

struct RocketImageView: View {
    let cx: CGFloat
    let cy: CGFloat
    let tileSize: CGFloat
    let t: Double
    let launchStart: Double

    var body: some View {
        let elapsedTime = t - launchStart
        let riseProgress = min(elapsedTime / 12.0, 1.0)
        let easeProgress = riseProgress * riseProgress * (3 - 2 * riseProgress)
        let yOffset = easeProgress * 45.0 * tileSize
        let rocketTilesAbove = yOffset / tileSize
        let opacity = rocketTilesAbove > 30 ? max(0, 1.0 - (rocketTilesAbove - 30) / 15.0) : 1.0

        if let img = SiloLayer.rocketImg {
            Image(nsImage: img)
                .interpolation(.high)
                .frame(width: 4.8125 * tileSize, height: 11.75 * tileSize)
                .position(x: cx, y: cy - 2.03 * tileSize - yOffset)
                .opacity(opacity)
        }
    }
}

struct ProgressBarView: View {
    let cx: CGFloat
    let cy: CGFloat
    let tileSize: CGFloat
    let silo: SiloData

    var body: some View {
        Canvas { canvas, _ in
            let orange95 = Color(red: 0.95, green: 0.72, blue: 0.10)
            let barW = 4.0 * tileSize
            let barH = 0.5 * tileSize
            let barX = cx - barW / 2
            let barY = cy + 5.0 * tileSize
            canvas.fill(Path(roundedRect: CGRect(x: barX, y: barY, width: barW, height: barH), cornerRadius: barH / 2), with: .color(Color.white.opacity(0.2)))
            let fillW = barW * CGFloat(min(max(silo.parts, 0), 100)) / 100.0
            canvas.fill(Path(roundedRect: CGRect(x: barX, y: barY, width: fillW, height: barH), cornerRadius: barH / 2), with: .color(orange95))
        }
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
    @ObservedObject var glide: Glide
    init(m: MarkerModel) { self.m = m; glide = m.glide }
    var body: some View {
        GeometryReader { g in
            if let p = m.shown, let f = m.frame {
                // same fill transform as the map image: scale to cover, centered
                let s = max(g.size.width / f.w, g.size.height / f.h)
                let x = (g.size.width - f.w * s) / 2 + (f.w / 2 + (p.x - f.cx) * f.ppt) * s
                let y = (g.size.height - f.h * s) / 2 + (f.h / 2 + (p.y - f.cy) * f.ppt) * s
                ZStack {
                    Circle().fill(Color.accentColor.opacity(m.moving ? 0.28 : 0.14)).frame(width: 30 * s, height: 30 * s)
                    if m.moving {
                        TimelineView(.animation(minimumInterval: 1.0 / 20)) { ctx in
                            let scale = 1.0 + 0.25 * sin(ctx.date.timeIntervalSinceReferenceDate * 4)
                            Circle().stroke(Color.accentColor.opacity(0.9), lineWidth: 2).frame(width: 34 * s, height: 34 * s)
                                .scaleEffect(scale)
                        }
                    } else {
                        Circle().stroke(Color.accentColor.opacity(0.9), lineWidth: 2).frame(width: 34 * s, height: 34 * s)
                    }
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

/// Combat overlay: enemies, turrets, and firing arcs on the live map
struct CombatLayer: View {
    @ObservedObject var m: MarkerModel
    var body: some View {
        GeometryReader { g in
            if let f = m.frame, let c = m.combat, !c.enemies.isEmpty || !c.turrets.isEmpty {
                let s = max(g.size.width / f.w, g.size.height / f.h)
                TimelineView(.animation(minimumInterval: 1.0 / 15)) { ctx in
                    let t = ctx.date.timeIntervalSinceReferenceDate
                    Canvas { canvas, _ in
                        // Draw enemies: [x,y,kind,size]
                        for (i, enemy) in c.enemies.enumerated() where enemy.count >= 4 {
                            let ex = (g.size.width - f.w * s) / 2 + (f.w / 2 + (enemy[0] - f.cx) * f.ppt) * s
                            let ey = (g.size.height - f.h * s) / 2 + (f.h / 2 + (enemy[1] - f.cy) * f.ppt) * s
                            let dx = ex - (g.size.width / 2)
                            let dy = ey - (g.size.height / 2)
                            guard abs(dx) < g.size.width && abs(dy) < g.size.height else { continue }
                            let kind = Int(enemy[2])
                            let size = Int(enemy[3])
                            let sizeRadius: CGFloat = [0.8, 1.1, 1.5, 2.0][min(size, 3)] * f.ppt * s
                            if kind == 2 { // worm: triangle
                                var tri = Path()
                                tri.move(to: CGPoint(x: ex, y: ey - sizeRadius))
                                tri.addLine(to: CGPoint(x: ex + sizeRadius, y: ey + sizeRadius))
                                tri.addLine(to: CGPoint(x: ex - sizeRadius, y: ey + sizeRadius))
                                tri.closeSubpath()
                                canvas.fill(tri, with: .color(Color(red: 0.6, green: 0, blue: 0)))
                                canvas.stroke(tri, with: .color(.black.opacity(0.6)), lineWidth: 1)
                            } else if kind == 3 { // nest: rounded square
                                let rectSize = 3.0 * f.ppt * s
                                let rect = CGRect(x: ex - rectSize / 2, y: ey - rectSize / 2, width: rectSize, height: rectSize)
                                canvas.fill(Path(roundedRect: rect, cornerRadius: rectSize * 0.2), with: .color(Color(red: 0.6, green: 0, blue: 0)))
                                canvas.stroke(Path(roundedRect: rect, cornerRadius: rectSize * 0.2), with: .color(Color(red: 0.8, green: 0.2, blue: 0.2).opacity(0.7)), lineWidth: 1)
                            } else {
                                // biter or spitter: circle
                                let col = kind == 0 ? Color.red : Color(red: 1, green: 0.6, blue: 0)
                                let jiggle = sin(t * 5 + Double(i) * 0.5) * 1.5 * s
                                let jiggledX = ex + jiggle
                                let jiggledY = ey + jiggle * 0.5
                                canvas.fill(Path(ellipseIn: CGRect(x: jiggledX - sizeRadius, y: jiggledY - sizeRadius, width: 2 * sizeRadius, height: 2 * sizeRadius)), with: .color(col))
                                canvas.stroke(Path(ellipseIn: CGRect(x: jiggledX - sizeRadius, y: jiggledY - sizeRadius, width: 2 * sizeRadius, height: 2 * sizeRadius)), with: .color(.black.opacity(0.6)), lineWidth: 1)
                            }
                        }
                        // Draw firing turrets: [x,y,firing]
                        for turret in c.turrets where turret.count >= 3 && Int(turret[2]) != 0 {
                            let tx = (g.size.width - f.w * s) / 2 + (f.w / 2 + (turret[0] - f.cx) * f.ppt) * s
                            let ty = (g.size.height - f.h * s) / 2 + (f.h / 2 + (turret[1] - f.cy) * f.ppt) * s
                            let tdx = tx - (g.size.width / 2)
                            let tdy = ty - (g.size.height / 2)
                            guard abs(tdx) < g.size.width && abs(tdy) < g.size.height else { continue }
                            let pulseRadius = (1.2 + sin(t * 4) * 0.5) * f.ppt * s
                            canvas.fill(Path(ellipseIn: CGRect(x: tx - pulseRadius, y: ty - pulseRadius, width: 2 * pulseRadius, height: 2 * pulseRadius)), with: .color(Color(red: 1, green: 1, blue: 0.7)))
                            let nearestEnemy = c.enemies.filter { $0.count >= 2 }.min { e1, e2 in
                                let d1 = (e1[0] - turret[0]) * (e1[0] - turret[0]) + (e1[1] - turret[1]) * (e1[1] - turret[1])
                                let d2 = (e2[0] - turret[0]) * (e2[0] - turret[0]) + (e2[1] - turret[1]) * (e2[1] - turret[1])
                                return d1 < d2
                            }
                            if let nearest = nearestEnemy, nearest.count >= 2 {
                                let distSq = (nearest[0] - turret[0]) * (nearest[0] - turret[0]) + (nearest[1] - turret[1]) * (nearest[1] - turret[1])
                                if distSq < 484 { // 22 tiles
                                    let ex = (g.size.width - f.w * s) / 2 + (f.w / 2 + (nearest[0] - f.cx) * f.ppt) * s
                                    let ey = (g.size.height - f.h * s) / 2 + (f.h / 2 + (nearest[1] - f.cy) * f.ppt) * s
                                    var line = Path()
                                    line.move(to: CGPoint(x: tx, y: ty))
                                    line.addLine(to: CGPoint(x: ex, y: ey))
                                    canvas.stroke(line, with: .color(Color(red: 1, green: 1, blue: 0).opacity(0.9)), lineWidth: 1.5)
                                }
                            }
                        }
                    }
                }
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
    @ObservedObject var glide: Glide
    let size: CGSize
    let content: Content
    private let zoom: CGFloat = {   // --zoom N on the command line, 1.7 by default; 1.0 is pixel-for-pixel on a 1080p screen, which is what the landing video uses
        let a = CommandLine.arguments
        if let i = a.firstIndex(of: "--zoom"), i + 1 < a.count, let z = Double(a[i + 1]) { return CGFloat(z) }
        return 1.7
    }()
    init(m: MarkerModel, size: CGSize, @ViewBuilder content: () -> Content) { self.m = m; glide = m.glide; self.size = size; self.content = content() }
    var body: some View {
        let o = offset()
        content.scaleEffect(zoom).offset(x: o.width, y: o.height)
    }
    private func offset() -> CGSize {
        guard let f = m.frame, let p = m.shown else { return .zero }
        let s0 = max(size.width / f.w, size.height / f.h)
        let qx = (p.x - f.cx) * f.ppt * s0, qy = (p.y - f.cy) * f.ppt * s0
        // Center on the player, but never slide the picture past its own edge: the picture always covers the window, so there is never a dark bar.
        // When the player walks outside the picture (it re-renders on change or every 60 s) he leaves the view until the next frame re-centers it.
        let mx = max(0, zoom * f.w * s0 / 2 - size.width / 2), my = max(0, zoom * f.h * s0 / 2 - size.height / 2)
        let ox = min(max(-zoom * qx, -mx), mx), oy = min(max(-zoom * qy, -my), my)
        let res = CGSize(width: ox, height: oy)
        if ProcessInfo.processInfo.environment["CV_DEBUG"] != nil {   // QA aid: one line per frame to /tmp/cv_cam.log, then read it back
            let hw = zoom * f.w * s0 / 2, hh = zoom * f.h * s0 / 2
            let gapL = res.width - hw + size.width / 2, gapR = size.width / 2 - (res.width + hw), gapT = res.height - hh + size.height / 2, gapB = size.height / 2 - (res.height + hh)
            let line = String(format: "%.2f p=(%.1f,%.1f) frame=(%.1f,%.1f) screenPlayer=(%.0f,%.0f) win=(%.0f,%.0f) blackMargins L%.0f R%.0f T%.0f B%.0f\n", Date().timeIntervalSince1970, p.x, p.y, f.cx, f.cy, zoom * qx + res.width, zoom * qy + res.height, size.width, size.height, max(0, gapL), max(0, gapR), max(0, gapT), max(0, gapB))
            if let h = FileHandle(forWritingAtPath: "/tmp/cv_cam.log") ?? { FileManager.default.createFile(atPath: "/tmp/cv_cam.log", contents: nil); return FileHandle(forWritingAtPath: "/tmp/cv_cam.log") }() { h.seekToEndOfFile(); h.write(line.data(using: .utf8)!); try? h.close() }
        }
        return res
    }
}

/// Whole-base overview in the corner: base (light), oil (orange), enemy nests (red), and a dot where the player stands right now.
struct MiniMap: View {
    @ObservedObject var m: MarkerModel
    @ObservedObject var glide: Glide
    let win: CGSize   // the live window's size: the minimap is about a fifth of its width, never more than 40% of its height
    init(m: MarkerModel, win: CGSize) { self.m = m; glide = m.glide; self.win = win }
    var body: some View {
        if let img = m.mini, let meta = m.miniMeta {
            let aspect = img.size.height / max(img.size.width, 1)
            let w = min(max(win.width * 0.2, 110), 480, win.height * 0.4 / max(aspect, 0.1)), h = w * aspect
            let dot = max(6, w * 0.055)
            ZStack(alignment: .topLeading) {
                Image(nsImage: img).resizable().interpolation(.none).frame(width: w, height: h)
                if let p = m.shown {
                    let x = (p.x - meta.x0) / meta.w * w, y = (p.y - meta.y0) / meta.h * h
                    Circle().fill(Color.accentColor).overlay(Circle().stroke(Color.white, lineWidth: 1.5)).frame(width: dot, height: dot)
                        .offset(x: min(max(x, 0), w) - dot / 2, y: min(max(y, 0), h) - dot / 2)
                }
            }
            .frame(width: w, height: h)
            .clipShape(RoundedRectangle(cornerRadius: 8))
            .overlay(RoundedRectangle(cornerRadius: 8).stroke(Color.white.opacity(0.25), lineWidth: 1))
            .shadow(radius: 6, y: 2)
            .padding(max(8, w * 0.07))
            .allowsHitTesting(false)
        }
    }
}

/// Activity feed: recent events (last 40s) shown as small pills with color-coded status dots.
struct Feed: View {
    @ObservedObject var m: MarkerModel
    let win: CGSize
    var body: some View {
        TimelineView(.periodic(from: .now, by: 1)) { _ in
            if !m.events.isEmpty {
                let now = Date().timeIntervalSince1970
                let filtered = m.events.filter { now - $0.t < 40 }
                if !filtered.isEmpty {
                    let u = min(max(min(win.width / 900, win.height / 800), 0.7), 2.0)   // same window scale as the HUD
                    let maxWidth = win.width * 0.28
                    let hotbarHeight = min(max(win.width * 0.045, 28), 64)
                    VStack(alignment: .leading, spacing: 4 * u) {
                        ForEach(Array(filtered.enumerated()), id: \.offset) { i, event in
                            let age = now - event.t
                            let isFading = age > 30
                            let fadeAlpha = isFading ? max(0, 1.0 - (age - 30) / 10.0) : 1.0
                            let color: Color = event.kind == "ok" ? .green : (event.kind == "warn" ? .orange : .red)
                            HStack(spacing: 6 * u) {
                                Circle().fill(color).frame(width: 8 * u, height: 8 * u)
                                Text(event.text)
                                    .font(.system(size: 12 * u, weight: .semibold))
                                    .foregroundStyle(.white)
                                    .lineLimit(1)
                            }
                            .padding(.horizontal, 8 * u)
                            .padding(.vertical, 5 * u)
                            .background(.black.opacity(0.6), in: RoundedRectangle(cornerRadius: 8 * u))
                            .opacity(fadeAlpha)
                        }
                    }
                    .frame(maxWidth: maxWidth, alignment: .trailing)
                    .padding(8)
                    .padding(.bottom, hotbarHeight + 4)
                    .allowsHitTesting(false)
                }
            }
        }
    }
}

/// Game-style hotbar: 10 inventory slots showing the player's most abundant items.
struct Hotbar: View {
    @ObservedObject var m: MarkerModel
    let win: CGSize
    var body: some View {
        if !m.hotbar.isEmpty {
            let slotSize = min(max(win.width * 0.045, 28), 64)
            let totalWidth = min(slotSize * CGFloat(m.hotbar.count), win.width * 0.55)
            HStack(spacing: slotSize * 0.05) {
                ForEach(0..<10, id: \.self) { i in
                    ZStack(alignment: .bottomTrailing) {
                        RoundedRectangle(cornerRadius: 3).fill(Color(white: 0.18))
                            .overlay(RoundedRectangle(cornerRadius: 3).stroke(Color(white: 0.28), lineWidth: 1))
                        if i < m.hotbar.count {
                            let slot = m.hotbar[i]
                            VStack(spacing: 0) {
                                if let icon = loadIcon(slot.name, size: slotSize * 0.8) {
                                    Image(nsImage: icon).resizable().scaledToFit()
                                        .frame(width: slotSize * 0.8, height: slotSize * 0.8)
                                } else {
                                    Text(String(slot.name.prefix(2))).font(.system(size: slotSize * 0.3, weight: .bold)).foregroundStyle(.white.opacity(0.5))
                                }
                            }
                            Text("\(slot.count)").font(.system(size: slotSize * 0.25, weight: .semibold)).foregroundStyle(.white)
                                .shadow(radius: 1).padding(2)
                        }
                    }
                    .frame(width: slotSize, height: slotSize)
                }
            }
            .frame(width: totalWidth)
            .padding(8)
            .allowsHitTesting(false)
        }
    }

    /// The hotbar redraws whenever the marker model publishes (60 times a second while the engineer walks), so a PNG decode per slot per redraw cost about 20% of a core. Decode each icon once.
    private static var iconCache: [String: NSImage?] = [:]
    private func loadIcon(_ itemName: String, size: CGFloat) -> NSImage? {
        if let hit = Self.iconCache[itemName] { return hit }
        let img = decodeIcon(itemName)
        Self.iconCache[itemName] = .some(img)
        return img
    }

    private func decodeIcon(_ itemName: String) -> NSImage? {
        if let bundlePath = Bundle.main.path(forResource: itemName, ofType: "png", inDirectory: "icons"),
           let img = NSImage(contentsOfFile: bundlePath) { return img }
        let steamPath = NSString(string: "~/Library/Application Support/Steam/steamapps/common/Factorio/factorio.app/Contents/data/base/graphics/icons/\(itemName).png").expandingTildeInPath
        guard FileManager.default.fileExists(atPath: steamPath) else { return nil }
        return NSImage(contentsOfFile: steamPath)
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
                            // The layer is the whole picture at cover scale, not a window-sized crop of it: CameraRig's edge clamp assumes exactly this size.
                            let f = poller.marker.frame
                            let s0 = f.map { max(g.size.width / $0.w, g.size.height / $0.h) } ?? 1
                            Image(nsImage: map).resizable().interpolation(.high)
                                .frame(width: (f?.w ?? g.size.width) * s0, height: (f?.h ?? g.size.height) * s0)
                        } else {
                            Text("Waiting for the first frame").foregroundStyle(.secondary)
                        }
                        SiloLayer(m: poller.marker)
                        StatusDots(m: poller.marker)
                        PlayerMarker(m: poller.marker)
                        CombatLayer(m: poller.marker)
                    }
                }
            }
            .frame(width: g.size.width, height: g.size.height)   // the map layer is bigger than the window; without this the corner overlays anchor off-window
            .clipped()
            .overlay(alignment: .topLeading) { if poller.hudVisible { hud.scaleEffect(min(max(min(g.size.width / 900, g.size.height / 800), 0.7), 2.2), anchor: .topLeading) } }   // HUD grows and shrinks with the window
            .overlay(alignment: .bottom) { Hotbar(m: poller.marker, win: g.size) }
            .overlay(alignment: .bottomLeading) { Feed(m: poller.marker, win: g.size) }
            .overlay(alignment: .bottomTrailing) { MiniMap(m: poller.marker, win: g.size) }
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
            TimelineView(.periodic(from: .now, by: 1)) { _ in   // the marker model is a separate object the HUD does not observe, so re-read it every second
                if let eng = poller.marker.engineer, !eng.item.isEmpty, Date().timeIntervalSince1970 - eng.t < 20 {
                    let label = eng.label.flatMap { s in s.isEmpty ? nil : s }
                    if let label = label {
                        Text(label).font(.system(size: 12)).foregroundStyle(.white.opacity(0.7))
                    } else {
                        let niceName = eng.item.replacingOccurrences(of: "-", with: " ")
                        Text("Checking the \(niceName) tile").font(.system(size: 12)).foregroundStyle(.white.opacity(0.7))
                    }
                }
                if let c = poller.marker.combat, Date().timeIntervalSince1970 - c.t < 4, c.player.count >= 2 {
                    let px = c.player[0], py = c.player[1]
                    let near = c.enemies.filter { $0.count >= 2 && (($0[0] - px) * ($0[0] - px) + ($0[1] - py) * ($0[1] - py)) < 1600 }  // 40 tiles
                    if !near.isEmpty {
                        let firing = c.turrets.filter { $0.count >= 3 && Int($0[2]) != 0 }.count
                        HStack(spacing: 5) {
                            Circle().fill(Color.red).frame(width: 6, height: 6)
                            Text("\(near.count) enemies near\(firing > 0 ? ", \(firing) turrets firing" : "")").font(.system(size: 12)).foregroundStyle(.white.opacity(0.7))
                        }
                    }
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

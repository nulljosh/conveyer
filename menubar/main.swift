import SwiftUI
import Darwin

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
        case "idle": research = Research(current: "advanced-circuit", percent: 36, techs: 41, queue: ["advanced-circuit", "chemical-science-pack"], labs: 9, labs_working: 0)
        case "nodata": status = nil; research = nil; milestones = []; map = nil
        default: break
        }
    }
    private let scriptsDir = NSString(
        string: "~/Documents/Code/conveyer/menubar"
    ).expandingTildeInPath

    init() {
        poll()
        Timer.scheduledTimer(withTimeInterval: 3, repeats: true) { _ in
            Task { @MainActor in self.poll() }
        }
    }

    func poll() {
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
        let renderer = ImageRenderer(content: Self.popover(demoPoller).background(Color(white: 0.16)).environment(\.colorScheme, .dark))
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
                Text("\(done) of \(all.count) done").font(.system(size: 11)).foregroundStyle(.secondary)
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
                            Label(working == 0 ? "Labs idle, waiting for science packs" : "\(working) of \(labs) labs working",
                                  systemImage: working == 0 ? "exclamationmark.circle.fill" : "checkmark.circle.fill")
                                .font(.system(size: 11))
                                .foregroundStyle(working == 0 ? Color.orange : Color.secondary)
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
    private static func narrate(_ skill: String) -> String {
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

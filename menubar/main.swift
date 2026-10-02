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

    /// "advanced-circuit" -> "Advanced circuit"
    static func nice(_ name: String) -> String {
        let t = name.replacingOccurrences(of: "-", with: " ")
        return t.prefix(1).uppercased() + t.dropFirst()
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
    private let researchPath = NSString(
        string: "~/Documents/Code/conveyer/research.json"
    ).expandingTildeInPath
    private var mapStamp: Date?
    private let mapPath = NSString(
        string: "~/Documents/Code/conveyer/preview.png"
    ).expandingTildeInPath

    private let statusPath = NSString(
        string: "~/Documents/Code/conveyer/status.json"
    ).expandingTildeInPath
    private let pidPath = NSString(
        string: "~/Documents/Code/conveyer/runner.pid"
    ).expandingTildeInPath
    private var autoRestartedAt: Date?
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
        checkLiveness()
    }

    /// The runner rewrites preview.png every ~8s while idle; only decode it when it changed.
    private func loadMap() {
        guard let m = (try? FileManager.default.attributesOfItem(atPath: mapPath))?[.modificationDate] as? Date,
              m != mapStamp else { return }
        mapStamp = m
        map = NSImage(contentsOfFile: mapPath)
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
        let renderer = ImageRenderer(content: Self.popover(StatusPoller()).background(Color(white: 0.16)).environment(\.colorScheme, .dark))
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


    @MainActor
    static func popover(_ poller: StatusPoller) -> some View {
            VStack(alignment: .leading, spacing: 10) {
                if let map = poller.map {
                    Image(nsImage: map)
                        .resizable()
                        .interpolation(.high)
                        .aspectRatio(contentMode: .fit)
                        .frame(maxWidth: .infinity, maxHeight: 240)
                        .clipShape(RoundedRectangle(cornerRadius: 6))
                }
                if let r = poller.research, !r.current.isEmpty {
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
                        let next = r.queue.dropFirst().map { Research.nice($0).lowercased() }
                        Text(next.isEmpty ? "\(r.techs) techs done" : "\(r.techs) techs done. Next: \(next.joined(separator: ", "))")
                            .font(.system(size: 11))
                            .foregroundStyle(.secondary)
                    }
                }
                if let s = poller.status, s.skill != "?" {
                    HStack(spacing: 4) {
                        Text(s.skill)
                            .font(.system(size: 12, weight: .semibold))
                        Text(s.worked ? "done" : "didn't work")
                            .font(.system(size: 11))
                            .foregroundStyle(s.worked ? Color.secondary : Color.red)
                        Spacer()
                        Text("step \(s.step)")
                            .font(.system(size: 11))
                            .foregroundStyle(.secondary)
                    }
                    Text(s.message.replacingOccurrences(of: "SKILL_OK ", with: ""))
                        .font(.system(size: 11))
                        .foregroundStyle(.secondary)
                        .lineLimit(4)
                        .fixedSize(horizontal: false, vertical: true)

                    if !poller.runnerAlive {
                        Text("Stopped. It restarts on its own while the game is running.")
                            .font(.system(size: 11))
                            .foregroundStyle(.red)
                    } else if poller.stale {
                        Text("Waiting on a slow step.")
                            .font(.system(size: 11))
                            .foregroundStyle(.secondary)
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
        case "harvest": return "harvesting"
        case "mine": return "drilling"
        case "smelt": return "smelting"
        case "craft": return "crafting"
        case "place", "place_at", "place_inserter": return "building"
        case "feed", "collect": return "loading"
        case "auto_feed", "belt": return "automating"
        case "research", "research_progress": return "researching"
        case "inspect", "peek", "nearby", "dropcheck", "find", "recipe": return "scouting"
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

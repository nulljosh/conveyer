import SwiftUI
import Darwin

struct Status: Decodable {
    let step: Int
    let skill: String
    let ok: Bool
    let message: String
    let updated_at: Double
}

@MainActor
final class StatusPoller: ObservableObject {
    @Published var status: Status?
    @Published var stale = false
    @Published var runnerAlive = true
    @Published var busy = false

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
        checkLiveness()
    }

    /// True process liveness (kill(pid, 0)), not just "no recent status update" —
    /// a long smelt/harvest wait is a real gap, not a crash. Auto-restarts once
    /// if the PID is actually dead, debounced so it can't loop.
    private func checkLiveness() {
        guard let pidText = try? String(contentsOfFile: pidPath, encoding: .utf8),
              let pid = pid_t(pidText.trimmingCharacters(in: .whitespacesAndNewlines))
        else { return }
        let alive = Darwin.kill(pid, 0) == 0
        runnerAlive = alive
        if !alive {
            let now = Date()
            if autoRestartedAt == nil || now.timeIntervalSince(autoRestartedAt!) > 60 {
                autoRestartedAt = now
                run("restart_runner.sh")
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

    var body: some Scene {
        MenuBarExtra {
            VStack(alignment: .leading, spacing: 10) {
                if let s = poller.status {
                    HStack(spacing: 4) {
                        Text(s.skill)
                            .font(.system(size: 12, weight: .semibold))
                        Text(s.ok ? "ok" : "failed")
                            .font(.system(size: 11))
                            .foregroundStyle(s.ok ? Color.secondary : Color.red)
                        Spacer()
                        Text("step \(s.step)")
                            .font(.system(size: 11))
                            .foregroundStyle(.secondary)
                    }
                    Text(s.message)
                        .font(.system(size: 11))
                        .foregroundStyle(.secondary)
                        .lineLimit(4)
                        .fixedSize(horizontal: false, vertical: true)

                    if !poller.runnerAlive {
                        Text("Runner died — auto-restarting…")
                            .font(.system(size: 11))
                            .foregroundStyle(.red)
                    } else if poller.stale {
                        Text("No update in 2min+ — likely a long smelt/harvest wait")
                            .font(.system(size: 11))
                            .foregroundStyle(.secondary)
                    }
                } else {
                    Text("No status yet — start the server below")
                        .font(.system(size: 12))
                        .foregroundStyle(.secondary)
                }

                Divider()

                Text("Server controls")
                    .font(.system(size: 10, weight: .semibold))
                    .foregroundStyle(.secondary)

                VStack(spacing: 4) {
                    controlButton("Restart runner", systemImage: "arrow.clockwise") {
                        poller.run("restart_runner.sh")
                    }
                    controlButton("Restart server + runner", systemImage: "arrow.triangle.2.circlepath") {
                        poller.run("restart_server.sh")
                    }
                    controlButton("Stop server", systemImage: "stop.circle") {
                        poller.run("stop_all.sh")
                    }
                }

                if poller.busy {
                    HStack(spacing: 5) {
                        ProgressView().controlSize(.small)
                        Text("Working…").font(.system(size: 11)).foregroundStyle(.secondary)
                    }
                }

                Divider()
                Button("Quit monitor") { NSApplication.shared.terminate(nil) }
                    .font(.system(size: 12))
            }
            .padding(12)
            .frame(width: 280)
        } label: {
            Text(labelText)
                .font(.system(size: 12, design: .monospaced))
        }
        .menuBarExtraStyle(.window)
    }

    private var labelText: String {
        if !poller.runnerAlive { return "⚠ died" }
        guard let s = poller.status else { return "…" }
        let dot = s.ok ? "●" : "○"
        return "\(dot) \(Self.narrate(s.skill))"
    }

    /// Skill names as they'd be said out loud, matching how progress reads in
    /// chat ("smelting", "building a base") instead of the raw dispatch name.
    private static func narrate(_ skill: String) -> String {
        switch skill {
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
    private func controlButton(_ title: String, systemImage: String, action: @escaping () -> Void) -> some View {
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

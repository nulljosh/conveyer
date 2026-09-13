import SwiftUI
import Darwin

struct Status: Decodable {
    let step: Int
    let skill: String
    let ok: Bool
    let message: String
    let updated_at: Double
}

struct MapEntity: Decodable {
    let kind: String
    let x: Double
    let y: Double
    let step: Int
}

@MainActor
final class StatusPoller: ObservableObject {
    @Published var status: Status?
    @Published var log: [Status] = []
    @Published var map: [MapEntity] = []
    @Published var preview: NSImage?
    @Published var stale = false
    @Published var runnerAlive = true
    @Published var busy = false

    private let statusPath = NSString(
        string: "~/Documents/Code/conveyer/status.json"
    ).expandingTildeInPath
    private let logPath = NSString(
        string: "~/Documents/Code/conveyer/status_log.json"
    ).expandingTildeInPath
    private let mapPath = NSString(
        string: "~/Documents/Code/conveyer/map.json"
    ).expandingTildeInPath
    private let pidPath = NSString(
        string: "~/Documents/Code/conveyer/runner.pid"
    ).expandingTildeInPath
    private let previewPath = NSString(
        string: "~/Documents/Code/conveyer/preview.png"
    ).expandingTildeInPath
    private var autoRestartedAt: Date?
    private var previewMtime: Date?
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
        if let data = FileManager.default.contents(atPath: logPath),
           let decoded = try? JSONDecoder().decode([Status].self, from: data) {
            log = decoded
        }
        if let data = FileManager.default.contents(atPath: mapPath),
           let decoded = try? JSONDecoder().decode([MapEntity].self, from: data) {
            map = decoded
        }
        if let attrs = try? FileManager.default.attributesOfItem(atPath: previewPath),
           let mtime = attrs[.modificationDate] as? Date,
           mtime != previewMtime {
            previewMtime = mtime
            if let full = NSImage(contentsOfFile: previewPath) {
                preview = Self.centerCrop(full, fraction: 0.28)
            }
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

    /// Crop to the center `fraction` of the image and upscale back to the
    /// original size — the base is always near frame center (render is
    /// player-centered), so this zooms in on the action instead of showing
    /// mostly empty ground.
    static func centerCrop(_ image: NSImage, fraction: CGFloat) -> NSImage {
        guard let cgImage = image.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
            return image
        }
        let w = CGFloat(cgImage.width), h = CGFloat(cgImage.height)
        let cropW = w * fraction, cropH = h * fraction
        let rect = CGRect(x: (w - cropW) / 2, y: (h - cropH) / 2, width: cropW, height: cropH)
        guard let cropped = cgImage.cropping(to: rect) else { return image }
        return NSImage(cgImage: cropped, size: NSSize(width: w, height: h))
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

private struct StatusDot: View {
    let color: Color
    var body: some View {
        Circle().fill(color).frame(width: 7, height: 7)
    }
}

private struct MinimapView: View {
    let entities: [MapEntity]

    private func color(for kind: String) -> Color {
        switch kind {
        case "BurnerMiningDrill", "ElectricMiningDrill": return .orange
        case "StoneFurnace", "ElectricFurnace": return .red
        case "AssemblingMachine1", "AssemblingMachine2": return .cyan
        case "Boiler", "SteamEngine", "OffshorePump": return .blue
        default: return .yellow
        }
    }

    var body: some View {
        Canvas { context, size in
            // dark 8-bit-ish grid background
            let cell: CGFloat = 8
            context.fill(Path(CGRect(origin: .zero, size: size)), with: .color(Color.black.opacity(0.6)))
            var x: CGFloat = 0
            while x < size.width {
                context.stroke(Path { p in p.move(to: CGPoint(x: x, y: 0)); p.addLine(to: CGPoint(x: x, y: size.height)) }, with: .color(.white.opacity(0.04)))
                x += cell
            }
            var y: CGFloat = 0
            while y < size.height {
                context.stroke(Path { p in p.move(to: CGPoint(x: 0, y: y)); p.addLine(to: CGPoint(x: size.width, y: y)) }, with: .color(.white.opacity(0.04)))
                y += cell
            }

            guard !entities.isEmpty else { return }
            let xs = entities.map(\.x), ys = entities.map(\.y)
            let minX = xs.min()!, maxX = xs.max()!, minY = ys.min()!, maxY = ys.max()!
            let spanX = max(maxX - minX, 1), spanY = max(maxY - minY, 1)
            let pad: CGFloat = 14

            for e in entities {
                let nx = (e.x - minX) / spanX
                let ny = (e.y - minY) / spanY
                let px = pad + CGFloat(nx) * (size.width - pad * 2)
                let py = pad + CGFloat(ny) * (size.height - pad * 2)
                let rect = CGRect(x: px - 3, y: py - 3, width: 6, height: 6)
                context.fill(Path(rect), with: .color(color(for: e.kind)))
            }
        }
        .frame(height: 130)
        .clipShape(RoundedRectangle(cornerRadius: 6))
        .overlay(RoundedRectangle(cornerRadius: 6).stroke(Color.white.opacity(0.08)))
    }
}

private struct LogRow: View {
    let entry: Status
    var body: some View {
        HStack(alignment: .top, spacing: 6) {
            Circle()
                .fill(entry.ok ? Color.green : Color.red)
                .frame(width: 5, height: 5)
                .padding(.top, 5)
            VStack(alignment: .leading, spacing: 1) {
                HStack(spacing: 4) {
                    Text("#\(entry.step)")
                        .font(.system(size: 10))
                        .foregroundStyle(.tertiary)
                    Text(entry.skill)
                        .font(.system(size: 11, weight: .medium))
                }
                Text(entry.message)
                    .font(.system(size: 10.5))
                    .foregroundStyle(.secondary)
                    .lineLimit(2)
            }
        }
    }
}

@main
struct ConveyerMonitorApp: App {
    @StateObject private var poller = StatusPoller()
    @State private var showHistory = true

    var body: some Scene {
        MenuBarExtra {
            VStack(alignment: .leading, spacing: 10) {
                HStack(spacing: 6) {
                    StatusDot(color: dotColor)
                    Text("Conveyer")
                        .font(.system(size: 13, weight: .semibold))
                    Spacer()
                    if let s = poller.status {
                        Text("step \(s.step)")
                            .font(.system(size: 11))
                            .foregroundStyle(.secondary)
                    }
                }

                if let s = poller.status {
                    HStack(spacing: 4) {
                        Text(s.skill)
                            .font(.system(size: 11, weight: .medium))
                        Text(s.ok ? "ok" : "failed")
                            .font(.system(size: 10))
                            .foregroundStyle(s.ok ? Color.secondary : Color.red)
                        Spacer()
                    }
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

                Button(action: { showHistory.toggle() }) {
                    HStack {
                        Text("Step history (\(poller.log.count))")
                            .font(.system(size: 11, weight: .semibold))
                            .foregroundStyle(.secondary)
                        Spacer()
                        Image(systemName: showHistory ? "chevron.up" : "chevron.down")
                            .font(.system(size: 9))
                            .foregroundStyle(.secondary)
                    }
                }
                .buttonStyle(.plain)

                if showHistory {
                    ScrollView {
                        VStack(alignment: .leading, spacing: 8) {
                            ForEach(poller.log, id: \.step) { entry in
                                LogRow(entry: entry)
                            }
                        }
                    }
                    .frame(height: 320)
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
            .frame(width: 300)
        } label: {
            Image(systemName: labelIcon)
        }
        .menuBarExtraStyle(.window)
    }

    private var dotColor: Color {
        if !poller.runnerAlive { return .red }
        guard let s = poller.status else { return .gray }
        return s.ok ? .green : .orange
    }

    private var labelIcon: String {
        if !poller.runnerAlive { return "exclamationmark.triangle.fill" }
        guard let s = poller.status else { return "gearshape" }
        return s.ok ? "gearshape.fill" : "gearshape.fill"
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

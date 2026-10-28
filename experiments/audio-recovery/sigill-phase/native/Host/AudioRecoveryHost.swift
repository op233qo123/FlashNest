import SwiftUI
import WebKit

/// Separate diagnostic target only. Uses production Session, shell and bridge.
@main struct AudioRecoveryHost: App {
    @StateObject private var model = RecoveryModel()
    var body: some Scene { WindowGroup { RecoveryHostView(model: model).task { await model.open() } } }
}
@MainActor final class RecoveryModel: ObservableObject {
    let session = PlayerSession()
    @Published var status = "starting"
    @Published var probe = ""
    @Published var hostError = "none"
    private var root: URL?
    private var package: GamePackage?
    func open() async {
        guard root == nil else { return }
        StartupJournal.shared.reset()
        do {
            let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
            self.root = root
            guard let fixture = Bundle.main.url(forResource: "lifecycle", withExtension: nil) else {
                throw NSError(domain: "RecoveryHost", code: 1)
            }
            let packages = root.appendingPathComponent("packages")
            let package = try PackageImporter(root: packages).stageAndCommit(fixture)
            self.package = package
            await session.start(package: package, contentRoot: packages.appendingPathComponent(package.id.uuidString).appendingPathComponent("content"))
            status = "opened"
            StartupJournal.shared.nativeOpened()
        } catch { hostError = String(describing: error) }
    }
    func key(_ code: String) { session.key(code, down: true); session.key(code, down: false) }
    func snapshot() async {
        do { probe = try await js("JSON.stringify(window.FlashNestAudioProbe.status())") as? String ?? "invalid" }
        catch { hostError = String(describing: error) }
    }
    func inject() async {
        do {
            let mode = ProcessInfo.processInfo.environment["AUDIO_RECOVERY_MODE"] ?? "candidate-known"
            guard ["candidate-known", "candidate-unknown", "baseline-known"].contains(mode) else {
                throw NSError(domain: "RecoveryHost", code: 2)
            }
            session.setPaused(true)
            let end = Date().addingTimeInterval(5)
            var suspended = false
            repeat {
                suspended = (try await js("window.FlashNestAudioProbe.contextState()") as? String) == "suspended"
                if suspended { break }
                try await Task.sleep(nanoseconds: 100_000_000)
            } while Date() < end
            guard suspended else { throw NSError(domain: "RecoveryHost.suspendDeadline", code: 3) }
            let kind = mode == "candidate-unknown" ? "unknown" : "known"
            _ = try await js("window.FlashNestAudioProbe.arm('\(kind)', \(mode == "baseline-known" ? "true" : "false")); true")
            session.setPaused(false)
            status = "injection-requested"
        } catch { hostError = String(describing: error) }
    }
    func restart() async {
        if !(await session.saveAndRestart()) { hostError = "Explicit diagnostic save restart failed" }
    }
    func close() async {
        do {
            _ = try await js("window.FlashNestAudioProbe.dispose(); true")
            try await session.closeWithoutSaving()
            if let package { UserDefaults.standard.removeObject(forKey: RendererSettings.preferenceKey(for: package.id)) }
            if let root { try FileManager.default.removeItem(at: root) }
            status = "closed-and-drained"
        } catch { hostError = String(describing: error) }
    }
    private func js(_ source: String) async throws -> Any {
        guard let view = session.webView else { throw NSError(domain: "RecoveryHost.noView", code: 4) }
        return try await withCheckedThrowingContinuation { continuation in
            var done = false
            view.evaluateJavaScript(source) { result, error in
                guard !done else { return }; done = true
                if let error { continuation.resume(throwing: error) }
                else { continuation.resume(returning: result ?? NSNull()) }
            }
            Task { @MainActor in
                try? await Task.sleep(nanoseconds: 3_000_000_000)
                guard !done else { return }; done = true
                continuation.resume(throwing: NSError(domain: "RecoveryHost.javascriptDeadline", code: 5))
            }
        }
    }
}
struct RecoveryHostView: View {
    @ObservedObject var model: RecoveryModel
    @ObservedObject private var startupJournal = StartupJournal.shared
    var body: some View {
        VStack {
            SessionSurface(session: model.session)
            Text(model.status).accessibilityIdentifier("recovery-host-status")
            Text(model.probe).font(.caption2).lineLimit(2).accessibilityIdentifier("recovery-probe").accessibilityValue(startupJournal.json)
            Text(model.hostError).accessibilityIdentifier("recovery-host-error")
            HStack {
                Button("Enter") { model.key("Enter") }.accessibilityIdentifier("recovery-enter")
                Button("Space") { model.key("Space") }.accessibilityIdentifier("recovery-space")
                Button("Inject resume") { Task { await model.inject() } }.accessibilityIdentifier("recovery-inject")
            }.buttonStyle(.bordered)
            HStack {
                Button("Snapshot") { Task { await model.snapshot() } }.accessibilityIdentifier("recovery-snapshot")
                Button("Verify saved restart") { Task { await model.restart() } }.accessibilityIdentifier("recovery-restart")
                Button("Close") { Task { await model.close() } }.accessibilityIdentifier("recovery-close")
            }.buttonStyle(.bordered)
        }
    }
}
private struct SessionSurface: View {
    @ObservedObject var session: PlayerSession
    var body: some View {
        VStack {
            if let view = session.webView { RecoveryWebView(view: view) }
            Text(session.failure ?? "none").accessibilityIdentifier("recovery-native-failure")
        }.onChange(of: session.failure) { value in
            if value != nil { StartupJournal.shared.nativeFailure() }
        }
    }
}
private struct RecoveryWebView: UIViewRepresentable {
    let view: WKWebView
    func makeUIView(context: Context) -> WKWebView { view }
    func updateUIView(_ uiView: WKWebView, context: Context) {}
}

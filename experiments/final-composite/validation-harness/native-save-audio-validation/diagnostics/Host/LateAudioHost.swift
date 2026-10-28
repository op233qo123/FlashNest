import SwiftUI
import WebKit

// LOCAL diagnostic target only; never include in the shipping App target.
@main struct LateAudioHost: App {
    @StateObject private var model = LateAudioModel()
    var body: some Scene { WindowGroup { LateAudioView(model: model).task { await model.open() } } }
}
@MainActor final class LateAudioModel: ObservableObject {
    let session = PlayerSession()
    @Published var status = "starting"
    @Published var snapshot = ""
    @Published var hostError = "none"
    @Published var cleanup = ""
    private var disposedObserved = false
    private var root: URL?
    private var package: GamePackage?
    private var closing = false, begun = false, injected = false
    private var watchdog: Task<Void, Never>?
    private var mode: String { ProcessInfo.processInfo.environment["AUDIO_RECOVERY_MODE"] ?? "invalid" }
    private func error(_ message: String) -> NSError { NSError(domain: "LateAudioHost", code: 1, userInfo: [NSLocalizedDescriptionKey: message]) }
    func open() async {
        guard root == nil else { return }
        do {
            guard ["candidate-known", "candidate-unknown", "baseline-known"].contains(mode) else { throw error("Invalid explicit diagnostic mode") }
            let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
            self.root = root
            guard let fixture = Bundle.main.url(forResource: "lifecycle", withExtension: nil) else { throw error("Missing fixture") }
            let packages = root.appendingPathComponent("packages")
            let package = try PackageImporter(root: packages).stageAndCommit(fixture)
            self.package = package
            watchdog = Task { [weak self] in
                try? await Task.sleep(nanoseconds: self?.mode == "candidate-known" ? 350_000_000_000 : 170_000_000_000)
                guard !Task.isCancelled, let self else { return }
                self.hostError = "Functional diagnostic deadline"
                await self.close()
            }
            await session.start(package: package, contentRoot: packages.appendingPathComponent(package.id.uuidString).appendingPathComponent("content"))
            status = "opened"
        } catch { hostError = String(describing: error); await close() }
    }
    func key(_ code: String) { session.key(code, down: true); session.key(code, down: false) }
    // XCTest invokes this only AFTER its actual Play tap and genuine fixture traces.
    // The page independently requires its passive trusted Play and real trace/SOL records.
    func begin() async {
        guard !begun, !closing else { hostError = "Duplicate/closed late begin"; return }
        begun = true
        do {
            guard session.failure == nil, session.ready, !session.paused else { throw error("Native session not active") }
            guard try await js("(() => { const e=window.FlashNestLateEvidence.snapshot(); return e.active && Object.values(e.readiness).every(x=>x===true); })()") as? Bool == true else { throw error("Real Play/root/child/nonempty SOL readiness absent") }
            for name in ["late-audio-probe", "late-host-adapter"] {
                guard let url = Bundle.main.url(forResource: name, withExtension: "js") else { throw error("Missing pinned late script: " + name) }
                _ = try await js(try String(contentsOf: url, encoding: .utf8) + "\n;true")
            }
            _ = try await js("window.FlashNestLateHost.begin('\(mode)'); true")
            let end = Date().addingTimeInterval(15)
            var complete = false
            repeat {
                let value = try await js("window.FlashNestLateHost.snapshot().captureState") as? String
                if value == "fulfilled" { complete = true; break }
                if value == "rejected" { throw error("Capture failed") }
                try await Task.sleep(nanoseconds: 100_000_000)
            } while Date() < end && !closing
            guard complete else { throw error("Capture deadline") }
            status = "captured"
            await readSnapshot()
        } catch { hostError = String(describing: error); await close() }
    }
    func inject() async {
        guard begun, !injected, !closing, status == "captured" else { hostError = "Injection phase invalid"; return }
        injected = true
        do {
            session.setPaused(true)
            let end = Date().addingTimeInterval(5)
            var suspended = false
            repeat {
                suspended = (try await js("window.FlashNestLateHost.snapshot().probe.contextState") as? String) == "suspended"
                if suspended { break }
                try await Task.sleep(nanoseconds: 100_000_000)
            } while Date() < end && !closing
            guard suspended, session.paused else { throw error("Production suspension deadline/state") }
            // This staged-only method updates native paused=false and evaluates ONE
            // synchronous inject(()=>FlashNest.resume()) call; never setPaused(false).
            try await session.diagnosticLateInject(kind: mode == "candidate-unknown" ? "unknown" : "known")
            status = "injected"
        } catch { hostError = String(describing: error); await close() }
    }
    func readSnapshot() async {
        do { snapshot = try await js("JSON.stringify(window.FlashNestLateHost.snapshot())") as? String ?? "invalid" }
        catch { hostError = String(describing: error); await close() }
    }
    func verify() async {
        do {
            guard session.failure == nil, !session.paused else { throw error("Native production failure/paused") }
            let result = try await js("JSON.stringify(window.FlashNestLateHost.verify())") as? String ?? "invalid"
            snapshot = result
            guard let data = result.data(using: .utf8), let object = try JSONSerialization.jsonObject(with: data) as? [String: Any], object["ok"] as? Bool == true else { throw error("Recovery verification failed") }
            status = "verified-in-place"
        } catch { hostError = String(describing: error); await close() }
    }
    func restart() async {
        guard status == "verified-in-place" else { hostError = "Reopen before in-place acceptance forbidden"; return }
        do {
            disposedObserved = try await js("window.FlashNestLateHost.dispose()") as? Bool == true
            guard disposedObserved else { throw error("Probe disposal unconfirmed") }
        }
        catch { hostError = String(describing: error); await close(); return }
        if await session.saveAndRestart() { status = "reopened" } else { hostError = "Explicit restart failed"; await close() }
    }
    func close() async {
        guard !closing else { return }; closing = true
        watchdog?.cancel(); watchdog = nil
        // Disposal failure (including a dead WebContent process) MUST NOT skip drain.
        if begun, session.webView != nil {
            do {
                let result = try await js("window.FlashNestLateHost ? window.FlashNestLateHost.dispose() : null")
                if let confirmed = result as? Bool { disposedObserved = confirmed }
            }
            catch { if hostError == "none" { hostError = "Cleanup JS: \(error)" } }
        }
        do { try await session.closeWithoutSaving() }
        catch { hostError = "Native drain: \(error)"; status = "cleanup-failed"; return }
        do {
            if let package { UserDefaults.standard.removeObject(forKey: RendererSettings.preferenceKey(for: package.id)) }
            if let root { try FileManager.default.removeItem(at: root) }
            cleanup = "{\"disposed\":\(disposedObserved),\"drained\":true,\"closed\":true}"
            status = "closed-and-drained"
        } catch { hostError = "Fixture cleanup: \(error)"; status = "cleanup-failed" }
    }
    private func js(_ source: String) async throws -> Any {
        guard let view = session.webView else { throw error("No WebView") }
        return try await withCheckedThrowingContinuation { continuation in
            var done = false
            view.evaluateJavaScript(source) { result, error in
                guard !done else { return }; done = true
                if let error { continuation.resume(throwing: error) } else { continuation.resume(returning: result ?? NSNull()) }
            }
            Task { @MainActor in
                try? await Task.sleep(nanoseconds: 3_000_000_000)
                guard !done else { return }; done = true
                continuation.resume(throwing: self.error("JavaScript deadline"))
            }
        }
    }
}
struct LateAudioView: View {
    @ObservedObject var model: LateAudioModel
    var body: some View { VStack {
        LateSessionSurface(session: model.session)
        Text(model.status).accessibilityIdentifier("late-status")
        Text(model.snapshot).font(.caption2).lineLimit(2).accessibilityIdentifier("late-snapshot")
        Text(model.hostError).accessibilityIdentifier("late-error")
        Text(model.cleanup).accessibilityIdentifier("late-cleanup")
        HStack {
            Button("Enter") { model.key("Enter") }.accessibilityIdentifier("late-enter")
            Button("Space") { model.key("Space") }.accessibilityIdentifier("late-space")
            Button("Begin late capture") { Task { await model.begin() } }.accessibilityIdentifier("late-begin")
            Button("Inject") { Task { await model.inject() } }.accessibilityIdentifier("late-inject")
        }
        HStack {
            Button("Snapshot") { Task { await model.readSnapshot() } }.accessibilityIdentifier("late-read")
            Button("Verify") { Task { await model.verify() } }.accessibilityIdentifier("late-verify")
            Button("Reopen") { Task { await model.restart() } }.accessibilityIdentifier("late-reopen")
            Button("Close") { Task { await model.close() } }.accessibilityIdentifier("late-close")
        }
    }.buttonStyle(.bordered) }
}
private struct LateSessionSurface: View {
    @ObservedObject var session: PlayerSession
    var body: some View { VStack {
        if let view = session.webView { LateWebView(view: view) }
        Text(session.failure ?? "none").accessibilityIdentifier("late-native-failure")
    } }
}
private struct LateWebView: UIViewRepresentable {
    let view: WKWebView
    func makeUIView(context: Context) -> WKWebView { view }
    func updateUIView(_ uiView: WKWebView, context: Context) {}
}

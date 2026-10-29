import UIKit
import SwiftUI
import WebKit

// Separate simulator-only executable. All App models/session/views/Web resources
// are compiled/copied unchanged except the documented gate + passive-script hook.
@MainActor enum NativeSamplingProbe {
    static var navigationEvents: [String] = []
    static var traces: [String] = []
    static var traceOverflow = false
    static func recordTrace(_ value: String) {
        guard value.hasPrefix("SWF: DENSITY|") else { return }
        if traces.count < 128 && value.utf8.count < 1024 { traces.append(value) } else { traceOverflow = true }
    }
    static func record(_ event: String) { if navigationEvents.count < 64 { navigationEvents.append(event) } }
    static func initialURL(_ url: URL) -> URL {
        let args = ProcessInfo.processInfo.arguments
        var components = URLComponents(url: url, resolvingAgainstBaseURL: false)!
        var items = components.queryItems ?? []
        if args.contains("--redirect-initial") { items.append(URLQueryItem(name: "nativeSamplingRedirect", value: "1")) }
        if let i = args.firstIndex(of: "--diagnostic-quality"), i + 1 < args.count, ["low", "high"].contains(args[i + 1]) {
            items.append(URLQueryItem(name: "nativeSamplingQuality", value: args[i + 1]))
        }
        components.queryItems = items; return components.url!
    }
    static var script: WKUserScript {
        let url = Bundle.main.url(forResource: "sampling-probe", withExtension: "js")!
        return WKUserScript(source: try! String(contentsOf: url), injectionTime: .atDocumentStart, forMainFrameOnly: true)
    }
}

// Dedicated loopback fixture faults, compiled ONLY in this simulator host.
// Same-origin/same-path redirect retains the real app navigation policy.
enum NativeSamplingTransport {
    static func response(target: String) -> Data? {
        guard var parts = URLComponents(string: target) else { return nil }
        if parts.queryItems?.contains(URLQueryItem(name: "nativeSamplingFail", value: "1")) == true { return Data() }
        guard parts.queryItems?.contains(URLQueryItem(name: "nativeSamplingRedirect", value: "1")) == true else { return nil }
        parts.queryItems = parts.queryItems?.filter { $0.name != "nativeSamplingRedirect" }
        guard let location = parts.string, !location.contains("\r"), !location.contains("\n") else { return nil }
        return Data("HTTP/1.1 302 Found\r\nLocation: \(location)\r\nContent-Length: 0\r\nConnection: close\r\nCache-Control: no-store\r\n\r\n".utf8)
    }
}

@main @MainActor final class SamplingHostApp: UIResponder, UIApplicationDelegate {
    var window: UIWindow?
    let controller = SamplingHostController()
    func application(_ application: UIApplication, didFinishLaunchingWithOptions options: [UIApplication.LaunchOptionsKey: Any]? = nil) -> Bool {
        let window = UIWindow(frame: UIScreen.main.bounds)
        window.rootViewController = controller; window.makeKeyAndVisible(); self.window = window
        return true
    }
    func applicationDidEnterBackground(_ application: UIApplication) {
        Task { await controller.session.suspendAndSave() }
    }
    func applicationWillEnterForeground(_ application: UIApplication) {
        Task { await controller.session.resumeAfterSuspension() }
    }
}

@MainActor final class SamplingHostController: UIViewController {
    private let root = FileManager.default.temporaryDirectory.appendingPathComponent("sampling-" + UUID().uuidString)
    lazy var session = PlayerSession(saveStore: SaveStore(root: root.appendingPathComponent("saves")),
                                    incidentStore: LastSessionDiagnostics(root: root.appendingPathComponent("incidents")))
    private let content = UIView(), evidence = UILabel(), toolbar = UIStackView()
    private var package: GamePackage?
    private var failure: String?
    private var epoch = 0, request = 0
    private var retainedOldView: WKWebView?
    private let arguments = ProcessInfo.processInfo.arguments
    private var identity: [String: Any] = [:]
    override var supportedInterfaceOrientations: UIInterfaceOrientationMask { .allButUpsideDown }
    override func viewDidLoad() {
        super.viewDidLoad(); view.backgroundColor = .black
        if let url = Bundle.main.url(forResource: "SamplingIdentity", withExtension: "json"),
           let data = try? Data(contentsOf: url), let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any] { identity = object }
        toolbar.axis = .horizontal; toolbar.distribution = .fillEqually; toolbar.backgroundColor = .systemBackground
        for (name, selector) in [("Snapshot", #selector(snapshotTapped)), ("Settings", #selector(settingsTapped)),
                                 ("Restart", #selector(restartTapped)), ("Stale", #selector(staleTapped)),
                                 ("Reload", #selector(reloadTapped)), ("Fail", #selector(failTapped))] {
            let button = UIButton(type: .system); button.setTitle(name, for: .normal)
            button.accessibilityIdentifier = "sampling-" + name.lowercased()
            button.addTarget(self, action: selector, for: .touchUpInside); toolbar.addArrangedSubview(button)
        }
        evidence.text = "Sampling evidence"; evidence.textColor = .white; evidence.font = .systemFont(ofSize: 1)
        evidence.isAccessibilityElement = true; evidence.accessibilityIdentifier = "sampling-evidence"
        evidence.accessibilityValue = "{}"
        content.accessibilityIdentifier = "sampling-viewport"
        for child in [toolbar, evidence, content] { child.translatesAutoresizingMaskIntoConstraints = false; view.addSubview(child) }
        NSLayoutConstraint.activate([
            toolbar.topAnchor.constraint(equalTo: view.safeAreaLayoutGuide.topAnchor), toolbar.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            toolbar.trailingAnchor.constraint(equalTo: view.trailingAnchor), toolbar.heightAnchor.constraint(equalToConstant: 44),
            evidence.topAnchor.constraint(equalTo: toolbar.bottomAnchor), evidence.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            evidence.trailingAnchor.constraint(equalTo: view.trailingAnchor), evidence.heightAnchor.constraint(equalToConstant: 1),
            content.topAnchor.constraint(equalTo: evidence.bottomAnchor), content.leadingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.leadingAnchor),
            content.trailingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.trailingAnchor), content.bottomAnchor.constraint(equalTo: view.safeAreaLayoutGuide.bottomAnchor)
        ])
        Task { await open() }
    }
    private func argument(_ key: String, default fallback: String) -> String {
        guard let i = arguments.firstIndex(of: "--" + key), i + 1 < arguments.count else { return fallback }
        return arguments[i + 1]
    }
    private func open() async {
        do {
            let fixture = argument("fixture", default: "showAll-center.swf")
            guard ["showAll-center.swf", "noScale-center.swf"].contains(fixture),
                  let base = Bundle.main.url(forResource: "SamplingFixtures", withExtension: nil),
                  let mode = RenderSamplingSettings.Mode(rawValue: argument("scale", default: "original")),
                  let renderer = RendererSettings.Mode(rawValue: argument("renderer", default: "automatic")) else { throw NSError(domain: "SamplingHost", code: 1) }
            let packages = root.appendingPathComponent("packages")
            let game = try PackageImporter(root: packages).stageAndCommit(base.appendingPathComponent(fixture))
            package = game
            guard RenderSamplingSettings(mode: mode).save(for: game.id), RendererSettings(mode: renderer).save(for: game.id) else { throw NSError(domain: "SamplingHost", code: 2) }
            await session.start(package: game, contentRoot: packages.appendingPathComponent(game.id.uuidString).appendingPathComponent("content"))
            attach(); await snapshot()
        } catch { failure = "Synthetic fixture setup failed: \(error.localizedDescription)"; await snapshot() }
    }
    private func attach() {
        content.subviews.forEach { $0.removeFromSuperview() }
        guard let web = session.webView else { return }
        epoch += 1; web.translatesAutoresizingMaskIntoConstraints = false; content.addSubview(web)
        NSLayoutConstraint.activate([web.leadingAnchor.constraint(equalTo: content.leadingAnchor), web.trailingAnchor.constraint(equalTo: content.trailingAnchor),
            web.topAnchor.constraint(equalTo: content.topAnchor), web.bottomAnchor.constraint(equalTo: content.bottomAnchor)])
    }
    @objc private func snapshotTapped() { Task { await snapshot() } }
    private func restartSafeDiagnosticText(_ text: String) -> String {
        var safe = text
        for pattern in [#"(?i)\b(?:https?|file|wss?|flashnest)://[^\s\"'<>]+"#, #"\b[A-Za-z0-9_-]{32,}={0,2}\b"#] {
            if let regex = try? NSRegularExpression(pattern: pattern) {
                safe = regex.stringByReplacingMatches(in: safe, range: NSRange(safe.startIndex..., in: safe), withTemplate: "[redacted]")
            }
        }
        return safe.count > 2048 ? String(safe.prefix(2048)) + " [truncated]" : safe
    }
    private var restartObservationPhase = "idle"
    private func snapshot() async {
        request += 1
        var result: [String: Any] = ["schema": 1, "request": request, "epoch": epoch, "identity": identity,
            "screenScale": UIScreen.main.scale, "nativeScale": UIScreen.main.nativeScale,
            "screenBounds": [UIScreen.main.bounds.width, UIScreen.main.bounds.height],
            "os": UIDevice.current.systemVersion, "gate": RenderSamplingSettings.runtimeValidated,
            "loaded": session.isLoaded, "failure": restartSafeDiagnosticText(failure ?? session.failure ?? ""),
            "restartObservation": ["saveReady": session.saveReady, "saveFailure": restartSafeDiagnosticText(session.saveFailure ?? ""),
                "restartFailure": restartSafeDiagnosticText(session.restartFailure ?? ""), "restartRequired": session.restartRequired,
                "hasWebView": session.webView != nil, "restartPhase": restartObservationPhase,
                "processTerminated": NSNull(), "preservationStage": NSNull(),
                "privateFieldAvailability": "not-exposed-by-product"] as [String: Any],
            "traces": NativeSamplingProbe.traces, "traceOverflow": NativeSamplingProbe.traceOverflow,
            "requested": session.requestedSamplingSettings?.mode.scale ?? -1,
            "applied": session.appliedSamplingStatus.applied ?? -1,
            "status": String(describing: session.appliedSamplingStatus.state),
            "navigationEvents": NativeSamplingProbe.navigationEvents,
            "staleBarrier": session.diagnostics.contains { $0.contains("SAMPLING_STALE_BARRIER") },
            "viewport": [content.convert(content.bounds, to: view).minX, content.convert(content.bounds, to: view).minY, content.bounds.width, content.bounds.height]]
        if let web = session.webView {
            do { result["measurement"] = try await web.evaluateJavaScript("window.__samplingNativeProbe?.measure() || null") }
            catch { result["probeError"] = "JavaScript observation unavailable" }
        }
        if let data = try? JSONSerialization.data(withJSONObject: result, options: [.sortedKeys]), data.count < 48_000 {
            evidence.accessibilityValue = String(decoding: data, as: UTF8.self)
        } else { evidence.accessibilityValue = "{\"failure\":\"Evidence serialization or 48KiB limit\"}" }
    }
    @objc private func settingsTapped() {
        guard let package else { return }
        let panel = SamplingSettingsPanel(session: session, package: package)
        present(UIHostingController(rootView: panel), animated: false)
    }
    @objc private func restartTapped() {
        restartObservationPhase = "requested"
        Task {
            retainedOldView = session.webView
            restartObservationPhase = "before-saveAndRestart"
            let restartSucceeded = await session.saveAndRestart()
            restartObservationPhase = restartSucceeded ? "returned-true" : "returned-false"
            guard restartSucceeded else { failure = "Actual save/restart failed"; await snapshot(); return }
            attach(); restartObservationPhase = "attached"; await snapshot()
            // Keep the released WK object only through this explicit old-view check.
            if let old = retainedOldView, let url = old.url {
                session.receiveScriptMessage(from: old, isMainFrame: true, requestURL: url,
                    body: ["type": "samplingStatus", "session": "old", "sequence": 999_999, "status": "unknown"])
            }
            retainedOldView = nil
        }
    }
    @objc private func staleTapped() {
        Task {
            do {
                // Negative messages traverse REAL WKScriptMessageHandler. They are
                // separate fault injections, never substituted for render evidence.
                _ = try await session.webView?.evaluateJavaScript("""
                (() => { const token = new URLSearchParams(location.search).get('samplingSession');
                  const send = body => window.webkit.messageHandlers.flashnest.postMessage(body);
                  send({type:'samplingStatus',session:'stale-token',sequence:999999,status:'unknown'});
                  send({type:'samplingStatus',session:token,sequence:1,status:'unknown'});
                  send({type:'diagnostic',message:'SAMPLING_STALE_BARRIER'}); return true; })()
                """)
            } catch { failure = "WK stale message injection failed" }
            await snapshot()
        }
    }
    @objc private func reloadTapped() { session.webView?.reload() }
    @objc private func failTapped() {
        guard let web = session.webView, let url = web.url, var parts = URLComponents(url: url, resolvingAgainstBaseURL: false) else { return }
        parts.queryItems = (parts.queryItems ?? []) + [URLQueryItem(name: "nativeSamplingFail", value: "1")]
        if let target = parts.url { web.load(URLRequest(url: target)) }
    }
}

private struct SamplingSettingsPanel: View {
    @ObservedObject var session: PlayerSession
    let package: GamePackage
    @Environment(\.dismiss) var dismiss
    @State private var selected = RenderSamplingSettings()
    var body: some View {
        NavigationStack {
            PlayerSamplingSettingsView(selection: selected, requested: session.requestedSamplingSettings,
                applied: session.appliedSamplingStatus, failure: nil) { mode in
                    let settings = RenderSamplingSettings(mode: mode)
                    if settings.save(for: package.id) { selected = settings }
                }.toolbar { ToolbarItem(placement: .topBarLeading) { Button("Done") { dismiss() }.accessibilityIdentifier("sampling-done") } }
        }.onAppear { selected = RenderSamplingSettings.load(for: package.id) }
    }
}

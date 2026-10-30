import UIKit
import SwiftUI
import WebKit

// Disposable simulator host; original import, session, shell, renderer and runtime chain.
@MainActor enum NativeSamplingProbe {
    static var navigationEvents: [String] = []
    static var sceneRecords: [[String: Any]] = []
    static var overflow = false
    static var traceSuppressed = false
    static var terminated = false
    static var terminatedAt: Double?
    static func record(_ event: String) {
        if navigationEvents.count < 32 { navigationEvents.append(event) } else { overflow = true }
    }
    static func recordTrace(_ value: String) {
        if value.hasPrefix("Web process terminated:") {
            terminated = true; terminatedAt = ProcessInfo.processInfo.systemUptime
        }
        if value.hasPrefix("SWF trace limit:") || value.hasPrefix("SWF 跟踪限流：") { traceSuppressed = true }
        let prefix = "SWF: SCENE_PHASE "
        guard value.hasPrefix(prefix) else { return }
        let raw = String(value.dropFirst(prefix.count))
        guard raw.utf8.count <= 2048, sceneRecords.count < 64,
              let data = raw.data(using: .utf8),
              let phase = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else { overflow = true; return }
        sceneRecords.append(["nativeUptimeSeconds": ProcessInfo.processInfo.systemUptime, "phase": phase])
    }
    static func initialURL(_ url: URL) -> URL { url } // No redirect, quality override or forced policy.
    static var script: WKUserScript {
        let url = Bundle.main.url(forResource: "sampling-probe", withExtension: "js")!
        return WKUserScript(source: try! String(contentsOf: url), injectionTime: .atDocumentStart, forMainFrameOnly: true)
    }
}
enum NativeSamplingTransport { static func response(target: String) -> Data? { nil } }

@main @MainActor final class SamplingHostApp: UIResponder, UIApplicationDelegate {
    var window: UIWindow?
    let controller = SceneLoaderHostController()
    func application(_ application: UIApplication, didFinishLaunchingWithOptions options: [UIApplication.LaunchOptionsKey: Any]? = nil) -> Bool {
        let window = UIWindow(frame: UIScreen.main.bounds)
        window.rootViewController = controller; window.makeKeyAndVisible(); self.window = window
        return true
    }
}

@MainActor final class SceneLoaderHostController: UIViewController {
    private let root = FileManager.default.temporaryDirectory.appendingPathComponent("scene-control-" + UUID().uuidString)
    lazy var session = PlayerSession(saveStore: SaveStore(root: root.appendingPathComponent("saves")),
                                    incidentStore: LastSessionDiagnostics(root: root.appendingPathComponent("incidents")))
    private let content = UIView(), evidence = UILabel(), snapshotButton = UIButton(type: .system), transitionButton = UIButton(type: .system)
    private var identity: [String: Any] = [:]
    private var fixtureCase = "", failure = ""
    private var request = 0, epoch = 0
    private var transitionCount = 0
    private var transitionAt: Double?
    private weak var initialWeb: WKWebView?
    private var webIDs: [ObjectIdentifier: Int] = [:]
    private var cachedJS: [String: Any] = [:]
    private var jsCompletedForRequest = 0
    private var jsPending = false
    override var supportedInterfaceOrientations: UIInterfaceOrientationMask { .portrait }
    override func viewDidLoad() {
        super.viewDidLoad();view.backgroundColor = .black
        if let url = Bundle.main.url(forResource: "SamplingIdentity", withExtension: "json"),
           let data = try? Data(contentsOf: url), let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any] { identity = object }
        snapshotButton.setTitle("Snapshot", for: .normal);snapshotButton.accessibilityIdentifier = "scene-snapshot"
        snapshotButton.addTarget(self, action: #selector(snapshotTapped), for: .touchUpInside)
        transitionButton.setTitle("One scene transition",for: .normal);transitionButton.accessibilityIdentifier = "scene-transition"
        transitionButton.addTarget(self,action: #selector(transitionTapped),for: .touchUpInside)
        evidence.isAccessibilityElement = true;evidence.accessibilityIdentifier = "scene-evidence";evidence.accessibilityValue = "{}"
        evidence.font = .systemFont(ofSize: 1);evidence.text = "Scene evidence"
        for child in [snapshotButton,transitionButton,evidence,content] { child.translatesAutoresizingMaskIntoConstraints = false;view.addSubview(child) }
        NSLayoutConstraint.activate([
            snapshotButton.topAnchor.constraint(equalTo: view.safeAreaLayoutGuide.topAnchor),snapshotButton.leadingAnchor.constraint(equalTo: view.leadingAnchor),snapshotButton.trailingAnchor.constraint(equalTo: view.trailingAnchor),snapshotButton.heightAnchor.constraint(equalToConstant: 36),
            transitionButton.topAnchor.constraint(equalTo: snapshotButton.bottomAnchor),transitionButton.leadingAnchor.constraint(equalTo: view.leadingAnchor),transitionButton.trailingAnchor.constraint(equalTo: view.trailingAnchor),transitionButton.heightAnchor.constraint(equalToConstant: 36),
            evidence.topAnchor.constraint(equalTo: transitionButton.bottomAnchor),evidence.leadingAnchor.constraint(equalTo: view.leadingAnchor),evidence.trailingAnchor.constraint(equalTo: view.trailingAnchor),evidence.heightAnchor.constraint(equalToConstant: 1),
            content.topAnchor.constraint(equalTo: evidence.bottomAnchor),content.leadingAnchor.constraint(equalTo: view.leadingAnchor),content.trailingAnchor.constraint(equalTo: view.trailingAnchor),content.bottomAnchor.constraint(equalTo: view.safeAreaLayoutGuide.bottomAnchor)])
        Task { await open() }
    }
    private func open() async {
        do {
            let args = ProcessInfo.processInfo.arguments
            guard let i = args.firstIndex(of: "--scene-case"),i+1 < args.count,["retain","drop"].contains(args[i+1]),
                  let base = Bundle.main.url(forResource: "SamplingFixtures",withExtension: nil) else { throw NSError(domain: "SceneHost",code: 1) }
            fixtureCase = args[i+1]
            let packages = root.appendingPathComponent("packages")
            var game = try PackageImporter(root: packages).stageAndCommit(base.appendingPathComponent("scene-cws/retention"))
            let entry = "main-"+fixtureCase+".swf"
            guard game.movies.contains(entry) else { throw NSError(domain: "SceneHost",code: 2) }
            game.selectedMovie = entry
            guard RenderSamplingSettings(mode: .original).save(for: game.id),RendererSettings(mode: .automatic).save(for: game.id) else { throw NSError(domain: "SceneHost",code: 3) }
            await session.start(package: game,contentRoot: packages.appendingPathComponent(game.id.uuidString).appendingPathComponent("content"))
            guard let web = session.webView else { throw NSError(domain: "SceneHost",code: 4) }
            initialWeb = web;epoch += 1;web.translatesAutoresizingMaskIntoConstraints = false;content.addSubview(web)
            NSLayoutConstraint.activate([web.leadingAnchor.constraint(equalTo: content.leadingAnchor),web.trailingAnchor.constraint(equalTo: content.trailingAnchor),web.topAnchor.constraint(equalTo: content.topAnchor),web.bottomAnchor.constraint(equalTo: content.bottomAnchor)])
            snapshot()
        } catch { failure = "Synthetic folder import or session start failed";snapshot() }
    }
    private func safe(_ text: String) -> String {
        var value = text
        for pattern in [#"(?i)\b(?:https?|file|wss?|flashnest)://[^\s\"'<>]+"#,#"\b[A-Za-z0-9_-]{32,}={0,2}\b"#] {
            if let regex = try? NSRegularExpression(pattern: pattern) {
                value = regex.stringByReplacingMatches(in: value,range: NSRange(value.startIndex...,in: value),withTemplate: "[redacted]")
            }
        }
        return String(value.prefix(1024))
    }
    @objc private func transitionTapped() {
        guard transitionCount == 0, session.webView != nil, session.webView === initialWeb else { return }
        transitionCount = 1;transitionAt = ProcessInfo.processInfo.systemUptime
        session.key("Space",down: true);session.key("Space",down: false)
        transitionButton.isEnabled = false;snapshot()
    }
    @objc private func snapshotTapped() { snapshot() }
    private func publish() {
        let web = session.webView
        var webID = 0
        if let web {
            let key = ObjectIdentifier(web)
            if webIDs[key] == nil && webIDs.count < 4 { webIDs[key] = webIDs.count+1 }
            webID = webIDs[key] ?? -1
        }
        let observedAt = ProcessInfo.processInfo.systemUptime
        let ready = session.status == L10n.text("Runtime ready") || session.status == L10n.text("Playing") || session.isLoaded
        var result: [String: Any] = ["schema":"flashnest-native-scene-snapshot-v1","case":fixtureCase,"identity":identity,
            "request":request,"transitionCount":transitionCount,"transitionAt":transitionAt.map { $0 as Any } ?? NSNull(),"epoch":epoch,"wkID":webID,"sameWK":web != nil && web === initialWeb,
            "screenBounds":[UIScreen.main.bounds.width,UIScreen.main.bounds.height],"viewport":[content.convert(content.bounds,to:nil).minX,content.convert(content.bounds,to:nil).minY,content.bounds.width,content.bounds.height],
            "nativeUptimeSeconds":observedAt,"observedUptimeSeconds":observedAt,"screenScale":UIScreen.main.scale,"os":UIDevice.current.systemVersion,
            "ready":ready,"loaded":session.isLoaded,"status":safe(session.status),"failure":safe(failure.isEmpty ? (session.failure ?? "") : failure),
            "terminated":NativeSamplingProbe.terminated,"terminatedAt":NativeSamplingProbe.terminatedAt.map { $0 as Any } ?? NSNull(),
            "asRecords":NativeSamplingProbe.sceneRecords,"asOverflow":NativeSamplingProbe.overflow,"traceSuppressed":NativeSamplingProbe.traceSuppressed,"navigationEvents":NativeSamplingProbe.navigationEvents,
            "jsPending":jsPending,"jsCompletedForRequest":jsCompletedForRequest,"measurement":cachedJS["measurement"] ?? NSNull(),"body":cachedJS["body"] ?? NSNull()]
        if cachedJS["probeError"] != nil { result["probeError"] = cachedJS["probeError"] }
        if let data = try? JSONSerialization.data(withJSONObject: result,options: [.sortedKeys]),data.count <= 60000 {
            evidence.accessibilityValue = String(decoding: data,as: UTF8.self)
        } else { evidence.accessibilityValue = "{\"schema\":\"flashnest-native-scene-evidence-overflow\"}" }
    }
    private func snapshot() {
        request += 1;publish() // Native state and termination survive an unresponsive JavaScript context.
        guard !jsPending,let web = session.webView else { return }
        jsPending = true;let attempt = request;publish()
        Task {
            do {
                let value = try await web.evaluateJavaScript("({measurement:window.__samplingNativeProbe?.measure() || null,body:window.__sceneBodyDiagnostic?.snapshot() || null})")
                if let object = value as? [String: Any] { cachedJS = object } else { cachedJS = ["probeError":"Observation result unavailable"] }
            } catch { cachedJS = ["probeError":"JavaScript observation unavailable"] }
            jsCompletedForRequest = attempt;jsPending = false;publish()
        }
    }
}

import CryptoKit
import Foundation
import UIKit
import WebKit

/// Standalone diagnostic host: no FlashNest App sources except the unchanged
/// loopback HTTP transport, no normal player policy changes and no user content.
@main @MainActor final class NativeAudioApp: UIResponder, UIApplicationDelegate {
    var window: UIWindow?
    func application(_ application: UIApplication, didFinishLaunchingWithOptions options: [UIApplication.LaunchOptionsKey: Any]?) -> Bool {
        let window = UIWindow(frame: UIScreen.main.bounds)
        window.rootViewController = NativeAudioController()
        window.makeKeyAndVisible()
        self.window = window
        return true
    }
}

@MainActor final class NativeAudioController: UIViewController, WKScriptMessageHandler, WKNavigationDelegate {
    private let status = UILabel()
    private let abort = UIButton(type: .system)
    private var webView: WKWebView?
    private var server: LoopbackServer?
    private var evidenceRoot: URL?
    private var files = Set<String>()
    private var retainedBytes = 0
    private var finishing = false
    private var watchdog: Task<Void, Never>?
    private var arm = "", mode = ""
    private var completedCases = 0
    private var nextEventSequence = 0
    private var nextReceiptOrdinal = 0
    private var midcaseChunks = 0
    private var lastCaseReceipt: [String: Any]?
    private var caseReceiptTasks: [Task<String?, Never>] = []
    private var diagnostics: [String] = []
    private var deadlineMS = 0.0
    private var startTime = Date()
    private enum DiagnosticError: Error { case invalid(String), javascriptDeadline }

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = .systemBackground
        status.text = "STARTING"
        status.accessibilityIdentifier = "audio-native-status"
        status.numberOfLines = 3
        status.font = .monospacedSystemFont(ofSize: 11, weight: .regular)
        status.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(status)
        abort.setTitle("Abort diagnostic", for: .normal)
        abort.accessibilityIdentifier = "audio-native-abort"
        abort.addTarget(self, action: #selector(abortRequested), for: .touchUpInside)
        abort.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(abort)
        NSLayoutConstraint.activate([
            status.topAnchor.constraint(equalTo: view.safeAreaLayoutGuide.topAnchor),
            status.leadingAnchor.constraint(equalTo: view.leadingAnchor, constant: 8),
            status.trailingAnchor.constraint(equalTo: view.trailingAnchor, constant: -8),
            status.heightAnchor.constraint(equalToConstant: 66),
            abort.topAnchor.constraint(equalTo: status.bottomAnchor),
            abort.leadingAnchor.constraint(equalTo: view.leadingAnchor, constant: 8),
            abort.heightAnchor.constraint(equalToConstant: 36)
        ])
        Task { await start() }
    }

    @objc private func abortRequested() {
        Task { await finish(passed: false, reason: "XCTest requested bounded diagnostic abort", payload: nil) }
    }

    private func require(_ value: Bool, _ reason: String) throws {
        if !value { throw DiagnosticError.invalid(reason) }
    }

    private func start() async {
        do {
            let environment = ProcessInfo.processInfo.environment
            arm = environment["AUDIO_ARM"] ?? ""
            mode = environment["AUDIO_MODE"] ?? ""
            try require(["baseline", "candidate"].contains(arm), "Invalid immutable runtime arm")
            try require(["normal", "start-first", "start-second", "synthetic-ended"].contains(mode), "Invalid bounded mode")
            let suite = try required(environment["AUDIO_SUITE"], "Missing suite UUID")
            try require(UUID(uuidString: suite) != nil, "Invalid suite UUID")
            deadlineMS = Double(environment["AUDIO_DEADLINE_MS"] ?? "") ?? 0
            let now = Date().timeIntervalSince1970 * 1000
            try require(deadlineMS > now && deadlineMS <= now + 600_000, "Missing/excessive global 10-minute deadline")
            let documents = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
            let directory = documents.appendingPathComponent("audio-native-evidence").appendingPathComponent(suite)
                .appendingPathComponent(arm + "-" + mode)
            try require(!FileManager.default.fileExists(atPath: directory.path), "Refusing evidence overwrite")
            try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
            evidenceRoot = directory
            let web = try required(Bundle.main.url(forResource: "Web", withExtension: nil), "Missing attested Web bundle")
            let manifest = try verifyBundle(web)
            try retain("identity.json", ["manifestSHA256": NativeAudioIdentity.manifestSHA256,
                "manifest": manifest, "systemVersion": UIDevice.current.systemVersion,
                "displayScale": UIScreen.main.scale, "mediaPolicy": "require-audio-and-video-user-action",
                "arm": arm, "mode": mode])
            let configuration = WKWebViewConfiguration()
            configuration.websiteDataStore = .nonPersistent()
            configuration.allowsInlineMediaPlayback = true
            configuration.mediaTypesRequiringUserActionForPlayback = [.audio, .video]
            let host: [String: Any] = ["deadlineMS": deadlineMS, "displayScale": UIScreen.main.scale,
                                      "manifestSHA256": NativeAudioIdentity.manifestSHA256]
            let json = String(decoding: try JSONSerialization.data(withJSONObject: host, options: [.sortedKeys]), as: UTF8.self)
            configuration.userContentController.addUserScript(WKUserScript(
                source: "Object.defineProperty(window,'__nativeAudioHost',{value:Object.freeze(\(json)),writable:false,configurable:false});",
                injectionTime: .atDocumentStart, forMainFrameOnly: true))
            configuration.userContentController.add(self, name: "audioLifecycle")
            let webView = WKWebView(frame: .zero, configuration: configuration)
            webView.navigationDelegate = self
            webView.translatesAutoresizingMaskIntoConstraints = false
            view.addSubview(webView)
            NSLayoutConstraint.activate([
                webView.topAnchor.constraint(equalTo: abort.bottomAnchor),
                webView.leadingAnchor.constraint(equalTo: view.leadingAnchor),
                webView.trailingAnchor.constraint(equalTo: view.trailingAnchor),
                webView.bottomAnchor.constraint(equalTo: view.safeAreaLayoutGuide.bottomAnchor)
            ])
            self.webView = webView
            // Separate diagnostic port and capability; the production server
            // implementation retains its 10-second start and 5-second drain bounds.
            let server = LoopbackServer(port: 28791, capability: UUID().uuidString.lowercased(), webRoot: web)
            self.server = server
            server.onDiagnostic = { [weak self] text in Task { @MainActor in
                guard let self else { return }
                if self.diagnostics.count < 64 { self.diagnostics.append(String(text.prefix(2048))) }
            } }
            try await server.start()
            var url = URLComponents(url: server.shellURL, resolvingAgainstBaseURL: false)!
            url.queryItems = [.init(name: "runtime", value: arm), .init(name: "mode", value: mode)]
            webView.load(URLRequest(url: url.url!))
            watchdog = Task { [weak self] in
                while !Task.isCancelled {
                    try? await Task.sleep(nanoseconds: 250_000_000)
                    guard let self, !Task.isCancelled else { return }
                    if Date().timeIntervalSince1970 * 1000 >= self.deadlineMS {
                        await self.finish(passed: false, reason: "Global 10-minute matrix deadline", payload: nil)
                        return
                    }
                }
            }
        } catch { await finish(passed: false, reason: "Host startup/attestation: \(error)", payload: nil) }
    }

    private func required<T>(_ value: T?, _ reason: String) throws -> T {
        guard let value else { throw DiagnosticError.invalid(reason) }
        return value
    }

    func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
        guard !finishing else { return }
        do {
            try require(message.frameInfo.isMainFrame && message.frameInfo.securityOrigin.host == "127.0.0.1" &&
                        message.frameInfo.securityOrigin.port == 28791, "Foreign script message")
            let body = try required(message.body as? [String: Any], "Invalid script envelope")
            try require(body["arm"] as? String == arm && body["mode"] as? String == mode, "Wrong runtime/mode envelope")
            switch body["type"] as? String {
            case "action":
                let token = try required(body["token"] as? String, "Missing action token")
                try require(token.count < 100 && !token.contains("\n"), "Invalid action token")
                status.text = "ACTION " + token
            case "busy": status.text = "BUSY"
            case "case-start":
                let cycle = try required(body["cycle"] as? Int, "Missing start cycle")
                try require(cycle == completedCases && cycle < (mode == "normal" ? 8 : 1), "Invalid start cycle")
                if let lastCaseReceipt {
                    let previous = try required(body["previousReceipt"] as? [String: Any], "Missing accepted previous receipt")
                    try require(NSDictionary(dictionary: previous).isEqual(to: lastCaseReceipt), "Wrong accepted previous receipt")
                } else { try require(body["previousReceipt"] is NSNull, "Unexpected initial receipt") }
                try retain("case-start-\(cycle).json", body)
                status.text = "LOADING"
            case "case", "event-chunk":
                let isChunk = body["type"] as? String == "event-chunk"
                let kind = isChunk ? "chunk" : "case"
                try require(nextReceiptOrdinal < 40 && (!isChunk || midcaseChunks < 32), "Evidence receipt/chunk cap")
                let config = try required(body["config"] as? [String: Any], "Missing case configuration")
                let cycle = try required(config["cycle"] as? Int, "Missing cycle")
                try require(cycle == completedCases && cycle < (mode == "normal" ? 8 : 1), "Duplicate/out-of-order case")
                let serialized = try required(body["caseJSON"] as? String, "Missing serialized case")
                let bytes = Data(serialized.utf8)
                try require(bytes.count > 0 && bytes.count <= 2 * 1024 * 1024, "Case byte bound")
                let expectedDigest = try required(body["sha256"] as? String, "Missing case digest")
                let actualDigest = SHA256.hash(data: bytes).map { String(format: "%02x", $0) }.joined()
                try require(expectedDigest == actualDigest, "Serialized case digest mismatch")
                let entry = try required(try JSONSerialization.jsonObject(with: bytes) as? [String: Any], "Invalid serialized case")
                try require(entry["type"] as? String == (isChunk ? "event-chunk" : "case") && entry["arm"] as? String == arm && entry["mode"] as? String == mode,
                            "Foreign serialized case")
                let entryConfig = try required(entry["config"] as? [String: Any], "Missing serialized configuration")
                try require(NSDictionary(dictionary: entryConfig).isEqual(to: config), "Serialized configuration mismatch")
                let window = try required(entry["eventWindow"] as? [String: Any], "Missing case event interval")
                try require(Set(window.keys) == ["kind", "ordinal", "token", "cycle", "start", "endExclusive", "count"], "Event interval schema")
                let token = try required(window["token"] as? String, "Missing receipt token")
                try require(window["kind"] as? String == kind && window["ordinal"] as? Int == nextReceiptOrdinal &&
                            token == "\(arm)/\(mode)/\(cycle)/\(kind)/\(nextReceiptOrdinal)", "Wrong receipt identity")
                let first = try required(window["start"] as? Int, "Missing event start")
                let end = try required(window["endExclusive"] as? Int, "Missing event end")
                let count = try required(window["count"] as? Int, "Missing event count")
                try require(window["cycle"] as? Int == cycle && first == nextEventSequence && end >= first &&
                            count == end - first && count <= 4096 && (!isChunk || count >= 1024), "Noncontiguous evidence interval")
                let evidence = try required(entry["evidence"] as? [String: Any], "Missing original case evidence")
                let audio = try required(evidence["audio"] as? [String: Any], "Missing original audio evidence")
                let events = try required(audio["events"] as? [[String: Any]], "Missing original events")
                try require(events.count == count && events.enumerated().allSatisfy { $0.element["seq"] as? Int == first + $0.offset },
                            "Case event sequence differs")
                let evidenceName = isChunk ? "event-chunk-\(nextReceiptOrdinal).json" : "case-\(cycle).json"
                let receiptName = isChunk ? "event-receipt-\(nextReceiptOrdinal).json" : "case-receipt-\(cycle).json"
                try retainBytes(evidenceName, bytes)
                let receipt: [String: Any] = ["kind": kind, "ordinal": nextReceiptOrdinal,
                    "token": token, "cycle": cycle, "start": first, "endExclusive": end,
                    "count": count, "bytes": bytes.count, "sha256": actualDigest]
                try retain(receiptName, receipt)
                lastCaseReceipt = receipt; nextEventSequence = end; nextReceiptOrdinal += 1
                if isChunk { midcaseChunks += 1 } else { completedCases += 1 }
                let receiptJSON = String(decoding: try JSONSerialization.data(withJSONObject: receipt, options: [.sortedKeys]), as: UTF8.self)
                let target = try required(webView, "Receipt target unavailable")
                caseReceiptTasks.append(Task { [weak self, weak target] in
                    guard let self, let target else { return "Receipt target retired" }
                    do {
                        let accepted = try await self.evaluate("window.__nativeAudioReceipt(\(receiptJSON))", in: target)
                        guard accepted as? Bool == true else { return "Case receipt not accepted" }
                        return nil
                    } catch { return "Case receipt delivery: \(error)" }
                })
            case "complete":
                let result = try required(body["result"] as? [String: Any], "Missing terminal result")
                let receiptMatches: Bool
                if let lastCaseReceipt, let terminalReceipt = body["lastReceipt"] as? [String: Any] {
                    receiptMatches = NSDictionary(dictionary: terminalReceipt).isEqual(to: lastCaseReceipt)
                } else { receiptMatches = lastCaseReceipt == nil && body["lastReceipt"] is NSNull }
                let passed = result["passed"] as? Bool == true && receiptMatches && completedCases == (mode == "normal" ? 8 : 1)
                // Original-fixture evidence only. Retain the exact terminal body in
                // XCTest as well as Documents; container lookup can fail after exit.
                // The full observer snapshot can exceed AX limits. Mirror only
                // exact result diagnostics and control geometry, with a full-body
                // digest/size; raw Documents remains the independent acceptance gate.
                var summary: [String: Any] = ["diagnosticOnly": true, "type": "complete",
                    "arm": arm, "mode": mode, "completedCases": completedCases]
                for key in ["passed", "error", "errorMessage", "errorStack", "cleanupError", "snapshotError", "tailSettlementError"] {
                    if let value = result[key] { summary[key] = value }
                }
                if let value = body["diagnosticContext"] { summary["diagnosticContext"] = value }
                if let bytes = try? JSONSerialization.data(withJSONObject: body, options: [.sortedKeys, .withoutEscapingSlashes]) {
                    summary["fullBodyBytes"] = bytes.count
                    summary["fullBodySHA256"] = SHA256.hash(data: bytes).map { String(format: "%02x", $0) }.joined()
                }
                if let bytes = try? JSONSerialization.data(withJSONObject: summary, options: [.sortedKeys, .withoutEscapingSlashes]),
                   bytes.count <= 131_072 {
                    status.accessibilityValue = redactDiagnosticURL(String(decoding: bytes, as: UTF8.self))
                } else {
                    status.accessibilityValue = "{\"terminalExportUnavailable\":true,\"maximumBytes\":131072}"
                }
                let detail = String(redactDiagnosticURL(result["error"] as? String ?? "missing/partial terminal result").prefix(2048))
                let reason = passed ? "Exact mode contract completed" : "Page contract failed/partial: " + detail
                Task { await finish(passed: passed, reason: reason, payload: body) }
            case "page-error": throw DiagnosticError.invalid("Page error: \(body["message"] ?? "unknown")")
            default: throw DiagnosticError.invalid("Unknown script message")
            }
        } catch { Task { await finish(passed: false, reason: "Evidence/bridge error: \(error)", payload: nil) } }
    }

    func webViewWebContentProcessDidTerminate(_ webView: WKWebView) {
        Task { await finish(passed: false, reason: "WebContent process terminated", payload: nil) }
    }
    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
        Task { await finish(passed: false, reason: "Navigation failed: \(error)", payload: nil) }
    }
    func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
        Task { await finish(passed: false, reason: "Navigation failed: \(error)", payload: nil) }
    }

    private func finish(passed initialPassed: Bool, reason: String, payload: [String: Any]?) async {
        guard !finishing else { return }
        finishing = true
        watchdog?.cancel()
        status.text = "DRAINING"
        var failures: [String] = []
        // Delivery callbacks have their original individual three-second bound.
        // A JS receipt may have been accepted before the native completion arrives.
        for task in caseReceiptTasks { if let reason = await task.value { failures.append(reason) } }
        if let payload { do { try retain("page-terminal.json", payload) } catch { failures.append("Terminal evidence: \(error)") } }
        if let webView {
            do {
                let snapshot = try await evaluate("(() => { window.nativeAudioEvidenceWindow.markFinalBoundary(); return JSON.stringify(window.snapshot()); })()", in: webView)
                let text = try required(snapshot as? String, "Final snapshot unavailable")
                try retain("host-final-snapshot.json", ["snapshotJSON": text])
            } catch { failures.append("Final snapshot: \(error)") }
            do {
                // The finite observation cutoff is this final status read followed
                // synchronously by hook restoration, not a claim about future GC.
                let result = try await evaluate("(() => { const status=window.nativeAudioEvidenceWindow.status(); window.restoreNativeAudioObservation(); return JSON.stringify(status); })()", in: webView)
                let text = try required(result as? String, "Final window status unavailable")
                let window = try required(try JSONSerialization.jsonObject(with: Data(text.utf8)) as? [String: Any], "Invalid final window status")
                try retain("host-final-window.json", window)
                let end = try required(window["endExclusive"] as? Int, "Missing final event end")
                try require(window["overflow"] as? Bool == false && window["receiptPending"] as? Bool == false &&
                            window["postFinalActivity"] as? Int == 0 && window["finalBoundary"] as? Int == end,
                            "Late activity after final snapshot or incomplete event window")
            } catch { failures.append("Final evidence cutoff: \(error)") }
            do { _ = try await evaluate("window.dispose?.(); true", in: webView) }
            catch { failures.append("Page cleanup: \(error)") }
            webView.configuration.userContentController.removeScriptMessageHandler(forName: "audioLifecycle")
            webView.navigationDelegate = nil
            webView.stopLoading()
            webView.removeFromSuperview()
            self.webView = nil
        }
        var drained = server == nil
        if let server {
            do { try await server.stopAndWait(); drained = true }
            catch { failures.append("Server drain: \(error)") }
        }
        server = nil
        let passed = initialPassed && failures.isEmpty && drained
        do {
            try retain("host-summary.json", ["passed": passed, "reason": reason, "failures": failures,
                "arm": arm, "mode": mode, "completedCases": completedCases,
                "midcaseChunks": midcaseChunks, "receiptCount": nextReceiptOrdinal,
                "serverDrained": drained, "manifestSHA256": NativeAudioIdentity.manifestSHA256,
                "systemVersion": UIDevice.current.systemVersion, "diagnostics": diagnostics,
                "elapsedSeconds": Date().timeIntervalSince(startTime),
                "scope": "Observable handler/Promise lifecycle only, not GC, RAM, speaker output or phone crash causality"])
        } catch {
            status.text = "FAIL evidence-write"
            return
        }
        status.text = passed ? "DONE \(arm)/\(mode)/\(completedCases)" : "FAIL \(arm)/\(mode): \(reason) \(failures.joined(separator: "; "))"
    }

    // Callback and deadline settle on MainActor. A late callback cannot resume
    // twice, and task cancellation alone is not mistaken for a WebKit deadline.
    private func evaluate(_ script: String, in view: WKWebView) async throws -> Any {
        try await withCheckedThrowingContinuation { (continuation: CheckedContinuation<Any, Error>) in
            var completed = false
            view.evaluateJavaScript(script) { value, error in Task { @MainActor in
                guard !completed else { return }; completed = true
                if let error { continuation.resume(throwing: error) }
                else { continuation.resume(returning: value ?? NSNull()) }
            } }
            Task { @MainActor in
                try? await Task.sleep(nanoseconds: 3_000_000_000)
                guard !completed else { return }; completed = true
                continuation.resume(throwing: DiagnosticError.javascriptDeadline)
            }
        }
    }

    private func redactDiagnosticURL(_ value: String) -> String {
        guard let server else { return value }
        let prefix = server.shellURL.deletingLastPathComponent().deletingLastPathComponent().absoluteString
        return value.replacingOccurrences(of: prefix, with: server.origin.absoluteString + "/<capability>/")
    }

    private func retain(_ name: String, _ body: [String: Any]) throws {
        let data = try JSONSerialization.data(withJSONObject: body, options: [.prettyPrinted, .sortedKeys])
        try retainBytes(name, data)
    }

    private func retainBytes(_ name: String, _ data: Data) throws {
        let root = try required(evidenceRoot, "Evidence directory unavailable")
        try require(!name.contains("/") && !name.contains("..") && !files.contains(name) && files.count < 93, "Duplicate/unsafe evidence name")
        try require(data.count <= 2 * 1024 * 1024 && retainedBytes + data.count <= 16 * 1024 * 1024, "Evidence byte limit")
        let file = root.appendingPathComponent(name)
        try data.write(to: file, options: [.atomic])
        retainedBytes += data.count; files.insert(name)
        let attributes = try FileManager.default.attributesOfItem(atPath: file.path)
        try require(attributes[.size] as? Int == data.count, "Persisted evidence size mismatch")
        let handle = try FileHandle(forReadingFrom: file)
        defer { try? handle.close() }
        let readback = try handle.read(upToCount: 2 * 1024 * 1024 + 1) ?? Data()
        try require(readback == data, "Persisted evidence readback mismatch")
    }

    private func verifyBundle(_ root: URL) throws -> [String: Any] {
        let manifestURL = root.appendingPathComponent("native-manifest.json")
        try require(try sha(manifestURL) == NativeAudioIdentity.manifestSHA256, "Bundle manifest differs from compiled pin")
        let manifest = try required(try JSONSerialization.jsonObject(with: Data(contentsOf: manifestURL)) as? [String: Any], "Invalid manifest")
        try require(manifest["schemaVersion"] as? Int == 1, "Unsupported native manifest")
        try require(manifest["adapterScope"] as? String == "canvas-audio-only", "Wrong native adapter scope")
        try require(manifest["eventWindowProtocol"] as? Int == 2, "Missing native event-window protocol")
        let files = try required(manifest["files"] as? [String: [String: Any]], "Missing exact inventory")
        let keys: Set<URLResourceKey> = [.isDirectoryKey, .isRegularFileKey, .isSymbolicLinkKey, .fileSizeKey]
        let rootType = try root.resourceValues(forKeys: keys)
        try require(rootType.isDirectory == true && rootType.isSymbolicLink != true, "Invalid bundle directory")
        let enumerator = try required(FileManager.default.enumerator(at: root, includingPropertiesForKeys: Array(keys)), "Cannot enumerate bundle")
        var observed = Set<String>()
        let prefix = root.standardizedFileURL.path + "/"
        for case let url as URL in enumerator {
            let type = try url.resourceValues(forKeys: keys)
            try require(type.isSymbolicLink != true, "Bundled symlink")
            if type.isDirectory == true { continue }
            try require(type.isRegularFile == true && url.standardizedFileURL.path.hasPrefix(prefix), "Invalid bundle file")
            let relative = String(url.standardizedFileURL.path.dropFirst(prefix.count))
            if relative == "native-manifest.json" { continue }
            let row = try required(files[relative], "Unlisted bundle file")
            let bytes = try required(row["bytes"] as? Int, "Invalid file size")
            let digest = try required(row["sha256"] as? String, "Missing file digest")
            let actualDigest = try sha(url)
            try require(type.fileSize == bytes && bytes >= 0 && actualDigest == digest, "Bundled file differs: \(relative)")
            observed.insert(relative)
        }
        try require(observed == Set(files.keys), "Missing bundled files")
        return manifest
    }
    private func sha(_ file: URL) throws -> String {
        let handle = try FileHandle(forReadingFrom: file)
        defer { try? handle.close() }
        var digest = SHA256()
        while let data = try handle.read(upToCount: 1_048_576), !data.isEmpty { digest.update(data: data) }
        return digest.finalize().map { String(format: "%02x", $0) }.joined()
    }
}

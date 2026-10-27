import Foundation
import WebKit
import SwiftUI

@MainActor final class PlayerSession: NSObject, ObservableObject, WKNavigationDelegate, WKScriptMessageHandler {
    @Published var status = L10n.text("Starting local player…")
    @Published private(set) var isLoaded = false
    @Published var failure: String?
    @Published var diagnostics: [String] = []
    @Published private(set) var previousSessionDiagnostic: String?
    private let incidentStore: LastSessionDiagnostics
    @Published var paused = false
    @Published var webView: WKWebView?
    private var server: LoopbackServer?
    private var generation = UUID()
    private(set) var activeRenderSettings: RenderSettings?
    private var renderSettingsPackageID: UUID?
    private var ready = false
    private var processTerminated = false
    @Published private(set) var saveFailure: String?
    @Published private(set) var saveReady = false
    @Published private(set) var restartRequired = false
    private let saveStore: SaveStore
    private var currentPackage: GamePackage?
    private var currentContentRoot: URL?
    private var saveTask: Task<Bool, Never>?
    private static var activePackageIDs = Set<UUID>()
    // An unconfirmed old page may still flush later. Keep the affected profile
    // closed for this process; app restart terminates the uncertain old page.
    private static var blockedPackageIDs = Set<UUID>()
    private var ownsPackageLease = false
    private var pendingRestoreID: UUID?
    private var preserveNativeOnEmptyCapture = false
    private var memoryWarningObserver: NSObjectProtocol?
    private var memoryWarningCount = 0
    private var lastMemoryWarning: Date?

    init(saveStore: SaveStore = SaveStore(), incidentStore: LastSessionDiagnostics? = nil) {
        self.saveStore = saveStore
        self.incidentStore = incidentStore ?? LastSessionDiagnostics()
        super.init()
        memoryWarningObserver = NotificationCenter.default.addObserver(
            forName: UIApplication.didReceiveMemoryWarningNotification, object: nil, queue: .main) { [weak self] _ in
                Task { @MainActor [weak self] in self?.recordHostMemoryWarning() }
            }
    }

    deinit {
        if let memoryWarningObserver { NotificationCenter.default.removeObserver(memoryWarningObserver) }
    }

    // Host-app evidence only. WebContent is a separate process and warnings are
    // best effort: zero warnings does NOT establish that memory was sufficient.
    func recordHostMemoryWarning() {
        guard webView != nil, !processTerminated else { return }
        memoryWarningCount = min(memoryWarningCount + 1, 999)
        lastMemoryWarning = Date()
        if memoryWarningCount <= 10 { record("Host app memory warning: count=\(memoryWarningCount); WebContent cause remains unknown") }
    }

    func start(package: GamePackage, contentRoot: URL, storageOnly: Bool = false) async {
        guard server == nil else { return }
        currentPackage = package; currentContentRoot = contentRoot
        previousSessionDiagnostic = incidentStore.latest(for: package.id)?.summary
        guard !Self.blockedPackageIDs.contains(package.id) else {
            restartRequired = true
            failure = L10n.text("Saving did not finish safely. Close and reopen FlashNest before opening this game again.")
            saveFailure = failure
            return
        }
        restartRequired = false
        guard !Self.activePackageIDs.contains(package.id) else {
            failure = L10n.text("This game is already open.")
            return
        }
        Self.activePackageIDs.insert(package.id)
        ownsPackageLease = true
        currentPackage = package; currentContentRoot = contentRoot
        // Snapshot once per opened game, not on foreground/save-panel restart.
        // A preference edit never changes the live movie's coordinate system.
        if !storageOnly, activeRenderSettings == nil || renderSettingsPackageID != package.id {
            activeRenderSettings = RenderSettings.load(for: package.id)
            renderSettingsPackageID = package.id
        }
        pendingRestoreID = nil
        saveReady = false; saveFailure = nil; processTerminated = false
        memoryWarningCount = 0; lastMemoryWarning = nil
        let attempt = UUID()
        generation = attempt
        ready = false; isLoaded = false; paused = false; failure = nil; status = L10n.text("Starting local player…")
        do {
            guard let webRoot = Bundle.main.url(forResource: "Web", withExtension: nil),
                  FileManager.default.fileExists(atPath: webRoot.appendingPathComponent("runtime/ruffle.js").path) else {
                throw PackageError.corrupt("Bundled Ruffle runtime is missing. Rebuild with the pinned runtime preparation script.")
            }
            let defaults = UserDefaults.standard
            let port: UInt16
            if let saved = defaults.object(forKey: "loopbackPort") as? Int, (20000...60000).contains(saved) { port = UInt16(saved) }
            else { port = UInt16.random(in: 20000...60000); defaults.set(Int(port), forKey: "loopbackPort") }
            let capability = defaults.string(forKey: "loopbackCapability") ?? UUID().uuidString.replacingOccurrences(of: "-", with: "") + UUID().uuidString.replacingOccurrences(of: "-", with: "")
            defaults.set(capability.lowercased(), forKey: "loopbackCapability")
            let local = LoopbackServer(port: port, capability: capability.lowercased(), webRoot: webRoot)
            local.onDiagnostic = { [weak self] message in Task { @MainActor in self?.record(message) } }
            local.activate(packageID: package.id, root: contentRoot)
            server = local
            try await local.start()
            guard generation == attempt else { local.stop(); return }
            let controller = WKUserContentController()
            let store = saveStore
            // Missing current.json is NOT an empty save: preserve legacy WK data.
            if !storageOnly, let snapshot = try await Task.detached(priority: .userInitiated, operation: {
                try store.currentSnapshot(packageID: package.id)
            }).value {
                guard generation == attempt else { local.stop(); return }
                let capture = SaveCapture(version: 1, entries: snapshot.entries.map {
                    SaveEntry(scope: $0.scope, key: $0.key, value: $0.value)
                })
                let encoded = try JSONEncoder().encode(capture)
                let literal = String(decoding: encoded, as: UTF8.self)
                let mode = snapshot.restoreRequired == true ? "replace" : "ifEmpty"
                if snapshot.restoreRequired == true { pendingRestoreID = snapshot.id }
                controller.addUserScript(WKUserScript(
                    source: "window.__FlashNestRestore = " + literal + "; window.__FlashNestRestorePolicy = '" + mode + "';",
                    injectionTime: .atDocumentStart, forMainFrameOnly: true))
            }
            controller.add(self, name: "flashnest")
            let configuration = WKWebViewConfiguration()
            configuration.userContentController = controller
            // A URL path is not a storage boundary: Flash SharedObjects may use
            // localPath="/". Give each package an isolated, persistent profile.
            configuration.websiteDataStore = PackageWebKitProfiles.shared.store(for: package.id, retaining: Self.activePackageIDs)
            configuration.allowsInlineMediaPlayback = true
            configuration.mediaTypesRequiringUserActionForPlayback = [.audio, .video]
            // Block remote subresources; permit same-origin blobs and inert data media alongside CSP.
            let host = "^http://127\\.0\\.0\\.1:\(port)/"
            let rules: [[String: Any]] = [
                ["trigger": ["url-filter": ".*"], "action": ["type": "block"]],
                ["trigger": ["url-filter": host], "action": ["type": "ignore-previous-rules"]],
                ["trigger": ["url-filter": "^blob:" + String(host.dropFirst())], "action": ["type": "ignore-previous-rules"]],
                ["trigger": ["url-filter": "^data:", "resource-type": ["image", "media", "font"]], "action": ["type": "ignore-previous-rules"]]
            ]
            let encoded = try JSONSerialization.data(withJSONObject: rules)
            let ruleList: WKContentRuleList = try await withCheckedThrowingContinuation { continuation in
                WKContentRuleListStore.default().compileContentRuleList(
                    forIdentifier: "FlashNestOffline-\(port)", encodedContentRuleList: String(decoding: encoded, as: UTF8.self)) { list, error in
                    if let error { continuation.resume(throwing: error) }
                    else if let list { continuation.resume(returning: list) }
                    else { continuation.resume(throwing: PackageError.corrupt("Offline content policy could not be installed")) }
                }
            }
            guard generation == attempt else { local.stop(); return }
            controller.add(ruleList)
            let view = WKWebView(frame: .zero, configuration: configuration)
            view.navigationDelegate = self
            view.isOpaque = false
            view.backgroundColor = .black
            view.scrollView.isScrollEnabled = false
            webView = view
            var components = URLComponents(url: local.shellURL, resolvingAgainstBaseURL: false)!
            components.queryItems = [URLQueryItem(name: "entry", value: package.selectedMovie), URLQueryItem(name: "package", value: package.id.uuidString), URLQueryItem(name: "language", value: L10n.languageCode)]
            components.queryItems?.append(URLQueryItem(name: "nativeSaveHandshake", value: "1"))
            if storageOnly { components.queryItems?.append(URLQueryItem(name: "storageOnly", value: "1")) }
            else if activeRenderSettings?.usesHalfResolution == true {
                components.queryItems?.append(URLQueryItem(name: "renderMode", value: "half"))
            }
            guard let url = components.url else { throw PackageError.invalidPath(package.selectedMovie) }
            view.load(URLRequest(url: url))
        } catch {
            guard generation == attempt else { return }
            record(error.localizedDescription)
            failure = L10n.error(error)
            stop()
        }
    }

    func stop() {
        generation = UUID()
        isLoaded = false; saveReady = false
        if ownsPackageLease, let id = currentPackage?.id { Self.activePackageIDs.remove(id) }
        ownsPackageLease = false
        webView?.evaluateJavaScript("window.FlashNest?.releaseKeys(); window.FlashNest?.pause(); true")
        webView?.stopLoading()
        webView?.configuration.userContentController.removeScriptMessageHandler(forName: "flashnest")
        webView?.navigationDelegate = nil
        webView = nil
        server?.stop(); server = nil
    }

    func releaseAllKeys() {
        webView?.evaluateJavaScript("window.FlashNest?.releaseKeys(); true")
    }

    /// Explicit discard/emergency cleanup only; normal exits use closeAndSave.
    func closeWithoutSaving() async throws {
        if let task = saveTask { _ = await task.value }
        let closingServer = server
        stop()
        try await closingServer?.stopAndWait()
    }

    /// Destroy Ruffle to flush SharedObjects, then atomically save a verified
    /// capture. No timeout/error path writes an empty replacement.
    func closeAndSave() async -> Bool {
        if let task = saveTask { return await task.value }
        let task = Task { @MainActor [self] in
            let result = await captureAndPersistIfReady()
            let closingServer = server
            stop()
            do { try await closingServer?.stopAndWait() }
            catch {
                saveFailure = L10n.text("The local player did not finish closing. Please reopen the app.")
                return false
            }
            return result
        }
        saveTask = task
        let result = await task.value
        saveTask = nil
        return result
    }

    private func captureAndPersistIfReady() async -> Bool {
        // A terminated page cannot provide a trustworthy final capture. Never
        // turn process loss into an empty replacement of an existing archive.
        guard !processTerminated else { return false }
        guard let view = webView, let package = currentPackage else { return saveFailure == nil }
        guard saveReady else {
            // No game starts before saveReady. Closing during bootstrap must
            // not clobber an existing native/legacy save with an empty value.
            return true
        }
        releaseAllKeys()
        var shutdownConfirmed = false
        do {
            let object = try await captureObject(from: view)
            guard !processTerminated else { return false }
            shutdownConfirmed = true
            let data = try JSONSerialization.data(withJSONObject: object)
            guard data.count <= SaveStore.maximumArchiveBytes else { throw SaveStoreError.limit("archive size") }
            let capture = try JSONDecoder().decode(SaveCapture.self, from: data)
            if preserveNativeOnEmptyCapture, capture.entries.isEmpty {
                // A storage-only browse must not mistake a missing/evicted WK
                // profile for a game intentionally clearing its save.
                return true
            }
            let store = saveStore
            _ = try await Task.detached(priority: .userInitiated) {
                try store.persistLatest(capture, package: package)
            }.value
            saveFailure = nil
            return true
        } catch {
            // WebKit errors may contain capability URLs; display only a
            // stable local message and retain all previous native snapshots.
            if processTerminated {
                // WebKit confirmed the old process is gone: unlike an unknown
                // flush timeout, there is no old page to quarantine across retry.
                saveFailure = L10n.text("The web player stopped. Previous saves were kept, but unsaved progress may be lost.")
            } else if !shutdownConfirmed {
                persistIncident(.unconfirmedSaveFlush)
                Self.blockedPackageIDs.insert(package.id)
                restartRequired = true
                saveFailure = L10n.text("Saving did not finish safely. Close and reopen FlashNest before opening this game again.")
            } else {
                persistIncident(.nativeSaveWriteFailed)
                saveFailure = L10n.text("Save could not be completed. Previous backups were kept.")
            }
            return false
        }
    }

    private func captureObject(from view: WKWebView) async throws -> Any {
        try await SaveWebKitBridge.capture(from: view)
    }

    func suspendAndSave() async {
        let background = UIApplication.shared.beginBackgroundTask(withName: "FlashNest save", expirationHandler: nil)
        defer { if background != .invalid { UIApplication.shared.endBackgroundTask(background) } }
        _ = await closeAndSave()
    }

    func resumeAfterSuspension(allowingSaveFailure: Bool = false) async {
        if let task = saveTask { _ = await task.value }
        guard allowingSaveFailure || saveFailure == nil else { return }
        guard server == nil, let package = currentPackage, let root = currentContentRoot else { return }
        await start(package: package, contentRoot: root)
    }

    /// Captures a legacy persistent profile without starting the movie. Call
    /// before import if no current.json exists, so overwrite has a real backup.
    static func preserveLegacySave(package: GamePackage, store: SaveStore = SaveStore(), forceCaptureLive: Bool = false) async throws {
        guard !blockedPackageIDs.contains(package.id) else { throw SaveStoreError.invalid("app restart required after unconfirmed save flush") }
        guard !activePackageIDs.contains(package.id) else { throw SaveStoreError.invalid("game is still open") }
        // A confirmed import not yet applied is authoritative; do not replace
        // it with the target profile's older live values during backup/export.
        if !forceCaptureLive, try store.currentSnapshot(packageID: package.id)?.restoreRequired == true { return }
        let session = PlayerSession(saveStore: store)
        let prior = try store.currentSnapshot(packageID: package.id)
        session.preserveNativeOnEmptyCapture = !forceCaptureLive && prior?.entries.isEmpty == false
        let root = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("Packages").appendingPathComponent(package.id.uuidString).appendingPathComponent("content")
        await session.start(package: package, contentRoot: root, storageOnly: true)
        defer { session.stop() }
        let deadline = Date().addingTimeInterval(15)
        while !session.saveReady, session.failure == nil, Date() < deadline {
            try await Task.sleep(nanoseconds: 100_000_000)
        }
        guard session.saveReady, await session.closeAndSave() else {
            throw SaveStoreError.invalid("existing game save could not be preserved")
        }
    }

    static func clearPackageCaches(packageID: UUID) async throws {
        guard !activePackageIDs.contains(packageID) else { throw SaveStoreError.invalid("game is still open") }
        let profile = PackageWebKitProfiles.shared.store(for: packageID, retaining: activePackageIDs)
        try await withCheckedThrowingContinuation { (continuation: CheckedContinuation<Void, Error>) in
            var completed = false
            profile.removeData(ofTypes: [WKWebsiteDataTypeDiskCache, WKWebsiteDataTypeMemoryCache,
                                         WKWebsiteDataTypeOfflineWebApplicationCache], modifiedSince: .distantPast) {
                Task { @MainActor in
                    guard !completed else { return }
                    completed = true
                    continuation.resume()
                }
            }
            Task { @MainActor in
                try? await Task.sleep(nanoseconds: 15_000_000_000)
                guard !completed else { return }
                completed = true
                continuation.resume(throwing: SaveStoreError.invalid("temporary cache cleanup timed out; game copy retained"))
            }
        }
    }

    static func preparePackageRemoval(package: GamePackage) async throws {
        // Refresh legacy/live data unless an already-confirmed pending import
        // is authoritative. Native save directories are never deleted here.
        try await preserveLegacySave(package: package)
        try await clearPackageCaches(packageID: package.id)
    }

    func setPaused(_ value: Bool) {
        paused = value
        guard ready else { return }
        webView?.evaluateJavaScript(value ? "window.FlashNest?.pause()" : "window.FlashNest?.resume()")
    }

    func key(_ code: String, down: Bool) {
        guard let data = try? JSONEncoder().encode(code), let literal = String(data: data, encoding: .utf8) else { return }
        webView?.evaluateJavaScript("window.FlashNest?.key(\(literal), \(down ? "true" : "false"))")
    }

    func clearPreviousSessionDiagnostic() {
        guard let id = currentPackage?.id else { return }
        do {
            try incidentStore.clear(for: id)
            previousSessionDiagnostic = nil
        } catch {
            record("Diagnostic metadata could not be cleared")
        }
    }

    private func persistIncident(_ event: LastSessionDiagnostic.Event) {
        guard let id = currentPackage?.id else { return }
        let incident = LastSessionDiagnostic(event: event, date: Date(), loaded: isLoaded,
            ready: ready, paused: paused, saveReady: saveReady, saving: saveTask != nil,
            retainedProfiles: min(PackageWebKitProfiles.shared.retainedCount, 1024),
            memoryWarningCount: memoryWarningCount, lastMemoryWarning: lastMemoryWarning)
        previousSessionDiagnostic = incident.summary
        do { try incidentStore.record(incident, for: id) }
        catch { record("Diagnostic metadata could not be retained") }
    }

    private func record(_ message: String) {
        diagnostics.append(String(L10n.detail(message).prefix(500)))
        if diagnostics.count > 60 { diagnostics.removeFirst(diagnostics.count - 60) }
    }

    func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
        guard !processTerminated, message.frameInfo.isMainFrame,
              let current = message.frameInfo.request.url, let shell = server?.shellURL,
              current.scheme == shell.scheme, current.host == shell.host, current.port == shell.port,
              current.path == shell.path,
              let body = message.body as? [String: Any], let type = body["type"] as? String else { return }
        let text = String((body["message"] as? String ?? "").prefix(500))
        switch type {
        case "saveReady":
            let attempt = generation
            Task { @MainActor [weak self] in
                guard let self, self.generation == attempt, let view = self.webView else { return }
                do {
                    if let snapshotID = self.pendingRestoreID, let package = self.currentPackage {
                        let store = self.saveStore
                        try await Task.detached(priority: .userInitiated) {
                            try store.markRestoreApplied(packageID: package.id, snapshotID: snapshotID)
                        }.value
                    }
                    guard self.generation == attempt else { return }
                    self.pendingRestoreID = nil
                    _ = try await view.evaluateJavaScript("window.FlashNest.confirmSaveReady(); true")
                    guard self.generation == attempt else { return }
                    self.saveReady = true
                } catch {
                    guard self.generation == attempt else { return }
                    self.saveFailure = L10n.text("Save restoration could not be confirmed. The game was not started.")
                    self.failure = self.saveFailure
                    self.stop()
                }
            }
        case "ready": status = L10n.text("Runtime ready"); ready = true; if paused { setPaused(true) }
        case "loaded": status = L10n.text("Playing"); ready = true; isLoaded = true
        case "error": failure = text
        case "diagnostic": record(text)
        default: break
        }
    }

    func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction,
                 decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        guard let url = navigationAction.request.url, let shell = server?.shellURL,
              url.scheme == shell.scheme, url.host == shell.host, url.port == shell.port,
              url.path == shell.path, navigationAction.targetFrame?.isMainFrame == true else {
            record(L10n.text("Blocked navigation outside the bundled player"))
            decisionHandler(.cancel); return
        }
        decisionHandler(.allow)
    }
    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) { record(error.localizedDescription); failure = L10n.error(error) }
    func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) { record(error.localizedDescription); failure = L10n.error(error) }
    func webViewWebContentProcessDidTerminate(_ webView: WKWebView) {
        guard self.webView === webView, !processTerminated else { return }
        // Public WebKit callback supplies no termination reason. Record only
        // bounded state, never a URL, capability, save payload or game filename.
        record("Web process terminated: cause=unknown, loaded=\(isLoaded), ready=\(ready), paused=\(paused), saveReady=\(saveReady), saving=\(saveTask != nil), profiles=\(PackageWebKitProfiles.shared.retainedCount)")
        persistIncident(.webProcessTerminated)
        processTerminated = true
        generation = UUID() // invalidate any pending bootstrap acknowledgement
        ready = false; isLoaded = false; saveReady = false
        failure = L10n.text("The web player stopped unexpectedly. The cause is unknown. Close this game and reopen it.")
        saveFailure = L10n.text("The web player stopped. Previous saves were kept, but unsaved progress may be lost.")
    }
}


/// Avoids the refined callAsyncJavaScript Swift overlay, which is missing from
/// affected iOS 18.5 simulator runtimes (WebKit bug 293831, target <= iOS 18.3).
/// The longstanding plain evaluateJavaScript API starts the same Promise and
/// polls its result; capture still resolves only after Ruffle destroy/flush.
@MainActor enum SaveWebKitBridge {
    static func capture(from view: WKWebView, timeout: TimeInterval = 15) async throws -> Any {
        let key = "__FlashNestNativeCapture_" + UUID().uuidString.replacingOccurrences(of: "-", with: "")
        defer { view.evaluateJavaScript("delete window.\(key); true") }
        let deadline = Date().addingTimeInterval(timeout)
        _ = try await evaluate("""
        window.\(key) = {state:'pending'};
        Promise.resolve().then(() => window.FlashNest.shutdownAndCapture()).then(value => {
          if (window.\(key)) window.\(key) = {state:'complete', value};
        }, () => {
          if (window.\(key)) window.\(key) = {state:'error'};
        }); true;
        """, in: view, before: deadline)
        while Date() < deadline {
            try Task.checkCancellation()
            if let result = try await evaluate("window.\(key)", in: view, before: deadline) as? [String: Any] {
                if result["state"] as? String == "complete", let value = result["value"] { return value }
                if result["state"] as? String == "error" { throw SaveStoreError.invalid("save flush failed") }
            }
            try await Task.sleep(nanoseconds: 50_000_000)
        }
        throw SaveStoreError.invalid("save flush timed out")
    }

    private static func evaluate(_ script: String, in view: WKWebView, before deadline: Date) async throws -> Any {
        let remaining = deadline.timeIntervalSinceNow
        guard remaining > 0 else { throw SaveStoreError.invalid("save flush timed out") }
        return try await withCheckedThrowingContinuation { continuation in
            var completed = false
            view.evaluateJavaScript(script) { value, error in
                Task { @MainActor in
                    guard !completed else { return }
                    completed = true
                    if let error { continuation.resume(throwing: error) }
                    else { continuation.resume(returning: value ?? NSNull()) }
                }
            }
            Task { @MainActor in
                try? await Task.sleep(nanoseconds: UInt64(remaining * 1_000_000_000))
                guard !completed else { return }
                completed = true
                continuation.resume(throwing: SaveStoreError.invalid("save flush timed out"))
            }
        }
    }

}

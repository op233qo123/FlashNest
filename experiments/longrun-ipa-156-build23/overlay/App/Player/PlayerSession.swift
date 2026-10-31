import Foundation
import WebKit
import SwiftUI

@MainActor final class PlayerSession: NSObject, ObservableObject, WKNavigationDelegate, WKScriptMessageHandler {
    @Published var status = L10n.text("Starting local player…")
    @Published private(set) var isLoaded = false
    /// Snapshot for this new player page; preference changes never reconfigure a live page.
    @Published private(set) var requestedRendererSettings: RendererSettings?
    @Published private(set) var requestedSamplingSettings: RenderSamplingSettings?
    @Published private(set) var appliedSamplingStatus = SamplingAppliedStatus.unknown
    private var samplingStatusTracker = SamplingStatusTracker()
    /// Pinned Ruffle's public API exposes requested config, not the actual backend.
    /// Nil is intentionally honest; do not infer success from preferredRenderer.
    @Published private(set) var activeRendererBackend: String?
    @Published var failure: String?
    @Published var diagnostics: [String] = []
    @Published private(set) var previousSessionDiagnostic: String?
    @Published var loadingPhaseDiagnosticsEnabled = UserDefaults.standard.bool(forKey: LoadingPhaseDiagnostics.preferenceKey) {
        didSet { UserDefaults.standard.set(loadingPhaseDiagnosticsEnabled, forKey: LoadingPhaseDiagnostics.preferenceKey) }
    }
    @Published private(set) var loadingPhaseSummary: String?
    @Published private(set) var previousLoadingPhaseSummary: String?
    @Published private(set) var loadingPhasePersistenceFailed = false
    private let loadingPhaseStore = LoadingPhaseDiagnostics()
    private var loadingPhaseSnapshot: LoadingPhaseSnapshot?
    private var loadingPhaseEpoch = 0
    @Published var longRunDiagnosticsEnabled = UserDefaults.standard.bool(forKey: LongRunDiagnostics.preferenceKey) {
        didSet { UserDefaults.standard.set(longRunDiagnosticsEnabled, forKey: LongRunDiagnostics.preferenceKey) }
    }
    @Published private(set) var longRunSummary: String?
    @Published private(set) var previousLongRunSummary: String?
    @Published private(set) var longRunPersistenceFailed = false
    private let longRunStore: LongRunDiagnostics
    private var longRunSnapshot: LongRunSnapshot?
    private var longRunEpoch = 0
    private var longRunTimer: Task<Void, Never>?
    private var longRunLastSampleUptime: TimeInterval = 0
    private var longRunLastAcceptedUptime: TimeInterval?
    private var longRunLastMarkerUptime: TimeInterval?
    private var longRunLastNoisyEventUptime: TimeInterval?
    private var longRunIsBackground = false
    private var longRunScenePhase = ScenePhase.active
    private var longRunStaleRecorded = false
    private let incidentStore: LastSessionDiagnostics
    @Published var paused = false
    @Published var webView: WKWebView?
    private var server: LoopbackServer?
    private var generation = UUID()
    private var ready = false
    private var processTerminated = false
    private var samplingDocumentBinding = SamplingDocumentBinding()
    @Published private(set) var saveFailure: String?
    @Published private(set) var checkpointFailure: String?
    @Published private(set) var checkpointDidChange: Bool?
    @Published private(set) var restartFailure: String?
    @Published private(set) var saveReady = false
    @Published private(set) var restartRequired = false
    private let saveStore: SaveStore
    private var currentPackage: GamePackage?
    private var currentContentRoot: URL?
    private var saveTask: Task<Bool, Never>?
    private var checkpointTask: Task<Bool, Never>?
    private var restartTask: Task<Bool, Never>?
    private static var activePackageIDs = Set<UUID>()
    // An unconfirmed old page may still flush later. Keep the affected profile
    // closed for this process; app restart terminates the uncertain old page.
    private static var blockedPackageIDs = Set<UUID>()
    private var ownsPackageLease = false
    private var pendingRestoreID: UUID?
    private var preserveNativeOnEmptyCapture = false
    private var preservationStage: LegacySavePreservationError.Stage = .startup
    private var acceptedMessages = 0
    private var rejectedIdentityMessages = 0
    private var rejectedEnvelopeMessages = 0
    private var receivedSaveReady = false
    private var memoryWarningObserver: NSObjectProtocol?
    private var memoryWarningCount = 0
    private var lastMemoryWarning: Date?

    init(saveStore: SaveStore = SaveStore(), incidentStore: LastSessionDiagnostics? = nil, longRunStore: LongRunDiagnostics? = nil) {
        self.saveStore = saveStore
        self.incidentStore = incidentStore ?? LastSessionDiagnostics()
        self.longRunStore = longRunStore ?? LongRunDiagnostics()
        super.init()
        memoryWarningObserver = NotificationCenter.default.addObserver(
            forName: UIApplication.didReceiveMemoryWarningNotification, object: nil, queue: .main) { [weak self] _ in
                Task { @MainActor [weak self] in self?.recordHostMemoryWarning() }
            }
    }

    deinit {
        longRunTimer?.cancel()
        if let memoryWarningObserver { NotificationCenter.default.removeObserver(memoryWarningObserver) }
    }

    // Host-app evidence only. WebContent is a separate process and warnings are
    // best effort: zero warnings does NOT establish that memory was sufficient.
    func recordHostMemoryWarning() {
        guard webView != nil, !processTerminated else { return }
        memoryWarningCount = min(memoryWarningCount + 1, 999)
        lastMemoryWarning = Date()
        recordLongRun(.memoryWarning)
        if memoryWarningCount <= 10 { record("Host app memory warning: count=\(memoryWarningCount); WebContent cause remains unknown") }
    }

    func start(package: GamePackage, contentRoot: URL, storageOnly: Bool = false) async {
        guard restartTask == nil else { return }
        await startConfigured(package: package, contentRoot: contentRoot, storageOnly: storageOnly)
    }

    private func startConfigured(package: GamePackage, contentRoot: URL, storageOnly: Bool = false) async {
        guard server == nil else { return }
        currentPackage = package; currentContentRoot = contentRoot
        previousSessionDiagnostic = incidentStore.latest(for: package.id)?.summary
        previousLoadingPhaseSummary = loadingPhaseStore.read().map(\.summary).joined(separator: "\n\n")
        if previousLoadingPhaseSummary?.isEmpty == true { previousLoadingPhaseSummary = nil }
        loadingPhaseSummary = nil; loadingPhaseSnapshot = nil; loadingPhasePersistenceFailed = false
        longRunTimer?.cancel(); longRunTimer = nil
        previousLongRunSummary = longRunStore.read().map(\.summary).joined(separator: "\n\n")
        if previousLongRunSummary?.isEmpty == true { previousLongRunSummary = nil }
        longRunSummary = nil; longRunSnapshot = nil; longRunPersistenceFailed = false
        longRunLastAcceptedUptime = nil; longRunLastMarkerUptime = nil; longRunLastNoisyEventUptime = nil
        longRunIsBackground = false; longRunScenePhase = .active; longRunStaleRecorded = false
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
        restartFailure = nil
        currentPackage = package; currentContentRoot = contentRoot
        requestedRendererSettings = storageOnly ? nil : RendererSettings.load(for: package.id)
        requestedSamplingSettings = storageOnly ? nil : (RenderSamplingSettings.runtimeValidated
            ? RenderSamplingSettings.load(for: package.id) : RenderSamplingSettings())
        activeRendererBackend = nil
        samplingDocumentBinding.reset()
        samplingStatusTracker.reset(); appliedSamplingStatus = .unknown
        pendingRestoreID = nil
        saveReady = false; saveFailure = nil; checkpointFailure = nil; checkpointDidChange = nil; processTerminated = false
        memoryWarningCount = 0; lastMemoryWarning = nil
        preservationStage = .startup
        acceptedMessages = 0; rejectedIdentityMessages = 0; rejectedEnvelopeMessages = 0
        receivedSaveReady = false
        let attempt = UUID()
        generation = attempt
        if longRunDiagnosticsEnabled && !storageOnly {
            longRunEpoch = min(longRunEpoch + 1, 9_999_999)
            longRunSnapshot = LongRunSnapshot(session: attempt, wkEpoch: longRunEpoch)
            longRunLastSampleUptime = ProcessInfo.processInfo.systemUptime
            recordLongRun(.sessionStart)
        }
        if loadingPhaseDiagnosticsEnabled && !storageOnly {
            loadingPhaseEpoch = min(loadingPhaseEpoch + 1, 9_999_999)
            loadingPhaseSnapshot = LoadingPhaseSnapshot(session: attempt, wkEpoch: loadingPhaseEpoch)
        }
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
            let local = LoopbackServer(port: port, capability: capability.lowercased(), webRoot: webRoot, loadPhaseDiagnosticsEnabled: loadingPhaseSnapshot != nil)
            local.onDiagnostic = { [weak self] message in Task { @MainActor in self?.record(message) } }
            local.onLoadPhase = { [weak self] event in
                Task { @MainActor [weak self] in
                    guard let self, self.generation == attempt, !self.processTerminated,
                          let phase = LoadingPhaseEvent.Phase(rawValue: event.phase.rawValue) else { return }
                    self.recordLoadingPhase(LoadingPhaseEvent(phase: phase, receivedAt: Date(),
                        requestID: event.requestID, bytes: event.acceptedBytes,
                        expectedBytes: event.expectedBytes, status: event.status))
                }
            }
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
            if let snapshot = longRunSnapshot {
                // Only anonymous binding scalars. No entry, package or capability in the observer config.
                let config: [String: Any] = ["session": snapshot.session.uuidString, "epoch": snapshot.wkEpoch]
                let bytes = try JSONSerialization.data(withJSONObject: config)
                let literal = String(decoding: bytes, as: UTF8.self)
                controller.addUserScript(WKUserScript(source: "window.__FlashNestLongRunConfig = " + literal + ";",
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
            startLongRunHeartbeatWatch(attempt: attempt)
            var components = URLComponents(url: local.shellURL, resolvingAgainstBaseURL: false)!
            components.queryItems = [URLQueryItem(name: "entry", value: package.selectedMovie), URLQueryItem(name: "package", value: package.id.uuidString), URLQueryItem(name: "language", value: L10n.languageCode)]
            components.queryItems?.append(URLQueryItem(name: "nativeSaveHandshake", value: "1"))
            if storageOnly { components.queryItems?.append(URLQueryItem(name: "storageOnly", value: "1")) }
            if let renderer = requestedRendererSettings?.mode.queryValue {
                components.queryItems?.append(URLQueryItem(name: "renderer", value: renderer))
            }
            components.queryItems?.append(URLQueryItem(name: "samplingSession", value: generation.uuidString))
            if loadingPhaseSnapshot != nil {
                components.queryItems?.append(URLQueryItem(name: "phaseDiagnostics", value: "1"))
                components.queryItems?.append(URLQueryItem(name: "phaseSession", value: attempt.uuidString))
            }
            if let scale = requestedSamplingSettings?.mode.queryValue {
                components.queryItems?.append(URLQueryItem(name: "renderScale", value: scale))
            }
            guard let url = components.url else { throw PackageError.invalidPath(package.selectedMovie) }
            preservationStage = .handshake
            view.load(URLRequest(url: url))
        } catch {
            guard generation == attempt else { return }
            record(error.localizedDescription)
            failure = L10n.error(error)
            stop()
        }
    }

    func stop() {
        recordLongRun(.stopped)
        longRunTimer?.cancel(); longRunTimer = nil
        longRunSnapshot = nil
        samplingDocumentBinding.reset()
        generation = UUID()
        samplingStatusTracker.reset(); appliedSamplingStatus = .unknown
        isLoaded = false; saveReady = false
        requestedRendererSettings = nil; requestedSamplingSettings = nil; activeRendererBackend = nil
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
        if let task = checkpointTask { _ = await task.value }
        let closingServer = server
        stop()
        try await closingServer?.stopAndWait()
    }

    /// Destroy Ruffle to flush SharedObjects, then atomically save a verified
    /// capture. No timeout/error path writes an empty replacement.
    func closeAndSave() async -> Bool {
        if let task = saveTask { return await task.value }
        let task = Task { @MainActor [self] in
            // A checkpoint is not a close. Wait for its atomic write, then
            // still destroy/flush and take a final authoritative capture.
            if let checkpoint = checkpointTask { _ = await checkpoint.value }
            let result = await captureAndPersistIfReady()
            let closingServer = server
            stop()
            if result { preservationStage = .drain }
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

    /// An explicit save-and-restart, never a library dismissal. Public WebKit
    /// APIs release our old page and clear cache types, but cannot promise all
    /// OS-managed WebContent/GPU allocations have been physically reclaimed.
    func saveAndRestart() async -> Bool {
        if let task = restartTask { return await task.value }
        guard let package = currentPackage, let root = currentContentRoot else { return false }
        restartFailure = nil
        let task = Task { @MainActor [self] in
            guard await closeAndSave() else {
                restartFailure = saveFailure ?? L10n.text("Save failed. The game was not restarted.")
                return false
            }
            do {
                // closeAndSave has dropped the old WKWebView and drained its
                // listener before this API checks that the package is inactive.
                try await Self.clearPackageCaches(packageID: package.id)
            } catch {
                restartFailure = L10n.text("The game was saved, but temporary cache cleanup failed. It was not restarted.")
                return false
            }
            await startConfigured(package: package, contentRoot: root)
            guard failure == nil, webView != nil else {
                restartFailure = failure ?? L10n.text("The game was saved, but could not be restarted.")
                return false
            }
            return true
        }
        restartTask = task
        let result = await task.value
        restartTask = nil
        return result
    }

    /// Copies only already-written SOLs. Does not flush live Flash RAM, stop,
    /// pause, resume, or reload the movie, and is not an emulator savestate.
    func checkpointWrittenSaves() async -> Bool {
        checkpointDidChange = nil
        guard saveTask == nil, checkpointTask == nil, restartTask == nil else {
            checkpointFailure = L10n.text("Another save operation is in progress.")
            return false
        }
        guard saveReady, !processTerminated, let view = webView, let package = currentPackage else {
            checkpointFailure = L10n.text("The player is not ready to copy game-written saves.")
            return false
        }
        checkpointFailure = nil
        let attempt = generation
        let task = Task { @MainActor [self] in
            do {
                let object = try await SaveWebKitBridge.captureWrittenSaves(from: view)
                guard generation == attempt, !processTerminated, webView === view else {
                    throw SaveStoreError.invalid("player changed during checkpoint")
                }
                let data = try JSONSerialization.data(withJSONObject: object)
                guard data.count <= SaveStore.maximumArchiveBytes else { throw SaveStoreError.limit("archive size") }
                let capture = try JSONDecoder().decode(SaveCapture.self, from: data)
                guard !capture.entries.isEmpty else {
                    checkpointFailure = L10n.text("No game-written save is available yet. Existing backups were kept.")
                    return false
                }
                let store = saveStore
                let changed = try await Task.detached(priority: .userInitiated) {
                    let previousID = try store.currentSnapshot(packageID: package.id)?.id
                    let saved = try store.persistLatest(capture, package: package)
                    return saved.id != previousID
                }.value
                checkpointDidChange = changed
                checkpointFailure = nil
                return true
            } catch {
                // No shutdown was attempted: a failed read must not quarantine
                // the profile or replace its previous archive with empty data.
                checkpointFailure = L10n.text("Game-written saves could not be copied. Existing backups were kept.")
                return false
            }
        }
        checkpointTask = task
        let result = await task.value
        checkpointTask = nil
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
            preservationStage = .capture
            let object = try await captureObject(from: view)
            guard !processTerminated else { return false }
            shutdownConfirmed = true
            preservationStage = .validation
            let data = try JSONSerialization.data(withJSONObject: object)
            guard data.count <= SaveStore.maximumArchiveBytes else { throw SaveStoreError.limit("archive size") }
            let capture = try JSONDecoder().decode(SaveCapture.self, from: data)
            if preserveNativeOnEmptyCapture, capture.entries.isEmpty {
                // A storage-only browse must not mistake a missing/evicted WK
                // profile for a game intentionally clearing its save.
                return true
            }
            let store = saveStore
            preservationStage = .persistence
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

    /// Ordinary app switching retains the live scene. Only explicit save/end
    /// destroys Ruffle. This best-effort checkpoint cannot flush pending Flash
    /// RAM and cannot preserve a scene if iOS later kills its web process.
    func suspendAndSave() async {
        guard webView != nil, !processTerminated else { return }
        releaseAllKeys()
        setPaused(true)
        guard saveTask == nil, checkpointTask == nil, saveReady else { return }
        var background: UIBackgroundTaskIdentifier = .invalid
        background = UIApplication.shared.beginBackgroundTask(withName: "FlashNest written-save checkpoint") {
            Task { @MainActor in
                if background != .invalid {
                    UIApplication.shared.endBackgroundTask(background)
                    background = .invalid
                }
            }
        }
        defer {
            if background != .invalid {
                UIApplication.shared.endBackgroundTask(background)
                background = .invalid
            }
        }
        _ = await checkpointWrittenSaves()
    }

    func resumeAfterSuspension(allowingSaveFailure: Bool = false) async {
        guard restartTask == nil else { return }
        if let task = saveTask { _ = await task.value }
        guard allowingSaveFailure || (saveFailure == nil && restartFailure == nil) else { return }
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
        let started = Date()
        await session.start(package: package, contentRoot: root, storageOnly: true)
        defer { session.stop() }
        let deadline = Date().addingTimeInterval(15)
        while !session.saveReady, session.failure == nil, Date() < deadline {
            try await Task.sleep(nanoseconds: 100_000_000)
        }
        func evidence(_ outcome: LegacySavePreservationError.Outcome) -> LegacySavePreservationError {
            let error = LegacySavePreservationError(stage: session.preservationStage, outcome: outcome,
                elapsedMilliseconds: max(0, min(3_600_000, Int(Date().timeIntervalSince(started) * 1000))),
                acceptedMessages: session.acceptedMessages, rejectedIdentity: session.rejectedIdentityMessages,
                rejectedEnvelope: session.rejectedEnvelopeMessages, receivedSaveReady: session.receivedSaveReady)
            NSLog("%@", error.redactedSummary)
            return error
        }
        if let outcome = LegacySavePreservationError.handshakeOutcome(ready: session.saveReady,
            failed: session.failure != nil, terminated: session.processTerminated, now: Date(), deadline: deadline) {
            throw evidence(outcome)
        }
        guard session.saveReady else { throw evidence(.failed) }
        guard await session.closeAndSave() else { throw evidence(session.processTerminated ? .terminated : .failed) }
    }

    static func clearPackageCaches(packageID: UUID) async throws {
        let supported = CacheCleanupError.supportedMask(WKWebsiteDataStore.allWebsiteDataTypes())
        guard !activePackageIDs.contains(packageID) else {
            throw CacheCleanupError(reason: .active, elapsedMilliseconds: 0, supportedTypeMask: supported)
        }
        let profile = PackageWebKitProfiles.shared.store(for: packageID, retaining: activePackageIDs)
        let started = Date()
        let deadline = started.addingTimeInterval(15)
        let lease = CacheCleanupWarmLease(profile: profile)
        defer { lease.close() }
        try await lease.prepare(before: deadline)
        try Task.checkCancellation()
        NSLog("CACHE-CLEANUP-BEGIN supportedMask=%d", supported)
        try await withCheckedThrowingContinuation { (continuation: CheckedContinuation<Void, Error>) in
            var completed = false
            profile.removeData(ofTypes: CacheCleanupError.requestedTypes, modifiedSince: .distantPast) {
                Task { @MainActor in
                    guard !completed else { return }
                    completed = true
                    let elapsed = max(0, min(3_600_000, Int(Date().timeIntervalSince(started) * 1000)))
                    NSLog("CACHE-CLEANUP-COMPLETE elapsedMs=%d supportedMask=%d", elapsed, supported)
                    continuation.resume()
                }
            }
            Task { @MainActor in
                try? await Task.sleep(nanoseconds: UInt64(max(0, deadline.timeIntervalSinceNow) * 1_000_000_000))
                guard !completed else { return }
                completed = true
                let elapsed = max(0, min(3_600_000, Int(Date().timeIntervalSince(started) * 1000)))
                let error = CacheCleanupError(reason: .deadline, elapsedMilliseconds: elapsed, supportedTypeMask: supported)
                NSLog("%@", error.redactedSummary)
                continuation.resume(throwing: error)
            }
        }
        // removeData itself has no public cancellation API. Keep its callback
        // bounded by the same deadline, then reject cancelled removal callers.
        try Task.checkCancellation()
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

    /// All long-run records remain anonymous and separate from saves and free-form logs.
    private func persistLongRunSnapshot() {
        guard let snapshot = longRunSnapshot else { return }
        longRunSummary = snapshot.summary
        do { try longRunStore.record(snapshot) }
        catch { longRunPersistenceFailed = true }
    }

    private func recordLongRun(_ kind: LongRunEvent.Kind) {
        guard var snapshot = longRunSnapshot, snapshot.session == generation else { return }
        if kind == .memoryWarning || kind == .navigationFailed {
            let now = ProcessInfo.processInfo.systemUptime
            guard longRunLastNoisyEventUptime.map({ now - $0 >= 5 }) ?? true else {
                snapshot.noteRejectedMessage(); longRunSnapshot = snapshot; return
            }
            longRunLastNoisyEventUptime = now
        }
        guard snapshot.record(kind) else { return }
        longRunSnapshot = snapshot
        persistLongRunSnapshot()
    }

    private func receiveLongRun(_ body: [String: Any]) {
        guard var snapshot = longRunSnapshot, snapshot.session == generation else { return }
        let now = ProcessInfo.processInfo.systemUptime
        // Bound native work/disk writes even if page code sends valid-looking messages too often.
        guard longRunLastAcceptedUptime.map({ now - $0 >= 5 }) ?? true else {
            snapshot.noteRejectedMessage(); longRunSnapshot = snapshot; return
        }
        let accepted = snapshot.receive(body)
        longRunSnapshot = snapshot // Retain bounded rejected count, but never write once per rejection.
        guard accepted else { return }
        longRunLastAcceptedUptime = now; longRunLastSampleUptime = now
        longRunStaleRecorded = false
        persistLongRunSnapshot()
    }

    private func startLongRunHeartbeatWatch(attempt: UUID) {
        guard longRunSnapshot != nil else { return }
        longRunTimer?.cancel()
        longRunTimer = Task { @MainActor [weak self] in
            while !Task.isCancelled {
                do { try await Task.sleep(nanoseconds: 10_000_000_000) } catch { return }
                guard let self, self.generation == attempt, self.longRunSnapshot != nil,
                      !self.processTerminated else { return }
                if !self.longRunIsBackground && !self.longRunStaleRecorded &&
                    ProcessInfo.processInfo.systemUptime - self.longRunLastSampleUptime >= 35 {
                    self.longRunStaleRecorded = true
                    self.recordLongRun(.heartbeatStale)
                }
            }
        }
    }

    func markLongRunObservation() {
        let now = ProcessInfo.processInfo.systemUptime
        guard longRunLastMarkerUptime.map({ now - $0 >= 1 }) ?? true else { return }
        longRunLastMarkerUptime = now
        recordLongRun(.userMarker)
    }

    func recordLongRunSceneActivity(_ phase: ScenePhase) {
        guard longRunSnapshot != nil, phase != longRunScenePhase else { return }
        longRunScenePhase = phase
        longRunIsBackground = phase != .active
        longRunLastSampleUptime = ProcessInfo.processInfo.systemUptime
        longRunStaleRecorded = false
        recordLongRun(phase == .active ? .foreground : (phase == .background ? .background : .inactive))
    }

    func clearLongRunDiagnostics() {
        // Stop recording before deletion; stale callbacks must never recreate cleared logs.
        longRunTimer?.cancel(); longRunTimer = nil; longRunSnapshot = nil
        webView?.evaluateJavaScript("window.__FlashNestLongRunObserver?.stop(); true")
        do {
            try longRunStore.clear()
            previousLongRunSummary = nil; longRunSummary = nil; longRunPersistenceFailed = false
        } catch { longRunPersistenceFailed = true }
    }

    var longRunExport: String? {
        let sections = [previousLongRunSummary, longRunSummary].compactMap { $0 }.filter { !$0.isEmpty }
        return sections.isEmpty ? nil : sections.joined(separator: "\n\n")
    }

    private func recordLoadingPhase(_ event: LoadingPhaseEvent) {
        guard var snapshot = loadingPhaseSnapshot, snapshot.session == generation,
              snapshot.append(event) else { return }
        loadingPhaseSnapshot = snapshot
        loadingPhaseSummary = snapshot.summary
        do { try loadingPhaseStore.record(snapshot) }
        catch { loadingPhasePersistenceFailed = true }
    }

    func clearLoadingPhaseDiagnostics() {
        do {
            try loadingPhaseStore.clear()
            previousLoadingPhaseSummary = nil; loadingPhaseSummary = nil
            // Stop this session's recording, preventing later callbacks from restoring cleared metadata.
            loadingPhaseSnapshot = nil
            loadingPhasePersistenceFailed = false
        } catch { loadingPhasePersistenceFailed = true }
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
        receiveScriptMessage(from: message.webView, isMainFrame: message.frameInfo.isMainFrame,
                             requestURL: message.frameInfo.request.url, body: message.body)
    }

    /// A stable loopback origin/path is not page identity. A queued callback from
    /// a released page must not acknowledge restoration or mutate its successor.
    /// Structured input keeps this boundary testable without private WebKit APIs.
    func receiveScriptMessage(from source: WKWebView?, isMainFrame: Bool, requestURL: URL?, body payload: Any) {
        guard let active = webView, source === active, !processTerminated else {
            rejectedIdentityMessages = min(999, rejectedIdentityMessages + 1)
            return
        }
        guard isMainFrame, let current = requestURL, let shell = server?.shellURL,
              current.scheme == shell.scheme, current.host == shell.host, current.port == shell.port,
              current.path == shell.path,
              let body = payload as? [String: Any], let type = body["type"] as? String else {
            rejectedEnvelopeMessages = min(999, rejectedEnvelopeMessages + 1)
            return
        }
        acceptedMessages = min(999, acceptedMessages + 1)
        let text = String((body["message"] as? String ?? "").prefix(500))
        switch type {
        case "longRunDiagnostics":
            receiveLongRun(body)
        case "loadingPhase":
            guard let snapshot = loadingPhaseSnapshot, snapshot.session == generation,
                  let event = LoadingPhaseEvent.client(body, session: generation) else { return }
            recordLoadingPhase(event)
        case "samplingStatus":
            guard failure == nil, samplingDocumentBinding.acceptsReports else { return }
            if samplingStatusTracker.receive(body, session: generation.uuidString,
                expectedRequest: requestedSamplingSettings?.mode.scale) {
                appliedSamplingStatus = samplingStatusTracker.status
            }
        case "saveReady":
            receivedSaveReady = true
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
        case "error": failure = text; samplingDocumentBinding.invalidate(); samplingStatusTracker.reset(); appliedSamplingStatus = .unknown
        case "diagnostic": record(text)
        default: break
        }
    }

    // Status-only binding: never changes navigation policy or suppresses WebKit errors.
    // A same-view document replacement has no fresh trusted token, so stop reporting
    // until start creates a new WKWebView. Actual callback ordering needs native tests.
    func webView(_ webView: WKWebView, didStartProvisionalNavigation navigation: WKNavigation!) {
        guard self.webView === webView, !processTerminated else { return }
        samplingDocumentBinding.provisionalStarted()
        if !samplingDocumentBinding.acceptsReports {
            samplingStatusTracker.reset(); appliedSamplingStatus = .unknown
        }
    }
    func webView(_ webView: WKWebView, didCommit navigation: WKNavigation!) {
        guard self.webView === webView, !processTerminated else { return }
        samplingDocumentBinding.committed()
        if !samplingDocumentBinding.acceptsReports {
            samplingStatusTracker.reset(); appliedSamplingStatus = .unknown
        }
    }

    func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction,
                 decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        guard self.webView === webView, !processTerminated else { decisionHandler(.cancel); return }
        guard let url = navigationAction.request.url, let shell = server?.shellURL,
              url.scheme == shell.scheme, url.host == shell.host, url.port == shell.port,
              url.path == shell.path, navigationAction.targetFrame?.isMainFrame == true else {
            record(L10n.text("Blocked navigation outside the bundled player"))
            decisionHandler(.cancel); return
        }
        decisionHandler(.allow)
    }
    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
        guard self.webView === webView, !processTerminated else { return }
        record(error.localizedDescription); failure = L10n.error(error)
        recordLongRun(.navigationFailed)
        samplingDocumentBinding.invalidate()
        samplingStatusTracker.reset(); appliedSamplingStatus = .unknown
    }
    func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
        guard self.webView === webView, !processTerminated else { return }
        record(error.localizedDescription); failure = L10n.error(error)
        recordLongRun(.navigationFailed)
        samplingDocumentBinding.invalidate()
        samplingStatusTracker.reset(); appliedSamplingStatus = .unknown
    }
    func webViewWebContentProcessDidTerminate(_ webView: WKWebView) {
        guard self.webView === webView, !processTerminated else { return }
        // Public WebKit callback supplies no termination reason. Record only
        // bounded state, never a URL, capability, save payload or game filename.
        record("Web process terminated: cause=unknown, loaded=\(isLoaded), ready=\(ready), paused=\(paused), saveReady=\(saveReady), saving=\(saveTask != nil), profiles=\(PackageWebKitProfiles.shared.retainedCount)")
        recordLongRun(.webProcessTerminated)
        longRunTimer?.cancel(); longRunTimer = nil
        recordLoadingPhase(LoadingPhaseEvent(phase: .webProcessTerminated, receivedAt: Date()))
        persistIncident(.webProcessTerminated)
        processTerminated = true
        samplingDocumentBinding.reset()
        generation = UUID() // invalidate any pending bootstrap acknowledgement
        samplingStatusTracker.reset(); appliedSamplingStatus = .unknown
        ready = false; isLoaded = false; saveReady = false
        failure = L10n.text("The web player stopped unexpectedly. The cause is unknown. Close this game and reopen it.")
        saveFailure = L10n.text("The web player stopped. Previous saves were kept, but unsaved progress may be lost.")
    }
}


/// Avoids the refined callAsyncJavaScript Swift overlay, which is missing from
/// affected iOS 18.5 simulator runtimes (WebKit bug 293831, target <= iOS 18.3).
/// The longstanding plain evaluateJavaScript API starts the same Promise and
/// polls its result. Final capture awaits Ruffle destroy/flush; the separate
/// written-only operation only reads existing browser storage.
@MainActor enum SaveWebKitBridge {
    static func capture(from view: WKWebView, timeout: TimeInterval = 15) async throws -> Any {
        try await capture(from: view, timeout: timeout, writtenOnly: false)
    }

    static func captureWrittenSaves(from view: WKWebView, timeout: TimeInterval = 15) async throws -> Any {
        try await capture(from: view, timeout: timeout, writtenOnly: true)
    }

    private static func capture(from view: WKWebView, timeout: TimeInterval, writtenOnly: Bool) async throws -> Any {
        let operation = writtenOnly ? "captureWrittenSaves" : "shutdownAndCapture"
        let key = "__FlashNestNativeCapture_" + UUID().uuidString.replacingOccurrences(of: "-", with: "")
        defer { view.evaluateJavaScript("delete window.\(key); true") }
        let deadline = Date().addingTimeInterval(timeout)
        _ = try await evaluate("""
        window.\(key) = {state:'pending'};
        Promise.resolve().then(() => window.FlashNest.\(operation)()).then(value => {
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


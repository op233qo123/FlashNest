import XCTest
import UIKit
import WebKit
import CryptoKit
@testable import FlashNest

/// Original SWFs execute actual SharedObject.getLocal/data/flush operations in
/// bundled Ruffle. These are save-data tests, not emulator savestate tests.
@MainActor final class SharedObjectPersistenceTests: XCTestCase {
    func testLiveCheckpointCopiesExplicitlyFlushedSaveWithoutRestartingScene() async throws {
        executionTimeAllowance = 120
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: root) }
        let store = SaveStore(root: root.appendingPathComponent("save"))
        let packages = root.appendingPathComponent("packages")
        var package = try fixturePackage(in: packages)
        let content = packages.appendingPathComponent(package.id.uuidString).appendingPathComponent("content")
        let deadline = Date().addingTimeInterval(105)
        package.selectedMovie = "explicit-flush.swf"
        try await runMovie(package, content: content, store: store, before: "undefined", deadline: deadline,
                           checkpointExpectedWritten: true)
        package.selectedMovie = "read-only.swf"
        try await runMovie(package, content: content, store: store, before: "42", deadline: deadline)
    }

    func testLiveCheckpointDoesNotPretendToFlushRAMOnlySave() async throws {
        executionTimeAllowance = 120
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: root) }
        let store = SaveStore(root: root.appendingPathComponent("save"))
        let packages = root.appendingPathComponent("packages")
        var package = try fixturePackage(in: packages)
        let content = packages.appendingPathComponent(package.id.uuidString).appendingPathComponent("content")
        let deadline = Date().addingTimeInterval(105)
        package.selectedMovie = "close-flush.swf"
        try await runMovie(package, content: content, store: store, before: "undefined", deadline: deadline,
                           checkpointExpectedWritten: false, testBackgroundRetention: true)
        XCTAssertFalse(try XCTUnwrap(store.latest(packageID: package.id)).entries.isEmpty,
                       "Final destroy, unlike live checkpoint, must flush the fixture's RAM-only save")
        package.selectedMovie = "read-only.swf"
        try await runMovie(package, content: content, store: store, before: "42", deadline: deadline)
    }

    func testExplicitSaveAndRestartUsesNewPageAndPreservesSaveAndGameFiles() async throws {
        executionTimeAllowance = 120
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: root) }
        let store = SaveStore(root: root.appendingPathComponent("save"))
        let packages = root.appendingPathComponent("packages")
        var package = try fixturePackage(in: packages)
        package.selectedMovie = "explicit-flush.swf"
        let content = packages.appendingPathComponent(package.id.uuidString).appendingPathComponent("content")
        let movie = content.appendingPathComponent(package.selectedMovie)
        let original = try Data(contentsOf: movie)
        try await runMovie(package, content: content, store: store, before: "undefined",
                           deadline: Date().addingTimeInterval(105), testExplicitRestart: true)
        XCTAssertEqual(try Data(contentsOf: movie), original, "Restart must never delete or rewrite game content")
    }

    func testDestroyFlushPersistsAndRestartReadsActualSharedObject() async throws {
        executionTimeAllowance = 120
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: root) }
        let store = SaveStore(root: root.appendingPathComponent("save"))
        var package = try fixturePackage(in: root.appendingPathComponent("packages"))
        let content = root.appendingPathComponent("packages").appendingPathComponent(package.id.uuidString).appendingPathComponent("content")
        let deadline = Date().addingTimeInterval(105)
        package.selectedMovie = "close-flush.swf"
        try await runMovie(package, content: content, store: store, before: "undefined", deadline: deadline)
        let saved = try XCTUnwrap(store.latest(packageID: package.id))
        XCTAssertFalse(saved.entries.isEmpty, "Destroy must flush real SOL bytes before native capture")
        XCTAssertTrue(FileManager.default.fileExists(atPath: store.root.appendingPathComponent(package.id.uuidString).appendingPathComponent("current.json").path))
        package.selectedMovie = "read-only.swf"
        try await runMovie(package, content: content, store: store, before: "42", deadline: deadline)
    }

    func testExportImportMapsToSelectedNewPackageAndDoesNotLeakToAnotherGame() async throws {
        executionTimeAllowance = 120
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: root) }
        let packages = root.appendingPathComponent("packages")
        let store = SaveStore(root: root.appendingPathComponent("save"))
        var source = try fixturePackage(in: packages)
        var target = try fixturePackage(in: packages)
        var isolated = try fixturePackage(in: packages)
        func content(_ package: GamePackage) -> URL {
            packages.appendingPathComponent(package.id.uuidString).appendingPathComponent("content")
        }
        let deadline = Date().addingTimeInterval(105)
        source.selectedMovie = "explicit-flush.swf"
        try await runMovie(source, content: content(source), store: store, before: "undefined", deadline: deadline)
        let capture = try XCTUnwrap(store.latest(packageID: source.id))
        let snapshot = try store.capture(capture, package: source, name: "Portable fixture")
        let archive = try store.export(snapshot)
        let decoded = try store.decodeImport(archive)
        _ = try store.importSnapshot(decoded, to: target)
        XCTAssertEqual(try store.latest(packageID: target.id)?.entries, capture.entries)
        target.selectedMovie = "read-only.swf"
        try await runMovie(target, content: content(target), store: store, before: "42", deadline: deadline)
        isolated.selectedMovie = "read-only.swf"
        try await runMovie(isolated, content: content(isolated), store: store, before: "undefined", deadline: deadline)
    }

    func testUpgradePreservesExistingWebKitSaveBeforeFirstNativeArchive() async throws {
        executionTimeAllowance = 120
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: root) }
        let store = SaveStore(root: root.appendingPathComponent("save"))
        let packages = root.appendingPathComponent("packages")
        var package = try fixturePackage(in: packages)
        let content = packages.appendingPathComponent(package.id.uuidString).appendingPathComponent("content")
        let deadline = Date().addingTimeInterval(105)
        package.selectedMovie = "explicit-flush.swf"
        try await runMovie(package, content: content, store: store, before: "undefined", deadline: deadline, persist: false)
        XCTAssertNil(try store.latest(packageID: package.id))
        try await PlayerSession.preserveLegacySave(package: package, store: store)
        XCTAssertFalse(try XCTUnwrap(store.latest(packageID: package.id)).entries.isEmpty)
        package.selectedMovie = "read-only.swf"
        try await runMovie(package, content: content, store: store, before: "42", deadline: deadline)
    }

    func testConfirmedImportAppliesOnceAndNewerLiveFlushSurvivesMissedNativeCapture() async throws {
        executionTimeAllowance = 120
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: root) }
        let store = SaveStore(root: root.appendingPathComponent("save"))
        let packages = root.appendingPathComponent("packages")
        var package = try fixturePackage(in: packages)
        let content = packages.appendingPathComponent(package.id.uuidString).appendingPathComponent("content")
        let deadline = Date().addingTimeInterval(105)
        package.selectedMovie = "explicit-flush.swf"
        try await runMovie(package, content: content, store: store, before: "undefined", deadline: deadline)
        let knownFortyTwo = try XCTUnwrap(store.latest(packageID: package.id)).entries
        XCTAssertFalse(knownFortyTwo.isEmpty)
        let reset = try store.capture(SaveCapture(version: 1, entries: []), package: package, name: "Explicit reset fixture")
        _ = try store.importSnapshot(reset, to: package)
        XCTAssertEqual(try store.currentSnapshot(packageID: package.id)?.restoreRequired, true)
        package.selectedMovie = "read-only.swf"
        try await runMovie(package, content: content, store: store, before: "undefined", deadline: deadline, persist: false)
        XCTAssertNotEqual(try store.currentSnapshot(packageID: package.id)?.restoreRequired, true,
                          "Import intent must be consumed before game actions, not on later close")
        package.selectedMovie = "explicit-flush.swf"
        try await runMovie(package, content: content, store: store, before: "undefined", deadline: deadline,
                           persist: false, expectedDiscardedCapture: knownFortyTwo)
        XCTAssertTrue(try XCTUnwrap(store.latest(packageID: package.id)).entries.isEmpty,
                      "Simulate interrupted native capture: disk is older than live WK SharedObject")
        package.selectedMovie = "read-only.swf"
        try await runMovie(package, content: content, store: store, before: "42", deadline: deadline,
                           expectedBootstrapCapture: knownFortyTwo)
    }

    func testUnconfirmedFlushBlocksSameProfileAcrossSessionsWithoutReplacingCurrent() async throws {
        executionTimeAllowance = 60
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: root) }
        let packages = root.appendingPathComponent("packages")
        let store = SaveStore(root: root.appendingPathComponent("save"))
        let package = try fixturePackage(in: packages)
        let content = packages.appendingPathComponent(package.id.uuidString).appendingPathComponent("content")
        _ = try store.persistLatest(SaveCapture(version: 1, entries: []), package: package)
        let current = store.root.appendingPathComponent(package.id.uuidString).appendingPathComponent("current.json")
        let original = try Data(contentsOf: current)
        let session = PlayerSession(saveStore: store)
        defer { session.stop() }
        await session.start(package: package, contentRoot: content, storageOnly: true)
        let deadline = Date().addingTimeInterval(15)
        while !session.saveReady, session.failure == nil, Date() < deadline {
            try await Task.sleep(nanoseconds: 50_000_000)
        }
        XCTAssertTrue(session.saveReady)
        let view = try XCTUnwrap(session.webView)
        _ = try await view.evaluateJavaScript("""
        window.FlashNest = {releaseKeys(){}, pause(){},
          shutdownAndCapture: () => Promise.reject(new Error('intentional unconfirmed fixture flush'))}; true;
        """)
        let saved = await session.closeAndSave()
        XCTAssertFalse(saved)
        XCTAssertTrue(session.restartRequired)
        XCTAssertEqual(try Data(contentsOf: current), original)
        let reopened = PlayerSession(saveStore: store)
        defer { reopened.stop() }
        await reopened.start(package: package, contentRoot: content, storageOnly: true)
        XCTAssertTrue(reopened.restartRequired)
        XCTAssertNil(reopened.webView, "A new session must not bypass the process-wide unsafe-profile lease")
        XCTAssertNotNil(reopened.failure)
    }

    /// Inject the public delegate signal; this is not an OOM reproduction.
    func testProcessTerminationKeepsNativeArchiveAndAllowsCleanReopen() async throws {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: root) }
        let store = SaveStore(root: root.appendingPathComponent("save"))
        let packages = root.appendingPathComponent("packages")
        let package = try fixturePackage(in: packages)
        let content = packages.appendingPathComponent(package.id.uuidString).appendingPathComponent("content")
        _ = try store.persistLatest(SaveCapture(version: 1, entries: []), package: package)
        let current = store.root.appendingPathComponent(package.id.uuidString).appendingPathComponent("current.json")
        let original = try Data(contentsOf: current)
        let session = PlayerSession(saveStore: store)
        defer { session.stop() }
        await session.start(package: package, contentRoot: content, storageOnly: true)
        let deadline = Date().addingTimeInterval(15)
        while !session.saveReady, session.failure == nil, Date() < deadline {
            try await Task.sleep(nanoseconds: 50_000_000)
        }
        XCTAssertTrue(session.saveReady)
        let view = try XCTUnwrap(session.webView)
        // A stale callback from some other page must not affect this session.
        session.webViewWebContentProcessDidTerminate(WKWebView())
        XCTAssertNil(session.failure)
        session.recordHostMemoryWarning()
        session.recordHostMemoryWarning()
        session.webViewWebContentProcessDidTerminate(view)
        XCTAssertTrue(session.previousSessionDiagnostic?.contains("hostMemoryWarnings=2") == true)
        await session.suspendAndSave()
        await session.resumeAfterSuspension()
        XCTAssertTrue(session.webView === view, "Foreground must not silently create a new page after confirmed process loss")
        XCTAssertNotNil(session.failure)
        XCTAssertFalse(session.saveReady)
        XCTAssertNotNil(session.saveFailure)
        XCTAssertTrue(session.diagnostics.contains { $0.contains("cause=unknown") })
        let saved = await session.closeAndSave()
        XCTAssertFalse(saved)
        XCTAssertFalse(session.restartRequired, "Confirmed process death is not an uncertain flush timeout")
        XCTAssertEqual(try Data(contentsOf: current), original)
        let reopened = PlayerSession(saveStore: store)
        defer { reopened.stop() }
        await reopened.start(package: package, contentRoot: content, storageOnly: true)
        let reopenedDeadline = Date().addingTimeInterval(15)
        while !reopened.saveReady, reopened.failure == nil, Date() < reopenedDeadline {
            try await Task.sleep(nanoseconds: 50_000_000)
        }
        XCTAssertTrue(reopened.saveReady)
        XCTAssertNil(reopened.failure)
        XCTAssertEqual(try Data(contentsOf: current), original)
        try await reopened.closeWithoutSaving()
    }

    func testCloseWaitsForCheckpointThenStillClosesPlayer() async throws {
        executionTimeAllowance = 90
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: root) }
        let store = SaveStore(root: root.appendingPathComponent("save"))
        let package = try fixturePackage(in: root.appendingPathComponent("packages"))
        let content = root.appendingPathComponent("packages").appendingPathComponent(package.id.uuidString).appendingPathComponent("content")
        let scene = try XCTUnwrap(UIApplication.shared.connectedScenes.compactMap { $0 as? UIWindowScene }.first)
        let previous = scene.windows.first(where: { $0.isKeyWindow })
        let window = UIWindow(windowScene: scene)
        let controller = UIViewController()
        window.rootViewController = controller
        window.makeKeyAndVisible()
        let session = PlayerSession(saveStore: store)
        defer { session.stop(); window.isHidden = true; previous?.makeKey() }
        print("FLASHNEST_CHECKPOINT_ORDER phase=bootstrap-begin")
        await session.start(package: package, contentRoot: content, storageOnly: true)
        let view = try XCTUnwrap(session.webView)
        view.frame = controller.view.bounds
        controller.view.addSubview(view)
        // iOS18.2 CI recorded15.569s merely launching WebContent. Give cold
        // test-process startup its own bound; production capture stays15s.
        let deadline = Date().addingTimeInterval(30)
        while !session.saveReady, session.failure == nil, Date() < deadline {
            try await Task.sleep(nanoseconds: 50_000_000)
        }
        print("FLASHNEST_CHECKPOINT_ORDER phase=bootstrap-end ready=\(session.saveReady) failed=\(session.failure != nil) loading=\(view.isLoading) attached=\(view.window != nil) diagnostics=\(session.diagnostics.count)")
        XCTAssertTrue(session.saveReady, "Visible storage-only page must finish bootstrap before fault injection")
        guard session.saveReady else {
            try? await session.closeWithoutSaving()
            throw SaveStoreError.invalid("fixture storage bootstrap did not become ready")
        }
        try await replaceBridgeMethod("captureWrittenSaves",
            implementation: "() => new Promise(resolve => { window.__resolveCheckpoint = resolve; })", in: view)
        let checkpoint = Task { @MainActor in await session.checkpointWrittenSaves() }
        var closing: Task<Bool, Never>?
        do {
        let resolverDeadline = Date().addingTimeInterval(5)
        var waiting = false
        while !waiting, Date() < resolverDeadline {
            waiting = (try await view.evaluateJavaScript("typeof window.__resolveCheckpoint === 'function'") as? Bool) == true
            if !waiting { try await Task.sleep(nanoseconds: 20_000_000) }
        }
        print("FLASHNEST_CHECKPOINT_ORDER phase=resolver waiting=\(waiting) ready=\(session.saveReady) failed=\(session.failure != nil)")
        XCTAssertTrue(waiting)
        guard waiting else { throw SaveStoreError.invalid("fixture checkpoint never entered injected wait") }
        let close = Task { @MainActor in await session.closeAndSave() }
        closing = close
        await Task.yield()
        let duplicate = await session.checkpointWrittenSaves()
        XCTAssertFalse(duplicate, "No checkpoint may start while close owns the lifecycle")
        _ = try await view.evaluateJavaScript("window.__resolveCheckpoint({version:1,entries:[]}); true")
        let copied = await checkpoint.value
        let closed = await close.value
        print("FLASHNEST_CHECKPOINT_ORDER phase=complete checkpoint=\(copied) close=\(closed) pageReleased=\(session.webView == nil)")
        XCTAssertFalse(copied, "Empty read is not a save")
        XCTAssertTrue(closed, "Close must not merely return checkpoint's false result")
        XCTAssertNil(session.webView)
        XCTAssertNotNil(try store.currentSnapshot(packageID: package.id), "Final close still captures the completed shutdown")
        } catch {
            checkpoint.cancel()
            _ = await checkpoint.value
            if let closing { _ = await closing.value }
            try? await session.closeWithoutSaving()
            throw error
        }
    }

    /// The production API object is frozen. Replace the global object rather
    /// than silently assigning one of its non-writable method properties.
    private func replaceBridgeMethod(_ method: String, implementation: String, in view: WKWebView) async throws {
        let methodLiteral = String(decoding: try JSONEncoder().encode(method), as: UTF8.self)
        let installed = try await view.evaluateJavaScript("""
        (() => {
          const original = window.FlashNest;
          const replacement = (\(implementation));
          window.FlashNest = Object.freeze({...original, [\(methodLiteral)]: replacement});
          return window.FlashNest !== original && window.FlashNest[\(methodLiteral)] === replacement;
        })();
        """) as? Bool
        XCTAssertEqual(installed, true, "Fault injection must be verified before exercising failure behavior")
        guard installed == true else { throw SaveStoreError.invalid("fixture fault injection failed") }
    }

    private func fixturePackage(in root: URL) throws -> GamePackage {
        let fixtureRoot = try XCTUnwrap(Bundle(for: Self.self).url(forResource: "fixtures", withExtension: nil))
        return try PackageImporter(root: root).stageAndCommit(fixtureRoot.appendingPathComponent("shared-object"))
    }

    private func runMovie(_ package: GamePackage, content: URL, store: SaveStore,
                          before: String, deadline: Date, persist: Bool = true,
                          expectedDiscardedCapture: [SaveEntry]? = nil,
                          expectedBootstrapCapture: [SaveEntry]? = nil,
                          checkpointExpectedWritten: Bool? = nil,
                          testBackgroundRetention: Bool = false,
                          testExplicitRestart: Bool = false) async throws {
        let native = try store.currentSnapshot(packageID: package.id)
        print("FLASHNEST_SAVE_STAGE movie=\(package.selectedMovie) expected=\(before) nativeCapture=\(persist) nativeCount=\(native?.entries.count ?? -1) restoreRequired=\(native?.restoreRequired == true)")
        let scene = try XCTUnwrap(UIApplication.shared.connectedScenes.compactMap { $0 as? UIWindowScene }.first)
        let previous = scene.windows.first(where: { $0.isKeyWindow })
        let window = UIWindow(windowScene: scene)
        let controller = UIViewController()
        window.rootViewController = controller
        window.makeKeyAndVisible()
        let session = PlayerSession(saveStore: store)
        defer { session.stop(); window.isHidden = true; previous?.makeKey() }
        do {
        await session.start(package: package, contentRoot: content)
        let view = try XCTUnwrap(session.webView)
        view.frame = controller.view.bounds
        controller.view.addSubview(view)
        var started = false
        while Date() < deadline {
            if session.failure != nil {
                try? await session.closeWithoutSaving()
                XCTFail("SharedObject fixture failed to load")
                return
            }
            if !started && session.isLoaded {
                let bootstrap = try await view.evaluateJavaScript("""
                window.FlashNestSaveBridge.create({storage:localStorage, location:location.href,
                  packageID:new URLSearchParams(location.search).get('package')}).capture();
                """)
                let bootstrapBytes = try JSONSerialization.data(withJSONObject: bootstrap, options: [.sortedKeys])
                let bootstrapCapture = try JSONDecoder().decode(SaveCapture.self, from: bootstrapBytes)
                let bootstrapHash = SHA256.hash(data: bootstrapBytes).map { String(format: "%02x", $0) }.joined()
                print("FLASHNEST_SAVE_BEFORE_PLAY movie=\(package.selectedMovie) count=\(bootstrapCapture.entries.count) sha256=\(bootstrapHash)")
                if let expectedBootstrapCapture {
                    XCTAssertTrue(bootstrapCapture.entries == expectedBootstrapCapture,
                                  "Before Play, live storage must already contain known42; count=\(bootstrapCapture.entries.count), sha256=\(bootstrapHash)")
                }
                _ = try await view.evaluateJavaScript("document.getElementById('start').click(); true")
                started = true
            }
            if session.diagnostics.contains(where: { $0.contains("FLASHNEST_SAVE_READY") }) {
                let observed = session.diagnostics.filter { $0.contains("FLASHNEST_SAVE_BEFORE:") }
                XCTAssertTrue(observed.contains(where: { $0.contains("FLASHNEST_SAVE_BEFORE:" + before) }),
                              "Movie=\(package.selectedMovie), expected=\(before), observed=\(observed), nativeCapture=\(persist), bootstrap=\(session.diagnostics.filter { $0.contains("SAVE_BOOTSTRAP") })")
                XCTAssertTrue(session.saveReady)
                if testExplicitRestart {
                    let diagnosticStart = session.diagnostics.count
                    let restarted = await session.saveAndRestart()
                    XCTAssertTrue(restarted, "Final save, server drain and cache cleanup must precede restart")
                    let replacement = try XCTUnwrap(session.webView)
                    XCTAssertFalse(replacement === view)
                    replacement.frame = controller.view.bounds
                    controller.view.addSubview(replacement)
                    var clicked = false
                    var observedRestoredValue = false
                    while Date() < deadline, session.failure == nil {
                        if session.isLoaded && !clicked {
                            _ = try await replacement.evaluateJavaScript("document.getElementById('start').click(); true")
                            clicked = true
                        }
                        let recent = Array(session.diagnostics.dropFirst(min(diagnosticStart, session.diagnostics.count)))
                        if recent.contains(where: { $0.contains("FLASHNEST_SAVE_BEFORE:42") }) {
                            observedRestoredValue = true
                            break
                        }
                        try await Task.sleep(nanoseconds: 100_000_000)
                    }
                    XCTAssertTrue(observedRestoredValue, "The same actual SWF must read its saved42 on the replacement page")
                    let archive = store.root.appendingPathComponent(package.id.uuidString).appendingPathComponent("current.json")
                    let savedBytes = try Data(contentsOf: archive)
                    try await replaceBridgeMethod("shutdownAndCapture",
                        implementation: "() => Promise.reject(new Error('fixture final-save failure'))", in: replacement)
                    let failedRestart = await session.saveAndRestart()
                    XCTAssertFalse(failedRestart)
                    XCTAssertNotNil(session.restartFailure)
                    XCTAssertNil(session.webView, "Failed final save must never launch a new page")
                    XCTAssertEqual(try Data(contentsOf: archive), savedBytes)
                    await session.resumeAfterSuspension()
                    XCTAssertNil(session.webView, "A dismissed error panel must not implicitly retry restart")
                    return
                }
                if testBackgroundRetention {
                    let archiveBefore = try store.currentSnapshot(packageID: package.id)
                    _ = try await view.evaluateJavaScript("window.__backgroundSceneMarker = 'live-RAM-scene'; true")
                    await session.suspendAndSave()
                    XCTAssertTrue(session.webView === view, "Ordinary background must not destroy the current scene")
                    XCTAssertTrue(session.isLoaded)
                    XCTAssertTrue(session.paused)
                    XCTAssertNil(session.saveFailure)
                    XCTAssertEqual(try store.currentSnapshot(packageID: package.id)?.id, archiveBefore?.id,
                                   "The unflushed fixture must not be converted into an empty archive on background")
                    await session.resumeAfterSuspension()
                    XCTAssertTrue(session.webView === view)
                    let marker = try await view.evaluateJavaScript("window.__backgroundSceneMarker") as? String
                    XCTAssertEqual(marker, "live-RAM-scene")
                    session.setPaused(false) // same foreground intent applied by PlayerView
                    XCTAssertFalse(session.paused)
                }
                if let expectedWritten = checkpointExpectedWritten {
                    let beforeArchive = try store.currentSnapshot(packageID: package.id)
                    let wasPaused = session.paused
                    _ = try await view.evaluateJavaScript("window.__checkpointSceneMarker = 'same-page'; true")
                    let copied = await session.checkpointWrittenSaves()
                    XCTAssertEqual(copied, expectedWritten)
                    XCTAssertTrue(session.webView === view)
                    XCTAssertTrue(session.isLoaded)
                    XCTAssertEqual(session.paused, wasPaused)
                    let marker = try await view.evaluateJavaScript("window.__checkpointSceneMarker") as? String
                    XCTAssertEqual(marker, "same-page")
                    if expectedWritten {
                        XCTAssertFalse(try XCTUnwrap(store.latest(packageID: package.id)).entries.isEmpty)
                        let savedBytes = try Data(contentsOf: store.root.appendingPathComponent(package.id.uuidString).appendingPathComponent("current.json"))
                        let copiedAgain = await session.checkpointWrittenSaves()
                        XCTAssertTrue(copiedAgain)
                        XCTAssertEqual(session.checkpointDidChange, false)
                        XCTAssertEqual(try Data(contentsOf: store.root.appendingPathComponent(package.id.uuidString).appendingPathComponent("current.json")), savedBytes,
                                       "Unchanged written saves must retain the same archive and timestamp")
                        // Rejecting a read must preserve archive and live player,
                        // not enter the uncertain-shutdown quarantine.
                        _ = try await view.evaluateJavaScript("window.__originalCheckpoint = window.FlashNest.captureWrittenSaves; true")
                        try await replaceBridgeMethod("captureWrittenSaves",
                            implementation: "() => Promise.reject(new Error('fixture read failure'))", in: view)
                        let failed = await session.checkpointWrittenSaves()
                        XCTAssertFalse(failed)
                        XCTAssertFalse(session.restartRequired)
                        XCTAssertNil(session.saveFailure)
                        XCTAssertTrue(session.webView === view)
                        XCTAssertEqual(try Data(contentsOf: store.root.appendingPathComponent(package.id.uuidString).appendingPathComponent("current.json")), savedBytes)
                        try await replaceBridgeMethod("captureWrittenSaves",
                            implementation: "() => Promise.resolve({version:1,entries:[]})", in: view)
                        let empty = await session.checkpointWrittenSaves()
                        XCTAssertFalse(empty)
                        XCTAssertEqual(try Data(contentsOf: store.root.appendingPathComponent(package.id.uuidString).appendingPathComponent("current.json")), savedBytes,
                                       "An empty checkpoint must not erase a previous nonempty archive")
                        try await replaceBridgeMethod("captureWrittenSaves",
                            implementation: "window.__originalCheckpoint", in: view)
                    } else {
                        XCTAssertNotNil(session.checkpointFailure)
                        XCTAssertEqual(try store.currentSnapshot(packageID: package.id)?.id, beforeArchive?.id)
                    }
                }
                if persist {
                    let saved = await session.closeAndSave()
                    XCTAssertTrue(saved, "Awaited destroy/capture/native persistence must succeed")
                } else {
                    // Model a missed native archive update, not an actual OS kill.
                    // Await Ruffle destruction but deliberately discard its capture:
                    // an old page must not flush later over the next page's writes.
                    let result = try await SaveWebKitBridge.capture(from: view)
                    let bytes = try JSONSerialization.data(withJSONObject: result, options: [.sortedKeys])
                    let capture = try JSONDecoder().decode(SaveCapture.self, from: bytes)
                    let digest = SHA256.hash(data: bytes).map { String(format: "%02x", $0) }.joined()
                    print("FLASHNEST_SAVE_DISCARDED_CAPTURE movie=\(package.selectedMovie) count=\(capture.entries.count) sha256=\(digest)")
                    if let expectedDiscardedCapture {
                        XCTAssertTrue(capture.entries == expectedDiscardedCapture,
                                      "Real writer must flush known42 before native capture is omitted; count=\(capture.entries.count), sha256=\(digest)")
                    }
                    try await session.closeWithoutSaving()
                }
                return
            }
            try await Task.sleep(nanoseconds: 100_000_000)
        }
        try? await session.closeWithoutSaving()
        XCTFail("Real SharedObject fixture exceeded shared 105-second deadline")
        } catch {
            // Even a fixture assertion/JS exception must drain the old stable
            // port before the next test creates a fresh PlayerSession.
            try? await session.closeWithoutSaving()
            throw error
        }
    }
}

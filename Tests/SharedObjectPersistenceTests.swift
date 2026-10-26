import XCTest
import UIKit
import WebKit
import CryptoKit
@testable import FlashNest

/// Original SWFs execute actual SharedObject.getLocal/data/flush operations in
/// bundled Ruffle. These are save-data tests, not emulator savestate tests.
@MainActor final class SharedObjectPersistenceTests: XCTestCase {
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

    private func fixturePackage(in root: URL) throws -> GamePackage {
        let fixtureRoot = try XCTUnwrap(Bundle(for: Self.self).url(forResource: "fixtures", withExtension: nil))
        return try PackageImporter(root: root).stageAndCommit(fixtureRoot.appendingPathComponent("shared-object"))
    }

    private func runMovie(_ package: GamePackage, content: URL, store: SaveStore,
                          before: String, deadline: Date, persist: Bool = true,
                          expectedDiscardedCapture: [SaveEntry]? = nil,
                          expectedBootstrapCapture: [SaveEntry]? = nil) async throws {
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
        await session.start(package: package, contentRoot: content)
        let view = try XCTUnwrap(session.webView)
        view.frame = controller.view.bounds
        controller.view.addSubview(view)
        var started = false
        while Date() < deadline {
            if session.failure != nil { XCTFail("SharedObject fixture failed to load"); return }
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
        XCTFail("Real SharedObject fixture exceeded shared 105-second deadline")
    }
}

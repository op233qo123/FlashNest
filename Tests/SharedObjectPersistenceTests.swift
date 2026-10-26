import XCTest
import UIKit
import WebKit
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

    func testConfirmedImportAppliesOnceAndNewerLiveFlushSurvivesAbnormalStop() async throws {
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
        let reset = try store.capture(SaveCapture(version: 1, entries: []), package: package, name: "Explicit reset fixture")
        _ = try store.importSnapshot(reset, to: package)
        XCTAssertEqual(try store.currentSnapshot(packageID: package.id)?.restoreRequired, true)
        package.selectedMovie = "read-only.swf"
        try await runMovie(package, content: content, store: store, before: "undefined", deadline: deadline, persist: false)
        XCTAssertNotEqual(try store.currentSnapshot(packageID: package.id)?.restoreRequired, true,
                          "Import intent must be consumed before game actions, not on later close")
        package.selectedMovie = "explicit-flush.swf"
        try await runMovie(package, content: content, store: store, before: "undefined", deadline: deadline, persist: false)
        XCTAssertTrue(try XCTUnwrap(store.latest(packageID: package.id)).entries.isEmpty,
                      "Simulate interrupted native capture: disk is older than live WK SharedObject")
        package.selectedMovie = "read-only.swf"
        try await runMovie(package, content: content, store: store, before: "42", deadline: deadline)
    }

    private func fixturePackage(in root: URL) throws -> GamePackage {
        let fixtureRoot = try XCTUnwrap(Bundle(for: Self.self).url(forResource: "fixtures", withExtension: nil))
        return try PackageImporter(root: root).stageAndCommit(fixtureRoot.appendingPathComponent("shared-object"))
    }

    private func runMovie(_ package: GamePackage, content: URL, store: SaveStore,
                          before: String, deadline: Date, persist: Bool = true) async throws {
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
                _ = try await view.evaluateJavaScript("document.getElementById('start').click(); true")
                started = true
            }
            if session.diagnostics.contains(where: { $0.contains("FLASHNEST_SAVE_READY") }) {
                XCTAssertTrue(session.diagnostics.contains(where: { $0.contains("FLASHNEST_SAVE_BEFORE:" + before) }),
                              "Actual SWF must observe expected isolated/restored progress")
                XCTAssertTrue(session.saveReady)
                if persist {
                    let saved = await session.closeAndSave()
                    XCTAssertTrue(saved, "Awaited destroy/capture/native persistence must succeed")
                } else {
                    try await session.closeWithoutSaving()
                }
                return
            }
            try await Task.sleep(nanoseconds: 100_000_000)
        }
        XCTFail("Real SharedObject fixture exceeded shared 105-second deadline")
    }
}

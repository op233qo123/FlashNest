import XCTest
import UIKit
import WebKit
@testable import FlashNest

/// Real bundled Ruffle + original AVM2 SWFs. No user-provided game/save data.
@MainActor final class RawSOLWebKitTests: XCTestCase {
    func testRawAMF3ImportIsReadThenWrittenAndReadAfterReopenWithoutCrossGameLeak() async throws {
        executionTimeAllowance = 120
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: root) }
        let store = SaveStore(root: root.appendingPathComponent("save"))
        let fixtures = try XCTUnwrap(Bundle(for: Self.self).url(forResource: "fixtures", withExtension: nil))
        let packages = root.appendingPathComponent("packages")
        var game = try PackageImporter(root: packages).stageAndCommit(fixtures.appendingPathComponent("raw-sol"))
        let content = packages.appendingPathComponent(game.id.uuidString).appendingPathComponent("content")
        let deadline = Date().addingTimeInterval(105)
        game.selectedMovie = "writer.swf"
        try await run(game, content: content, store: store, expected: "undefined", deadline: deadline)
        let initial = try XCTUnwrap(store.latest(packageID: game.id))
        XCTAssertEqual(initial.entries.count, 1)
        XCTAssertEqual(try RawSOLDocument.parse(XCTUnwrap(Data(base64Encoded: initial.entries[0].value))).encoding, .amf3)
        let unrelated = SaveEntry(scope: "origin", key: "Unrelated", value: RawSOLTestFixtures.sol(name: "Unrelated", progress: 9).base64EncodedString())
        let current = try store.persistLatest(SaveCapture(version: 1, entries: initial.entries + [unrelated]), package: game)
        let raw = try Data(contentsOf: fixtures.appendingPathComponent("raw-sol/original-progress-7.sol"))
        let plan = try RawSOLImportPlan.prepare(data: raw, current: current, targetPackageID: game.id)
        XCTAssertEqual(plan.candidates, [RawSOLTarget(scope: "origin", key: "FlashNestFixture")])
        let imported = try store.importRawSOL(plan, selecting: XCTUnwrap(plan.candidates.first), to: game)
        XCTAssertEqual(Data(base64Encoded: imported.entries[0].value), raw, "Import must preserve AMF bytes, not transcode")
        XCTAssertEqual(imported.entries[1].value, unrelated.value)
        XCTAssertTrue(try store.list(packageID: game.id).contains { $0.entries == current.entries }, "Pre-import backup must retain all old objects")
        game.selectedMovie = "reader.swf"
        try await run(game, content: content, store: store, expected: "7", deadline: deadline)
        game.selectedMovie = "writer.swf"
        try await run(game, content: content, store: store, expected: "7", deadline: deadline)
        game.selectedMovie = "reader.swf"
        try await run(game, content: content, store: store, expected: "42", deadline: deadline)
        let final = try XCTUnwrap(store.latest(packageID: game.id))
        XCTAssertEqual(final.entries.first(where: { $0.key == "Unrelated" })?.value, unrelated.value)
        var isolated = try PackageImporter(root: packages).stageAndCommit(fixtures.appendingPathComponent("raw-sol"))
        isolated.selectedMovie = "reader.swf"
        let isolatedContent = packages.appendingPathComponent(isolated.id.uuidString).appendingPathComponent("content")
        try await run(isolated, content: isolatedContent, store: store, expected: "undefined", deadline: deadline)
        XCTAssertEqual(try store.latest(packageID: game.id)?.entries, final.entries, "Other game must not mutate the imported save")
    }

    private func run(_ package: GamePackage, content: URL, store: SaveStore, expected: String, deadline: Date) async throws {
        let scene = try XCTUnwrap(UIApplication.shared.connectedScenes.compactMap { $0 as? UIWindowScene }.first)
        let previous = scene.windows.first(where: { $0.isKeyWindow })
        let window = UIWindow(windowScene: scene)
        let controller = UIViewController(); window.rootViewController = controller; window.makeKeyAndVisible()
        let session = PlayerSession(saveStore: store)
        defer { session.stop(); window.isHidden = true; previous?.makeKey() }
        print("RAW_SOL_RUNTIME begin movie=\(package.selectedMovie) expected=\(expected)")
        do {
            await session.start(package: package, contentRoot: content)
            let view = try XCTUnwrap(session.webView)
            view.frame = controller.view.bounds; controller.view.addSubview(view)
            var clicked = false
            var clickError: Error?
            while Date() < deadline {
                if let failure = session.failure { throw SaveStoreError.invalid("synthetic raw SOL runtime: " + failure) }
                if let clickError { throw clickError }
                if session.isLoaded && !clicked {
                    clicked = true
                    view.evaluateJavaScript("document.getElementById('start').click(); true") { _, error in clickError = error }
                }
                if session.diagnostics.contains(where: { $0.contains("RAW_SOL_READY") }) {
                    XCTAssertTrue(session.diagnostics.contains(where: { $0.contains("RAW_SOL_BEFORE " + expected) }),
                        "Actual AVM2 SharedObject value mismatch; " + session.diagnostics.suffix(12).joined(separator: " | "))
                    XCTAssertTrue(session.saveReady)
                    let saved = await session.closeAndSave()
                    guard saved else { throw SaveStoreError.invalid("synthetic raw SOL final save failed") }
                    print("RAW_SOL_RUNTIME complete movie=\(package.selectedMovie)")
                    return
                }
                try await Task.sleep(nanoseconds: 100_000_000)
            }
            throw SaveStoreError.invalid("synthetic raw SOL shared deadline exceeded")
        } catch {
            try? await session.closeWithoutSaving() // Await server drain, never race a new stable-port session.
            throw error
        }
    }
}

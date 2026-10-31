import XCTest
import UIKit
import WebKit
@testable import FlashNest

/// Real WK pages and production bridge/store integration. Manual termination callback
/// tests native sealing only; it is NOT a real WebContent crash, OOM or long-run test.
@MainActor final class LongRunSessionTests: XCTestCase {
    private enum Failure: Error { case invalid(String), javascriptDeadline }

    func testDefaultOffAndStorageOnlyNeverInstallLongRunObserver() async throws {
        executionTimeAllowance = 150
        try await withHarness { session, package, content, controller, store, deadline in
            XCTAssertFalse(session.longRunDiagnosticsEnabled)
            let first = try await self.open(session, package: package, content: content,
                                            controller: controller, deadline: deadline)
            let firstConfiguration = try await self.configurationState(first)
            XCTAssertEqual(firstConfiguration, "absent:absent")
            XCTAssertTrue(store.read().isEmpty)
            XCTAssertNil(session.longRunSummary)
            try await session.closeWithoutSaving()
            first.removeFromSuperview()
            // Even an opted-in preference must not instrument the storage-only
            // page used for save preservation instead of actual gameplay.
            session.longRunDiagnosticsEnabled = true
            let storage = try await self.open(session, package: package, content: content,
                controller: controller, deadline: deadline, storageOnly: true)
            let storageConfiguration = try await self.configurationState(storage)
            XCTAssertEqual(storageConfiguration, "absent:absent")
            XCTAssertTrue(store.read().isEmpty)
            XCTAssertNil(session.longRunSummary)
        }
    }

    func testOptInClearAndCurrentWKTerminationBoundary() async throws {
        executionTimeAllowance = 150
        try await withHarness { session, package, content, controller, store, deadline in
            session.longRunDiagnosticsEnabled = true
            let old = try await self.open(session, package: package, content: content,
                controller: controller, deadline: deadline)
            try await self.waitForSample(store, session: session, deadline: deadline)
            let enabledConfiguration = try await self.configurationState(old)
            XCTAssertEqual(enabledConfiguration, "present:present")
            let first = try XCTUnwrap(store.read().first)
            XCTAssertNotNil(first.lastSample, "Real document-start observer must post a valid snapshot")
            session.markLongRunObservation()
            XCTAssertEqual(store.read().first?.events.last?.kind, .userMarker)
            // Clear while the real page is alive, then attempt a valid delayed
            // bridge callback. Clearing must disable this session's persistence.
            let oldURL = try XCTUnwrap(old.url)
            let delayed = try self.body(from: first)
            session.clearLongRunDiagnostics()
            XCTAssertTrue(store.read().isEmpty)
            session.receiveScriptMessage(from: old, isMainFrame: true, requestURL: oldURL, body: delayed)
            session.markLongRunObservation()
            let stopped = try await self.evaluateString(old,
                script: "String(window.__FlashNestLongRunObserver?.isActive() === false)")
            XCTAssertEqual(stopped, "true", "Clearing must stop the actual live-page observer")
            XCTAssertTrue(store.read().isEmpty, "Cleared recording must not be recreated by queued messages")
            try await session.closeWithoutSaving()
            old.removeFromSuperview()
            XCTAssertTrue(store.read().isEmpty, "Stopping a cleared session must not recreate it")

            let active = try await self.open(session, package: package, content: content,
                controller: controller, deadline: deadline)
            try await self.waitForSample(store, session: session, deadline: deadline)
            let current = try XCTUnwrap(store.read().first)
            XCTAssertNotEqual(current.session, first.session)
            XCTAssertFalse(active === old)
            let activeURL = try XCTUnwrap(active.url)
            let validCurrentBody = try self.body(from: current)
            let before = store.read()
            // Use an otherwise current envelope to ensure WK object identity,
            // not only the anonymous session token, rejects the retained page.
            session.receiveScriptMessage(from: old, isMainFrame: true,
                                         requestURL: activeURL, body: validCurrentBody)
            session.webViewWebContentProcessDidTerminate(old)
            XCTAssertEqual(store.read(), before)
            XCTAssertNil(session.failure)

            // Manual delegate invocation exercises the existing native adapter;
            // no claim that this test killed the WebContent process.
            session.webViewWebContentProcessDidTerminate(active)
            let terminal = try XCTUnwrap(store.read().first)
            XCTAssertTrue(terminal.terminated)
            XCTAssertEqual(terminal.events.last?.kind, .webProcessTerminated)
            session.receiveScriptMessage(from: active, isMainFrame: true,
                                         requestURL: activeURL, body: validCurrentBody)
            XCTAssertEqual(store.read().first, terminal)
            session.clearLongRunDiagnostics()
            XCTAssertTrue(store.read().isEmpty)
        }
    }

    private func body(from snapshot: LongRunSnapshot) throws -> [String: Any] {
        var sample = try XCTUnwrap(snapshot.lastSample)
        sample.seq += 1
        sample.webElapsedMs += 10_000
        let data = try JSONEncoder().encode(sample)
        var value = try XCTUnwrap(JSONSerialization.jsonObject(with: data) as? [String: Any])
        value["type"] = "longRunDiagnostics"; value["schema"] = 1
        value["session"] = snapshot.session.uuidString; value["wkEpoch"] = snapshot.wkEpoch
        return value
    }

    private func withHarness(_ body: (PlayerSession, GamePackage, URL, UIViewController,
                                      LongRunDiagnostics, Date) async throws -> Void) async throws {
        let deadline = Date().addingTimeInterval(130)
        let root = FileManager.default.temporaryDirectory.resolvingSymlinksInPath()
            .appendingPathComponent(UUID().uuidString, isDirectory: true)
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: root) }
        let keys = [LongRunDiagnostics.preferenceKey, LoadingPhaseDiagnostics.preferenceKey]
        let previous = keys.map { UserDefaults.standard.object(forKey: $0) }
        for key in keys { UserDefaults.standard.removeObject(forKey: key) }
        defer {
            for (key, value) in zip(keys, previous) {
                if let value { UserDefaults.standard.set(value, forKey: key) }
                else { UserDefaults.standard.removeObject(forKey: key) }
            }
        }
        let fixtures = try XCTUnwrap(Bundle(for: LongRunSessionTests.self).url(forResource: "fixtures", withExtension: nil))
        let packages = root.appendingPathComponent("packages")
        let package = try PackageImporter(root: packages).stageAndCommit(
            fixtures.appendingPathComponent("frame-order/control-no-child-goto.swf"))
        let content = packages.appendingPathComponent(package.id.uuidString).appendingPathComponent("content")
        let store = LongRunDiagnostics(root: root.appendingPathComponent("long-run"))
        let session = PlayerSession(saveStore: SaveStore(root: root.appendingPathComponent("saves")),
            incidentStore: LastSessionDiagnostics(root: root.appendingPathComponent("incidents")), longRunStore: store)
        let scene = try XCTUnwrap(UIApplication.shared.connectedScenes.compactMap { $0 as? UIWindowScene }.first)
        let oldWindow = scene.windows.first(where: { $0.isKeyWindow })
        let window = UIWindow(windowScene: scene), controller = UIViewController()
        window.rootViewController = controller; window.makeKeyAndVisible()
        defer { window.isHidden = true; oldWindow?.makeKey() }
        var originalError: Error?
        do { try await body(session, package, content, controller, store, deadline) }
        catch { originalError = error }
        // Drain the real loopback listener and detach every retained test view on
        // both success and failure, before deleting the temporary file roots.
        do { try await session.closeWithoutSaving() }
        catch { if originalError == nil { originalError = error } }
        controller.view.subviews.forEach { $0.removeFromSuperview() }
        if let originalError { throw originalError }
    }

    private func open(_ session: PlayerSession, package: GamePackage, content: URL,
                      controller: UIViewController, deadline: Date, storageOnly: Bool = false) async throws -> WKWebView {
        await session.start(package: package, contentRoot: content, storageOnly: storageOnly)
        let view = try XCTUnwrap(session.webView, session.failure ?? "No WK page")
        view.frame = controller.view.bounds
        view.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        controller.view.addSubview(view)
        let end = min(deadline, Date().addingTimeInterval(35))
        while !session.saveReady && session.failure == nil && Date() < end {
            try await Task.sleep(nanoseconds: 50_000_000)
        }
        guard session.saveReady && session.failure == nil else { throw Failure.invalid("Bounded save-bridge startup did not finish") }
        return view
    }
    private func waitForSample(_ store: LongRunDiagnostics, session: PlayerSession, deadline: Date) async throws {
        let end = min(deadline, Date().addingTimeInterval(15))
        while store.read().first?.lastSample == nil && session.failure == nil && Date() < end {
            try await Task.sleep(nanoseconds: 50_000_000)
        }
        guard store.read().first?.lastSample != nil && session.failure == nil else { throw Failure.invalid("Bounded native long-run observer sample did not arrive") }
    }
    private func configurationState(_ view: WKWebView) async throws -> String {
        let script = "(Object.prototype.hasOwnProperty.call(window,'__FlashNestLongRunConfig')?'present':'absent')+':'+(Object.prototype.hasOwnProperty.call(window,'__FlashNestLongRunObserver')?'present':'absent')"
        return try await evaluateString(view, script: script)
    }
    private func evaluateString(_ view: WKWebView, script: String) async throws -> String {
        let value: Any = try await withCheckedThrowingContinuation { continuation in
            var completed = false
            view.evaluateJavaScript(script) { value, error in
                Task { @MainActor in
                    guard !completed else { return }; completed = true
                    if let error { continuation.resume(throwing: error) }
                    else { continuation.resume(returning: value ?? NSNull()) }
                }
            }
            Task { @MainActor in
                try? await Task.sleep(nanoseconds: 3_000_000_000)
                guard !completed else { return }; completed = true
                continuation.resume(throwing: Failure.javascriptDeadline)
            }
        }
        return try XCTUnwrap(value as? String)
    }
}

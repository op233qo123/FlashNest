import XCTest
import UIKit
import WebKit
@testable import FlashNest

/// Real AVM1 SharedObject bytecode and the pinned bundled Ruffle in WebKit.
/// Linux source checks do not constitute execution of these iOS-only tests.
@MainActor final class SharedObjectWebKitTests: XCTestCase {
    func testDestroyFlushCaptureRestoreAndPackageStorageIsolation() async throws {
        executionTimeAllowance = 120
        let deadline = Date().addingTimeInterval(110)
        let writer = try SaveFixturePage(movie: "close-flush.swf", label: "writer", deadline: deadline)
        defer { writer.stop() }
        try await writer.load()
        try await writer.waitForFixture(before: "undefined", deadline: deadline)
        _ = try await writer.evaluate("window.FlashNest.pause(); true", phase: "pause")
        let pausedCount = try await writer.storedSOLCount()
        XCTAssertEqual(pausedCount, 0,
                       "Pausing alone must not masquerade as flushing the unflushed SharedObject")
        let capture = try await writer.shutdownAndCapture()
        XCTAssertEqual(capture.version, 1)
        XCTAssertEqual(capture.entries.count, 1)
        let object = try XCTUnwrap(capture.entries.first)
        XCTAssertEqual(object.scope, "origin", "The fixture explicitly calls getLocal(name, '/')")
        XCTAssertEqual(object.key, "FlashNestFixture")
        let bytes = try XCTUnwrap(Data(base64Encoded: object.value))
        XCTAssertGreaterThan(bytes.count, 16)
        XCTAssertEqual(Array(bytes[0..<2]), [0, 0xbf])
        XCTAssertEqual(String(data: bytes[6..<10], encoding: .ascii), "TCSO")
        let destroyedCount = try await writer.storedSOLCount()
        XCTAssertEqual(destroyedCount, 1,
                       "Removing the player must flush before capture resolves")
        let writerUnrelated = try await writer.unrelatedValue()
        XCTAssertEqual(writerUnrelated, "keep-me")
        let capturedAgain = try await writer.shutdownAndCapture()
        XCTAssertEqual(capturedAgain.entries, capture.entries, "Repeated shutdown must be idempotent")
        let json = String(decoding: try JSONEncoder().encode(capture), as: UTF8.self)
        XCTAssertFalse(json.contains(writer.capability))
        XCTAssertFalse(json.contains(writer.packageID.uuidString))
        XCTAssertFalse(json.contains("127.0.0.1"))

        // Simulate divergence after WebKit flushed but native current.json was
        // stale/empty: ordinary open must prefer the newer live WebKit SOL.
        // Reuse this view/profile/origin so the extra load is not another cold
        // profile and so an accidental replacement genuinely loses progress42.
        try await writer.reload(movie: "read-only.swf",
                                restore: SaveCapture(version: 1, entries: []), policy: "ifEmpty")
        try await writer.waitForFixture(before: "42", deadline: deadline)
        let afterStaleNative = try await writer.shutdownAndCapture()
        XCTAssertEqual(afterStaleNative.entries, capture.entries,
                       "An ordinary open must not replace live saves with stale native backup data")
        let retainedUnrelated = try await writer.unrelatedValue()
        XCTAssertEqual(retainedUnrelated, "keep-me")

        // A different per-package persistent profile, capability, package UUID,
        // and loopback origin must restore before Ruffle executes the movie.
        // These extra identities exercise logical mapping with bytes produced
        // by real Ruffle. They do not claim this root-scope SWF emitted them.
        let mappedCapture = SaveCapture(version: 1, entries: capture.entries + [
            SaveEntry(scope: "package", key: "nested/FixtureObject", value: object.value),
            SaveEntry(scope: "ancestor", key: "games/FixtureGamesObject", value: object.value),
            SaveEntry(scope: "ancestor", key: "capability/FixtureCapabilityObject", value: object.value)
        ])
        let reader = try SaveFixturePage(movie: "read-only.swf", restore: mappedCapture, label: "reader", deadline: deadline)
        defer { reader.stop() }
        XCTAssertNotEqual(reader.packageID, writer.packageID)
        XCTAssertNotEqual(reader.capability, writer.capability)
        try await reader.load()
        try await reader.waitForFixture(before: "42", deadline: deadline)
        let readerUnrelated = try await reader.unrelatedValue()
        XCTAssertEqual(readerUnrelated, "keep-me",
                       "Restoring saves must not clear unrelated localStorage")
        let restored = try await reader.shutdownAndCapture()
        let identityOrder: (SaveEntry, SaveEntry) -> Bool = { left, right in
            left.scope + "\0" + left.key < right.scope + "\0" + right.key
        }
        XCTAssertEqual(restored.entries.sorted(by: identityOrder), mappedCapture.entries.sorted(by: identityOrder))
        let restoredJSON = String(decoding: try JSONEncoder().encode(restored), as: UTF8.self)
        XCTAssertFalse(restoredJSON.contains(reader.capability))
        XCTAssertFalse(restoredJSON.contains(reader.packageID.uuidString))

        // Even root localPath saves must not bleed into another game's profile.
        let isolated = try SaveFixturePage(movie: "read-only.swf", label: "isolated", deadline: deadline)
        defer { isolated.stop() }
        try await isolated.load()
        try await isolated.waitForFixture(before: "undefined", deadline: deadline)
        _ = try await isolated.shutdownAndCapture()
        // Keep the other profiles populated until isolation has been observed.
        // Their destroyed players cannot keep writing, but their views remain
        // attached so cleanup does not depend on waking a detached WebView.
        try await writer.clearTestStorage()
        try await reader.clearTestStorage()
        try await isolated.clearTestStorage()
    }

    func testExplicitSharedObjectFlushIsCapturedWithoutChangingItsBytes() async throws {
        executionTimeAllowance = 120
        let deadline = Date().addingTimeInterval(110)
        let page = try SaveFixturePage(movie: "explicit-flush.swf", label: "explicit", deadline: deadline)
        defer { page.stop() }
        try await page.load()
        try await page.waitForFixture(before: "undefined", deadline: deadline)
        XCTAssertTrue(page.messages.traces.contains(where: { $0.hasPrefix("SWF: FLASHNEST_SAVE_FLUSH:") }))
        let explicitCount = try await page.storedSOLCount()
        XCTAssertEqual(explicitCount, 1)
        let before = try await page.solValues()
        let capture = try await page.shutdownAndCapture()
        XCTAssertEqual(capture.entries.count, 1)
        XCTAssertEqual(capture.entries.map(\.value), before,
                       "Export must preserve the actual Ruffle SOL bytes, not convert them to a savestate")
        let unrelated = try await page.unrelatedValue()
        XCTAssertEqual(unrelated, "keep-me")
        try await page.clearTestStorage()
    }
}

@MainActor private final class SaveFixtureMessages: NSObject, WKScriptMessageHandler {
    var types: [String] = []
    var traces: [String] = []
    var failed = false

    func userContentController(_ controller: WKUserContentController, didReceive message: WKScriptMessage) {
        guard message.frameInfo.isMainFrame, let body = message.body as? [String: Any],
              let type = body["type"] as? String else { return }
        types.append(type)
        if type == "error" { failed = true }
        // Deliberately retain only known fixture traces, never capability URLs.
        if let text = body["message"] as? String, text.hasPrefix("SWF: FLASHNEST_SAVE_") {
            traces.append(text)
        }
    }
}

@MainActor private final class SaveFixturePage {
    let packageID: UUID
    let capability: String
    let messages: SaveFixtureMessages
    let view: WKWebView
    private let server: LoopbackServer
    private let dataStore: WKWebsiteDataStore
    private let window: UIWindow
    private weak var previousKeyWindow: UIWindow?
    private let movie: String
    private let label: String
    private let deadline: Date
    private let beganAt = Date()
    private var serverStarted = false
    private var stopped = false

    init(movie: String, restore: SaveCapture? = nil, label: String, deadline: Date) throws {
        let identifier = UUID()
        let token = UUID().uuidString.lowercased()
        let recorder = SaveFixtureMessages()
        let fixtureRoot = try XCTUnwrap(Bundle(for: SharedObjectWebKitTests.self)
            .url(forResource: "fixtures", withExtension: nil)).appendingPathComponent("shared-object")
        let webRoot = try XCTUnwrap(Bundle.main.url(forResource: "Web", withExtension: nil))
        let localServer = LoopbackServer(port: UInt16.random(in: 49152...62000), capability: token, webRoot: webRoot)
        localServer.activate(packageID: identifier, root: fixtureRoot)
        let storage = WKWebsiteDataStore(forIdentifier: identifier)
        let configuration = WKWebViewConfiguration()
        configuration.websiteDataStore = storage
        configuration.allowsInlineMediaPlayback = true
        configuration.mediaTypesRequiringUserActionForPlayback = [.audio, .video]
        configuration.userContentController.add(recorder, name: "flashnest")
        var setup = "localStorage.setItem('FlashNestFixture.unrelated', 'keep-me');"
        if let restore {
            let json = String(decoding: try JSONEncoder().encode(restore), as: UTF8.self)
            setup += "window.__FlashNestRestore = \(json); window.__FlashNestRestorePolicy = 'replace';"
        }
        configuration.userContentController.addUserScript(WKUserScript(source: setup,
            injectionTime: .atDocumentStart, forMainFrameOnly: true))
        let webView = WKWebView(frame: .zero, configuration: configuration)
        let scene = try XCTUnwrap(UIApplication.shared.connectedScenes.compactMap { $0 as? UIWindowScene }.first)
        let previous = scene.windows.first(where: \.isKeyWindow)
        let fixtureWindow = UIWindow(windowScene: scene)
        let controller = UIViewController()
        fixtureWindow.rootViewController = controller
        fixtureWindow.makeKeyAndVisible()
        webView.frame = controller.view.bounds
        webView.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        controller.view.addSubview(webView)
        packageID = identifier
        capability = token
        messages = recorder
        view = webView
        server = localServer
        dataStore = storage
        window = fixtureWindow
        previousKeyWindow = previous
        self.movie = movie
        self.label = label
        self.deadline = deadline
    }

    func load(movie: String? = nil) async throws {
        guard !stopped else { throw fixtureError("Cannot load a stopped fixture") }
        _ = try remainingTime(for: "load")
        if !serverStarted {
            phase("server-start.begin")
            // LoopbackServer already bounds initial listener readiness to 10s.
            try await server.start()
            serverStarted = true
            phase("server-start.complete")
        }
        phase("navigation.begin movie=" + (movie ?? self.movie))
        var components = URLComponents(url: server.shellURL, resolvingAgainstBaseURL: false)!
        components.queryItems = [URLQueryItem(name: "entry", value: movie ?? self.movie),
                                URLQueryItem(name: "package", value: packageID.uuidString),
                                URLQueryItem(name: "language", value: "en")]
        view.load(URLRequest(url: try XCTUnwrap(components.url)))
        phase("navigation.issued")
    }

    func reload(movie: String, restore: SaveCapture, policy: String) async throws {
        phase("reload.prepare policy=" + policy)
        let json = String(decoding: try JSONEncoder().encode(restore), as: UTF8.self)
        let policyJSON = String(decoding: try JSONEncoder().encode(policy), as: UTF8.self)
        let setup = "window.__FlashNestRestore = \(json); window.__FlashNestRestorePolicy = \(policyJSON);"
        view.configuration.userContentController.removeAllUserScripts()
        view.configuration.userContentController.addUserScript(WKUserScript(source: setup,
            injectionTime: .atDocumentStart, forMainFrameOnly: true))
        messages.types.removeAll()
        messages.traces.removeAll()
        messages.failed = false
        try await load(movie: movie)
    }

    func waitForFixture(before: String, deadline: Date) async throws {
        phase("movie.await expected=" + before)
        var started = false
        while Date() < deadline {
            if messages.failed { throw fixtureError("Shell reported an error before the SharedObject fixture completed") }
            if !started, messages.types.contains("loaded") {
                guard let saveReady = messages.types.firstIndex(of: "saveReady"),
                      let loaded = messages.types.firstIndex(of: "loaded"), saveReady < loaded else {
                    throw fixtureError("Save restoration must finish before the movie is reported loaded")
                }
                // Synthetic click checks the real DOM overlay path, not trusted audio.
                _ = try await evaluate("document.getElementById('start').click(); true", phase: "movie.start")
                started = true
            }
            if messages.traces.contains("SWF: FLASHNEST_SAVE_READY") {
                XCTAssertTrue(started)
                XCTAssertTrue(messages.traces.contains("SWF: FLASHNEST_SAVE_BEFORE:\(before)"),
                              "Unexpected SharedObject value; observed only fixture traces: \(messages.traces)")
                XCTAssertNotNil(view.window)
                phase("movie.ready expected=" + before + " traces=" + messages.traces.joined(separator: " | "))
                return
            }
            try await Task.sleep(nanoseconds: 100_000_000)
        }
        throw fixtureError("SharedObject fixture exceeded its deadline; started=\(started), message types=\(messages.types)")
    }

    func shutdownAndCapture() async throws -> SaveCapture {
        phase("capture.begin")
        let result = try await SaveWebKitBridge.capture(from: view, timeout: min(15, try remainingTime(for: "capture")))
        let bytes = try JSONSerialization.data(withJSONObject: result)
        let capture = try JSONDecoder().decode(SaveCapture.self, from: bytes)
        phase("capture.complete objects=\(capture.entries.count)")
        return capture
    }

    func solValues() async throws -> [String] {
        let result = try await evaluate("""
        Object.keys(localStorage).map(key => localStorage.getItem(key)).filter(value => {
          try {
            const bytes = atob(value);
            return bytes.length >= 16 && bytes.charCodeAt(0) === 0 && bytes.charCodeAt(1) === 191 && bytes.slice(6, 10) === 'TCSO';
          } catch (_) { return false; }
        }).sort()
        """, phase: "storage.read-sol")
        return try XCTUnwrap(result as? [String])
    }

    func storedSOLCount() async throws -> Int { (try await solValues()).count }

    func unrelatedValue() async throws -> String? {
        try await evaluate("localStorage.getItem('FlashNestFixture.unrelated')", phase: "storage.read-unrelated") as? String
    }

    func clearTestStorage() async throws {
        // Match the already-passing explicit-flush path: finish data-store work
        // while this fixture's view is attached, before detaching/suspending it.
        guard view.window != nil, !stopped else { throw fixtureError("Cleanup requires an attached fixture") }
        phase("storage-cleanup.begin")
        let allowance = min(5, try remainingTime(for: "storage-cleanup"))
        try await withCheckedThrowingContinuation { (continuation: CheckedContinuation<Void, Error>) in
            var completed = false
            dataStore.removeData(ofTypes: WKWebsiteDataStore.allWebsiteDataTypes(), modifiedSince: .distantPast) {
                Task { @MainActor in
                    guard !completed else { return }
                    completed = true
                    continuation.resume()
                }
            }
            Task { @MainActor in
                try? await Task.sleep(nanoseconds: UInt64(allowance * 1_000_000_000))
                guard !completed else { return }
                completed = true
                continuation.resume(throwing: self.fixtureError("Timed out during storage-cleanup"))
            }
        }
        phase("storage-cleanup.complete")
    }

    /// Test diagnostics use the longstanding callback API and a deadline, not
    /// the affected refined callAsyncJavaScript overlay or an unbounded await.
    func evaluate(_ script: String, phase name: String) async throws -> Any {
        phase(name + ".begin")
        let allowance = min(10, try remainingTime(for: name))
        let result: Any = try await withCheckedThrowingContinuation { continuation in
            var completed = false
            view.evaluateJavaScript(script) { value, error in
                Task { @MainActor in
                    guard !completed else { return }
                    completed = true
                    if error != nil { continuation.resume(throwing: self.fixtureError("JavaScript failed during " + name)) }
                    else { continuation.resume(returning: value ?? NSNull()) }
                }
            }
            Task { @MainActor in
                try? await Task.sleep(nanoseconds: UInt64(allowance * 1_000_000_000))
                guard !completed else { return }
                completed = true
                continuation.resume(throwing: self.fixtureError("Timed out during " + name))
            }
        }
        phase(name + ".complete")
        return result
    }

    private func remainingTime(for operation: String) throws -> TimeInterval {
        let remaining = deadline.timeIntervalSinceNow
        guard remaining > 0 else { throw fixtureError("Shared fixture deadline exceeded during " + operation) }
        return remaining
    }

    private func phase(_ name: String) {
        // Never log a capability URL, imported key, or save contents.
        print("FLASHNEST_SAVE_TEST \(label) \(name) elapsed=\(String(format: "%.2f", Date().timeIntervalSince(beganAt))) attached=\(view.window != nil) types=\(messages.types.joined(separator: ","))")
    }

    func stop() {
        guard !stopped else { return }
        phase("stop")
        stopped = true
        view.stopLoading()
        view.configuration.userContentController.removeScriptMessageHandler(forName: "flashnest")
        view.removeFromSuperview()
        window.isHidden = true
        previousKeyWindow?.makeKey()
        server.stop()
    }

    private func fixtureError(_ detail: String) -> Error {
        NSError(domain: "FlashNestSharedObjectFixture", code: 1,
                userInfo: [NSLocalizedDescriptionKey: detail])
    }
}

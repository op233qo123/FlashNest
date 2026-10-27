import XCTest
import WebKit
@testable import FlashNest

/// Two real WKWebViews with structured synthetic bridge input. This tests the
/// native callback boundary, NOT a reproduction of a WebContent SIGBUS or OOM.
@MainActor final class PlayerCallbackIdentityTests: XCTestCase {
    override func setUpWithError() throws { executionTimeAllowance = 120 }
    func testPriorPageMessagesCannotMutateReplacementAtSameShellURL() async throws {
        try await withSession { session, package, root in
            let old = try XCTUnwrap(session.webView)
            try await session.closeWithoutSaving()
            await session.start(package: package, contentRoot: root, storageOnly: true)
            try await self.waitForSaveReady(session)
            let active = try XCTUnwrap(session.webView)
            XCTAssertFalse(old === active)
            let url = try XCTUnwrap(active.url)
            let before = session.diagnostics
            XCTAssertFalse(session.isLoaded)
            // Deliver actual public WKScriptMessage objects from the retained old
            // page through the production adapter, not only the structured seam.
            let forwarded = try await self.postActualMessages(from: old, to: session,
                script: "window.webkit.messageHandlers.flashnest.postMessage({type:'loaded'}); window.webkit.messageHandlers.flashnest.postMessage({type:'error',message:'actual-old-page-error'}); true",
                count: 2)
            XCTAssertTrue(forwarded.allSatisfy { $0.webView === old && $0.frameInfo.isMainFrame && $0.frameInfo.request.url?.path == url.path })
            let bodies: [[String: Any]] = [
                ["type": "loaded"], ["type": "error", "message": "stale-page-error"],
                ["type": "diagnostic", "message": "stale-page-diagnostic"], ["type": "saveReady"]
            ]
            for body in bodies {
                session.receiveScriptMessage(from: old, isMainFrame: true, requestURL: url, body: body)
            }
            XCTAssertFalse(session.isLoaded, "An old page must not mark a storage-only successor loaded")
            XCTAssertNil(session.failure)
            XCTAssertEqual(session.diagnostics, before)
            XCTAssertTrue(session.saveReady)
            XCTAssertTrue(session.webView === active)
            let accepted = try await self.postActualMessages(from: active, to: session,
                script: "window.webkit.messageHandlers.flashnest.postMessage({type:'loaded'}); true", count: 1)
            XCTAssertTrue(accepted.first?.webView === active)
            XCTAssertTrue(session.isLoaded, "The active page's legitimate callback still works")
        }
    }

    func testNilForeignFrameAndStoppedPageMessagesAreRejected() async throws {
        try await withSession { session, _, _ in
            let active = try XCTUnwrap(session.webView), url = try XCTUnwrap(session.webView?.url)
            let before = session.diagnostics
            session.receiveScriptMessage(from: nil, isMainFrame: true, requestURL: url, body: ["type": "loaded"])
            session.receiveScriptMessage(from: active, isMainFrame: false, requestURL: url, body: ["type": "loaded"])
            session.receiveScriptMessage(from: active, isMainFrame: true, requestURL: URL(string: "https://example.invalid/"), body: ["type": "error", "message": "foreign-origin"])
            XCTAssertFalse(session.isLoaded); XCTAssertNil(session.failure); XCTAssertEqual(session.diagnostics, before)
            session.receiveScriptMessage(from: active, isMainFrame: true, requestURL: url, body: ["type": "diagnostic", "message": "active-page-proof"])
            XCTAssertTrue(session.diagnostics.contains { $0.contains("active-page-proof") })
            try await session.closeWithoutSaving()
            session.receiveScriptMessage(from: active, isMainFrame: true, requestURL: url, body: ["type": "error", "message": "after-stop"])
            XCTAssertNil(session.failure); XCTAssertNil(session.webView)
        }
    }

    func testStaleNavigationFailuresCannotOverwriteActiveOrTerminatedPageState() async throws {
        try await withSession { session, _, _ in
            let active = try XCTUnwrap(session.webView), stale = WKWebView()
            let error = NSError(domain: NSURLErrorDomain, code: NSURLErrorCannotConnectToHost)
            let before = session.diagnostics
            session.webView(stale, didFailProvisionalNavigation: nil, withError: error)
            session.webView(stale, didFail: nil, withError: error)
            XCTAssertNil(session.failure); XCTAssertEqual(session.diagnostics, before)
            session.webView(active, didFailProvisionalNavigation: nil, withError: error)
            XCTAssertNotNil(session.failure, "Active-page failures must remain visible")
            session.webViewWebContentProcessDidTerminate(active)
            let terminatedFailure = session.failure, terminatedDiagnostics = session.diagnostics
            session.webView(active, didFail: nil, withError: error)
            XCTAssertEqual(session.failure, terminatedFailure)
            XCTAssertEqual(session.diagnostics, terminatedDiagnostics)
        }
    }

    private func postActualMessages(from view: WKWebView, to session: PlayerSession,
                                    script: String, count: Int) async throws -> [WKScriptMessage] {
        let forwarder = CallbackMessageForwarder(session: session)
        let controller = view.configuration.userContentController
        controller.removeScriptMessageHandler(forName: "flashnest")
        controller.add(forwarder, name: "flashnest")
        defer {
            controller.removeScriptMessageHandler(forName: "flashnest")
            if session.webView === view { controller.add(session, name: "flashnest") }
        }
        _ = try await view.evaluateJavaScript(script)
        let deadline = Date().addingTimeInterval(5)
        while forwarder.messages.count < count, Date() < deadline { try await Task.sleep(nanoseconds: 20_000_000) }
        guard forwarder.messages.count == count else { throw SaveStoreError.invalid("actual WK callback count mismatch") }
        return forwarder.messages
    }

    private func withSession(_ body: (PlayerSession, GamePackage, URL) async throws -> Void) async throws {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: root) }
        let package = GamePackage(id: UUID(), title: "Original callback fixture", importedAt: Date(), movies: ["unused.swf"], selectedMovie: "unused.swf")
        let session = PlayerSession(saveStore: SaveStore(root: root.appendingPathComponent("save")))
        await session.start(package: package, contentRoot: root, storageOnly: true)
        do {
            try await waitForSaveReady(session)
            try await body(session, package, root)
        } catch {
            try? await session.closeWithoutSaving()
            throw error
        }
        try await session.closeWithoutSaving()
    }

    private func waitForSaveReady(_ session: PlayerSession) async throws {
        let deadline = Date().addingTimeInterval(30)
        while !session.saveReady, session.failure == nil, Date() < deadline {
            try await Task.sleep(nanoseconds: 50_000_000)
        }
        guard session.saveReady, session.failure == nil else { throw SaveStoreError.invalid("synthetic callback fixture did not become ready; failure=\(session.failure != nil), loaded=\(session.isLoaded), ready=\(session.saveReady), diagnostics=\(session.diagnostics.suffix(8).joined(separator: " | "))") }
    }
}

@MainActor private final class CallbackMessageForwarder: NSObject, WKScriptMessageHandler {
    let session: PlayerSession
    var messages: [WKScriptMessage] = []
    init(session: PlayerSession) { self.session = session }
    func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
        session.userContentController(userContentController, didReceive: message)
        messages.append(message)
    }
}

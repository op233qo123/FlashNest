import XCTest
import UIKit
import WebKit
@testable import FlashNest

/// Real bundled WASM in WKWebView, not a mocked Ruffle API. Must run on an iOS
/// simulator/device; a source/static pass is not evidence that this test passed.
@MainActor final class RuffleRuntimeTests: XCTestCase {
    func testFolderImportExecutesSecondaryMovieInWebKit() async throws {
        try await exerciseFixture(named: "multi-swf")
    }

    func testZIPImportExecutesSecondaryMovieInWebKit() async throws {
        try await exerciseFixture(named: "multi-swf.zip")
    }

    private func exerciseFixture(named name: String) async throws {
        let fixtures = try XCTUnwrap(Bundle(for: RuffleRuntimeTests.self).url(forResource: "fixtures", withExtension: nil))
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: root) }
        let package = try PackageImporter(root: root).stageAndCommit(fixtures.appendingPathComponent(name))
        XCTAssertTrue(package.movies.contains("sub/child.swf"))
        XCTAssertEqual(package.selectedMovie, "main.swf")

        let session = PlayerSession()
        // Ruffle pauses hidden/background views, so attach to a visible scene.
        let scene = try XCTUnwrap(UIApplication.shared.connectedScenes.compactMap { $0 as? UIWindowScene }.first)
        let previousKeyWindow = scene.windows.first(where: { $0.isKeyWindow })
        let window = UIWindow(windowScene: scene)
        let controller = UIViewController()
        window.rootViewController = controller
        window.makeKeyAndVisible()
        defer {
            session.stop()
            window.isHidden = true
            previousKeyWindow?.makeKey()
        }
        await session.start(package: package, contentRoot: root.appendingPathComponent(package.id.uuidString).appendingPathComponent("content"))
        if let failure = session.failure { XCTFail(failure); return }
        let view = try XCTUnwrap(session.webView)
        view.frame = controller.view.bounds
        view.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        controller.view.addSubview(view)

        let deadline = Date().addingTimeInterval(45)
        var started = false
        while Date() < deadline {
            if let failure = session.failure { XCTFail(failure); return }
            if !started && session.status == "Playing" {
                // Observe a real Ruffle asset request without substituting data.
                _ = try await view.evaluateJavaScript("""
                window.__fixtureText = null;
                window.__fixtureRemoteBlocked = null;
                const fixtureFetch = window.fetch.bind(window);
                window.fetch = async (...args) => {
                  const response = await fixtureFetch(...args);
                  if (new URL(response.url).pathname.endsWith('/sibling.txt')) {
                    window.__fixtureText = await response.clone().text();
                  }
                  return response;
                };
                fetch('https://example.com/flashnest-offline-probe').then(
                  () => { window.__fixtureRemoteBlocked = false; },
                  () => { window.__fixtureRemoteBlocked = true; }
                );
                true;
                """)
                // Synthetic click tests execution, not the trusted audio-gesture gate.
                _ = try await view.evaluateJavaScript("document.getElementById('start').click(); true")
                started = true
            }
            if session.diagnostics.contains(where: { $0.contains("FLASHNEST_CHILD_OK") }) {
                let assetsAndPolicy = try await view.evaluateJavaScript("window.__fixtureText?.includes('FLASHNEST_TEXT_OK') === true && window.__fixtureRemoteBlocked === true") as? Bool
                if assetsAndPolicy == true {
                    XCTAssertTrue(started)
                    XCTAssertFalse(session.diagnostics.contains(where: { $0.contains("Missing local asset") || $0.contains("Asset request failed") }))
                    return
                }
            }
            try await Task.sleep(nanoseconds: 100_000_000)
        }
        XCTFail("Real WKWebView did not complete child SWF, sibling text, and offline-denial checks. Status: \(session.status); diagnostics: \(session.diagnostics.joined(separator: " | "))")
    }
}

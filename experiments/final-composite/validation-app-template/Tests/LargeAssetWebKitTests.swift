import XCTest
import UIKit
import WebKit
import CryptoKit
@testable import FlashNest

/// Transport/inventory regression independent of Ruffle and of real game content.
/// Passing source checks on Linux is not execution of this iOS-only test.
@MainActor final class LargeAssetWebKitTests: XCTestCase {
    func testImportedContentFolderUnicodeLargeMovieArrivesIntactInWebKit() async throws {
        executionTimeAllowance = 120
        let fm = FileManager.default
        let root = fm.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try fm.createDirectory(at: root, withIntermediateDirectories: true)
        defer { try? fm.removeItem(at: root) }
        let source = root.appendingPathComponent("source")
        let sourceContent = source.appendingPathComponent("content")
        let web = root.appendingPathComponent("web")
        let library = root.appendingPathComponent("library")
        try fm.createDirectory(at: sourceContent, withIntermediateDirectories: true)
        try fm.createDirectory(at: web, withIntermediateDirectories: true)
        let relative = "content/打倒！超魔王様（Flash版）.swf"
        let original = source.appendingPathComponent(relative)
        XCTAssertTrue(fm.createFile(atPath: original.path, contents: nil))
        let writer = try FileHandle(forWritingTo: original)
        var digest = SHA256()
        // Every block has an index marker so duplicated/reordered chunks cannot
        // pass merely because a large fixture consists of identical zero bytes.
        let pattern = Data((0..<65_536).map { UInt8($0 % 251) })
        do {
            for index in 0..<(44 * 16) {
                var block = pattern
                block[0] = UInt8(index & 255)
                block[1] = UInt8((index >> 8) & 255)
                if index == 0 { block.replaceSubrange(0..<3, with: Data("FWS".utf8)) }
                digest.update(data: block)
                try writer.write(contentsOf: block)
            }
            let tail = Data((0..<17).map { UInt8(0xe0 + $0) })
            XCTAssertEqual(tail.count, 17)
            digest.update(data: tail)
            try writer.write(contentsOf: tail)
            try writer.close()
        } catch {
            try? writer.close()
            throw error
        }
        let expectedCount = 44 * 1_048_576 + 17
        let expectedHash = digest.finalize().map { String(format: "%02x", $0) }.joined()
        let package = try await Task.detached {
            try PackageImporter(root: library).stageAndCommit(source)
        }.value
        XCTAssertEqual(package.movies, [relative], "A genuine source folder named content must not be stripped")
        XCTAssertEqual(package.selectedMovie, relative)
        let importedRoot = library.appendingPathComponent(package.id.uuidString).appendingPathComponent("content")
        XCTAssertTrue(fm.fileExists(atPath: importedRoot.appendingPathComponent(relative).path))
        try Data("<!doctype html><title>Large asset transport ready</title><body>Transport probe</body>".utf8)
            .write(to: web.appendingPathComponent("index.html"))
        let server = LoopbackServer(port: UInt16.random(in: 49152...62000),
                                    capability: UUID().uuidString.lowercased(), webRoot: web)
        defer { server.stop() }
        server.activate(packageID: package.id, root: importedRoot)
        try await server.start()
        let assetURL = server.gameURL(packageID: package.id, relativePath: relative)
        let configuration = URLSessionConfiguration.ephemeral
        configuration.timeoutIntervalForRequest = 30
        configuration.timeoutIntervalForResource = 45
        let network = URLSession(configuration: configuration)
        defer { network.invalidateAndCancel() }
        do {
            let (bytes, response) = try await network.data(from: assetURL)
            XCTAssertEqual((response as? HTTPURLResponse)?.statusCode, 200)
            XCTAssertEqual(bytes.count, expectedCount)
            XCTAssertEqual(SHA256.hash(data: bytes).map { String(format: "%02x", $0) }.joined(), expectedHash)
        }

        let scene = try XCTUnwrap(UIApplication.shared.connectedScenes.compactMap { $0 as? UIWindowScene }.first)
        let previousKeyWindow = scene.windows.first(where: { $0.isKeyWindow })
        let window = UIWindow(windowScene: scene)
        let controller = UIViewController()
        window.rootViewController = controller
        window.makeKeyAndVisible()
        let webConfiguration = WKWebViewConfiguration()
        webConfiguration.websiteDataStore = .nonPersistent()
        let view = WKWebView(frame: controller.view.bounds, configuration: webConfiguration)
        view.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        controller.view.addSubview(view)
        defer {
            view.stopLoading()
            view.removeFromSuperview()
            window.isHidden = true
            previousKeyWindow?.makeKey()
        }
        view.load(URLRequest(url: server.shellURL))
        // Encode the URL as JSON rather than interpolating unescaped Unicode or
        // quotes into JavaScript. Never print this capability-bearing value.
        let urlJSON = String(data: try JSONEncoder().encode(assetURL.absoluteString), encoding: .utf8)!
        let deadline = Date().addingTimeInterval(90)
        var started = false
        var lastState = "page not ready"
        while Date() < deadline {
            if !started, (try? await view.evaluateJavaScript("document.title")) as? String == "Large asset transport ready" {
                _ = try await view.evaluateJavaScript("""
                window.__largeAsset = {state:'fetching'};
                (async () => {
                  try {
                    const response = await fetch(\(urlJSON), {cache:'no-store'});
                    window.__largeAsset = {state:'reading', status:response.status};
                    const body = await response.arrayBuffer();
                    window.__largeAsset = {state:'hashing', status:response.status, count:body.byteLength};
                    if (!window.crypto?.subtle) throw new Error('SHA-256 unavailable in loopback context');
                    const digest = new Uint8Array(await crypto.subtle.digest('SHA-256', body));
                    window.__largeAsset = {state:'complete', status:response.status, count:body.byteLength,
                      hash:Array.from(digest, x => x.toString(16).padStart(2,'0')).join('')};
                  } catch (_) {
                    // Do not log exception messages: network errors may include
                    // the capability URL. The last safe milestone is retained.
                    window.__largeAsset = {...window.__largeAsset, state:'error'};
                  }
                })(); true;
                """)
                started = true
            }
            if started, let result = try await view.evaluateJavaScript("window.__largeAsset") as? [String: Any] {
                lastState = "state=\(result["state"] ?? "unknown"), status=\(result["status"] ?? "unknown"), bytes=\(result["count"] ?? "unknown")"
                if result["state"] as? String == "complete" {
                    XCTAssertEqual((result["status"] as? NSNumber)?.intValue, 200)
                    XCTAssertEqual((result["count"] as? NSNumber)?.intValue, expectedCount)
                    XCTAssertEqual(result["hash"] as? String, expectedHash)
                    XCTAssertNotNil(view.window)
                    view.stopLoading()
                    view.removeFromSuperview()
                    try await exerciseProductionFetch(package: package, contentRoot: importedRoot,
                                                      controller: controller, deadline: deadline,
                                                      count: expectedCount, hash: expectedHash)
                    return
                }
                if result["state"] as? String == "error" { XCTFail("WKWebView large-asset fetch failed: \(lastState)"); return }
            }
            try await Task.sleep(nanoseconds: 100_000_000)
        }
        XCTFail("WKWebView large-asset fetch exceeded 90 seconds: \(lastState); started=\(started)")
    }

    /// The synthetic SWF is intentionally not a playable movie. This second
    /// probe asserts transport only, using the real session's persistent profile,
    /// offline content rules, bundled shell, and capability-protected routing.
    private func exerciseProductionFetch(package: GamePackage, contentRoot: URL,
                                         controller: UIViewController, deadline: Date,
                                         count: Int, hash: String) async throws {
        let session = PlayerSession()
        defer { session.stop() }
        await session.start(package: package, contentRoot: contentRoot)
        let view = try XCTUnwrap(session.webView, "Production session must create its WebKit view")
        view.frame = controller.view.bounds
        controller.view.addSubview(view)
        defer { view.removeFromSuperview() }
        let relative = "../games/" + package.id.uuidString + "/" + package.selectedMovie
        let literal = String(data: try JSONEncoder().encode(relative), encoding: .utf8)!
        var started = false
        var lastState = "shell not ready"
        while Date() < deadline {
            if !started, (try? await view.evaluateJavaScript("document.getElementById('stage') !== null")) as? Bool == true {
                _ = try await view.evaluateJavaScript("""
                window.__productionTransport = {state:'fetching'};
                (async () => {
                  try {
                    const response = await fetch(new URL(\(literal), location.href));
                    window.__productionTransport = {state:'reading', status:response.status};
                    const bytes = await response.arrayBuffer();
                    window.__productionTransport = {state:'hashing', status:response.status, count:bytes.byteLength};
                    const digest = new Uint8Array(await crypto.subtle.digest('SHA-256', bytes));
                    window.__productionTransport = {state:'complete', status:response.status, count:bytes.byteLength,
                      hash:Array.from(digest, x => x.toString(16).padStart(2,'0')).join('')};
                  } catch (_) {
                    window.__productionTransport = {...window.__productionTransport, state:'error'};
                  }
                })(); true;
                """)
                started = true
            }
            if started, let result = try await view.evaluateJavaScript("window.__productionTransport") as? [String: Any] {
                lastState = "state=\(result["state"] ?? "unknown"), status=\(result["status"] ?? "unknown"), bytes=\(result["count"] ?? "unknown")"
                if result["state"] as? String == "complete" {
                    XCTAssertEqual((result["status"] as? NSNumber)?.intValue, 200)
                    XCTAssertEqual((result["count"] as? NSNumber)?.intValue, count)
                    XCTAssertEqual(result["hash"] as? String, hash)
                    XCTAssertNotNil(view.window)
                    return
                }
                if result["state"] as? String == "error" {
                    XCTFail("Production-config large-asset transport failed: \(lastState)")
                    return
                }
            }
            try await Task.sleep(nanoseconds: 100_000_000)
        }
        XCTFail("Production-config transport exceeded shared 90-second deadline: \(lastState)")
    }

}

import XCTest
import UIKit
import WebKit
@testable import FlashNest

/// The pinned engine must execute the SWF hit handler with correct stage
/// coordinates. Synthetic DOM pointers here complement, not replace, the
/// trusted UIKit touches in ViewportRenderingUITests on iOS 18.2.
@MainActor final class ViewportRenderingRuntimeTests: XCTestCase {
    private let targets: [(String, CGPoint)] = [
        ("TL", CGPoint(x: 32, y: 32)), ("TR", CGPoint(x: 288, y: 32)),
        ("BL", CGPoint(x: 32, y: 208)), ("BR", CGPoint(x: 288, y: 208)),
        ("C", CGPoint(x: 160, y: 120))
    ]

    func testOriginalAndHalfResolutionKeepVisualBoundsAndChildInputMapping() async throws {
        executionTimeAllowance = 120
        let fixtures = try XCTUnwrap(Bundle(for: Self.self).url(forResource: "fixtures", withExtension: nil))
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: root) }
        let package = try PackageImporter(root: root).stageAndCommit(fixtures.appendingPathComponent("viewport-input"))
        defer { UserDefaults.standard.removeObject(forKey: RenderSettings.preferenceKey(for: package.id)) }
        let scene = try XCTUnwrap(UIApplication.shared.connectedScenes.compactMap { $0 as? UIWindowScene }.first)
        let previousKeyWindow = scene.windows.first(where: { $0.isKeyWindow })
        let window = UIWindow(windowScene: scene)
        let controller = UIViewController()
        window.rootViewController = controller; window.makeKeyAndVisible()
        defer { window.isHidden = true; previousKeyWindow?.makeKey() }
        var originalPixels: [CGFloat: Double] = [:]
        var originalDPR: Double?

        for half in [false, true] {
            RenderSettings(usesHalfResolution: half).save(for: package.id)
            let session = PlayerSession()
            defer { session.stop() }
            await session.start(package: package, contentRoot: root.appendingPathComponent(package.id.uuidString).appendingPathComponent("content"))
            let web = try XCTUnwrap(session.webView, session.failure ?? "Missing viewport WebView")
            web.frame = CGRect(x: 0, y: 0, width: 440, height: 860)
            controller.view.addSubview(web)
            guard try await waitUntil(seconds: 60, { session.isLoaded }) else {
                XCTFail("Viewport fixture failed to load: \(session.failure ?? "") \(session.diagnostics)"); return
            }
            _ = try await web.evaluateJavaScript("document.getElementById('start').click(); true")
            try await requireTrace("VIEWPORT_ROOT_READY", session: session)
            let activeQuery = URLComponents(url: try XCTUnwrap(web.url), resolvingAgainstBaseURL: false)?.queryItems
            XCTAssertEqual(activeQuery?.first(where: { $0.name == "renderMode" })?.value, half ? "half" : nil)
            // The setting is a next-opening preference, not a live reload.
            RenderSettings(usesHalfResolution: !half).save(for: package.id)
            XCTAssertEqual(session.activeRenderSettings?.usesHalfResolution, half)
            try await checkTargets(web, session: session)
            session.key("Enter", down: true); session.key("Enter", down: false)
            try await requireTrace("VIEWPORT_CHILD_READY", session: session)

            // Change the actual WK viewport dimensions; the separate UI test
            // rotates the simulator and exercises native touch routing too.
            for size in [CGSize(width: 440, height: 860), CGSize(width: 860, height: 440)] {
                web.frame.size = size
                let factor = half ? 0.5 : 1.0
                let settled = try await waitForMetrics(web, size: size, factor: factor)
                XCTAssertTrue(settled, "Canvas must settle to the selected layout before hit testing")
                let values = try await metrics(web)
                let dpr = try number("dpr", values)
                if let originalDPR { XCTAssertEqual(dpr, originalDPR, accuracy: 0.001, "No DPR monkeypatch") }
                else { originalDPR = dpr }
                XCTAssertEqual(try number("visualWidth", values), Double(size.width), accuracy: 1)
                XCTAssertEqual(try number("visualHeight", values), Double(size.height), accuracy: 1)
                XCTAssertEqual(try number("left", values), 0, accuracy: 1)
                XCTAssertEqual(try number("top", values), 0, accuracy: 1)
                XCTAssertEqual(try number("pixelsWidth", values), try number("cssWidth", values) * dpr, accuracy: 1)
                XCTAssertEqual(try number("pixelsHeight", values), try number("cssHeight", values) * dpr, accuracy: 1)
                let pixels = try number("pixelsWidth", values) * number("pixelsHeight", values)
                if half {
                    XCTAssertEqual(pixels / (try XCTUnwrap(originalPixels[size.width])), 0.25, accuracy: 0.003)
                } else {
                    originalPixels[size.width] = pixels
                    XCTAssertEqual(values["transform"] as? String, "none", "Original rendering is not transformed")
                }
                let attachment = XCTAttachment(string: "mode=\(half ? "half" : "normal") viewport=\(size) \(values)")
                attachment.name = "Actual viewport and backing pixels"; attachment.lifetime = .keepAlways; add(attachment)
                try await checkTargets(web, session: session)
                _ = try await web.evaluateJavaScript("""
                (() => { let probe = document.getElementById('viewport-blur-probe');
                  if (!probe) { probe = document.createElement('button'); probe.id = 'viewport-blur-probe'; document.body.append(probe); }
                  probe.focus(); return document.activeElement === probe; })();
                """)
                let previousKeys = count("VIEWPORT_KEY:65", session)
                session.key("KeyA", down: true); session.key("KeyA", down: false)
                try await requireTrace("VIEWPORT_KEY:65", session: session, after: previousKeys)
            }
            // Explicit compatibility limit, not a false claim that noScale is
            // preserved: ActionScript sees the reduced layout dimensions.
            session.key("KeyN", down: true); session.key("KeyN", down: false)
            try await requireTrace(half ? "VIEWPORT_STAGE:430:220" : "VIEWPORT_STAGE:860:440", session: session)
            try await session.closeWithoutSaving()
            web.removeFromSuperview()
        }
    }

    private func checkTargets(_ web: WKWebView, session: PlayerSession) async throws {
        for (name, point) in targets {
            let prefix = "VIEWPORT_HIT:\(name):"
            let previous = count(prefix, session)
            _ = try await web.evaluateJavaScript("""
            (() => {
              const canvas = document.querySelector('ruffle-player').shadowRoot.querySelector('canvas');
              const r = canvas.getBoundingClientRect(), scale = Math.min(r.width / 320, r.height / 240);
              const e = {bubbles:true, composed:true, pointerId:1, pointerType:'mouse', isPrimary:true,
                button:0, clientX:r.left + (r.width - 320 * scale) / 2 + \(point.x) * scale,
                clientY:r.top + (r.height - 240 * scale) / 2 + \(point.y) * scale};
              canvas.dispatchEvent(new PointerEvent('pointermove', {...e, buttons:0}));
              canvas.dispatchEvent(new PointerEvent('pointerdown', {...e, buttons:1}));
              canvas.dispatchEvent(new PointerEvent('pointerup', {...e, buttons:0}));
              return true;
            })();
            """)
            try await requireTrace(prefix, session: session, after: previous)
            let line = try XCTUnwrap(session.diagnostics.last(where: { $0.contains(prefix) }))
            let suffix = try XCTUnwrap(line.components(separatedBy: prefix).last)
            let parts = suffix.split(separator: ":")
            XCTAssertEqual(parts.count, 2, line)
            if parts.count == 2 {
                XCTAssertEqual(try XCTUnwrap(Double(parts[0])), Double(point.x), accuracy: 2, line)
                XCTAssertEqual(try XCTUnwrap(Double(parts[1])), Double(point.y), accuracy: 2, line)
            }
            // Exercise the production 20-traces/second limit without flooding
            // it; a missing callback must not be mistaken for rate limiting.
            try await Task.sleep(nanoseconds: 150_000_000)
        }
    }

    private func metrics(_ web: WKWebView) async throws -> [String: Any] {
        let result = try await web.evaluateJavaScript("""
        (() => { const p = document.querySelector('ruffle-player'), c = p.shadowRoot.querySelector('canvas');
          const r = c.getBoundingClientRect(); return {dpr:devicePixelRatio, cssWidth:c.clientWidth,
            cssHeight:c.clientHeight, pixelsWidth:c.width, pixelsHeight:c.height,
            visualWidth:r.width, visualHeight:r.height, left:r.left, top:r.top,
            transform:getComputedStyle(p.parentElement).transform}; })();
        """)
        return try XCTUnwrap(result as? [String: Any])
    }

    private func number(_ key: String, _ values: [String: Any]) throws -> Double {
        try XCTUnwrap((values[key] as? NSNumber)?.doubleValue, "Missing metric \(key): \(values)")
    }

    private func waitForMetrics(_ web: WKWebView, size: CGSize, factor: Double) async throws -> Bool {
        let deadline = Date().addingTimeInterval(5)
        while Date() < deadline {
            let values = try await metrics(web)
            if abs(try number("cssWidth", values) - Double(size.width) * factor) <= 1,
               abs(try number("cssHeight", values) - Double(size.height) * factor) <= 1,
               abs(try number("pixelsWidth", values) - number("cssWidth", values) * number("dpr", values)) <= 1,
               abs(try number("pixelsHeight", values) - number("cssHeight", values) * number("dpr", values)) <= 1 { return true }
            try await Task.sleep(nanoseconds: 100_000_000)
        }
        return false
    }

    private func count(_ marker: String, _ session: PlayerSession) -> Int {
        session.diagnostics.filter { $0.contains(marker) }.count
    }

    private func requireTrace(_ marker: String, session: PlayerSession, after previous: Int = 0) async throws {
        let found = try await waitUntil(seconds: 5) { self.count(marker, session) > previous }
        XCTAssertTrue(found, "Missing real SWF trace \(marker): \(session.failure ?? "") \(session.diagnostics)")
    }

    private func waitUntil(seconds: TimeInterval, _ condition: () -> Bool) async throws -> Bool {
        let deadline = Date().addingTimeInterval(seconds)
        while Date() < deadline {
            if condition() { return true }
            try await Task.sleep(nanoseconds: 100_000_000)
        }
        return condition()
    }
}

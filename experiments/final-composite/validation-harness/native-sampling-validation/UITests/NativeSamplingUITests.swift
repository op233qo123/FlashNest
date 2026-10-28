import XCTest
import UIKit
import CryptoKit

/// Actual XCUITest taps/drags and OS orientation; no synthetic input events.
/// Only diagnostics fault-inject status messages, after physical evidence.
final class NativeSamplingUITests: XCTestCase {
    private enum Failure: Error { case invalid(String) }
    private var identity: [String: Any] = [:]
    override func setUpWithError() throws {
        continueAfterFailure = false; executionTimeAllowance = 900
        let url = try XCTUnwrap(Bundle(for: Self.self).url(forResource: "SamplingIdentity", withExtension: "json"))
        identity = try XCTUnwrap(JSONSerialization.jsonObject(with: Data(contentsOf: url)) as? [String: Any])
        XCUIDevice.shared.orientation = .portrait
    }
    func testShippingAutomaticShowAll() throws { try matrix(renderer: "automatic", mode: "showAll") }
    func testShippingAutomaticNoScale() throws { try matrix(renderer: "automatic", mode: "noScale") }
    func testShippingWebGLShowAll() throws { try matrix(renderer: "webgl", mode: "showAll") }
    func testShippingWebGLNoScale() throws { try matrix(renderer: "webgl", mode: "noScale") }
    func testDiagnosticLaunchLowWebGLShowAll() throws {
        guard identity["arm"] as? String == "candidate" else { throw XCTSkip("Explicit quality diagnostic is candidate-only, not a shipping lane") }
        try matrix(renderer: "webgl", mode: "showAll", quality: "low")
    }
    func testDiagnosticLaunchHighWebGLShowAll() throws {
        guard identity["arm"] as? String == "candidate" else { throw XCTSkip("Explicit High diagnostic is candidate-only") }
        try matrix(renderer: "webgl", mode: "showAll", quality: "high")
    }
    func testActualInitialRedirectAndNavigationFailure() throws {
        guard identity["arm"] as? String == "candidate" else { throw XCTSkip("Candidate status lifecycle only") }
        let app = XCUIApplication()
        app.launchArguments = ["-FlashNest.language", "en", "-AppleLanguages", "(en)", "--redirect-initial",
            "--renderer", "automatic", "--scale", "quarter", "--fixture", "showAll-center.swf"]
        app.launch(); defer { app.terminate() }
        let play = app.webViews.buttons["Play / enable audio"].firstMatch
        XCTAssertTrue(play.waitForExistence(timeout: 90)); XCTAssertTrue(wait { play.isEnabled && play.isHittable }); play.tap()
        let loaded = try poll(app) { $0["status"] as? String != "unknown" }
        let events = loaded["navigationEvents"] as? [String] ?? []
        XCTAssertTrue(events.contains("redirect")); XCTAssertTrue(events.contains("provisional")); XCTAssertTrue(events.contains("commit"))
        XCTAssertLessThan(try XCTUnwrap(events.firstIndex(of: "redirect")), try XCTUnwrap(events.firstIndex(of: "commit")))
        app.buttons["sampling-fail"].tap()
        let deadline = Date().addingTimeInterval(30)
        var failed: [String: Any] = [:]
        repeat {
            failed = try snapshot(app, allowingFailure: true)
            if !(failed["failure"] as? String ?? "").isEmpty { break }
            Thread.sleep(forTimeInterval: 0.2)
        } while Date() < deadline
        XCTAssertFalse((failed["failure"] as? String ?? "").isEmpty, "Original navigation error must remain visible")
        XCTAssertEqual(failed["status"] as? String, "unknown")
        XCTAssertTrue((failed["navigationEvents"] as? [String] ?? []).contains { ["provisional-failure", "committed-failure"].contains($0) })
        try attachJSON(["schema": "flashnest-native-sampling-navigation-v1", "loaded": loaded, "failed": failed], name: "actual-WK-redirect-failure")
    }
    private func matrix(renderer: String, mode: String, quality: String? = nil) throws {
        let arm = try XCTUnwrap(identity["arm"] as? String)
        let tiers = arm == "baseline" ? ["original"] : (quality == "low" ? ["original", "quarter"] : ["original", "threeQuarter", "half", "quarter"])
        for tier in tiers {
            XCUIDevice.shared.orientation = .portrait
            let app = XCUIApplication()
            app.launchArguments = ["-FlashNest.language", "en", "-AppleLanguages", "(en)", "-AppleLocale", "en_US",
                "--renderer", renderer, "--scale", tier, "--fixture", mode + "-center.swf"]
            if let quality { app.launchArguments += ["--diagnostic-quality", quality] }
            app.launch(); defer { app.terminate() }
            let ready = app.webViews.buttons["Play / enable audio"].firstMatch
            XCTAssertTrue(ready.waitForExistence(timeout: 90)); XCTAssertTrue(wait { ready.isEnabled && ready.isHittable }); ready.tap()
            var initial = try poll(app) { self.trace($0, "READY").count == 1 && $0["measurement"] is [String: Any] }
            let dpr = try number(initial["screenScale"])
            XCTAssertTrue([2.0, 3.0].contains(dpr), "Required DPR2 or DPR3 simulator, not inferred from its name")
            XCTAssertEqual(initial["os"] as? String, "18.2", "No OS substitution")
            let lane = quality.map { "diagnostic-launch-" + $0 } ?? "shipping-default-quality"
            let rowID = "\(arm)-dpr\(Int(dpr))-\(renderer)-\(mode)-\(tier)-\(lane)"
            var target: [Double] = [100, 70]
            for (index, phase) in ["portrait", "landscape", "portrait-return"].enumerated() {
                if index == 1 { XCUIDevice.shared.orientation = .landscapeLeft }
                if index == 2 { XCUIDevice.shared.orientation = .portrait }
                let before = try poll(app) { object in
                    guard let m = object["measurement"] as? [String: Any], let css = m["css"] as? [Double] else { return false }
                    return css.count == 4 && (index == 1 ? css[2] > css[3] : css[3] > css[2]) && (arm == "baseline" || object["status"] as? String != "unknown")
                }
                XCTAssertEqual(try number(before["epoch"]), try number(initial["epoch"]), "Orientation replaced player")
                let measurement = try XCTUnwrap(before["measurement"] as? [String: Any])
                let css = try XCTUnwrap(measurement["css"] as? [Double]); let viewport = try XCTUnwrap(before["viewport"] as? [Double])
                let width = css[2], height = css[3], stageScale = mode == "showAll" ? min(width / 320, height / 240) : 1
                let visibleWidth = min(width, 320 * stageScale), visibleHeight = min(height, 240 * stageScale)
                let left = (width - visibleWidth) / 2, top = (height - visibleHeight) / 2
                let points = [[0.15, 0.15], [0.85, 0.15], [0.15, 0.85], [0.85, 0.85], [0.5, 0.5]].map {
                    [round(left + visibleWidth * $0[0]), round(top + visibleHeight * $0[1])]
                }
                let crop = try screenshot(app, before: before, name: rowID + "-" + phase)
                let oldDowns = trace(before, "DOWN").count, oldUps = trace(before, "UP").count
                for (i, point) in points.enumerated() {
                    coordinate(app, viewport: viewport, css: css, point: point).tap()
                    _ = try poll(app) { self.trace($0, "DOWN").count == oldDowns + i + 1 && self.trace($0, "UP").count == oldUps + i + 1 }
                }
                let taps = try snapshot(app), downs = trace(taps, "DOWN")
                let a = downs[oldDowns], b = downs[oldDowns + 1], c = downs[oldDowns + 2]
                let sx = (Double(b[0])! - Double(a[0])!) / (points[1][0] - points[0][0])
                let sy = (Double(c[1])! - Double(a[1])!) / (points[2][1] - points[0][1])
                XCTAssertGreaterThan(sx, 0); XCTAssertGreaterThan(sy, 0)
                let drag = [round(points[0][0] + (target[0] + 60 - Double(a[0])!) / sx),
                            round(points[0][1] + (target[1] + 50 - Double(a[1])!) / sy)]
                XCTAssertTrue(drag[0] > 0 && drag[0] + 8 < width && drag[1] > 0 && drag[1] + 6 < height)
                let end = [drag[0] + 8, drag[1] + 6]
                coordinate(app, viewport: viewport, css: css, point: drag).press(forDuration: 0.1,
                    thenDragTo: coordinate(app, viewport: viewport, css: css, point: end))
                let after = try poll(app) { self.trace($0, "DOWN").count == oldDowns + 6 && self.trace($0, "UP").count == oldUps + 6 }
                let finalDown = trace(after, "DOWN").last!, finalUp = trace(after, "UP").last!
                XCTAssertEqual(finalDown[2], "true", "Actual AVM1 hitTest, not a DOM/config echo")
                XCTAssertGreaterThan(Double(finalUp[2])!, target[0]); XCTAssertGreaterThan(Double(finalUp[3])!, target[1])
                target = [Double(finalUp[2])!, Double(finalUp[3])!]
                let record: [String: Any] = ["schema": "flashnest-native-sampling-v1", "row": rowID, "arm": arm, "lane": lane,
                    "rendererPolicy": renderer, "scaleMode": mode, "tier": tier, "phase": phase,
                    "before": before, "after": after, "points": points, "drag": [drag, end], "cropSHA256": crop]
                try attachJSON(record, name: rowID + "-" + phase)
                initial = before
            }
            if arm == "candidate" {
                try verifyStatusUI(app, expected: try snapshot(app))
                if tier == "quarter" && mode == "showAll" && quality == nil {
                    try lifecycle(app, row: rowID)
                }
            }
            app.terminate()
        }
    }
    private func lifecycle(_ app: XCUIApplication, row: String) throws {
        let before = try snapshot(app)
        app.buttons["sampling-stale"].tap()
        let stale = try poll(app) { $0["staleBarrier"] as? Bool == true }
        XCTAssertEqual(stale["status"] as? String, before["status"] as? String)
        XCTAssertEqual(try number(stale["applied"]), try number(before["applied"]))
        XCUIDevice.shared.press(.home); app.activate()
        let returned = try poll(app) { ($0["measurement"] as? [String: Any])?["hidden"] as? Bool == false }
        XCTAssertEqual(try number(returned["epoch"]), try number(before["epoch"]))
        app.buttons["sampling-reload"].tap()
        let invalidated = try poll(app) { $0["status"] as? String == "unknown" }
        XCTAssertEqual(try number(invalidated["epoch"]), try number(before["epoch"]), "Reload is same WKView")
        // Real same-view navigation must not rebind, even after new renderer starts.
        let play = app.webViews.buttons["Play / enable audio"].firstMatch
        XCTAssertTrue(play.waitForExistence(timeout: 60)); XCTAssertTrue(wait { play.isEnabled && play.isHittable }); play.tap()
        let afterReload = try poll(app) { ($0["measurement"] as? [String: Any])?["canvas"] != nil }
        XCTAssertEqual(afterReload["status"] as? String, "unknown")
        app.buttons["sampling-restart"].tap()
        XCTAssertTrue(play.waitForExistence(timeout: 90)); XCTAssertTrue(wait { play.isEnabled && play.isHittable }); play.tap()
        let expectedEpoch = try number(before["epoch"]) + 1
        let restarted = try poll(app) { $0["status"] as? String != "unknown" && (try? self.number($0["epoch"])) == expectedEpoch }
        XCTAssertEqual(try number(restarted["requested"]), 0.25)
        try verifyStatusUI(app, expected: restarted)
        try attachJSON(["schema": "flashnest-native-sampling-lifecycle-v1", "row": row, "before": before,
            "stale": stale, "returned": returned, "invalidated": invalidated, "afterReload": afterReload, "restarted": restarted], name: row + "-lifecycle")
    }
    private func verifyStatusUI(_ app: XCUIApplication, expected: [String: Any]) throws {
        app.buttons["sampling-settings"].tap()
        let label = app.staticTexts["sampling-applied-status"].firstMatch
        for _ in 0..<10 { if label.exists && label.isHittable { break }; app.swipeUp() }
        XCTAssertTrue(label.exists && label.isHittable)
        let scale = try number(expected["applied"])
        let text = expected["status"] as? String == "fallback"
            ? "Original (100%) — renderer fallback; requested reduction is not active."
            : [1.0: "Original (100%)", 0.75: "Reduced (75% per axis)", 0.5: "Low (50% per axis)", 0.25: "Very low (25% per axis)"][scale]
        XCTAssertEqual(label.label, text)
        let shot = XCTAttachment(screenshot: XCUIScreen.main.screenshot()); shot.name = "production-sampling-status-UI"; shot.lifetime = .keepAlways; add(shot)
        app.buttons["sampling-done"].tap()
    }
    private func snapshot(_ app: XCUIApplication, allowingFailure: Bool = false) throws -> [String: Any] {
        let element = app.staticTexts["sampling-evidence"]
        XCTAssertTrue(element.waitForExistence(timeout: 10))
        let previous = element.value as? String
        app.buttons["sampling-snapshot"].tap()
        XCTAssertTrue(wait { (element.value as? String) != previous })
        let data = try XCTUnwrap((element.value as? String)?.data(using: .utf8))
        let object = try XCTUnwrap(JSONSerialization.jsonObject(with: data) as? [String: Any])
        if !allowingFailure { XCTAssertEqual(object["failure"] as? String, "") }
        return object
    }
    private func poll(_ app: XCUIApplication, until predicate: ([String: Any]) -> Bool) throws -> [String: Any] {
        let deadline = Date().addingTimeInterval(30)
        var last: [String: Any] = [:]
        repeat { last = try snapshot(app); if predicate(last) { return last }; Thread.sleep(forTimeInterval: 0.2) } while Date() < deadline
        try attachJSON(last, name: "sampling-timeout"); throw Failure.invalid("Bounded native observation deadline")
    }
    private func wait(_ predicate: () -> Bool) -> Bool {
        let deadline = Date().addingTimeInterval(15)
        repeat { if predicate() { return true }; Thread.sleep(forTimeInterval: 0.1) } while Date() < deadline
        return predicate()
    }
    private func trace(_ object: [String: Any], _ kind: String) -> [[String]] {
        (object["traces"] as? [String] ?? []).compactMap { line in
            guard let range = line.range(of: "DENSITY|" + kind + "|") else { return nil }
            return String(line[range.upperBound...]).components(separatedBy: "|")
        }
    }
    private func number(_ value: Any?) throws -> Double { try XCTUnwrap(value as? NSNumber).doubleValue }
    private func coordinate(_ app: XCUIApplication, viewport: [Double], css: [Double], point: [Double]) -> XCUICoordinate {
        app.coordinate(withNormalizedOffset: .zero).withOffset(CGVector(dx: viewport[0] + css[0] + point[0], dy: viewport[1] + css[1] + point[1]))
    }
    private func screenshot(_ app: XCUIApplication, before: [String: Any], name: String) throws -> String {
        let image = XCUIScreen.main.screenshot().image, cg = try XCTUnwrap(image.cgImage)
        let viewport = try XCTUnwrap(before["viewport"] as? [Double]), screen = try XCTUnwrap(before["screenBounds"] as? [Double])
        let css = try XCTUnwrap((before["measurement"] as? [String: Any])?["css"] as? [Double])
        let sx = Double(cg.width) / screen[0], sy = Double(cg.height) / screen[1]
        let rect = CGRect(x: (viewport[0] + css[0]) * sx, y: (viewport[1] + css[1]) * sy, width: css[2] * sx, height: css[3] * sy).integral
        let crop = try XCTUnwrap(cg.cropping(to: rect)), bytes = try XCTUnwrap(UIImage(cgImage: crop).pngData())
        let attachment = XCTAttachment(data: bytes, uniformTypeIdentifier: "public.png")
        attachment.name = name + "-canvas.png"; attachment.lifetime = .keepAlways; add(attachment)
        return SHA256.hash(data: bytes).map { String(format: "%02x", $0) }.joined()
    }
    private func attachJSON(_ object: [String: Any], name: String) throws {
        let bytes = try JSONSerialization.data(withJSONObject: object, options: [.sortedKeys])
        XCTAssertLessThan(bytes.count, 128_000)
        let attachment = XCTAttachment(data: bytes, uniformTypeIdentifier: "public.json")
        attachment.name = name + ".json"; attachment.lifetime = .keepAlways; add(attachment)
    }
}

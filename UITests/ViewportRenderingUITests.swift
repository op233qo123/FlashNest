import XCTest
import UIKit

/// Trusted native touches through the production SwiftUI/WK hierarchy. The
/// original generated fixture is imported through Files from a separate app;
/// there is no production seeding hook or injected pointer-coordinate shim.
final class ViewportRenderingUITests: XCTestCase {
    private let fixtureTitle = "FlashNest Viewport Fixture"
    private let targets: [(String, CGFloat, CGFloat)] = [
        ("TL", 32, 32), ("TR", 288, 32), ("BL", 32, 208), ("BR", 288, 208), ("C", 160, 120)
    ]

    override func setUpWithError() throws {
        continueAfterFailure = false
        executionTimeAllowance = 420
        XCUIDevice.shared.orientation = .portrait
    }

    func testHalfResolutionTrustedCornersRotationChildAndVirtualKey() {
        let app = importFixture()
        defer { capture("Viewport final screen"); XCUIDevice.shared.orientation = .portrait }
        startMovie(app)
        trace("VIEWPORT_ROOT_READY", in: app)
        let menu = app.buttons["player-menu"].firstMatch
        menu.tap()
        let mode = app.switches["render-half-resolution"].firstMatch
        XCTAssertTrue(mode.waitForExistence(timeout: 10))
        XCTAssertEqual(mode.value as? String, "0", "Original rendering remains the default")
        setSwitch("controls-visible", enabled: false, in: app)
        done(app)
        rotate(.landscapeLeft, app: app)
        tapTargets(app)
        capture("Original resolution trusted corner hits")

        // Only the stored preference changes: no mid-game restart or save.
        menu.tap()
        setSwitch("render-half-resolution", enabled: true, in: app)
        XCTAssertTrue(app.staticTexts["render-mode-explanation"].exists)
        done(app)
        tapTargets(app)
        menu.tap()
        let diagnostics = app.buttons["Diagnostics"].firstMatch
        reveal(diagnostics, in: app); diagnostics.tap()
        let originalMode = app.staticTexts.matching(NSPredicate(format: "label CONTAINS %@", "renderMode=normal")).firstMatch
        reveal(originalMode, in: app)
        XCTAssertTrue(originalMode.exists, "Preference must not change the active runtime")
        XCTAssertFalse(app.staticTexts.matching(NSPredicate(format: "label CONTAINS %@", "renderMode=half")).firstMatch.exists)
        capture("Next-launch preference leaves active rendering unchanged")
        done(app)
        closeGame(app)

        // Opening a new player is the sole point where the new mode applies.
        rotate(.portrait, app: app)
        let row = app.buttons.matching(NSPredicate(format: "label BEGINSWITH %@", fixtureTitle)).firstMatch
        reveal(row, in: app); row.tap()
        let entry = app.buttons["entry-main.swf"].firstMatch
        XCTAssertTrue(entry.waitForExistence(timeout: 15)); entry.tap()
        startMovie(app)
        trace("VIEWPORT_ROOT_READY", in: app)
        XCTAssertTrue(wait { app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH %@", "touch-key-")).count == 0 })
        tapTargets(app)
        capture("Half resolution portrait trusted corner hits")
        rotate(.landscapeLeft, app: app)
        tapTargets(app)
        capture("Half resolution landscape left trusted corner hits")
        rotate(.landscapeRight, app: app)
        tapTargets(app)
        capture("Half resolution landscape right trusted corner hits")

        menu.tap()
        XCTAssertEqual(app.switches["render-half-resolution"].firstMatch.value as? String, "1")
        setSwitch("controls-visible", enabled: true, in: app)
        done(app)
        let enter = app.buttons["touch-key-default-5"].firstMatch
        XCTAssertTrue(enter.waitForExistence(timeout: 10)); XCTAssertTrue(enter.isHittable); enter.tap()
        trace("VIEWPORT_CHILD_READY", in: app)
        menu.tap(); setSwitch("controls-visible", enabled: false, in: app); done(app)
        tapTargets(app)
        XCTAssertTrue(menu.isHittable, "Menu stays full-size and recoverable outside the scaled render layer")
        capture("Half resolution child scene trusted corner hits")
        menu.tap(); reveal(diagnostics, in: app); diagnostics.tap()
        let halfMode = app.staticTexts.matching(NSPredicate(format: "label CONTAINS %@", "renderMode=half")).firstMatch
        reveal(halfMode, in: app); XCTAssertTrue(halfMode.exists)
        capture("Half resolution active renderer diagnostics")
        done(app)
    }

    private func tapTargets(_ app: XCUIApplication) {
        let web = app.webViews.firstMatch
        let frame = web.frame, appFrame = app.frame
        XCTAssertEqual(frame.width, appFrame.width, accuracy: 2)
        XCTAssertEqual(frame.height, appFrame.height, accuracy: 2)
        let scale = min(frame.width / 320, frame.height / 240)
        for (name, x, y) in targets {
            let point = CGVector(dx: (frame.width - 320 * scale) / 2 + x * scale,
                                 dy: (frame.height - 240 * scale) / 2 + y * scale)
            web.coordinate(withNormalizedOffset: .zero).withOffset(point).tap()
            // The target's real MovieClip.onRelease reports stage coordinates.
            // Tolerate point/pixel rounding, not a shifted or doubled mapping.
            let prefix = "VIEWPORT_HIT:\(name):"
            trace(prefix, in: app)
            let value = app.webViews.staticTexts.matching(NSPredicate(format: "label CONTAINS %@", prefix)).firstMatch.label
            let suffix = value.components(separatedBy: prefix).last ?? ""
            let coordinates = suffix.split(separator: ":").compactMap { Double($0) }
            XCTAssertEqual(coordinates.count, 2, value)
            if coordinates.count == 2 {
                XCTAssertEqual(coordinates[0], Double(x), accuracy: 2, value)
                XCTAssertEqual(coordinates[1], Double(y), accuracy: 2, value)
            }
        }
    }

    private func trace(_ value: String, in app: XCUIApplication) {
        let marker = app.webViews.staticTexts.matching(NSPredicate(format: "label CONTAINS %@", value)).firstMatch
        XCTAssertTrue(marker.waitForExistence(timeout: 8), "Missing real SWF callback: \(value)")
    }

    private func rotate(_ orientation: UIDeviceOrientation, app: XCUIApplication) {
        XCUIDevice.shared.orientation = orientation
        XCTAssertTrue(wait { let frame = app.frame; return orientation == .portrait ? frame.height > frame.width : frame.width > frame.height })
        // Native orientation can report before WebKit's viewport resize settles.
        let web = app.webViews.firstMatch
        if web.exists { XCTAssertTrue(wait { abs(web.frame.width - app.frame.width) < 2 && abs(web.frame.height - app.frame.height) < 2 }) }
    }

    private func startMovie(_ app: XCUIApplication) {
        let play = app.webViews.buttons["Play / enable audio"].firstMatch
        XCTAssertTrue(play.waitForExistence(timeout: 60)); XCTAssertTrue(wait { play.isEnabled }); play.tap()
    }

    private func closeGame(_ app: XCUIApplication) {
        app.buttons["player-menu"].firstMatch.tap()
        let close = app.buttons["player-close"].firstMatch
        reveal(close, in: app); close.tap()
        XCTAssertTrue(app.buttons["import-folder"].firstMatch.waitForExistence(timeout: 30))
    }

    private func setSwitch(_ identifier: String, enabled: Bool, in app: XCUIApplication) {
        let toggle = app.switches[identifier].firstMatch
        reveal(toggle, in: app)
        let expected = enabled ? "1" : "0"
        if (toggle.value as? String) != expected {
            // SwiftUI exposes the whole Form row as a switch in iOS 18.2.
            toggle.coordinate(withNormalizedOffset: CGVector(dx: 0.95, dy: 0.5)).tap()
        }
        XCTAssertTrue(wait { (toggle.value as? String) == expected })
    }

    private func done(_ app: XCUIApplication) { app.navigationBars.buttons["Done"].firstMatch.tap() }

    private func reveal(_ element: XCUIElement, in app: XCUIApplication) {
        for _ in 0..<7 { if element.exists && element.isHittable { return }; app.swipeUp() }
        XCTAssertTrue(element.isHittable)
    }

    private func importFixture() -> XCUIApplication {
        let source = XCUIApplication(bundleIdentifier: "com.flashnest.fixture-source")
        source.launchArguments = ["-AppleLanguages", "(en)", "-AppleLocale", "en_US"]
        source.launch(); XCTAssertTrue(source.staticTexts["source-ready"].waitForExistence(timeout: 30)); source.terminate()
        let app = XCUIApplication()
        app.launchArguments = ["--flashnest-cross-container-ui-test", "-FlashNest.language", "en", "-AppleLanguages", "(en)", "-AppleLocale", "en_US"]
        app.launch()
        let importButton = app.buttons["import-folder"].firstMatch
        XCTAssertTrue(importButton.waitForExistence(timeout: 15)); XCTAssertTrue(wait { importButton.isHittable }); importButton.tap()
        XCTAssertTrue(app.navigationBars["FullDocumentManagerViewControllerNavigationBar"].waitForExistence(timeout: 15))
        let title = app.navigationBars.buttons[fixtureTitle + ", Actions Menu"].firstMatch
        for _ in 0..<12 {
            if title.exists { break }
            let files = app.collectionViews["File View"]
            var navigated = false
            for label in [fixtureTitle, "FlashNest Source", "On My iPhone"] {
                let cell = files.cells.containing(.staticText, identifier: label).firstMatch
                if cell.exists && cell.isHittable { cell.tap(); navigated = true; break }
            }
            if navigated { continue }
            let back = app.navigationBars.buttons.allElementsBoundByIndex.first {
                ["FlashNest Source", "On My iPhone", "Browse"].contains($0.label) && $0.isHittable
            }
            if let back { back.tap(); continue }
            if let browse = app.buttons.matching(identifier: "Browse").allElementsBoundByIndex.first(where: { $0.isHittable }) { browse.tap() }
        }
        XCTAssertTrue(title.waitForExistence(timeout: 10)); app.buttons["Open"].firstMatch.tap()
        let entry = app.buttons["entry-main.swf"].firstMatch
        XCTAssertTrue(entry.waitForExistence(timeout: 45)); entry.tap()
        return app
    }

    private func wait(_ condition: () -> Bool) -> Bool {
        let deadline = Date().addingTimeInterval(15)
        repeat { if condition() { return true }; Thread.sleep(forTimeInterval: 0.2) } while Date() < deadline
        return condition()
    }

    private func capture(_ name: String) {
        let attachment = XCTAttachment(screenshot: XCUIScreen.main.screenshot())
        attachment.name = name; attachment.lifetime = .keepAlways; add(attachment)
    }
}

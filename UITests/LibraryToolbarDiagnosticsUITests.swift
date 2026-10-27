import XCTest

/// Bounded diagnosis of the visible SwiftUI Menu's AX/hit-test representation.
/// This does not replace any real Files, home, fullscreen or lifecycle gate.
final class LibraryToolbarDiagnosticsUITests: XCTestCase {
    override func setUpWithError() throws {
        continueAfterFailure = false
        executionTimeAllowance = 90
    }

    func testVisibleImportMenuOrdinaryTapOpensRealActions() {
        let app = XCUIApplication()
        app.launchArguments = ["-FlashNest.language", "en", "-AppleLanguages", "(en)", "-AppleLocale", "en_US"]
        app.launch()
        let menu = app.buttons["import-menu"].firstMatch
        XCTAssertTrue(menu.waitForExistence(timeout: 15))
        LibraryNavigation.captureControlState("import-menu", in: app, context: "Toolbar menu before one ordinary tap")
        let screenshot = XCTAttachment(screenshot: XCUIScreen.main.screenshot())
        screenshot.name = "Visible import menu before diagnostic tap"; screenshot.lifetime = .keepAlways; add(screenshot)
        XCTAssertTrue(menu.isEnabled, "Do not attempt to operate a truly disabled control")
        XCTAssertTrue(menu.frame.width > 0 && menu.frame.height > 0 && app.frame.intersects(menu.frame),
                      "The identified menu must have a visible nonempty frame")
        // Intentionally diagnose the reported isHittable false case using ONE
        // ordinary element tap, not a coordinate bypass or a retry loop.
        menu.tap()
        let folder = app.buttons["import-folder"].firstMatch
        let appeared = folder.waitForExistence(timeout: 10)
        if !appeared {
            LibraryNavigation.captureControlState("import-menu", in: app, context: "Toolbar menu after unsuccessful ordinary tap")
        }
        XCTAssertTrue(appeared, "The real import actions must appear; a delivered tap alone is not success")
        XCTAssertTrue(folder.isEnabled && folder.isHittable)
        XCTAssertTrue(app.buttons["import-files"].firstMatch.exists)
        XCTAssertTrue(app.buttons["import-inbox"].firstMatch.exists)
    }
}

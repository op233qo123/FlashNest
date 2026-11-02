import XCTest
import UIKit

/// Trusted XCTest touch drag/tap through the production SwiftUI menu.
/// Imports only the repository's original fixture through the real Files UI.
final class DraggablePlayerMenuUITests: XCTestCase {
    override func setUpWithError() throws {
        continueAfterFailure = false
        executionTimeAllowance = 420
        XCUIDevice.shared.orientation = .portrait
    }

    func testDragDoesNotOpenMenuAndTapWorksAfterRotationWithControlsHidden() {
        let source = XCUIApplication(bundleIdentifier: "com.flashnest.fixture-source")
        source.launchArguments = ["-AppleLanguages", "(en)", "-AppleLocale", "en_US"]
        source.launch()
        XCTAssertTrue(source.staticTexts["source-ready"].waitForExistence(timeout: 30))
        source.terminate()
        let app = XCUIApplication()
        app.launchArguments = ["--flashnest-cross-container-ui-test", "-FlashNest.language", "en",
                               "-AppleLanguages", "(en)", "-AppleLocale", "en_US"]
        app.launch()
        defer { XCUIDevice.shared.orientation = .portrait }
        LibraryNavigation.openSourceFolder(named: "FlashNest Player Fixture", in: app)
        LibraryNavigation.requireEntry("main.swf", in: app, towardTop: true).tap()
        let menu = app.buttons["player-menu"].firstMatch
        XCTAssertTrue(menu.waitForExistence(timeout: 30))
        XCTAssertTrue(LibraryNavigation.wait { menu.isHittable })
        // Do not start a gesture while the player's presentation is still settling.
        var lastFrame = CGRect.zero
        var stableReads = 0
        XCTAssertTrue(LibraryNavigation.wait {
            let frame = menu.frame
            stableReads = frame == lastFrame ? stableReads + 1 : 0
            lastFrame = frame
            return stableReads >= 4 && menu.isHittable
        }, "Menu did not settle: app=\(app.frame), menu=\(menu.frame)")
        let original = menu.frame
        print("MOUSE_MENU_BEFORE app=\(app.frame) menu=\(original)")
        let target = app.coordinate(withNormalizedOffset: CGVector(dx: 0.35, dy: 0.35))
        menu.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.5))
            .press(forDuration: 0.1, thenDragTo: target)
        let moved = LibraryNavigation.wait { abs(menu.frame.midX - original.midX) > 30 }
        print("MOUSE_MENU_AFTER app=\(app.frame) menu=\(menu.frame) original=\(original)")
        if !moved { print("MOUSE_MENU_FAILURE_TREE\n\(app.debugDescription)") }
        XCTAssertTrue(moved, "Drag did not change horizontal menu position: before=\(original), after=\(menu.frame), app=\(app.frame)")
        XCTAssertFalse(app.buttons["player-resume"].firstMatch.exists, "Dragging must not be recognized as menu tap")
        assertInsideScreen(menu, app: app)
        menu.tap()
        XCTAssertTrue(app.buttons["player-resume"].firstMatch.waitForExistence(timeout: 10))
        let mouse = app.switches["mouse-touch-enabled"].firstMatch
        XCTAssertTrue(mouse.exists)
        XCTAssertEqual(mouse.value as? String, "0", "New package starts with mouse touch off")
        mouse.coordinate(withNormalizedOffset: CGVector(dx: 0.95, dy: 0.5)).tap()
        XCTAssertTrue(LibraryNavigation.wait { mouse.value as? String == "1" })
        let visible = app.switches["controls-visible"].firstMatch
        for _ in 0..<4 {
            if visible.exists && visible.isHittable { break }
            app.swipeUp()
        }
        XCTAssertTrue(visible.isHittable)
        XCTAssertEqual(visible.value as? String, "1")
        visible.coordinate(withNormalizedOffset: CGVector(dx: 0.95, dy: 0.5)).tap()
        XCTAssertTrue(LibraryNavigation.wait { visible.value as? String == "0" })
        app.navigationBars.buttons["Done"].firstMatch.tap()
        XCTAssertTrue(LibraryNavigation.wait { menu.isHittable })
        XCTAssertEqual(app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH %@", "touch-key-")).count, 0)
        XCUIDevice.shared.orientation = .landscapeLeft
        XCTAssertTrue(LibraryNavigation.wait { app.frame.width > app.frame.height && menu.isHittable })
        assertInsideScreen(menu, app: app)
        menu.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.5))
            .press(forDuration: 0.1, thenDragTo: app.coordinate(withNormalizedOffset: CGVector(dx: 0.99, dy: 0.99)))
        XCTAssertTrue(LibraryNavigation.wait { menu.isHittable })
        XCTAssertFalse(app.buttons["player-resume"].firstMatch.exists)
        assertInsideScreen(menu, app: app)
        XCUIDevice.shared.orientation = .portrait
        XCTAssertTrue(LibraryNavigation.wait { app.frame.height > app.frame.width && menu.isHittable })
        assertInsideScreen(menu, app: app)
        menu.tap()
        XCTAssertTrue(app.buttons["player-resume"].firstMatch.waitForExistence(timeout: 10))
        XCTAssertEqual(app.switches["mouse-touch-enabled"].firstMatch.value as? String, "1")
        let attachment = XCTAttachment(screenshot: XCUIScreen.main.screenshot())
        attachment.name = "Moved menu opens after rotation; mouse mode retained"
        attachment.lifetime = .keepAlways
        add(attachment)
    }

    private func assertInsideScreen(_ menu: XCUIElement, app: XCUIApplication,
                                    file: StaticString = #filePath, line: UInt = #line) {
        let frame = menu.frame, bounds = app.frame
        XCTAssertGreaterThanOrEqual(frame.width, 44, file: file, line: line)
        XCTAssertGreaterThanOrEqual(frame.height, 44, file: file, line: line)
        XCTAssertGreaterThanOrEqual(frame.minX, bounds.minX, file: file, line: line)
        XCTAssertGreaterThanOrEqual(frame.minY, bounds.minY, file: file, line: line)
        XCTAssertLessThanOrEqual(frame.maxX, bounds.maxX, file: file, line: line)
        XCTAssertLessThanOrEqual(frame.maxY, bounds.maxY, file: file, line: line)
    }
}


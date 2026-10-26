import XCTest

/// Real UI coverage using an original playable SWF imported through Files from
/// the separate fixture-source sandbox. No production launch/seeding hook.
final class FullscreenPlayerUITests: XCTestCase {
    override func setUpWithError() throws {
        continueAfterFailure = false
        executionTimeAllowance = 240
        XCUIDevice.shared.orientation = .portrait
    }

    func testLandscapeSingleOverlayHideRecoverOpacityAndRotation() {
        let app = importPlayableFixture()
        defer {
            capture(app, "Fullscreen player final state")
            XCUIDevice.shared.orientation = .portrait
        }
        let play = app.webViews.buttons["Play / enable audio"]
        XCTAssertTrue(play.waitForExistence(timeout: 60))
        XCTAssertTrue(wait { play.isEnabled })
        play.tap()
        let menu = app.buttons["player-menu"]
        XCTAssertTrue(menu.waitForExistence(timeout: 10))
        menu.tap()
        reveal(app.buttons["Diagnostics"], in: app); app.buttons["Diagnostics"].tap()
        XCTAssertTrue(app.staticTexts.matching(NSPredicate(format: "label CONTAINS %@", "FLASHNEST_CHILD_OK")).firstMatch.waitForExistence(timeout: 30), "The real child SWF must execute before checking playback UI")
        app.buttons["Done"].tap()

        XCUIDevice.shared.orientation = .landscapeLeft
        XCTAssertTrue(wait { app.frame.width > app.frame.height })
        XCTAssertTrue(wait { menu.isHittable })
        let stage = app.webViews.firstMatch
        XCTAssertTrue(stage.exists)
        XCTAssertEqual(stage.frame.width, app.frame.width, accuracy: 2, "No native side border or reserved control column")
        XCTAssertEqual(stage.frame.height, app.frame.height, accuracy: 2, "No persistent toolbar/footer reducing the stage")
        XCTAssertEqual(stage.frame.minY, app.frame.minY, accuracy: 2)
        let nativeKeys = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH %@", "touch-key-"))
        XCTAssertEqual(nativeKeys.count, 6, "Exactly one native six-button default overlay")
        XCTAssertFalse(stage.buttons["Action"].exists, "Old duplicate web keypad must not exist")
        XCTAssertFalse(stage.buttons["Enter"].exists, "Old duplicate web keypad must not exist")
        capture(app, "Landscape full-bleed single overlay")

        menu.tap()
        let visibility = app.switches["controls-visible"]
        reveal(visibility, in: app)
        visibility.tap()
        dismissMenu(app)
        XCTAssertTrue(wait { nativeKeys.count == 0 })
        XCTAssertTrue(menu.isHittable, "The floating menu must remain usable with all controls hidden")
        capture(app, "Landscape hidden controls recoverable menu")

        menu.tap()
        reveal(visibility, in: app); visibility.tap()
        let opacity = app.sliders["control-opacity"]
        reveal(opacity, in: app); opacity.adjust(toNormalizedSliderPosition: 0)
        XCTAssertEqual(app.staticTexts["control-opacity-value"].label, "10%")
        let edit = app.buttons["controls-edit"]
        reveal(edit, in: app); edit.tap()
        let done = app.buttons["controls-editor-done"]
        XCTAssertTrue(done.waitForExistence(timeout: 10))
        XCTAssertEqual(app.staticTexts["control-opacity-value"].label, "10%")
        let first = app.buttons["edit-touch-key-default-0"]
        XCTAssertTrue(first.exists)
        let originalCenter = first.frame.origin
        first.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.5))
            .press(forDuration: 0.2, thenDragTo: app.coordinate(withNormalizedOffset: CGVector(dx: 0.4, dy: 0.65)))
        XCTAssertTrue(wait { abs(first.frame.minX - originalCenter.x) > 20 })
        capture(app, "Landscape controls editor ten percent opacity")
        done.tap()
        XCTAssertEqual(nativeKeys.count, 6)
        let landscapePosition = app.buttons["touch-key-default-0"].frame.origin

        XCUIDevice.shared.orientation = .portrait
        XCTAssertTrue(wait { app.frame.height > app.frame.width && menu.isHittable })
        XCTAssertEqual(nativeKeys.count, 6)
        XCTAssertTrue(app.buttons["touch-key-default-0"].isHittable)
        capture(app, "Portrait independent safe-area controls")
        XCUIDevice.shared.orientation = .landscapeLeft
        XCTAssertTrue(wait { app.frame.width > app.frame.height && menu.isHittable })
        XCTAssertEqual(app.buttons["touch-key-default-0"].frame.minX, landscapePosition.x, accuracy: 3)
        XCTAssertEqual(app.buttons["touch-key-default-0"].frame.minY, landscapePosition.y, accuracy: 3)
        menu.tap()
        reveal(app.sliders["control-opacity"], in: app)
        XCTAssertEqual(app.staticTexts["control-opacity-value"].label, "10%", "Opacity survives editing and orientation changes")
    }

    private func importPlayableFixture() -> XCUIApplication {
        let source = XCUIApplication(bundleIdentifier: "com.flashnest.fixture-source")
        source.launchArguments = ["-AppleLanguages", "(en)", "-AppleLocale", "en_US"]
        source.launch()
        XCTAssertTrue(source.staticTexts["source-ready"].waitForExistence(timeout: 30))
        source.terminate()
        let app = XCUIApplication()
        app.launchArguments = ["--flashnest-cross-container-ui-test", "-FlashNest.language", "en",
                               "-AppleLanguages", "(en)", "-AppleLocale", "en_US"]
        app.launch()
        let importButton = app.buttons["import-folder"]
        XCTAssertTrue(importButton.waitForExistence(timeout: 15))
        XCTAssertTrue(wait { importButton.isHittable })
        importButton.tap()
        let systemNavigation = app.navigationBars["FullDocumentManagerViewControllerNavigationBar"]
        XCTAssertTrue(systemNavigation.waitForExistence(timeout: 15))
        let title = app.navigationBars.buttons["FlashNest Player Fixture, Actions Menu"].firstMatch
        for _ in 0..<10 {
            if title.exists { break }
            let files = app.collectionViews["File View"]
            var navigated = false
            for label in ["FlashNest Player Fixture", "FlashNest Source", "On My iPhone"] {
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
        capture(app, "Playable fixture selected through Files")
        XCTAssertTrue(title.waitForExistence(timeout: 10))
        XCTAssertTrue(app.collectionViews["File View"].cells.containing(.staticText, identifier: "main.swf").firstMatch.exists)
        app.buttons["Open"].firstMatch.tap()
        let entry = app.buttons["entry-main.swf"]
        XCTAssertTrue(entry.waitForExistence(timeout: 45))
        XCTAssertTrue(app.buttons["entry-sub/child.swf"].exists)
        entry.tap()
        return app
    }

    private func reveal(_ element: XCUIElement, in app: XCUIApplication) {
        for _ in 0..<5 {
            if element.exists && element.isHittable { return }
            app.swipeUp()
        }
        XCTAssertTrue(element.isHittable)
    }

    private func dismissMenu(_ app: XCUIApplication) { app.navigationBars.buttons["Done"].tap() }

    private func wait(_ condition: () -> Bool) -> Bool {
        let deadline = Date().addingTimeInterval(15)
        repeat {
            if condition() { return true }
            Thread.sleep(forTimeInterval: 0.2)
        } while Date() < deadline
        return false
    }

    private func capture(_ app: XCUIApplication, _ name: String) {
        let attachment = XCTAttachment(screenshot: app.screenshot())
        attachment.name = name; attachment.lifetime = .keepAlways; add(attachment)
        let hierarchy = XCTAttachment(string: app.debugDescription)
        hierarchy.name = name + " accessibility"; hierarchy.lifetime = .keepAlways; add(hierarchy)
    }
}

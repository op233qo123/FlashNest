import XCTest

/// Exercises the real Files document picker. The app launch hook only seeds
/// Documents; neither this test nor the hook invokes an import/delegate API.
final class FolderPickerUITests: XCTestCase {
    override func setUpWithError() throws {
        continueAfterFailure = false
        executionTimeAllowance = 120
    }

    private func launch() -> XCUIApplication {
        let app = XCUIApplication()
        app.launchArguments = ["--flashnest-picker-ui-test", "-FlashNest.language", "en",
                               "-AppleLanguages", "(en)", "-AppleLocale", "en_US"]
        app.launch()
        XCTAssertTrue(app.buttons["import-folder"].waitForExistence(timeout: 15))
        return app
    }

    private func capture(_ app: XCUIApplication, _ name: String) {
        let screenshot = XCTAttachment(screenshot: app.screenshot())
        screenshot.name = name; screenshot.lifetime = .keepAlways; add(screenshot)
        let hierarchy = XCTAttachment(string: String(app.debugDescription.prefix(50_000)))
        hierarchy.name = name + " accessibility"; hierarchy.lifetime = .keepAlways; add(hierarchy)
    }

    private func openFixtureFolder(_ app: XCUIApplication) {
        app.buttons["import-folder"].tap()
        let title = app.navigationBars["FlashNest UI Fixture"].firstMatch
        if !title.waitForExistence(timeout: 8) {
            // directoryURL is a best-effort hint. Navigate only known UI labels,
            // then require the exact fixture title before accepting Open.
            for label in ["Browse", "On My iPhone", "FlashNest", "FlashNest UI Fixture"] {
                if title.exists { break }
                let button = app.buttons[label].firstMatch
                let text = app.staticTexts[label].firstMatch
                if button.waitForExistence(timeout: 2), button.isHittable { button.tap() }
                else if text.exists, text.isHittable { text.tap() }
            }
        }
        capture(app, "Files picker before Open")
        XCTAssertTrue(title.waitForExistence(timeout: 10), "Must select the seeded folder, never an arbitrary Files location")
    }

    func testSystemOpenDismissesPickerAndImportsNestedFolder() {
        let app = launch()
        defer { capture(app, "Folder import final state") }
        openFixtureFolder(app)
        let open = app.buttons["Open"].firstMatch
        XCTAssertTrue(open.waitForExistence(timeout: 5))
        XCTAssertTrue(open.isEnabled)
        open.tap()
        // These buttons exist only in the app-owned entry selector AFTER a
        // genuine picker callback, dismissal, background copy and discovery.
        XCTAssertTrue(app.buttons["entry-main.swf"].waitForExistence(timeout: 45), "Open must return to FlashNest and finish the import")
        XCTAssertTrue(app.buttons["entry-sub/level2/level3/child.swf"].exists, "Nested source directories must be discovered automatically")
        XCTAssertFalse(open.exists, "System Files picker must be dismissed")
    }

    func testCancelThenReopenDoesNotLosePickerDelegate() {
        let app = launch()
        defer { capture(app, "Picker cancel and reopen final state") }
        openFixtureFolder(app)
        let cancel = app.buttons["Cancel"].firstMatch
        XCTAssertTrue(cancel.waitForExistence(timeout: 5))
        cancel.tap()
        let importButton = app.buttons["import-folder"]
        XCTAssertTrue(importButton.waitForExistence(timeout: 10))
        XCTAssertTrue(importButton.isHittable)
        openFixtureFolder(app)
        app.buttons["Open"].firstMatch.tap()
        XCTAssertTrue(app.buttons["entry-sub/level2/level3/child.swf"].waitForExistence(timeout: 45))
    }
}

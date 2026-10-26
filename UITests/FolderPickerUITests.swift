import XCTest

/// Exercises the real Files document picker. The app launch hook only seeds
/// Documents; neither this test nor the hook invokes an import/delegate API.
final class FolderPickerUITests: XCTestCase {
    override func setUpWithError() throws {
        continueAfterFailure = false
        executionTimeAllowance = 180
    }

    private func launch() -> XCUIApplication {
        let app = XCUIApplication()
        app.launchArguments = ["--flashnest-picker-ui-test", "-FlashNest.language", "en",
                               "-AppleLanguages", "(en)", "-AppleLocale", "en_US"]
        app.launch()
        XCTAssertTrue(app.wait(for: .runningForeground, timeout: 15))
        XCTAssertTrue(app.buttons["import-folder"].waitForExistence(timeout: 15))
        XCTAssertTrue(waitUntil(timeout: 10) {
            app.buttons["import-folder"].isHittable && app.buttons["import-folder"].isEnabled
        }, "Import control must be interactive after cold launch")
        return app
    }

    private func waitUntil(timeout: TimeInterval, _ condition: @escaping () -> Bool) -> Bool {
        let expectation = XCTNSPredicateExpectation(predicate: NSPredicate { _, _ in condition() }, object: nil)
        return XCTWaiter.wait(for: [expectation], timeout: timeout) == .completed
    }

    private func capture(_ app: XCUIApplication, _ name: String) {
        let screenshot = XCTAttachment(screenshot: app.screenshot())
        screenshot.name = name; screenshot.lifetime = .keepAlways; add(screenshot)
        let description = String(app.debugDescription.prefix(50_000))
        print("FLASHNEST_UI_AX \(name)\n\(description)")
        let hierarchy = XCTAttachment(string: description)
        hierarchy.name = name + " accessibility"; hierarchy.lifetime = .keepAlways; add(hierarchy)
    }

    private func openFixtureFolder(_ app: XCUIApplication) {
        let importButton = app.buttons["import-folder"]
        let state = app.staticTexts["picker-state"]
        let originalState = state.value as? String
        let systemNavigation = app.navigationBars["FullDocumentManagerViewControllerNavigationBar"]
        XCTAssertTrue(waitUntil(timeout: 10) { importButton.isHittable && importButton.isEnabled })
        importButton.tap()
        if !waitUntil(timeout: 5, { state.value as? String == "picker.presented" || systemNavigation.exists }) {
            // On the first cold simulator launch, the run-3 screenshot showed
            // the button action never ran (state remained ready). Retry that
            // event once only, never a failed app presentation/Files operation.
            let untouched = originalState == "picker.ready" || originalState == "picker.cancelled"
            if untouched && state.value as? String == originalState && !systemNavigation.exists && importButton.isHittable {
                capture(app, "Cold launch tap not delivered — retry once")
                print("FLASHNEST_UI_RETRY import tap; app state unchanged: \(originalState ?? "nil")")
                importButton.tap()
            }
        }
        XCTAssertTrue(waitUntil(timeout: 10) { state.value as? String == "picker.presented" }, "The app must acknowledge the import tap")
        XCTAssertTrue(systemNavigation.waitForExistence(timeout: 15), "Files must be presented before navigating; never tap underlying library controls")
        // Captured iOS 18.2 AX identifies the title as an Actions Menu button,
        // not a bare title string or a navigation-bar identifier.
        let title = app.navigationBars.buttons["FlashNest UI Fixture, Actions Menu"].firstMatch
        if !title.waitForExistence(timeout: 8) {
            // directoryURL is a best-effort hint. Navigate only known UI labels,
            // then require the exact fixture title before accepting Open.
            for label in ["Browse", "On My iPhone", "FlashNest", "FlashNest UI Fixture"] {
                if title.exists { break }
                // The underlying library also has a "FlashNest" title. Select
                // the Files collection cell, not a hidden firstMatch behind it.
                let cells = app.collectionViews["File View"].cells.containing(.staticText, identifier: label)
                _ = cells.firstMatch.waitForExistence(timeout: 2)
                if let cell = cells.allElementsBoundByIndex.first(where: { $0.isHittable }) {
                    cell.tap()
                } else if let button = app.buttons.matching(identifier: label).allElementsBoundByIndex.first(where: { $0.isHittable }) {
                    button.tap()
                } else if let text = app.staticTexts.matching(identifier: label).allElementsBoundByIndex.first(where: { $0.isHittable }) {
                    text.tap()
                }
            }
        }
        capture(app, "Files picker before Open")
        XCTAssertTrue(title.waitForExistence(timeout: 10), "Must select the seeded folder, never an arbitrary Files location")
        XCTAssertTrue(title.isHittable, "The fixture folder must be the visible location")
        // Do not assert Files' private browsing-root identifier: the captured
        // 18.2 screenshot showed the correct visible folder while that identifier
        // still contained its parent title. Visible title + inventory is the gate.
        let files = app.collectionViews["File View"]
        XCTAssertTrue(files.cells.containing(.staticText, identifier: "main.swf").firstMatch.waitForExistence(timeout: 5))
        XCTAssertTrue(files.cells.containing(.staticText, identifier: "sub").firstMatch.waitForExistence(timeout: 5))
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
        // Files exposes its Cancel action at the Browse root; nested folders
        // display a back breadcrumb instead, as seen in the real 18.2 capture.
        for _ in 0..<4 {
            if cancel.exists && cancel.isHittable { break }
            let back = app.navigationBars.buttons.allElementsBoundByIndex.first {
                ["FlashNest", "On My iPhone", "Browse"].contains($0.label) && $0.isHittable
            }
            guard let back else { break }
            back.tap()
        }
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

import XCTest

/// Exercises the real Files picker across TWO app sandboxes. A separately
/// installed source app seeds its own Documents; FlashNest receives access only
/// through the user's simulated Open action, never an importer/delegate hook.
final class FolderPickerUITests: XCTestCase {
    override func setUpWithError() throws {
        continueAfterFailure = false
        executionTimeAllowance = 180
    }

    private func launch() -> XCUIApplication {
        let source = XCUIApplication(bundleIdentifier: "com.flashnest.fixture-source")
        source.launchArguments = ["-AppleLanguages", "(en)", "-AppleLocale", "en_US"]
        source.launch()
        XCTAssertTrue(source.staticTexts["source-ready"].waitForExistence(timeout: 20), "Separate source app must create its own Documents fixture")
        source.terminate()
        let app = XCUIApplication()
        // This flag must NOT seed FlashNest's Documents or set directoryURL.
        app.launchArguments = ["--flashnest-cross-container-ui-test", "-FlashNest.language", "en",
                               "-AppleLanguages", "(en)", "-AppleLocale", "en_US"]
        app.launch()
        XCTAssertTrue(app.wait(for: .runningForeground, timeout: 15))
        XCTAssertTrue(app.buttons["import-menu"].waitForExistence(timeout: 15))
        let interactive = waitForImportControl(app)
        if !interactive { LibraryNavigation.captureControlState("import-menu", in: app, context: "Cold-launch import guard failed") }
        XCTAssertTrue(interactive, "Import control must be interactive after cold launch")
        return app
    }

    private func waitForImportControl(_ app: XCUIApplication) -> Bool {
        // Resolve a fresh app element each time. Do not run a predicate waiter
        // spanning app and remote Files accessibility trees during dismissal.
        let deadline = Date().addingTimeInterval(10)
        repeat {
            let button = app.buttons["import-menu"]
            if button.exists && button.isHittable && button.isEnabled { return true }
            Thread.sleep(forTimeInterval: 0.25)
        } while Date() < deadline
        return false
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
        let importButton = LibraryNavigation.revealFolderImport(in: app)
        let state = app.buttons["import-menu"].firstMatch
        let originalState = state.value as? String
        let systemNavigation = app.navigationBars["FullDocumentManagerViewControllerNavigationBar"]
        XCTAssertTrue(importButton.isEnabled && importButton.isHittable)
        importButton.tap()
        if !systemNavigation.waitForExistence(timeout: 15) {
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
        XCTAssertTrue(systemNavigation.waitForExistence(timeout: 15), "Files must be presented before navigating; never tap underlying library controls")
        // Captured iOS 18.2 AX identifies the title as an Actions Menu button,
        // not a bare title string or a navigation-bar identifier.
        let title = app.navigationBars.buttons["FlashNest Cross-App Fixture, Actions Menu"].firstMatch
        if !title.waitForExistence(timeout: 8) {
            // directoryURL is a best-effort hint. Navigate only known UI labels,
            // then require the exact fixture title before accepting Open.
            for label in ["Browse", "On My iPhone", "FlashNest Source", "FlashNest Cross-App Fixture"] {
                if title.exists { break }
                // Select the separate source app's Files cell, not an app title
                // behind the picker or FlashNest's own Documents container.
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

    func testSystemOpenImportsNestedFolderFromSeparateAppContainer() {
        let app = launch()
        defer { capture(app, "Cross-container folder import final state") }
        openFixtureFolder(app)
        let open = app.buttons["Open"].firstMatch
        XCTAssertTrue(open.waitForExistence(timeout: 5))
        XCTAssertTrue(open.isEnabled)
        open.tap()
        // These buttons exist only in the app-owned entry selector AFTER a
        // genuine picker callback, dismissal, background copy and discovery.
        LibraryNavigation.requireEntry("main.swf", in: app)
        LibraryNavigation.requireEntry("sub/level2/level3/child.swf", in: app)
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
                ["FlashNest Source", "On My iPhone", "Browse"].contains($0.label) && $0.isHittable
            }
            guard let back else { break }
            back.tap()
        }
        XCTAssertTrue(cancel.waitForExistence(timeout: 5))
        cancel.tap()
        XCTAssertTrue(waitForImportControl(app), "Actual Cancel must return to the interactive app")
        openFixtureFolder(app)
        app.buttons["Open"].firstMatch.tap()
        LibraryNavigation.requireEntry("sub/level2/level3/child.swf", in: app)
    }
}

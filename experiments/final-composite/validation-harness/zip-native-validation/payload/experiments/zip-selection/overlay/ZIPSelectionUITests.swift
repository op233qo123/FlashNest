import XCTest

// Actual Files UI only; no delegate invocation, importer hook or directoryURL seed.
final class ZIPSelectionUITests: XCTestCase {
    override func setUpWithError() throws {
        continueAfterFailure = false
        executionTimeAllowance = 480
        XCUIDevice.shared.orientation = .portrait
    }
    private func capture(_ app: XCUIApplication, _ name: String) {
        let screenshot = XCTAttachment(screenshot: app.screenshot())
        screenshot.name = name; screenshot.lifetime = .keepAlways; add(screenshot)
        let tree = XCTAttachment(string: String(app.debugDescription.prefix(50000)))
        tree.name = name + " AX"; tree.lifetime = .keepAlways; add(tree)
    }
    private func count(_ app: XCUIApplication) -> Int {
        let result = app.staticTexts["library-result-count"]
        if result.exists { return Int(result.label.split(separator: " ").first ?? "") ?? -1 }
        return app.buttons["import-folder-empty"].exists ? 0 : -1
    }
    private func openFiles(_ app: XCUIApplication) {
        let menu = app.buttons["import-menu"]
        XCTAssertTrue(LibraryNavigation.wait { menu.isEnabled && menu.isHittable })
        menu.tap()
        let files = app.buttons["import-files"]
        XCTAssertTrue(files.waitForExistence(timeout: 5) && files.isHittable); files.tap()
        XCTAssertTrue(app.navigationBars["FullDocumentManagerViewControllerNavigationBar"].waitForExistence(timeout: 15))
    }
    private func sourceFile(_ name: String, in app: XCUIApplication) -> XCUIElement {
        let exact = LibraryNavigation.fileCell(named: name, in: app)
        if exact.exists { return exact }
        return LibraryNavigation.fileCell(named: (name as NSString).deletingPathExtension, in: app)
    }
    private func sourceRoot(_ app: XCUIApplication, fileName: String) {
        for _ in 0..<12 {
            let file = sourceFile(fileName, in: app)
            if file.exists && file.isHittable { return }
            var moved = false
            for name in ["FlashNest Source", "On My iPhone"] {
                let cell = LibraryNavigation.fileCell(named: name, in: app)
                if cell.exists && cell.isHittable { cell.tap(); moved = true; break }
            }
            if moved { continue }
            if LibraryNavigation.navigateBack(in: app) { continue }
            let browse = app.tabBars.buttons["Browse"]
            if browse.exists && browse.isHittable && !browse.isSelected { browse.tap(); continue }
            break
        }
        capture(app, "Source file navigation failed")
        XCTFail("Expected exact synthetic source file in local Files provider")
    }
    private func cancel(_ app: XCUIApplication) {
        for _ in 0..<5 {
            let button = app.buttons["Cancel"].firstMatch
            if button.exists && button.isHittable { button.tap(); break }
            if !LibraryNavigation.navigateBack(in: app) { break }
        }
        XCTAssertTrue(LibraryNavigation.wait {
            let menu = app.buttons["import-menu"]
            return menu.exists && menu.isEnabled && menu.isHittable && menu.value as? String == "picker.cancelled"
        })
        XCTAssertFalse(app.navigationBars["FullDocumentManagerViewControllerNavigationBar"].exists)
    }
    private func select(_ name: String, entry: String, in app: XCUIApplication, expectedCount: Int) {
        openFiles(app); sourceRoot(app, fileName: name)
        capture(app, "Before actual file tap " + name)
        let file = sourceFile(name, in: app)
        XCTAssertTrue(file.isEnabled && file.isHittable); file.tap()
        // Some system layouts require Open after selection; only use the actual
        // visible control, never manufacture a callback or retry an import tap.
        let navigation = app.navigationBars["FullDocumentManagerViewControllerNavigationBar"]
        let open = navigation.buttons["Open"].firstMatch
        if open.waitForExistence(timeout: 2) && open.isEnabled && open.isHittable { open.tap() }
        LibraryNavigation.requireEntry(entry, in: app)
        XCTAssertFalse(navigation.exists)
        capture(app, "Accepted actual file selection " + name)
        app.buttons["entry-cancel"].tap()
        XCTAssertTrue(LibraryNavigation.wait { self.count(app) == expectedCount })
    }
    func testRealFilesCancelZIPSWFRepeatAndWholeFolder() {
        let source = XCUIApplication(bundleIdentifier: "com.flashnest.fixture-source")
        source.launchArguments = ["-AppleLanguages", "(en)", "-AppleLocale", "en_US"]
        source.launch()
        XCTAssertTrue(source.staticTexts["source-ready"].waitForExistence(timeout: 20)); source.terminate()
        let app = XCUIApplication()
        app.launchArguments = ["--flashnest-cross-container-ui-test", "-FlashNest.language", "en", "-AppleLanguages", "(en)", "-AppleLocale", "en_US"]
        app.launch()
        defer { capture(app, "ZIP selection final state"); app.terminate() }
        XCTAssertTrue(app.buttons["import-menu"].waitForExistence(timeout: 15))
        XCTAssertEqual(count(app), 0, "Fresh diagnostic simulator must have no packages")
        openFiles(app); sourceRoot(app, fileName: "Synthetic ZIP Input.zip"); cancel(app)
        XCTAssertEqual(count(app), 0, "Manual cancellation must not import")
        select("Synthetic ZIP Input.zip", entry: "main.swf", in: app, expectedCount: 1)
        openFiles(app); cancel(app)
        XCTAssertEqual(count(app), 1, "Cancel after success preserves exactly one package")
        select("Synthetic SWF Input.swf", entry: "Synthetic SWF Input.swf", in: app, expectedCount: 2)
        select("Synthetic ZIP Input.zip", entry: "main.swf", in: app, expectedCount: 3)
        LibraryNavigation.revealFolderImport(in: app).tap()
        XCTAssertTrue(app.navigationBars["FullDocumentManagerViewControllerNavigationBar"].waitForExistence(timeout: 15))
        LibraryNavigation.navigateToSourceFolder(named: "FlashNest Cross-App Fixture", in: app)
        app.buttons["Open"].firstMatch.tap()
        LibraryNavigation.requireEntry("main.swf", in: app)
        LibraryNavigation.requireEntry("sub/child.swf", in: app)
        app.buttons["entry-cancel"].tap()
        XCTAssertTrue(LibraryNavigation.wait { self.count(app) == 4 })
    }
}

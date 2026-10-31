import XCTest

/// Real Files selection and real SwiftUI alert buttons. DEBUG launch flag only
/// lowers soft thresholds for the existing synthetic cross-container fixture.
final class ImportSizeWarningUITests: XCTestCase {
    override func setUpWithError() throws {
        continueAfterFailure = false
        executionTimeAllowance = 240
        XCUIDevice.shared.orientation = .portrait
    }
    private func launch() -> XCUIApplication {
        let source = XCUIApplication(bundleIdentifier: "com.flashnest.fixture-source")
        source.launch(); XCTAssertTrue(source.staticTexts["source-ready"].waitForExistence(timeout: 30)); source.terminate()
        let app = XCUIApplication()
        app.launchArguments = ["--flashnest-import-size-warning-ui-test", "-FlashNest.language", "en",
                               "-AppleLanguages", "(en)", "-AppleLocale", "en_US"]
        app.launch()
        return app
    }
    private func selectFixture(_ app: XCUIApplication) {
        LibraryNavigation.revealFolderImport(in: app).tap()
        XCTAssertTrue(app.navigationBars["FullDocumentManagerViewControllerNavigationBar"].waitForExistence(timeout: 15))
        LibraryNavigation.navigateToSourceFolder(named: "FlashNest Lifecycle Fixture", in: app)
        let open = app.buttons["Open"].firstMatch
        XCTAssertTrue(open.isEnabled && open.isHittable); open.tap()
        XCTAssertTrue(app.alerts["Large import warning"].waitForExistence(timeout: 30))
        XCTAssertFalse(app.buttons["entry-main.swf"].exists)
    }
    func testContinueAlertImportsInsteadOfBeingCancelledByDismissal() {
        let app = launch(); defer { app.terminate() }
        selectFixture(app)
        let alert = app.alerts["Large import warning"]
        XCTAssertTrue(alert.staticTexts.allElementsBoundByIndex.contains { $0.label.contains("available storage or memory") })
        let approve = alert.buttons["Continue import"]
        XCTAssertTrue(approve.isEnabled && approve.isHittable); approve.tap()
        LibraryNavigation.requireEntry("main.swf", in: app)
        XCTAssertFalse(alert.exists)
        app.buttons["entry-cancel"].firstMatch.tap()
        XCTAssertTrue(app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH %@", "play-")).firstMatch.waitForExistence(timeout: 10))
    }
    func testCancelAlertKeepsLibraryAndAllowsNewConfirmation() {
        let app = launch(); defer { app.terminate() }
        let query = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH %@", "play-"))
        let count = query.count
        selectFixture(app)
        app.alerts["Large import warning"].buttons["Cancel"].tap()
        XCTAssertTrue(LibraryNavigation.wait { !app.alerts["Large import warning"].exists && app.buttons["import-menu"].isEnabled })
        XCTAssertEqual(query.count, count)
        selectFixture(app)
        app.alerts["Large import warning"].buttons["Continue import"].tap()
        LibraryNavigation.requireEntry("main.swf", in: app)
        app.buttons["entry-cancel"].firstMatch.tap()
        XCTAssertEqual(query.count, count + 1)
    }
}

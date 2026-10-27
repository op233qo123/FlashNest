import XCTest

/// Exercises the OS document Open-In path from another app's sandbox.
/// No importer hooks, seeded Library records, direct callback or custom URL scheme.
final class ExternalDocumentImportUITests: XCTestCase {
    override func setUpWithError() throws {
        continueAfterFailure = false
        executionTimeAllowance = 240
        XCUIDevice.shared.orientation = .portrait
    }

    func testColdOpenInZIPRequiresExplicitImportAndWarmDismissKeepsLibrary() {
        let app = XCUIApplication()
        app.launchArguments = ["-FlashNest.language", "en", "-AppleLanguages", "(en)", "-AppleLocale", "en_US"]
        app.launch(); app.terminate()
        handoffZIP()
        XCTAssertTrue(app.wait(for: .runningForeground, timeout: 20))
        let pending = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH %@", "external-import-")).firstMatch
        XCTAssertTrue(pending.waitForExistence(timeout: 20))
        XCTAssertFalse(app.buttons["entry-main.swf"].exists, "Opening a document must not silently import/play it")
        XCTAssertTrue(pending.isEnabled && pending.isHittable); pending.tap()
        LibraryNavigation.requireEntry("main.swf", in: app)
        LibraryNavigation.requireEntry("sub/child.swf", in: app)
        let selector = app.descendants(matching: .any).matching(NSPredicate(format: "identifier BEGINSWITH %@", "entry-selector-")).firstMatch
        let packageID = String(selector.identifier.dropFirst("entry-selector-".count))
        XCTAssertNotNil(UUID(uuidString: packageID))
        app.buttons["entry-cancel"].firstMatch.tap()
        let imported = app.buttons["play-" + packageID].firstMatch
        XCTAssertTrue(imported.waitForExistence(timeout: 10))
        let libraryCount = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH %@", "play-")).count
        handoffZIP()
        XCTAssertTrue(app.wait(for: .runningForeground, timeout: 20))
        let dismiss = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH %@", "external-dismiss-")).firstMatch
        XCTAssertTrue(dismiss.waitForExistence(timeout: 20)); XCTAssertTrue(dismiss.isHittable); dismiss.tap()
        XCTAssertFalse(pending.exists)
        XCTAssertEqual(app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH %@", "play-")).count, libraryCount)
        XCTAssertTrue(imported.exists && imported.isHittable, "Dismissing a new handoff must retain the existing game")
        XCTAssertFalse(app.buttons["player-menu"].exists)
        app.terminate()
    }

    private func handoffZIP() {
        let source = XCUIApplication(bundleIdentifier: "com.flashnest.fixture-source")
        source.terminate(); source.launch()
        XCTAssertTrue(source.staticTexts["source-ready"].waitForExistence(timeout: 30))
        source.buttons["source-open-zip"].tap()
        // Actual iOS 18.2 UIDocumentInteractionController evidence exposes
        // application destinations as cells, not buttons (run 40504678869).
        let destinations = source.cells.matching(NSPredicate(format: "label == %@", "FlashNest"))
        let target = destinations.firstMatch
        let found = target.waitForExistence(timeout: 15)
        XCTContext.runActivity(named: "Actual OS ZIP Open-In menu") { activity in
            let ax = XCTAttachment(string: source.debugDescription); ax.lifetime = .keepAlways; activity.add(ax)
            let shot = XCTAttachment(screenshot: XCUIScreen.main.screenshot()); shot.lifetime = .keepAlways; activity.add(shot)
        }
        XCTAssertTrue(found, "The real system menu must advertise the declared ZIP handler")
        XCTAssertEqual(destinations.count, 1, "Exactly one real FlashNest destination must be shown")
        XCTAssertTrue(target.isEnabled && target.isHittable); target.tap()
    }
}

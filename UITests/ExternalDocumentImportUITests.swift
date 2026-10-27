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

    func testSaveJSONAndSOLUseExplicitTargetAndConfirmationWhileWrongJSONIsRejected() {
        let app = XCUIApplication()
        app.launchArguments = ["-FlashNest.language", "en", "-AppleLanguages", "(en)", "-AppleLocale", "en_US"]
        app.launch()
        defer { app.terminate() }
        handoffZIP()
        XCTAssertTrue(app.wait(for: .runningForeground, timeout: 20))
        tapPendingImport(in: app)
        LibraryNavigation.requireEntry("main.swf", in: app)
        let selector = app.descendants(matching: .any).matching(NSPredicate(format: "identifier BEGINSWITH %@", "entry-selector-")).firstMatch
        let packageID = String(selector.identifier.dropFirst("entry-selector-".count))
        XCTAssertNotNil(UUID(uuidString: packageID))
        XCTAssertNotEqual(packageID.lowercased(), "22222222-2222-4222-8222-222222222222", "A backup's authored game ID must never choose the destination")
        app.buttons["entry-cancel"].firstMatch.tap()
        let libraryCount = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH %@", "play-")).count

        handoffDocument(button: "source-open-save-json", kind: "save JSON")
        XCTAssertTrue(app.wait(for: .runningForeground, timeout: 20))
        tapPendingImport(in: app)
        chooseSaveTarget(packageID, in: app)
        let confirm = app.buttons["save-import-confirm"]
        let previewReady = confirm.waitForExistence(timeout: 30)
        captureSaveSurface("JSON target and validation", in: app)
        XCTAssertTrue(previewReady, "Only validated save data may reach replacement confirmation")
        XCTAssertTrue(confirm.isEnabled && confirm.isHittable)
        XCTAssertFalse(app.buttons["player-menu"].exists)
        confirm.tap()
        XCTAssertTrue(app.staticTexts["save-import-success"].waitForExistence(timeout: 30))
        app.buttons["OK"].firstMatch.tap()
        app.buttons["Done"].firstMatch.tap()
        XCTAssertTrue(app.buttons["play-" + packageID].waitForExistence(timeout: 10))

        handoffDocument(button: "source-open-sol", kind: "raw SOL")
        XCTAssertTrue(app.wait(for: .runningForeground, timeout: 20))
        tapPendingImport(in: app)
        chooseSaveTarget(packageID, in: app)
        let candidates = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH %@", "raw-sol-target-"))
        let candidate = candidates.firstMatch
        let rawReady = candidate.waitForExistence(timeout: 30)
        captureSaveSurface("Raw SOL existing-identity match", in: app)
        XCTAssertTrue(rawReady, "Raw SOL must match an existing object identity before confirmation")
        XCTAssertEqual(candidates.count, 1, "The original fixture contains exactly one matching namespace")
        XCTAssertTrue(candidate.label.contains("FlashNestFixture"))
        XCTAssertTrue(candidate.isEnabled && candidate.isHittable); candidate.tap()
        XCTAssertTrue(confirm.exists && confirm.isEnabled)
        let cancel = app.buttons["save-import-cancel"]
        XCTAssertTrue(cancel.isEnabled && cancel.isHittable); cancel.tap()
        XCTAssertFalse(confirm.exists)
        app.buttons["Done"].firstMatch.tap()

        handoffDocument(button: "source-open-invalid-json", kind: "ordinary JSON")
        XCTAssertTrue(app.wait(for: .runningForeground, timeout: 20))
        tapPendingImport(in: app)
        chooseSaveTarget(packageID, in: app)
        let rejected = app.staticTexts["save-import-error"].waitForExistence(timeout: 30)
        captureSaveSurface("Ordinary JSON validation rejection", in: app)
        XCTAssertTrue(rejected, "Ordinary JSON must fail validation, not become a game or overwrite a save")
        XCTAssertFalse(confirm.exists)
        app.buttons["OK"].firstMatch.tap()
        app.buttons["Done"].firstMatch.tap()
        XCTAssertTrue(app.buttons["play-" + packageID].waitForExistence(timeout: 10))
        XCTAssertEqual(app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH %@", "play-")).count, libraryCount)
        XCTAssertFalse(app.buttons["player-menu"].exists)
    }

    private func captureSaveSurface(_ name: String, in app: XCUIApplication) {
        XCTContext.runActivity(named: name) { activity in
            let ax = XCTAttachment(string: app.debugDescription); ax.lifetime = .keepAlways; activity.add(ax)
            let shot = XCTAttachment(screenshot: XCUIScreen.main.screenshot()); shot.lifetime = .keepAlways; activity.add(shot)
        }
    }

    private func tapPendingImport(in app: XCUIApplication) {
        let pending = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH %@", "external-import-")).firstMatch
        XCTAssertTrue(pending.waitForExistence(timeout: 20))
        XCTAssertTrue(pending.isEnabled && pending.isHittable); pending.tap()
    }

    private func chooseSaveTarget(_ packageID: String, in app: XCUIApplication) {
        let target = app.buttons["save-target-" + packageID]
        XCTAssertTrue(target.waitForExistence(timeout: 20), "External save must ask for an installed target game")
        XCTAssertFalse(app.buttons["save-import-confirm"].exists, "No replacement before target selection and validation")
        XCTAssertTrue(target.isEnabled && target.isHittable); target.tap()
    }

    private func handoffZIP() { handoffDocument(button: "source-open-zip", kind: "ZIP") }

    private func handoffDocument(button: String, kind: String) {
        let source = XCUIApplication(bundleIdentifier: "com.flashnest.fixture-source")
        source.terminate(); source.launch()
        XCTAssertTrue(source.staticTexts["source-ready"].waitForExistence(timeout: 30))
        source.buttons[button].tap()
        // Actual iOS 18.2 UIDocumentInteractionController evidence exposes
        // application destinations as cells, not buttons (run 40504678869).
        let destinations = source.cells.matching(NSPredicate(format: "label == %@", "FlashNest"))
        let target = destinations.firstMatch
        let found = target.waitForExistence(timeout: 15)
        XCTContext.runActivity(named: "Actual OS \(kind) Open-In menu") { activity in
            let ax = XCTAttachment(string: source.debugDescription); ax.lifetime = .keepAlways; activity.add(ax)
            let shot = XCTAttachment(screenshot: XCUIScreen.main.screenshot()); shot.lifetime = .keepAlways; activity.add(shot)
        }
        XCTAssertTrue(found, "The real system menu must advertise the declared \(kind) handler")
        XCTAssertEqual(destinations.count, 1, "Exactly one real FlashNest destination must be shown")
        XCTAssertTrue(target.isEnabled && target.isHittable); target.tap()
    }
}

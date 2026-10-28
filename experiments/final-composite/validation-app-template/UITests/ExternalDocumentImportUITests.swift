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
        let success = app.alerts["Save area"]
        XCTAssertTrue(success.waitForExistence(timeout: 30))
        XCTAssertTrue(success.staticTexts["Save imported. It will be applied when this game next opens."].exists,
                      "Require actual successful replacement, not just any alert")
        success.buttons["OK"].tap()
        closeSaveAreaFromDetail(in: app)
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
        closeSaveAreaFromDetail(in: app)

        handoffDocument(button: "source-open-invalid-json", kind: "ordinary JSON")
        XCTAssertTrue(app.wait(for: .runningForeground, timeout: 20))
        tapPendingImport(in: app)
        chooseSaveTarget(packageID, in: app)
        let errorAlert = app.alerts["Save error"]
        let rejected = errorAlert.waitForExistence(timeout: 30)
        captureSaveSurface("Ordinary JSON validation rejection", in: app)
        XCTAssertTrue(rejected, "Ordinary JSON must fail validation, not become a game or overwrite a save")
        XCTAssertFalse(confirm.exists)
        XCTAssertTrue(errorAlert.staticTexts.allElementsBoundByIndex.contains {
            !$0.label.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty && $0.label != "Save error"
        }, "Validation failure must show a meaningful explanation")
        errorAlert.buttons["OK"].tap()
        closeSaveAreaFromDetail(in: app)
        XCTAssertTrue(app.buttons["play-" + packageID].waitForExistence(timeout: 10))
        XCTAssertEqual(app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH %@", "play-")).count, libraryCount)
        XCTAssertFalse(app.buttons["player-menu"].exists)
        verifySyntheticArchiveDeletion(packageID, in: app)
    }

    private func verifySyntheticArchiveDeletion(_ packageID: String, in app: XCUIApplication) {
        // Archive only the synthetic package created by this test through the
        // same visible removal flow a user uses. No container writes or hooks.
        let options = app.buttons["game-options-" + packageID]
        XCTAssertTrue(options.isEnabled && options.isHittable); options.tap()
        let remove = app.buttons["game-options-remove-game"]
        XCTAssertTrue(remove.waitForExistence(timeout: 10)); XCTAssertTrue(remove.isHittable); remove.tap()
        let keepSaves = app.buttons["Remove game, keep saves"]
        XCTAssertTrue(keepSaves.waitForExistence(timeout: 10)); XCTAssertTrue(keepSaves.isHittable); keepSaves.tap()
        // Production cache cleanup itself has a 15s timeout after asynchronous
        // validation starts. Observe its terminal UI, not a competing 15s timer.
        let progress = app.descendants(matching: .any)["removal-progress"].firstMatch
        let result = app.descendants(matching: .any)["removal-result"].firstMatch
        let error = app.alerts["FlashNest"]
        let settled = LibraryNavigation.wait({
            error.exists || (!progress.exists && result.exists)
        }, timeout: 30)
        captureSaveSurface("Synthetic game removal terminal state", in: app)
        XCTAssertTrue(settled, "Removal must reach a terminal success/error state within the bounded diagnostic window")
        XCTAssertFalse(error.exists, "Removal failed: " + error.staticTexts.allElementsBoundByIndex.map(\.label).joined(separator: " | "))
        XCTAssertFalse(progress.exists)
        XCTAssertFalse(app.buttons["play-" + packageID].exists, "Archive testing requires actual successful removal of this exact synthetic package")
        let saveArea = app.buttons["save-area"].firstMatch
        XCTAssertTrue(LibraryNavigation.wait { saveArea.isEnabled && saveArea.isHittable }); saveArea.tap()
        let archive = app.buttons["archive-" + packageID]
        XCTAssertTrue(archive.waitForExistence(timeout: 20)); XCTAssertTrue(archive.isHittable); archive.tap()
        let delete = app.buttons["archive-delete"]
        XCTAssertTrue(delete.waitForExistence(timeout: 20)); XCTAssertTrue(delete.isHittable); delete.tap()
        let confirm = app.buttons["archive-delete-confirm"]
        XCTAssertTrue(confirm.waitForExistence(timeout: 20))
        let dialog = app.sheets["Delete all files in this archive?"]
        XCTAssertTrue(dialog.exists)
        let details = dialog.staticTexts.allElementsBoundByIndex.map(\.label).joined(separator: "\n")
        XCTAssertTrue(details.contains(packageID), "Destructive confirmation must identify the exact archived group")
        XCTAssertTrue(details.contains("Current files: 1 · Backup files: 2"))
        XCTAssertTrue(details.contains("Total: 3 files"))
        XCTAssertTrue(details.contains("Original game files, other games and WebKit storage are not changed."))
        captureSaveSurface("Archived synthetic save deletion confirmation", in: app)
        let cancel = app.buttons["archive-delete-cancel"]
        XCTAssertTrue(cancel.isHittable); cancel.tap()
        XCTAssertTrue(delete.waitForExistence(timeout: 10) && delete.isEnabled)
        XCTAssertTrue(app.buttons.matching(identifier: "Export").count > 0, "Cancel must leave saved data exportable")
        delete.tap()
        XCTAssertTrue(confirm.waitForExistence(timeout: 10)); XCTAssertTrue(confirm.isEnabled && confirm.isHittable); confirm.tap()
        XCTAssertTrue(app.staticTexts["archive-delete-success"].waitForExistence(timeout: 20))
        XCTAssertFalse(delete.exists)
        XCTAssertEqual(app.buttons.matching(identifier: "Export").count, 0)
        let back = app.navigationBars["FlashNest External Fixture"].buttons["Save area"].firstMatch
        XCTAssertTrue(back.isHittable); back.tap()
        XCTAssertTrue(LibraryNavigation.wait { !archive.exists }, "Deleted group must disappear after root refresh")
        app.buttons["Done"].firstMatch.tap()
        XCTAssertFalse(app.buttons["play-" + packageID].exists)
    }

    private func closeSaveAreaFromDetail(in app: XCUIApplication) {
        // Observed native back control displays Back, but AX labels it Save area.
        // Scope it to this fixture's detail bar, never the Library toolbar.
        let back = app.navigationBars["FlashNest External Fixture"].buttons["Save area"].firstMatch
        XCTAssertTrue(back.waitForExistence(timeout: 10))
        XCTAssertTrue(back.isEnabled && back.isHittable); back.tap()
        let done = app.buttons["Done"].firstMatch
        XCTAssertTrue(done.waitForExistence(timeout: 10))
        XCTAssertTrue(done.isEnabled && done.isHittable); done.tap()
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

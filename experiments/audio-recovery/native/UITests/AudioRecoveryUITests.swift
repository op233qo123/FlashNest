import XCTest

final class AudioRecoveryUITests: XCTestCase {
    private var activeApp: XCUIApplication?
    override func tearDown() {
        let previous = continueAfterFailure
        continueAfterFailure = true
        defer { continueAfterFailure = previous; activeApp = nil; super.tearDown() }
        if let app = activeApp, app.state == .runningForeground {
            if app.staticTexts["recovery-host-status"].label != "closed-and-drained" {
                evidence("Audio recovery failure before bounded cleanup", app)
                try? close(app)
            }
            app.terminate()
        }
    }
    override func setUpWithError() throws { continueAfterFailure = false; executionTimeAllowance = 180 }
    func testKnownOwnedResumeRejectsThenTrustedRetryKeepsSceneAndSave() throws {
        executionTimeAllowance = 360 // Measured cold launch + full continuity/reopen journey; per-operation deadlines unchanged.
        let app = try start("candidate-known")
        let before = try snapshot(app)
        tap("recovery-inject", app)
        let retry = app.webViews.buttons["Retry audio"].firstMatch
        XCTAssertTrue(retry.waitForExistence(timeout: 15)); XCTAssertTrue(retry.isEnabled && retry.isHittable)
        XCTAssertEqual(app.staticTexts["recovery-native-failure"].label, "none")
        let rejected = try snapshot(app)
        XCTAssertEqual(rejected.page, before.page); XCTAssertEqual(rejected.injections, 1)
        XCTAssertEqual(rejected.trustedRetries, 0); XCTAssertTrue(rejected.sameSave)
        XCTAssertGreaterThan(rejected.saveEntries, 0)
        XCTAssertTrue(rejected.nativeResumeRestored); XCTAssertGreaterThan(rejected.rejectedOperation, 0)
        screenshot("Eligible audio warning before trusted Retry", app)
        retry.tap() // Trusted DOM input, never JavaScript click or fabricated status.
        XCTAssertTrue(wait { !retry.exists })
        let recovered = try snapshot(app)
        screenshot("Audio state immediately after trusted Retry", app)
        XCTAssertEqual(recovered.page, before.page); XCTAssertEqual(recovered.contexts, 1)
        XCTAssertEqual(recovered.injections, 1); XCTAssertEqual(recovered.trustedRetries, 1)
        XCTAssertGreaterThan(recovered.fulfilledOperation, recovered.rejectedOperation)
        XCTAssertTrue(recovered.sameSave); XCTAssertNil(recovered.failure)
        XCTAssertEqual(app.staticTexts["recovery-native-failure"].label, "none")
        tap("recovery-space", app); trace("LIFECYCLE_CHILD_KEY:32:2", app)
        XCTAssertFalse(app.webViews.buttons["Play / enable audio"].exists)
        evidence("Trusted retry retains live child and written save", app)
        // Only AFTER continuity assertions, explicitly reopen and let the real
        // SWF read its own SharedObject. No synthetic localStorage seeding.
        tap("recovery-restart", app)
        let play = app.webViews.buttons["Play / enable audio"].firstMatch
        XCTAssertTrue(play.waitForExistence(timeout: 60)); XCTAssertTrue(wait { play.isEnabled }); play.tap()
        trace("LIFECYCLE_ROOT_READY:420", app)
        try close(app)
    }
    func testUnknownResumeFailureStillReachesProductionNativeFailure() throws {
        try fatalControl("candidate-unknown", expected: "Original synthetic unknown audio failure")
    }
    func testUnpatchedBaselineKnownFailureStillReachesProductionNativeFailure() throws {
        try fatalControl("baseline-known", expected: "Failed to start the audio device")
    }
    private func fatalControl(_ mode: String, expected: String) throws {
        let app = try start(mode)
        let before = try snapshot(app); tap("recovery-inject", app)
        let failure = app.staticTexts["recovery-native-failure"]
        XCTAssertTrue(wait { failure.label.contains(expected) }, "Must reach actual PlayerSession.failure")
        XCTAssertFalse(app.webViews.buttons["Retry audio"].exists)
        let after = try snapshot(app)
        XCTAssertEqual(after.page, before.page); XCTAssertEqual(after.injections, 1)
        XCTAssertEqual(after.trustedRetries, 0); XCTAssertTrue(after.sameSave)
        XCTAssertGreaterThan(after.saveEntries, 0)
        XCTAssertTrue(after.nativeResumeRestored)
        evidence("Unrecognized or baseline failure remains fatal: " + mode, app)
        try close(app)
    }
    private func start(_ mode: String) throws -> XCUIApplication {
        let app = XCUIApplication(); activeApp = app; app.launchEnvironment = ["AUDIO_RECOVERY_MODE": mode]
        app.launchArguments = ["-FlashNest.language", "en", "-AppleLanguages", "(en)"]
        app.launch()
        let play = app.webViews.buttons["Play / enable audio"].firstMatch
        XCTAssertTrue(play.waitForExistence(timeout: 60)); XCTAssertTrue(wait { play.isEnabled && play.isHittable }); play.tap()
        trace("LIFECYCLE_ROOT_READY:undefined", app)
        tap("recovery-enter", app); trace("LIFECYCLE_CHILD_READY", app)
        tap("recovery-space", app); trace("LIFECYCLE_CHILD_KEY:32:1", app)
        XCTAssertEqual(app.staticTexts["recovery-host-error"].label, "none")
        return app
    }
    private struct Probe: Decodable {
        let page: String
        let contexts, injections, trustedRetries, rejectedOperation, fulfilledOperation, saveEntries: Int
        let nativeResumeRestored, sameSave: Bool
        let failure: String?
    }
    private func snapshot(_ app: XCUIApplication) throws -> Probe {
        let label = app.staticTexts["recovery-probe"]
        let previous = label.label
        tap("recovery-snapshot", app)
        XCTAssertTrue(wait { label.label.hasPrefix("{") && label.label != previous })
        // Snapshot button completion is also reflected by a fresh native AX read.
        let text = label.label
        XCTAssertLessThanOrEqual(text.utf8.count, 4096)
        print("AUDIO_RECOVERY_PROBE " + text)
        return try JSONDecoder().decode(Probe.self, from: Data(text.utf8))
    }
    private func close(_ app: XCUIApplication) throws {
        tap("recovery-close", app)
        XCTAssertTrue(wait { app.staticTexts["recovery-host-status"].label == "closed-and-drained" })
        XCTAssertEqual(app.staticTexts["recovery-host-error"].label, "none")
    }
    private func tap(_ id: String, _ app: XCUIApplication) {
        let button = app.buttons[id]; XCTAssertTrue(button.waitForExistence(timeout: 10))
        XCTAssertTrue(button.isEnabled && button.isHittable); button.tap()
    }
    private func trace(_ text: String, _ app: XCUIApplication) {
        XCTAssertTrue(app.webViews.staticTexts.matching(NSPredicate(format: "label CONTAINS %@", text))
            .firstMatch.waitForExistence(timeout: 15))
    }
    private func wait(_ predicate: () -> Bool) -> Bool {
        let end = Date().addingTimeInterval(15)
        repeat { if predicate() { return true }; Thread.sleep(forTimeInterval: 0.1) } while Date() < end
        return false
    }
    private func screenshot(_ name: String, _ app: XCUIApplication) {
        let attachment = XCTAttachment(screenshot: app.screenshot())
        attachment.name = name; attachment.lifetime = .keepAlways; add(attachment)
    }
    private func evidence(_ name: String, _ app: XCUIApplication) {
        for attachment in [XCTAttachment(string: app.debugDescription), XCTAttachment(screenshot: app.screenshot())] {
            attachment.name = name; attachment.lifetime = .keepAlways; add(attachment)
        }
    }
}

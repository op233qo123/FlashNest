import XCTest
import UIKit

// LOCAL diagnostic tests. Node/source-contract tests do not execute these taps.
final class LateAudioUITests: XCTestCase {
    private var activeApp: XCUIApplication?
    private var record: [String: Any] = [:]
    private var ordinal = 0
    private var order: [String: Int] = [:]
    override func setUpWithError() throws { continueAfterFailure = false; executionTimeAllowance = 180 }
    override func tearDown() {
        let previous = continueAfterFailure; continueAfterFailure = true
        if let app = activeApp, app.state == .runningForeground {
            if app.staticTexts["late-status"].label != "closed-and-drained" {
                attach("Failure before cleanup", app.debugDescription)
                tap("late-close", app)
                XCTAssertTrue(wait { app.staticTexts["late-status"].label == "closed-and-drained" })
            }
            app.terminate()
        }
        activeApp = nil; continueAfterFailure = previous; super.tearDown()
    }
    func testLateKnownRecoveryKeepsLiveChildAndRealSOL() throws {
        executionTimeAllowance = 360
        let app = try start("candidate-known")
        let before = try sample(app)
        record["capture"] = before["probe"]
        order["pause"] = next(); tap("late-inject", app)
        XCTAssertTrue(wait { app.staticTexts["late-status"].label == "injected" }); order["injection"] = next()
        let retry = app.webViews.buttons["Retry audio"].firstMatch
        XCTAssertTrue(retry.waitForExistence(timeout: 15)); XCTAssertTrue(retry.isEnabled && retry.isHittable)
        XCTAssertEqual(app.staticTexts["late-native-failure"].label, "none")
        let injected = try sample(app); record["injected"] = injected["probe"]
        record["retryTap"] = ["method":"XCTest.tap", "target":"Retry audio", "enabled":retry.isEnabled,"hittable":retry.isHittable,"ordinal":next()]
        retry.tap(); order["retry"] = next()
        // The label changes to Retrying audio… while pending: disappearance is NOT completion.
        let fulfilled = try waitForFulfilledRetry(app)
        let probe = try object(fulfilled["probe"])
        XCTAssertEqual(probe["contextState"] as? String, "running")
        XCTAssertNotNil(probe["fulfilledRetry"] as? [String: Any])
        record["afterRetryBeforeInput"] = fulfilled
        record["childInputSerialAfterFulfillment"] = try object(fulfilled["continuity"])["childInputSerial"]
        tap("late-space", app); trace("LIFECYCLE_CHILD_KEY:32:2", app); order["child"] = next()
        record["afterTrace"] = "LIFECYCLE_CHILD_KEY:32:2"
        let after = try sample(app)
        tap("late-verify", app)
        XCTAssertTrue(wait { app.staticTexts["late-status"].label == "verified-in-place" })
        let verified = try decode(app.staticTexts["late-snapshot"].label)
        XCTAssertEqual(verified["ok"] as? Bool, true)
        XCTAssertEqual(app.staticTexts["late-native-failure"].label, "none")
        let beforeContinuity = try object(before["continuity"]), afterContinuity = try object(after["continuity"])
        XCTAssertEqual(beforeContinuity["pageId"] as? String, afterContinuity["pageId"] as? String)
        XCTAssertEqual(beforeContinuity["solSnapshot"] as? String, afterContinuity["solSnapshot"] as? String)
        record["recovery"] = ["probe":verified,"before":beforeContinuity,"after":afterContinuity,"childInputTrace":"LIFECYCLE_CHILD_KEY:32:2","verifiedOrdinal":next()]
        record["nativeFailure"] = NSNull()
        record["before"] = beforeContinuity; record["after"] = afterContinuity; record["recovered"] = verified
        order["verified"] = next(); order["outcome"] = order["verified"]
        XCTAssertEqual(after["warningVisible"] as? Bool, false)
        record["warningVisible"] = after["warningVisible"]
        attach("In-place recovery before any reopen", app.debugDescription)
        tap("late-reopen", app)
        let play = app.webViews.buttons["Play / enable audio"].firstMatch
        XCTAssertTrue(play.waitForExistence(timeout: 60)); XCTAssertTrue(wait { play.isEnabled && play.isHittable }); play.tap()
        trace("LIFECYCLE_ROOT_READY:420", app)
        record["reopenRootTrace"] = "LIFECYCLE_ROOT_READY:420"; order["reopen"] = next()
        try closeAndRecord(app)
    }
    func testLateUnknownRemainsProductionFatal() throws { try fatal("candidate-unknown", "Original synthetic unknown audio failure") }
    func testLateBaselineKnownRemainsProductionFatal() throws { try fatal("baseline-known", "Failed to start the audio device") }
    private func fatal(_ mode: String, _ expected: String) throws {
        let app = try start(mode)
        let before = try sample(app)
        record["capture"] = before["probe"]; record["before"] = before["continuity"]
        order["pause"] = next(); tap("late-inject", app)
        XCTAssertTrue(wait { app.staticTexts["late-status"].label == "injected" }); order["injection"] = next()
        let failure = app.staticTexts["late-native-failure"]
        XCTAssertTrue(wait { failure.label.contains(expected) })
        XCTAssertFalse(app.webViews.buttons["Retry audio"].exists)
        record["nativeFailure"] = failure.label
        let after = try sample(app)
        XCTAssertEqual(after["warningVisible"] as? Bool, false)
        record["warningVisible"] = after["warningVisible"]
        record["injected"] = after["probe"]; record["after"] = after["continuity"]; order["outcome"] = next()
        record["recovered"] = NSNull(); record["reopenRootTrace"] = NSNull(); record["retryTap"] = NSNull()
        try closeAndRecord(app)
    }
    private func start(_ mode: String) throws -> XCUIApplication {
        let app = XCUIApplication(); activeApp = app
        app.launchEnvironment = ["AUDIO_RECOVERY_MODE":mode]
        app.launchArguments = ["-FlashNest.language","en","-AppleLanguages","(en)"]
        order = [:]
        record = ["schema":"late-native-case-v1","mode":mode,"execution":["kind":"native-ios","osVersion":UIDevice.current.systemVersion,"platform":"iOS Simulator"]]; ordinal = 0
        app.launch()
        let play = app.webViews.buttons["Play / enable audio"].firstMatch
        XCTAssertTrue(play.waitForExistence(timeout: 60)); XCTAssertTrue(wait { play.isEnabled && play.isHittable })
        let tapReceipt: [String: Any] = ["method":"XCTest.tap","target":"Play / enable audio","enabled":play.isEnabled,"hittable":play.isHittable,"ordinal":next()]
        play.tap(); order["play"] = next(); record["playTap"] = tapReceipt
        trace("LIFECYCLE_ROOT_READY:undefined", app)
        tap("late-enter", app); trace("LIFECYCLE_CHILD_READY", app)
        tap("late-space", app); trace("LIFECYCLE_CHILD_KEY:32:1", app)
        record["initialTraces"] = ["LIFECYCLE_ROOT_READY:undefined","LIFECYCLE_CHILD_READY","LIFECYCLE_CHILD_KEY:32:1"]; order["readiness"] = next()
        // No late helper source/factory may be loaded before this native gate.
        tap("late-begin", app)
        XCTAssertTrue(wait { app.staticTexts["late-status"].label == "captured" })
        XCTAssertEqual(app.staticTexts["late-error"].label, "none")
        let state = try sample(app)
        record["readiness"] = state["readiness"]; order["capture"] = next()
        return app
    }
    private func waitForFulfilledRetry(_ app: XCUIApplication) throws -> [String: Any] {
        let end = Date().addingTimeInterval(15)
        let label = app.staticTexts["late-snapshot"], button = app.buttons["late-read"]
        func checkFailure() throws {
            guard app.staticTexts["late-native-failure"].label == "none",
                  app.staticTexts["late-error"].label == "none" else {
                throw NSError(domain: "LateRetry.productionFailure", code: 1)
            }
        }
        repeat {
            try checkFailure()
            guard button.exists && button.isEnabled && button.isHittable else {
                throw NSError(domain: "LateRetry.snapshotUnavailable", code: 2)
            }
            let previous = label.label
            button.tap()
            // Share the original 15-second deadline; no nested 15-second waits.
            while Date() < end && label.label == previous {
                try checkFailure(); Thread.sleep(forTimeInterval: 0.1)
            }
            try checkFailure()
            guard Date() < end, label.label != previous else { break }
            guard label.label.utf8.count <= 4096 else { throw NSError(domain: "LateRetry.snapshotSize", code: 3) }
            let value = try decode(label.label)
            if value["retryReady"] as? Bool == true {
                let probe = try object(value["probe"])
                guard value["warningVisible"] as? Bool == false,
                      probe["contextState"] as? String == "running",
                      probe["fulfilledRetry"] is [String: Any] else {
                    throw NSError(domain: "LateRetry.invalidFulfillment", code: 4)
                }
                attach("Source-fulfilled retry before fresh input", label.label)
                return value
            }
            Thread.sleep(forTimeInterval: 0.1)
        } while Date() < end
        throw NSError(domain: "LateRetry.fulfillmentDeadline", code: 5)
    }
    private func sample(_ app: XCUIApplication) throws -> [String: Any] {
        let label = app.staticTexts["late-snapshot"], old = label.label
        tap("late-read", app)
        XCTAssertTrue(wait { label.label.hasPrefix("{") && label.label != old })
        XCTAssertLessThanOrEqual(label.label.utf8.count, 4096)
        let value = try decode(label.label), probe = try object(value["probe"])
        XCTAssertTrue(probe["totalContextCount"] is NSNull)
        XCTAssertEqual(probe["prototypeRestored"] as? Bool, true)
        attach("Late snapshot", label.label)
        return value
    }
    private func closeAndRecord(_ app: XCUIApplication) throws {
        tap("late-close", app)
        XCTAssertTrue(wait { app.staticTexts["late-status"].label == "closed-and-drained" })
        XCTAssertEqual(app.staticTexts["late-error"].label, "none")
        let cleanup = try decode(app.staticTexts["late-cleanup"].label)
        XCTAssertEqual(cleanup["disposed"] as? Bool, true)
        XCTAssertEqual(cleanup["closed"] as? Bool, true); XCTAssertEqual(cleanup["drained"] as? Bool, true)
        order["cleanup"] = next(); record["cleanup"] = cleanup
        record["order"] = order; record["hostError"] = NSNull()
        let data = try JSONSerialization.data(withJSONObject: record, options: [.sortedKeys])
        let text = String(decoding: data, as: UTF8.self)
        attach("Late final evidence", text); print("AUDIO_LATE_FINAL " + text)
    }
    private func next() -> Int { ordinal += 1; return ordinal }
    private func object(_ value: Any?) throws -> [String: Any] {
        guard let result = value as? [String: Any] else { throw NSError(domain:"LateEvidence",code:1) }; return result
    }
    private func decode(_ text: String) throws -> [String: Any] { try object(JSONSerialization.jsonObject(with: Data(text.utf8))) }
    private func tap(_ id: String, _ app: XCUIApplication) {
        let button = app.buttons[id]; XCTAssertTrue(button.waitForExistence(timeout:10)); XCTAssertTrue(button.isEnabled && button.isHittable); button.tap()
    }
    private func trace(_ text: String, _ app: XCUIApplication) {
        XCTAssertTrue(app.webViews.staticTexts.matching(NSPredicate(format:"label CONTAINS %@",text)).firstMatch.waitForExistence(timeout:15))
    }
    private func wait(_ condition: () -> Bool) -> Bool {
        let end = Date().addingTimeInterval(15)
        repeat { if condition() { return true }; Thread.sleep(forTimeInterval:0.1) } while Date() < end
        return false
    }
    private func attach(_ name: String, _ text: String) {
        let attachment = XCTAttachment(string:text); attachment.name = name; attachment.lifetime = .keepAlways; add(attachment)
    }
}

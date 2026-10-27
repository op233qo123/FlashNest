import Foundation
import XCTest

/// Real UI taps are required. evaluateJavaScript cannot establish trusted media
/// activation, and changing the WK media policy would invalidate this comparison.
final class NativeAudioLifecycleUITests: XCTestCase {
    private var lastTappedAction: String?
    private var activeApp: XCUIApplication?
    override func tearDown() {
        if let app = activeApp, app.state == .runningForeground || app.state == .runningBackground {
            requestAbortAndDrain(app: app, status: app.staticTexts["audio-native-status"])
            app.terminate()
        }
        activeApp = nil
        super.tearDown()
    }
    func testImmutableBaselineAndCandidateAudioLifecycleMatrix() throws {
        continueAfterFailure = false
        executionTimeAllowance = 660
        let app = XCUIApplication()
        activeApp = app
        let suite = UUID().uuidString.lowercased()
        let deadline = Date().addingTimeInterval(600)
        let status = app.staticTexts["audio-native-status"]
        defer {
            if app.state == .runningForeground || app.state == .runningBackground {
                requestAbortAndDrain(app: app, status: status)
                app.terminate()
            }
        }
        var completedCases = 0
        for arm in ["baseline", "candidate"] {
            for mode in ["normal", "start-first", "start-second", "synthetic-ended"] {
                app.launchEnvironment = ["AUDIO_ARM": arm, "AUDIO_MODE": mode,
                    "AUDIO_SUITE": suite,
                    "AUDIO_DEADLINE_MS": String(deadline.timeIntervalSince1970 * 1000)]
                app.launch()
                lastTappedAction = nil
                var sequence = 0
                for cycle in 0..<(mode == "normal" ? 8 : 1) {
                    let actions = mode.hasPrefix("start-") ? ["resume", "remove"] : ["resume", "pause", "resume", "remove"]
                    for name in actions {
                        sequence += 1
                        let token = "\(arm)/\(mode)/\(cycle)/\(sequence)/\(name)"
                        try waitForStatus("ACTION " + token, status: status, app: app, deadline: deadline)
                        let label = ["resume": "Resume", "pause": "Pause", "remove": "Remove"][name]!
                        let button = app.webViews.buttons[label].firstMatch
                        guard button.exists && button.isHittable else {
                            requestAbortAndDrain(app: app, status: status)
                            attachScreenshot("audio-native-unhittable-control", app: app)
                            let error = NSError(domain: "NativeAudioLifecycle", code: 3,
                                userInfo: [NSLocalizedDescriptionKey: "Actual WebView control is not hittable: " + label])
                            XCTFail(error.localizedDescription)
                            throw error
                        }
                        // Exactly one tap, no retries or native->JS media shortcut.
                        button.tap()
                        lastTappedAction = "ACTION " + token
                    }
                    completedCases += 1
                }
                let terminal = "DONE \(arm)/\(mode)/\(mode == "normal" ? 8 : 1)"
                try waitForStatus(terminal, status: status, app: app, deadline: deadline.addingTimeInterval(11))
                attachScreenshot("\(arm)-\(mode)-closed-and-drained", app: app)
                // DONE requires page contracts, bounded WebKit disposal and the
                // real LoopbackServer stopAndWait drain before the next mode/arm.
                app.terminate()
            }
        }
        XCTAssertEqual(completedCases, 22)
        let note = XCTAttachment(string: "suite=\(suite); cases=22; evidence=Documents/audio-native-evidence/\(suite); no GC/RAM/speaker-output/phone-crash claim")
        note.name = "audio-native-suite.txt"; note.lifetime = .keepAlways; add(note)
    }

    private func waitForStatus(_ expected: String, status: XCUIElement, app: XCUIApplication,
                               deadline: Date) throws {
        let localDeadline = min(deadline, Date().addingTimeInterval(90))
        while Date() < localDeadline {
            if status.exists {
                let value = status.label
                if value == expected { return }
                if value.hasPrefix("FAIL") || (value.hasPrefix("ACTION ") && value != expected && value != lastTappedAction) {
                    requestAbortAndDrain(app: app, status: status)
                    attachScreenshot("audio-native-failure", app: app)
                    let error = NSError(domain: "NativeAudioLifecycle", code: 1,
                        userInfo: [NSLocalizedDescriptionKey: "Expected \(expected), observed \(value)"])
                    XCTFail(error.localizedDescription)
                    throw error
                }
            }
            Thread.sleep(forTimeInterval: 0.05)
        }
        requestAbortAndDrain(app: app, status: status)
        attachScreenshot("audio-native-timeout", app: app)
        let error = NSError(domain: "NativeAudioLifecycle", code: 2,
            userInfo: [NSLocalizedDescriptionKey: "Bounded timeout awaiting \(expected); state=\(status.exists ? status.label : "missing")"])
        XCTFail(error.localizedDescription)
        throw error
    }
    private func requestAbortAndDrain(app: XCUIApplication, status: XCUIElement) {
        if status.exists && (status.label.hasPrefix("FAIL") || status.label.hasPrefix("DONE")) { return }
        let abort = app.buttons["audio-native-abort"]
        if abort.exists && abort.isHittable { abort.tap() }
        let deadline = Date().addingTimeInterval(15)
        while Date() < deadline {
            if status.exists && status.label.hasPrefix("FAIL") { return }
            Thread.sleep(forTimeInterval: 0.05)
        }
        let note = XCTAttachment(string: "Native abort did not confirm awaited drain; failure-path app termination is forced, not clean teardown proof")
        note.name = "audio-native-forced-termination.txt"; note.lifetime = .keepAlways; add(note)
    }
    private func attachScreenshot(_ name: String, app: XCUIApplication) {
        let attachment = XCTAttachment(screenshot: app.screenshot())
        attachment.name = name; attachment.lifetime = .keepAlways; add(attachment)
    }
}

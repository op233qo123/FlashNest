import XCTest
import UIKit

/// Two fresh WK sessions. Each generated parent performs one old→unload→new transition.
final class NativeSceneLoaderUITests: XCTestCase {
    private var identity: [String: Any] = [:]
    override func setUpWithError() throws {
        continueAfterFailure = true;executionTimeAllowance = 180
        let url = try XCTUnwrap(Bundle(for: Self.self).url(forResource: "SamplingIdentity",withExtension: "json"))
        identity = try XCTUnwrap(JSONSerialization.jsonObject(with: Data(contentsOf: url)) as? [String: Any])
        XCTAssertEqual(identity["arm"] as? String,"candidate")
        XCUIDevice.shared.orientation = .portrait
    }
    func test01TinySceneTransition() throws { try observe("tiny") }
    func test02SizedSceneTransition() throws { try observe("sized") }
    private func emit(_ value: [String: Any],name: String,marker: String) throws {
        let data = try JSONSerialization.data(withJSONObject: value,options: [.sortedKeys])
        guard data.count <= 65536 else { XCTFail("Bounded synthetic evidence exceeded64KiB");return }
        let attachment = XCTAttachment(data: data,uniformTypeIdentifier: "public.json")
        attachment.name = name;attachment.lifetime = .keepAlways;add(attachment)
        print(marker+" "+String(decoding: data,as: UTF8.self))
    }
    private func snapshot(_ app: XCUIApplication) -> [String: Any] {
        let element = app.staticTexts["scene-evidence"]
        guard element.exists else { return ["observationError":"Native evidence label missing"] }
        var last: [String: Any] = [:]
        if let text = element.value as? String,let data = text.data(using: .utf8),let value = try? JSONSerialization.jsonObject(with: data) as? [String: Any] { last = value }
        let previous = last["request"] as? Int ?? -1
        let button = app.buttons["scene-snapshot"]
        if button.exists && button.isHittable { button.tap() }
        let deadline = ProcessInfo.processInfo.systemUptime+2
        repeat {
            if let text = element.value as? String,let data = text.data(using: .utf8),let value = try? JSONSerialization.jsonObject(with: data) as? [String: Any] { last = value }
            if let request = last["request"] as? Int,request > previous,last["jsCompletedForRequest"] as? Int == request { break }
            Thread.sleep(forTimeInterval: 0.1)
        } while ProcessInfo.processInfo.systemUptime < deadline
        return last // Native partial state is retained even if JavaScript never returns.
    }
    private func phases(_ snapshot: [String: Any]) -> [String] {
        (snapshot["asRecords"] as? [[String: Any]] ?? []).compactMap { ($0["phase"] as? [String: Any])?["phase"] as? String }
    }
    private func observe(_ fixtureCase: String) throws {
        let app = XCUIApplication();app.launchArguments = ["-FlashNest.language","en","-AppleLanguages","(en)","-AppleLocale","en_US","--scene-case",fixtureCase]
        let launchedAt = ProcessInfo.processInfo.systemUptime
        app.launch();defer { app.terminate() }
        var last: [String: Any] = [:],readyAt: Double? = nil,error = "",count = 0
        func capture(_ snapshot: [String: Any]) throws {
            guard count < 32 else { return }
            count += 1
            try emit(["schema":"flashnest-native-scene-observation-v1","diagnosticOnly":true,"nativeAcceptance":false,
                "case":fixtureCase,"index":count,"nativeUptimeSeconds":ProcessInfo.processInfo.systemUptime,
                "identity":identity,"snapshot":snapshot],name:"scene-\(fixtureCase)-\(count)",marker:"FLASHNEST_SCENE_OBSERVATION_JSON")
        }
        let play = app.webViews.buttons["Play / enable audio"].firstMatch
        if play.waitForExistence(timeout: 30) && play.isEnabled && play.isHittable { play.tap() }
        else { error = "Original Play activation unavailable" }
        let initialDeadline = launchedAt+50
        if error.isEmpty {
            repeat {
                last = snapshot(app)
                if last["ready"] as? Bool == true { readyAt = ProcessInfo.processInfo.systemUptime;break }
                if last["terminated"] as? Bool == true || !(last["failure"] as? String ?? "").isEmpty { error = "Native failure before ready";break }
                Thread.sleep(forTimeInterval: 0.25)
            } while ProcessInfo.processInfo.systemUptime < initialDeadline
            if readyAt == nil && error.isEmpty { error = "Runtime ready was not observed within initial50s bound" }
        } else { last = snapshot(app) }
        try capture(last)
        if let readyAt {
            let deadline = readyAt+120
            while count < 31 && ProcessInfo.processInfo.systemUptime < deadline {
                if phases(last).contains("parent.done") { break }
                if last["terminated"] as? Bool == true || !(last["failure"] as? String ?? "").isEmpty { error = "Native failure during scene transition";break }
                let remaining = deadline-ProcessInfo.processInfo.systemUptime
                if remaining <= 0 { break }
                Thread.sleep(forTimeInterval: min(4,remaining));last = snapshot(app);try capture(last)
            }
            if !phases(last).contains("parent.done") && error.isEmpty { error = "Parent completion not observed within120s or32 records" }
        }
        let activeFinishedAt = ProcessInfo.processInfo.systemUptime
        let completedInsideWindow = phases(last).contains("parent.done") && (readyAt.map { activeFinishedAt <= $0+120 } ?? false)
        if readyAt != nil && !completedInsideWindow && error.isEmpty { error = "Completion was not frozen inside120s observation window" }
        last = snapshot(app);try capture(last) // Post-window evidence never converts a timeout into success.
        let image = XCTAttachment(screenshot: XCUIScreen.main.screenshot());image.name = "scene-\(fixtureCase)-final-screen";image.lifetime = .keepAlways;add(image)
        let finishedAt = ProcessInfo.processInfo.systemUptime
        if finishedAt-activeFinishedAt > 10 && error.isEmpty { error = "Final evidence capture exceeded10s" }
        let complete = completedInsideWindow
        try emit(["schema":"flashnest-native-scene-case-v1","diagnosticOnly":true,"nativeAcceptance":false,
            "case":fixtureCase,"identity":identity,"launchedAt":launchedAt,"readyAt":readyAt.map { $0 as Any } ?? NSNull(),
            "finishedAt":finishedAt,"finalEvidenceBudgetSeconds":10,"activeFinishedAt":activeFinishedAt,"postEvidenceParentDone":phases(last).contains("parent.done"),"observationCount":count,"parentDoneObserved":complete,
            "terminated":last["terminated"] as? Bool ?? false,"error":error,"lastSnapshot":last],name:"scene-\(fixtureCase)-outcome",marker:"FLASHNEST_SCENE_CASE_JSON")
        XCTAssertTrue(error.isEmpty,error);XCTAssertTrue(complete,"Server response/headers are not child scene completion")
        XCTAssertFalse(last["terminated"] as? Bool ?? false,"Web process terminated; cause remains unknown")
        XCTAssertTrue(last["sameWK"] as? Bool ?? false,"Case must retain the original WK object")
        XCTAssertEqual(last["epoch"] as? Int,1)
        XCTAssertFalse(last["asOverflow"] as? Bool ?? true,"Missing/suppressed trace cannot establish missing stage")
        XCTAssertFalse(last["traceSuppressed"] as? Bool ?? true,"Suppressed trace is inconclusive")
    }
}

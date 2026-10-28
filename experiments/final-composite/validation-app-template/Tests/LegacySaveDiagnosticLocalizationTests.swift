import XCTest
@testable import FlashNest

@MainActor final class LegacySaveDiagnosticLocalizationTests: XCTestCase {
    func testPreparationFailureShowsLocalizedNeutralTextAndFixedCodeOnly() {
        let previous = UserDefaults.standard.object(forKey: L10n.preferenceKey)
        defer {
            if let previous { UserDefaults.standard.set(previous, forKey: L10n.preferenceKey) }
            else { UserDefaults.standard.removeObject(forKey: L10n.preferenceKey) }
        }
        let failure = LegacySavePreservationError(stage: .drain, outcome: .deadline,
            elapsedMilliseconds: 12_345, acceptedMessages: 3, rejectedIdentity: 1,
            rejectedEnvelope: 0, receivedSaveReady: true)
        L10n.setLanguage("en")
        XCTAssertEqual(L10n.error(failure), "Game save preparation did not finish.\nDiagnostic code: SAVE-PRESERVE-DRAIN-DEADLINE")
        L10n.setLanguage("zh-Hans")
        XCTAssertEqual(L10n.error(failure), "游戏存档准备未完成。\n诊断代码：SAVE-PRESERVE-DRAIN-DEADLINE")
        XCTAssertFalse(L10n.error(failure).contains("12345"), "Detailed counters belong in bounded diagnostics, not the alert")
        XCTAssertFalse(L10n.error(failure).contains("receivedSaveReady"))
    }
}

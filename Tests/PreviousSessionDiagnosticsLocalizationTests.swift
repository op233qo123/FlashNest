import XCTest
@testable import FlashNest

@MainActor final class PreviousSessionDiagnosticsLocalizationTests: XCTestCase {
    func testPreviousSessionSectionAndClearActionAreBilingual() {
        let previous = UserDefaults.standard.object(forKey: L10n.preferenceKey)
        defer {
            if let previous { UserDefaults.standard.set(previous, forKey: L10n.preferenceKey) }
            else { UserDefaults.standard.removeObject(forKey: L10n.preferenceKey) }
        }
        L10n.setLanguage("en")
        XCTAssertEqual(L10n.text("Previous session diagnostics"), "Previous session diagnostics")
        XCTAssertEqual(L10n.text("Clear previous diagnostics"), "Clear previous diagnostics")
        L10n.setLanguage("zh-Hans")
        XCTAssertEqual(L10n.text("Previous session diagnostics"), "上次会话诊断")
        XCTAssertEqual(L10n.text("Clear previous diagnostics"), "清除上次诊断记录")
    }
}

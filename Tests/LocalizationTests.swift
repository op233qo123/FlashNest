import XCTest
@testable import FlashNest

@MainActor final class LocalizationTests: XCTestCase {
    func testBothLocalizedResourceBundlesArePackagedAndSwitchable() throws {
        let previous = UserDefaults.standard.object(forKey: L10n.preferenceKey)
        defer {
            if let previous { UserDefaults.standard.set(previous, forKey: L10n.preferenceKey) }
            else { UserDefaults.standard.removeObject(forKey: L10n.preferenceKey) }
        }
        XCTAssertNotNil(Bundle.main.path(forResource: "en", ofType: "lproj"))
        XCTAssertNotNil(Bundle.main.path(forResource: "zh-Hans", ofType: "lproj"))
        L10n.setLanguage("en")
        XCTAssertEqual(L10n.text("Library"), "Library")
        L10n.setLanguage("zh-Hans")
        XCTAssertEqual(L10n.text("Library"), "游戏库")
        XCTAssertEqual(L10n.text("import.copying"), "正在复制文件…")
    }

    func testAppVersionIsExplicitAndIconIsConfigured() {
        XCTAssertEqual(Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String, "1.5.3")
        XCTAssertEqual(Bundle.main.object(forInfoDictionaryKey: "CFBundleVersion") as? String, "14")
        let icons = Bundle.main.object(forInfoDictionaryKey: "CFBundleIcons") as? [String: Any]
        let primary = icons?["CFBundlePrimaryIcon"] as? [String: Any]
        XCTAssertEqual(primary?["CFBundleIconName"] as? String, "AppIcon")
    }
}

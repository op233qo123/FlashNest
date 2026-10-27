import XCTest
@testable import FlashNest

final class RenderSettingsTests: XCTestCase {
    func testDefaultAndCorruptPreferencesAlwaysUseOriginalRendering() throws {
        let suite = "FlashNest.RenderTests." + UUID().uuidString
        let defaults = try XCTUnwrap(UserDefaults(suiteName: suite))
        defer { defaults.removePersistentDomain(forName: suite) }
        let id = UUID()
        XCTAssertFalse(RenderSettings.load(for: id, defaults: defaults).usesHalfResolution)
        defaults.set(Data("{\"usesHalfResolution\":\"yes\"}".utf8), forKey: RenderSettings.preferenceKey(for: id))
        XCTAssertFalse(RenderSettings.load(for: id, defaults: defaults).usesHalfResolution)
    }

    func testRenderPreferenceIsPerGameAndIndependentOfTouchControls() throws {
        let suite = "FlashNest.RenderTests." + UUID().uuidString
        let defaults = try XCTUnwrap(UserDefaults(suiteName: suite))
        defer { defaults.removePersistentDomain(forName: suite) }
        let first = UUID(), second = UUID()
        RenderSettings(usesHalfResolution: true).save(for: first, defaults: defaults)
        XCTAssertTrue(RenderSettings.load(for: first, defaults: defaults).usesHalfResolution)
        XCTAssertFalse(RenderSettings.load(for: second, defaults: defaults).usesHalfResolution)
        XCTAssertNil(defaults.object(forKey: TouchControlSettings.preferenceKey(for: first)))
        RenderSettings().save(for: first, defaults: defaults)
        XCTAssertFalse(RenderSettings.load(for: first, defaults: defaults).usesHalfResolution)
    }
}

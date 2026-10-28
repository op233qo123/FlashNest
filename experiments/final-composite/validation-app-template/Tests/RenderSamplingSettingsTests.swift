import XCTest
@testable import FlashNest

final class RenderSamplingSettingsTests: XCTestCase {
    func testOriginalDefaultAndStrictQueryContract() {
        XCTAssertEqual(RenderSamplingSettings().mode, .original)
        XCTAssertEqual(RenderSamplingSettings.Mode.allCases.map(\.rawValue), ["original", "threeQuarter", "half", "quarter"])
        XCTAssertNil(RenderSamplingSettings.Mode.original.queryValue)
        XCTAssertEqual(RenderSamplingSettings.Mode.allCases.map(\.scale), [1, 0.75, 0.5, 0.25])
        XCTAssertEqual(RenderSamplingSettings.Mode.half.queryValue, "0.5")
    }

    func testIsolatedPerGameRoundTripAndCopiedRequest() throws {
        let suite = "FlashNest.RenderSamplingSettingsTests." + UUID().uuidString
        let defaults = try XCTUnwrap(UserDefaults(suiteName: suite))
        defer { defaults.removePersistentDomain(forName: suite) }
        let first = UUID(), second = UUID()
        let touchKey = TouchControlSettings.preferenceKey(for: first)
        defaults.set("unchanged", forKey: touchKey)
        defaults.set("unchanged", forKey: "save-sentinel")
        let originalRequest = RenderSamplingSettings.load(for: first, defaults: defaults)
        XCTAssertTrue(RenderSamplingSettings(mode: .half).save(for: first, defaults: defaults))
        XCTAssertEqual(originalRequest.mode, .original, "Value snapshot cannot mutate with later preference writes")
        XCTAssertEqual(RenderSamplingSettings.load(for: first, defaults: defaults).mode, .half)
        XCTAssertEqual(RenderSamplingSettings.load(for: second, defaults: defaults).mode, .original)
        XCTAssertTrue(RenderSamplingSettings().save(for: first, defaults: defaults))
        XCTAssertEqual(RenderSamplingSettings.load(for: first, defaults: defaults).mode, .original)
        XCTAssertEqual(defaults.string(forKey: touchKey), "unchanged")
        XCTAssertEqual(defaults.string(forKey: "save-sentinel"), "unchanged")
    }

    func testEveryTierRoundTripsWithoutChangingRenderer() throws {
        let suite = "FlashNest.SamplingAllTiers." + UUID().uuidString
        let defaults = try XCTUnwrap(UserDefaults(suiteName: suite))
        defer { defaults.removePersistentDomain(forName: suite) }
        let id = UUID()
        XCTAssertTrue(RendererSettings(mode: .webgl).save(for: id, defaults: defaults))
        for mode in RenderSamplingSettings.Mode.allCases {
            XCTAssertTrue(RenderSamplingSettings(mode: mode).save(for: id, defaults: defaults))
            XCTAssertEqual(RenderSamplingSettings.load(for: id, defaults: defaults).mode, mode)
            XCTAssertEqual(RendererSettings.load(for: id, defaults: defaults).mode, .webgl)
        }
        XCTAssertFalse(RenderSamplingSettings.runtimeValidated, "Do not enable an unvalidated runtime")
    }

    func testInvalidAndOversizedPreferencesFailClosedWithoutDestructiveMigration() throws {
        let suite = "FlashNest.RenderSamplingSettingsTests." + UUID().uuidString
        let defaults = try XCTUnwrap(UserDefaults(suiteName: suite))
        defer { defaults.removePersistentDomain(forName: suite) }
        let id = UUID(), key = RenderSamplingSettings.preferenceKey(for: id)
        for data in [Data("not JSON".utf8), Data("{\"version\":2,\"mode\":\"webgl\"}".utf8),
                     Data("{\"version\":1,\"mode\":\"canvas\"}".utf8),
                     Data("{\"version\":1,\"mode\":true}".utf8),
                     Data(repeating: 32, count: RenderSamplingSettings.maximumBytes + 1)] {
            defaults.set(data, forKey: key)
            XCTAssertEqual(RenderSamplingSettings.load(for: id, defaults: defaults).mode, .original)
            XCTAssertEqual(defaults.data(forKey: key), data)
        }
        defaults.set(Data("{\"version\":1}".utf8), forKey: key)
        XCTAssertEqual(RenderSamplingSettings.load(for: id, defaults: defaults).mode, .original)
    }

    func testArchivedCSSExperimentsNeverOptIntoDensity() throws {
        let suite = "FlashNest.RenderSamplingSettingsTests." + UUID().uuidString
        let defaults = try XCTUnwrap(UserDefaults(suiteName: suite))
        defer { defaults.removePersistentDomain(forName: suite) }
        let id = UUID()
        for prefix in ["FlashNest.renderSettings.v1.", "FlashNest.renderResolution.v1."] {
            defaults.set(Data("{\"version\":1,\"tier\":\"half\",\"usesHalfResolution\":true}".utf8), forKey: prefix + id.uuidString)
        }
        XCTAssertEqual(RenderSamplingSettings.load(for: id, defaults: defaults).mode, .original)
        XCTAssertNil(defaults.data(forKey: RenderSamplingSettings.preferenceKey(for: id)))
        // Real Session tests separately verify new-page application vs retained-page backgrounding.
    }
}

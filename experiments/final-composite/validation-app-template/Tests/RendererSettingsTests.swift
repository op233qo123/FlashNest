import XCTest
@testable import FlashNest

final class RendererSettingsTests: XCTestCase {
    func testAutomaticDefaultAndStrictQueryContract() {
        XCTAssertEqual(RendererSettings().mode, .automatic)
        XCTAssertEqual(RendererSettings.Mode.allCases.map(\.rawValue), ["automatic", "webgl", "enhanced"])
        XCTAssertNil(RendererSettings.Mode.automatic.queryValue)
        XCTAssertEqual(RendererSettings.Mode.webgl.queryValue, "webgl")
        XCTAssertEqual(RendererSettings.Mode.enhanced.queryValue, "enhanced", "Shell policy token must not masquerade as a runtime backend")
    }

    func testIsolatedPerGameRoundTripAndCopiedRequest() throws {
        let suite = "FlashNest.RendererSettingsTests." + UUID().uuidString
        let defaults = try XCTUnwrap(UserDefaults(suiteName: suite))
        defer { defaults.removePersistentDomain(forName: suite) }
        let first = UUID(), second = UUID()
        let touchKey = TouchControlSettings.preferenceKey(for: first)
        defaults.set("unchanged", forKey: touchKey)
        defaults.set("unchanged", forKey: "save-sentinel")
        let originalRequest = RendererSettings.load(for: first, defaults: defaults)
        XCTAssertTrue(RendererSettings(mode: .webgl).save(for: first, defaults: defaults))
        XCTAssertEqual(originalRequest.mode, .automatic, "Value snapshot cannot mutate with later preference writes")
        XCTAssertEqual(RendererSettings.load(for: first, defaults: defaults).mode, .webgl)
        XCTAssertEqual(RendererSettings.load(for: second, defaults: defaults).mode, .automatic)
        let webglRequest = RendererSettings.load(for: first, defaults: defaults)
        XCTAssertTrue(RendererSettings(mode: .enhanced).save(for: first, defaults: defaults))
        XCTAssertEqual(webglRequest.mode, .webgl, "Changing the next-opening policy cannot mutate a copied live request")
        XCTAssertEqual(RendererSettings.load(for: first, defaults: defaults).mode, .enhanced)
        XCTAssertEqual(RendererSettings.load(for: second, defaults: defaults).mode, .automatic)
        XCTAssertEqual(originalRequest.mode, .automatic)
        XCTAssertTrue(RendererSettings().save(for: first, defaults: defaults))
        XCTAssertEqual(RendererSettings.load(for: first, defaults: defaults).mode, .automatic)
        XCTAssertEqual(defaults.string(forKey: touchKey), "unchanged")
        XCTAssertEqual(defaults.string(forKey: "save-sentinel"), "unchanged")
    }

    func testInvalidAndOversizedPreferencesFailClosedWithoutDestructiveMigration() throws {
        let suite = "FlashNest.RendererSettingsTests." + UUID().uuidString
        let defaults = try XCTUnwrap(UserDefaults(suiteName: suite))
        defer { defaults.removePersistentDomain(forName: suite) }
        let id = UUID(), key = RendererSettings.preferenceKey(for: id)
        for data in [Data("not JSON".utf8), Data("{\"version\":2,\"mode\":\"webgl\"}".utf8),
                     Data("{\"version\":1,\"mode\":\"canvas\"}".utf8),
                     Data("{\"version\":1,\"mode\":\"Enhanced\"}".utf8),
                     Data("{\"version\":1,\"mode\":\"wgpu-webgl\"}".utf8),
                     Data("{\"version\":2,\"mode\":\"enhanced\"}".utf8),
                     Data("{\"version\":1,\"mode\":true}".utf8),
                     Data(repeating: 32, count: RendererSettings.maximumBytes + 1)] {
            defaults.set(data, forKey: key)
            XCTAssertEqual(RendererSettings.load(for: id, defaults: defaults).mode, .automatic)
            XCTAssertEqual(defaults.data(forKey: key), data)
        }
        defaults.set(Data("{\"version\":1}".utf8), forKey: key)
        XCTAssertEqual(RendererSettings.load(for: id, defaults: defaults).mode, .automatic)
    }

    func testVersionOneModesRoundTripWithoutRewritingExistingPreferences() throws {
        let suite = "FlashNest.RendererSettingsTests." + UUID().uuidString
        let defaults = try XCTUnwrap(UserDefaults(suiteName: suite))
        defer { defaults.removePersistentDomain(forName: suite) }
        let id = UUID(), key = RendererSettings.preferenceKey(for: id)
        for mode in RendererSettings.Mode.allCases {
            let existing = Data("{\"version\":1,\"mode\":\"\(mode.rawValue)\"}".utf8)
            defaults.set(existing, forKey: key)
            let loaded = RendererSettings.load(for: id, defaults: defaults)
            XCTAssertEqual(loaded.mode, mode)
            XCTAssertEqual(defaults.data(forKey: key), existing, "Read must not migrate or rewrite stored bytes")
            let encoded = try JSONEncoder().encode(loaded)
            let object = try XCTUnwrap(JSONSerialization.jsonObject(with: encoded) as? [String: Any])
            XCTAssertEqual(object["version"] as? Int, 1)
            XCTAssertEqual(object["mode"] as? String, mode.rawValue)
            XCTAssertEqual(try JSONDecoder().decode(RendererSettings.self, from: encoded), loaded)
        }
    }

    func testResolutionExperimentsNeverOptIntoCompatibility() throws {
        let suite = "FlashNest.RendererSettingsTests." + UUID().uuidString
        let defaults = try XCTUnwrap(UserDefaults(suiteName: suite))
        defer { defaults.removePersistentDomain(forName: suite) }
        let id = UUID()
        for prefix in ["FlashNest.renderSettings.v1.", "FlashNest.renderResolution.v1."] {
            defaults.set(Data("{\"version\":1,\"tier\":\"half\",\"usesHalfResolution\":true}".utf8), forKey: prefix + id.uuidString)
        }
        XCTAssertEqual(RendererSettings.load(for: id, defaults: defaults).mode, .automatic)
        XCTAssertNil(defaults.data(forKey: RendererSettings.preferenceKey(for: id)))
        // Real Session tests separately verify new-page application vs retained-page backgrounding.
    }
}

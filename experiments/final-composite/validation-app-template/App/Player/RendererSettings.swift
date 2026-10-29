import Foundation

/// Per-game renderer policy. A session copies this preference when creating a new
/// player page; selecting it never changes or restarts an existing page.
/// Separate from resolution experiments, touch controls and game save data.
struct RendererSettings: Codable, Equatable {
    enum Mode: String, Codable, CaseIterable, Identifiable {
        case automatic, webgl, enhanced
        var id: String { rawValue }
        // Automatic omits the URL override; the shell applies compatibility-first policy.
        // Enhanced is a shell policy token, NOT a runtime backend identifier: the
        // shell omits preferredRenderer to restore the original automatic order.
        var queryValue: String? {
            switch self {
            case .automatic: return nil
            case .webgl: return "webgl"
            case .enhanced: return "enhanced"
            }
        }
    }

    static let maximumBytes = 1_024
    var mode: Mode = .automatic

    init(mode: Mode = .automatic) { self.mode = mode }

    static func preferenceKey(for packageID: UUID) -> String {
        "FlashNest.rendererCompatibility.v1." + packageID.uuidString
    }

    static func load(for packageID: UUID, defaults: UserDefaults = .standard) -> Self {
        guard let data = defaults.data(forKey: preferenceKey(for: packageID)),
              data.count <= maximumBytes,
              let result = try? JSONDecoder().decode(Self.self, from: data) else { return Self() }
        return result
    }

    @discardableResult func save(for packageID: UUID, defaults: UserDefaults = .standard) -> Bool {
        guard let data = try? JSONEncoder().encode(self), data.count <= Self.maximumBytes else { return false }
        defaults.set(data, forKey: Self.preferenceKey(for: packageID))
        return true
    }

    private enum CodingKeys: String, CodingKey { case version, mode }
    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        guard try container.decode(Int.self, forKey: .version) == 1 else {
            throw DecodingError.dataCorruptedError(forKey: .version, in: container,
                debugDescription: "Unsupported renderer preferences version")
        }
        mode = try container.decodeIfPresent(Mode.self, forKey: .mode) ?? .automatic
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(1, forKey: .version)
        try container.encode(mode, forKey: .mode)
    }
}

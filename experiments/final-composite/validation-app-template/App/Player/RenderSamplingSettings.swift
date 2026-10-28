import Foundation

/// Per-game opt-in only. A session copies this preference when creating a new
/// player page; selecting it never changes or restarts an existing page.
/// Separate from renderer selection, archived CSS experiments, touch controls and saves.
struct RenderSamplingSettings: Codable, Equatable {
    enum Mode: String, Codable, CaseIterable, Identifiable {
        case original, threeQuarter, half, quarter
        var id: String { rawValue }
        var scale: Double {
            switch self { case .original: return 1; case .threeQuarter: return 0.75; case .half: return 0.5; case .quarter: return 0.25 }
        }
        // Automatic keeps the production launch URL/configuration unchanged.
        var queryValue: String? { self == .original ? nil : String(scale) }
    }

    // Release gate: remains false until a combined audio+density runtime is built,
    // provenance-checked and passes the required geometry/device acceptance gates.
    static let runtimeValidated = false

    static let maximumBytes = 1_024
    var mode: Mode = .original

    init(mode: Mode = .original) { self.mode = mode }

    static func preferenceKey(for packageID: UUID) -> String {
        "FlashNest.onscreenSampling.v1." + packageID.uuidString
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
                debugDescription: "Unsupported sampling preferences version")
        }
        mode = try container.decodeIfPresent(Mode.self, forKey: .mode) ?? .original
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(1, forKey: .version)
        try container.encode(mode, forKey: .mode)
    }
}

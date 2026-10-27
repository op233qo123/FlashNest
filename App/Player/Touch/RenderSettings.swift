import Foundation

/// A per-game rendering experiment, separate from controls and game saves.
/// PlayerSession snapshots it when a game is opened; changing it never reloads
/// an active movie or changes the window's real devicePixelRatio.
struct RenderSettings: Codable, Equatable {
    var usesHalfResolution = false

    static func preferenceKey(for packageID: UUID) -> String {
        "FlashNest.renderSettings.v1." + packageID.uuidString
    }

    static func load(for packageID: UUID, defaults: UserDefaults = .standard) -> Self {
        guard let data = defaults.data(forKey: preferenceKey(for: packageID)),
              let value = try? JSONDecoder().decode(Self.self, from: data) else { return Self() }
        return value
    }

    func save(for packageID: UUID, defaults: UserDefaults = .standard) {
        guard let data = try? JSONEncoder().encode(self) else { return }
        defaults.set(data, forKey: Self.preferenceKey(for: packageID))
    }
}

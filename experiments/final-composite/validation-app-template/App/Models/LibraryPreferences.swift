import Foundation

/// Presentation metadata only. Never changes package manifests, content or saves.
struct LibraryPreferences: Codable, Equatable {
    enum SortOrder: String, Codable, CaseIterable {
        case imported, recentlyOpened, title
    }

    static let preferenceKey = "FlashNest.libraryPreferences.v1"
    static let maximumIDs = 1024
    static let maximumBytes = 131_072
    var sortOrder: SortOrder = .imported
    var favoritesOnly = false
    private(set) var favoriteIDs = Set<UUID>()
    private(set) var lastOpened: [UUID: Date] = [:]

    init() {}

    func isFavorite(_ id: UUID) -> Bool { favoriteIDs.contains(id) }

    /// False means the bounded favorites list is full; existing metadata stays.
    @discardableResult mutating func toggleFavorite(_ id: UUID) -> Bool {
        if favoriteIDs.contains(id) { favoriteIDs.remove(id); return true }
        guard favoriteIDs.count < Self.maximumIDs else { return false }
        favoriteIDs.insert(id)
        return true
    }

    /// Call after beginPlayback succeeds, not when a row or entry picker opens.
    /// Oldest history is bounded independently of favorites. Missing library IDs
    /// are not pruned: a failed manifest read is not evidence of game deletion.
    @discardableResult mutating func recordOpened(_ id: UUID, at date: Date = Date()) -> Bool {
        guard Self.valid(date) else { return false }
        lastOpened[id] = date
        while lastOpened.count > Self.maximumIDs {
            guard let oldest = lastOpened.filter({ $0.key != id }).min(by: {
                $0.value == $1.value ? $0.key.uuidString < $1.key.uuidString : $0.value < $1.value
            }) else { break }
            lastOpened.removeValue(forKey: oldest.key)
        }
        return true
    }

    static func load(defaults: UserDefaults = .standard) -> Self {
        guard let data = defaults.data(forKey: preferenceKey), data.count <= maximumBytes,
              let value = try? JSONDecoder().decode(Self.self, from: data) else { return Self() }
        return value
    }

    /// Invalid/oversized encoding leaves the previous preference value intact.
    @discardableResult func save(defaults: UserDefaults = .standard) -> Bool {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.sortedKeys]
        guard let data = try? encoder.encode(self), data.count <= Self.maximumBytes else { return false }
        defaults.set(data, forKey: Self.preferenceKey)
        return true
    }

    private enum CodingKeys: String, CodingKey { case version, sortOrder, favoritesOnly, favoriteIDs, lastOpened }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        guard try container.decode(Int.self, forKey: .version) == 1 else {
            throw DecodingError.dataCorruptedError(forKey: .version, in: container, debugDescription: "Unsupported library preferences version")
        }
        sortOrder = try container.decodeIfPresent(SortOrder.self, forKey: .sortOrder) ?? .imported
        favoritesOnly = try container.decodeIfPresent(Bool.self, forKey: .favoritesOnly) ?? false
        let favorites = try container.decodeIfPresent([String].self, forKey: .favoriteIDs) ?? []
        let opened = try container.decodeIfPresent([String: Date].self, forKey: .lastOpened) ?? [:]
        guard favorites.count <= Self.maximumIDs, opened.count <= Self.maximumIDs else {
            throw DecodingError.dataCorruptedError(forKey: .favoriteIDs, in: container, debugDescription: "Library metadata limit")
        }
        for raw in favorites {
            guard let id = UUID(uuidString: raw), favoriteIDs.insert(id).inserted else {
                throw DecodingError.dataCorruptedError(forKey: .favoriteIDs, in: container, debugDescription: "Invalid or duplicate favorite ID")
            }
        }
        for (raw, date) in opened {
            guard let id = UUID(uuidString: raw), lastOpened[id] == nil, Self.valid(date) else {
                throw DecodingError.dataCorruptedError(forKey: .lastOpened, in: container, debugDescription: "Invalid recently opened metadata")
            }
            lastOpened[id] = date
        }
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(1, forKey: .version)
        try container.encode(sortOrder, forKey: .sortOrder)
        try container.encode(favoritesOnly, forKey: .favoritesOnly)
        try container.encode(favoriteIDs.map(\.uuidString).sorted(), forKey: .favoriteIDs)
        try container.encode(Dictionary(uniqueKeysWithValues: lastOpened.map { ($0.key.uuidString, $0.value) }), forKey: .lastOpened)
    }

    private static func valid(_ date: Date) -> Bool {
        // Fixed range keeps decoding deterministic, independent of device clock.
        date.timeIntervalSince1970.isFinite && (0...4_102_444_800).contains(date.timeIntervalSince1970)
    }
}

/// Pure view query; cannot mutate a package, preference or file.
enum LibraryQuery {
    static func visible(packages: [GamePackage], search: String, preferences: LibraryPreferences) -> [GamePackage] {
        let needle = normalized(String(search.prefix(512)).trimmingCharacters(in: .whitespacesAndNewlines))
        return packages.filter { package in
            (!preferences.favoritesOnly || preferences.isFavorite(package.id)) &&
                (needle.isEmpty || normalized(package.title).contains(needle) || normalized(package.selectedMovie).contains(needle))
        }.sorted { lhs, rhs in
            switch preferences.sortOrder {
            case .imported:
                if lhs.importedAt != rhs.importedAt { return lhs.importedAt > rhs.importedAt }
            case .recentlyOpened:
                let left = preferences.lastOpened[lhs.id], right = preferences.lastOpened[rhs.id]
                if left != right {
                    if let left, let right { return left > right }
                    return left != nil
                }
                if lhs.importedAt != rhs.importedAt { return lhs.importedAt > rhs.importedAt }
            case .title:
                let left = normalized(lhs.title), right = normalized(rhs.title)
                if left != right { return left < right }
            }
            return lhs.id.uuidString < rhs.id.uuidString
        }
    }

    private static func normalized(_ text: String) -> String {
        text.folding(options: [.caseInsensitive, .diacriticInsensitive], locale: Locale(identifier: "en_US_POSIX"))
    }
}

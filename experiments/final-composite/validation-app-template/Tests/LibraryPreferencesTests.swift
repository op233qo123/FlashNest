import XCTest
@testable import FlashNest

final class LibraryPreferencesTests: XCTestCase {
    private func package(_ number: Int, title: String, movie: String = "main.swf", imported: TimeInterval = 10) -> GamePackage {
        let id = UUID(uuidString: String(format: "00000000-0000-0000-0000-%012d", number))!
        return GamePackage(id: id, title: title, importedAt: Date(timeIntervalSince1970: imported),
                           movies: [movie], selectedMovie: movie)
    }

    func testSearchMatchesChineseEnglishCaseDiacriticsAndSelectedEntry() {
        let games = [package(1, title: "打倒魔王", movie: "子目录/开始.swf"),
                     package(2, title: "Café Quest", movie: "Content/INTRO.SWF"),
                     package(3, title: "Unrelated")]
        let preferences = LibraryPreferences()
        XCTAssertEqual(LibraryQuery.visible(packages: games, search: "魔王", preferences: preferences).map(\.id), [games[0].id])
        XCTAssertEqual(LibraryQuery.visible(packages: games, search: "开始", preferences: preferences).map(\.id), [games[0].id])
        XCTAssertEqual(LibraryQuery.visible(packages: games, search: "  CAFE  ", preferences: preferences).map(\.id), [games[1].id])
        XCTAssertEqual(LibraryQuery.visible(packages: games, search: "intro.swf", preferences: preferences).map(\.id), [games[1].id])
        XCTAssertEqual(LibraryQuery.visible(packages: games, search: "\n ", preferences: preferences).count, 3)
        XCTAssertTrue(LibraryQuery.visible(packages: games, search: "missing", preferences: preferences).isEmpty)
    }

    func testImportedTitleAndRecentSortAreDeterministic() {
        let first = package(1, title: "beta", imported: 10)
        let second = package(2, title: "Álpha", imported: 20)
        let third = package(3, title: "alpha", imported: 20)
        let games = [third, first, second]
        var preferences = LibraryPreferences()
        func ids() -> [UUID] { LibraryQuery.visible(packages: games, search: "", preferences: preferences).map(\.id) }
        XCTAssertEqual(ids(), [second.id, third.id, first.id])
        preferences.sortOrder = .title
        XCTAssertEqual(ids(), [second.id, third.id, first.id])
        preferences.sortOrder = .recentlyOpened
        XCTAssertEqual(ids(), [second.id, third.id, first.id], "Never-opened entries retain imported ordering")
        preferences.recordOpened(first.id, at: Date(timeIntervalSince1970: 100))
        XCTAssertEqual(ids(), [first.id, second.id, third.id])
        preferences.recordOpened(third.id, at: Date(timeIntervalSince1970: 100))
        XCTAssertEqual(ids(), [third.id, first.id, second.id], "Tied recent dates fall back to import date, then UUID")
        for order in LibraryPreferences.SortOrder.allCases {
            preferences.sortOrder = order
            XCTAssertEqual(LibraryQuery.visible(packages: Array(games.reversed()), search: "", preferences: preferences).map(\.id), ids())
        }
    }

    func testFavoritesAndMissingIDsNeverMutatePackagesOrPruneMetadata() throws {
        let games = [package(1, title: "One"), package(2, title: "Two")]
        let original = games
        let missing = UUID()
        var preferences = LibraryPreferences()
        preferences.toggleFavorite(games[1].id)
        preferences.toggleFavorite(missing)
        preferences.recordOpened(missing, at: Date(timeIntervalSince1970: 100))
        preferences.favoritesOnly = true
        let before = preferences
        XCTAssertEqual(LibraryQuery.visible(packages: games, search: "", preferences: preferences), [games[1]])
        XCTAssertTrue(LibraryQuery.visible(packages: [], search: "", preferences: preferences).isEmpty)
        XCTAssertEqual(preferences, before, "A temporary missing/unreadable library must not erase presentation metadata")
        XCTAssertEqual(games, original, "Queries never change selected entry or package manifest values")
        preferences.toggleFavorite(games[1].id)
        XCTAssertFalse(preferences.isFavorite(games[1].id))
        XCTAssertTrue(preferences.isFavorite(missing))
    }

    func testPreferenceRoundTripAndDefaultsRemainSeparateFromOtherSettings() throws {
        let suite = "FlashNest.LibraryPreferencesTests." + UUID().uuidString
        let defaults = try XCTUnwrap(UserDefaults(suiteName: suite))
        defer { defaults.removePersistentDomain(forName: suite) }
        defaults.set("untouched", forKey: "save-or-control-sentinel")
        XCTAssertEqual(LibraryPreferences.load(defaults: defaults), LibraryPreferences())
        var preferences = LibraryPreferences()
        preferences.sortOrder = .recentlyOpened
        preferences.favoritesOnly = true
        let id = UUID()
        preferences.toggleFavorite(id)
        preferences.recordOpened(id, at: Date(timeIntervalSince1970: 100))
        XCTAssertTrue(preferences.save(defaults: defaults))
        XCTAssertEqual(LibraryPreferences.load(defaults: defaults), preferences)
        XCTAssertEqual(defaults.string(forKey: "save-or-control-sentinel"), "untouched")
        let encoded = try XCTUnwrap(defaults.data(forKey: LibraryPreferences.preferenceKey))
        XCTAssertLessThanOrEqual(encoded.count, LibraryPreferences.maximumBytes)
        XCTAssertFalse(String(decoding: encoded, as: UTF8.self).contains("main.swf"))
    }

    func testCorruptUnknownAndOversizedPreferencesFallBackWithoutRewriting() throws {
        let suite = "FlashNest.LibraryPreferencesTests." + UUID().uuidString
        let defaults = try XCTUnwrap(UserDefaults(suiteName: suite))
        defer { defaults.removePersistentDomain(forName: suite) }
        let id = UUID().uuidString
        let invalid = [Data("not JSON".utf8), Data("{\"version\":2}".utf8),
                       Data("{\"version\":1,\"sortOrder\":\"unknown\"}".utf8),
                       Data("{\"version\":1,\"favoriteIDs\":[\"invalid-id\"]}".utf8),
                       Data("{\"version\":1,\"favoriteIDs\":[\"\(id)\",\"\(id)\"]}".utf8),
                       Data("{\"version\":1,\"lastOpened\":{\"\(id)\":1e99}}".utf8),
                       Data(repeating: 32, count: LibraryPreferences.maximumBytes + 1)]
        for bytes in invalid {
            defaults.set(bytes, forKey: LibraryPreferences.preferenceKey)
            XCTAssertEqual(LibraryPreferences.load(defaults: defaults), LibraryPreferences())
            XCTAssertEqual(defaults.data(forKey: LibraryPreferences.preferenceKey), bytes)
        }
        defaults.set(Data("{\"version\":1}".utf8), forKey: LibraryPreferences.preferenceKey)
        XCTAssertEqual(LibraryPreferences.load(defaults: defaults), LibraryPreferences())
    }

    func testMetadataBoundsAndInvalidDatesPreserveFavorites() throws {
        var preferences = LibraryPreferences()
        var ids: [UUID] = []
        for index in 0..<LibraryPreferences.maximumIDs {
            let id = UUID(); ids.append(id)
            XCTAssertTrue(preferences.toggleFavorite(id))
            XCTAssertTrue(preferences.recordOpened(id, at: Date(timeIntervalSince1970: Double(index))))
        }
        let newer = UUID()
        XCTAssertFalse(preferences.toggleFavorite(newer))
        XCTAssertTrue(preferences.recordOpened(newer, at: Date(timeIntervalSince1970: 10_000)))
        XCTAssertEqual(preferences.lastOpened.count, LibraryPreferences.maximumIDs)
        XCTAssertNil(preferences.lastOpened[ids[0]])
        XCTAssertTrue(preferences.isFavorite(ids[0]), "History eviction must not alter favorites")
        let before = preferences
        XCTAssertFalse(preferences.recordOpened(newer, at: Date(timeIntervalSince1970: .infinity)))
        XCTAssertEqual(preferences, before)
        let encoded = try JSONEncoder().encode(preferences)
        XCTAssertLessThanOrEqual(encoded.count, LibraryPreferences.maximumBytes)
        let oversizedIDs = Array(repeating: UUID().uuidString, count: LibraryPreferences.maximumIDs + 1)
        let bytes = try JSONSerialization.data(withJSONObject: ["version": 1, "favoriteIDs": oversizedIDs])
        XCTAssertThrowsError(try JSONDecoder().decode(LibraryPreferences.self, from: bytes))
    }
}

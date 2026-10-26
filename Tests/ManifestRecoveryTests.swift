import XCTest
@testable import FlashNest

@MainActor final class ManifestRecoveryTests: XCTestCase {
    private func withFixture(actual: [String], recorded: [String], selected: String,
                             check: (LibraryStore, GamePackage, URL, Data) throws -> Void) throws {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: root) }
        let package = GamePackage(id: UUID(), title: "Original 游戏 title", importedAt: Date(timeIntervalSince1970: 123456),
                                  movies: recorded, selectedMovie: selected)
        let folder = root.appendingPathComponent(package.id.uuidString)
        for path in actual {
            let file = folder.appendingPathComponent("content").appendingPathComponent(path)
            try FileManager.default.createDirectory(at: file.deletingLastPathComponent(), withIntermediateDirectories: true)
            try Data("FWSfixture".utf8).write(to: file)
        }
        let manifest = folder.appendingPathComponent("manifest.json")
        let original = try JSONEncoder().encode(package)
        try original.write(to: manifest)
        try check(LibraryStore(root: root), package, manifest, original)
    }

    func testKnownContentPrefixIsRepairedAndMetadataAndSelectionPreserved() throws {
        try withFixture(actual: ["main.swf", "sub/child.swf"], recorded: ["content/main.swf", "content/sub/child.swf"], selected: "content/sub/child.swf") { store, original, file, _ in
            let repaired = try XCTUnwrap(store.packages.first)
            XCTAssertEqual(repaired.movies, ["main.swf", "sub/child.swf"])
            XCTAssertEqual(repaired.selectedMovie, "sub/child.swf")
            XCTAssertEqual(repaired.id, original.id)
            XCTAssertEqual(repaired.title, original.title)
            XCTAssertEqual(repaired.importedAt, original.importedAt)
            XCTAssertEqual(try JSONDecoder().decode(GamePackage.self, from: Data(contentsOf: file)), repaired)
            store.reload()
            XCTAssertEqual(store.packages, [repaired])
        }
    }

    func testGenuineContentDirectoryIsPreservedWithoutRewrite() throws {
        try withFixture(actual: ["content/main.swf"], recorded: ["content/main.swf"], selected: "content/main.swf") { store, original, file, bytes in
            XCTAssertEqual(store.packages, [original])
            XCTAssertEqual(try Data(contentsOf: file), bytes)
        }
    }

    func testExactPathsTakePriorityAndAmbiguousDuplicateMappingFailsClosed() throws {
        try withFixture(actual: ["main.swf", "content/main.swf"], recorded: ["content/main.swf", "content/content/main.swf"], selected: "content/main.swf") { store, _, file, bytes in
            XCTAssertTrue(store.packages.isEmpty)
            XCTAssertNotNil(store.error)
            XCTAssertEqual(try Data(contentsOf: file), bytes)
        }
    }

    func testUnknownPrefixIsNotGuessedAndManifestIsPreserved() throws {
        try withFixture(actual: ["main.swf"], recorded: ["ghost/main.swf"], selected: "ghost/main.swf") { store, _, file, bytes in
            XCTAssertTrue(store.packages.isEmpty)
            XCTAssertEqual(try Data(contentsOf: file), bytes)
        }
    }

    func testMissingMovieAndInvalidSelectionAreNotRewritten() throws {
        for selected in ["main.swf", "missing.swf"] {
            let recorded = selected == "main.swf" ? ["main.swf", "missing.swf"] : ["main.swf"]
            try withFixture(actual: ["main.swf"], recorded: recorded, selected: selected) { store, _, file, bytes in
                XCTAssertTrue(store.packages.isEmpty)
                XCTAssertEqual(try Data(contentsOf: file), bytes)
            }
        }
    }
}

import XCTest
@testable import FlashNest

final class SaveImportReaderTests: XCTestCase {
    private var directory: URL!
    private var store: SaveStore!
    private var game: GamePackage!

    override func setUpWithError() throws {
        directory = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        store = SaveStore(root: directory.appendingPathComponent("Saves"))
        game = GamePackage(id: UUID(), title: "Selected destination", importedAt: Date(), movies: ["main.swf"], selectedMovie: "main.swf")
    }
    override func tearDownWithError() throws { try FileManager.default.removeItem(at: directory) }

    private func current() throws -> SaveSnapshot {
        try store.persistLatest(SaveCapture(version: 1, entries: [SaveEntry(scope: "origin", key: "FlashNestFixture", value: RawSOLTestFixtures.sol().base64EncodedString())]), package: game)
    }

    func testCoordinatedJSONAndCustomExtensionValidateWithoutSelectingOrWritingTarget() throws {
        let original = try current()
        let author = GamePackage(id: UUID(), title: "Backup author", importedAt: Date(), movies: ["main.swf"], selectedMovie: "main.swf")
        let authorStore = SaveStore(root: directory.appendingPathComponent("Author"))
        let backup = try authorStore.capture(SaveCapture(version: 1, entries: []), package: author, name: "Original fixture")
        let bytes = try authorStore.export(backup)
        for suffix in ["JSON", "flashnestsave"] {
            let url = directory.appendingPathComponent("shared." + suffix)
            try bytes.write(to: url)
            guard case .json(let decoded) = try SaveImportReader.read(url, store: store, packageID: game.id) else {
                return XCTFail("Expected validated JSON preview")
            }
            XCTAssertEqual(decoded.packageID, author.id, "Reader decodes metadata; selected target stays an explicit UI decision")
            XCTAssertEqual(try store.export(XCTUnwrap(store.currentSnapshot(packageID: game.id))), try store.export(original))
            XCTAssertEqual(try Data(contentsOf: url), bytes)
        }
    }

    func testRawSOLMatchesExistingNamespaceWithoutChangingCurrentOrOriginal() throws {
        let original = try current(), bytes = RawSOLTestFixtures.sol()
        let url = directory.appendingPathComponent("shared.SOL")
        try bytes.write(to: url)
        guard case .sol(let preview) = try SaveImportReader.read(url, store: store, packageID: game.id) else {
            return XCTFail("Expected bounded raw SOL preview")
        }
        XCTAssertEqual(preview.document.bytes, bytes)
        XCTAssertEqual(preview.plan?.candidates, [RawSOLTarget(scope: "origin", key: "FlashNestFixture")])
        XCTAssertEqual(try store.export(XCTUnwrap(store.currentSnapshot(packageID: game.id))), try store.export(original))
        XCTAssertEqual(try Data(contentsOf: url), bytes)
    }

    func testUnknownJSONMissingProviderSymlinkAndOversizedSOLFailWithoutMutation() throws {
        let original = try current()
        let wrong = directory.appendingPathComponent("ordinary.json")
        try Data("{\"ordinary\":true}".utf8).write(to: wrong)
        let oversized = directory.appendingPathComponent("large.sol")
        try Data(repeating: 0, count: SaveStore.maximumObjectBytes + 1).write(to: oversized)
        let alias = directory.appendingPathComponent("alias.json")
        try FileManager.default.createSymbolicLink(at: alias, withDestinationURL: wrong)
        for url in [wrong, oversized, alias, directory.appendingPathComponent("missing.json"), URL(string: "https://example.invalid/save.json")!] {
            XCTAssertThrowsError(try SaveImportReader.read(url, store: store, packageID: game.id))
        }
        XCTAssertEqual(try store.export(XCTUnwrap(store.currentSnapshot(packageID: game.id))), try store.export(original))
    }
}

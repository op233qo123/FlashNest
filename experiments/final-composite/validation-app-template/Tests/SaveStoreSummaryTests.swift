import XCTest
@testable import FlashNest

final class SaveStoreSummaryTests: XCTestCase {
    private var root: URL!
    private var store: SaveStore!
    private var game: GamePackage!

    override func setUpWithError() throws {
        root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        store = SaveStore(root: root)
        game = GamePackage(id: UUID(), title: "Summary fixture", importedAt: Date(), movies: ["main.swf"], selectedMovie: "main.swf")
    }
    override func tearDownWithError() throws { if FileManager.default.fileExists(atPath: root.path) { try FileManager.default.removeItem(at: root) } }

    private func capture(marker: UInt8 = 0) -> SaveCapture {
        var data = Data(repeating: marker, count: 24)
        data[0] = 0; data[1] = 0xbf
        data.replaceSubrange(6..<10, with: "TCSO".utf8)
        data.replaceSubrange(10..<16, with: [0, 4, 0, 0, 0, 0])
        return SaveCapture(version: 1, entries: [SaveEntry(scope: "origin", key: "fixture", value: data.base64EncodedString())])
    }
    private func file(_ id: UUID) -> URL { root.appendingPathComponent(game.id.uuidString).appendingPathComponent(id.uuidString + ".json") }
    private var currentFile: URL { root.appendingPathComponent(game.id.uuidString).appendingPathComponent("current.json") }

    func testSummariesMatchValidatedCurrentAndBackupMetadataAndOrdering() throws {
        XCTAssertNil(try store.currentSummary(packageID: game.id))
        XCTAssertTrue(try store.recoverableSummaryList(packageID: game.id).summaries.isEmpty)
        let first = try store.capture(capture(), package: game, name: "First")
        let second = try store.capture(capture(marker: 1), package: game, name: "Second")
        let current = try store.persistLatest(capture(marker: 2), package: game)
        let listing = try store.recoverableSummaryList(packageID: game.id)
        XCTAssertEqual(listing.invalidFileCount, 0)
        XCTAssertEqual(Set(listing.summaries.map(\.id)), Set([first.id, second.id]))
        XCTAssertEqual(listing.summaries.map(\.createdAt), listing.summaries.map(\.createdAt).sorted(by: >))
        for row in listing.summaries {
            XCTAssertEqual(row.packageID, game.id); XCTAssertEqual(row.source, .backup)
            XCTAssertEqual(row.objectCount, 1); XCTAssertEqual(row.decodedBytes, 24)
            XCTAssertEqual(row.archiveSHA256.count, 64)
            let exported = try store.decodeImport(store.export(row, packageID: game.id))
            XCTAssertEqual(exported.id, row.id); XCTAssertEqual(exported.name, row.name)
        }
        let row = try XCTUnwrap(store.currentSummary(packageID: game.id))
        XCTAssertEqual(row.id, current.id); XCTAssertEqual(row.source, .current)
        XCTAssertEqual(try store.decodeImport(store.export(row, packageID: game.id)).entries, current.entries)
    }

    func testCorruptNeighborIsIsolatedAndStrictOldAPIUnchanged() throws {
        let good = try store.capture(capture(), package: game, name: "Good")
        let bad = file(UUID()), bytes = Data("bad JSON".utf8)
        try bytes.write(to: bad)
        let listing = try store.recoverableSummaryList(packageID: game.id)
        XCTAssertEqual(listing.summaries.map(\.id), [good.id]); XCTAssertEqual(listing.invalidFileCount, 1)
        XCTAssertEqual(try store.recoverableList(packageID: game.id).snapshots.map(\.id), [good.id])
        XCTAssertThrowsError(try store.list(packageID: game.id))
        XCTAssertEqual(try Data(contentsOf: bad), bytes)
    }

    func testExportRejectsCorruptMissingAndReplacedNamedArchiveAfterListing() throws {
        let original = try store.capture(capture(), package: game, name: "Original")
        let row = try XCTUnwrap(store.recoverableSummaryList(packageID: game.id).summaries.first)
        let path = file(original.id), before = try Data(contentsOf: path)
        try Data("corrupt".utf8).write(to: path)
        XCTAssertThrowsError(try store.export(row, packageID: game.id))
        try FileManager.default.removeItem(at: path)
        XCTAssertThrowsError(try store.export(row, packageID: game.id))
        // Still-valid same-ID archive with only its display name changed must
        // fail exact-byte binding; identity alone is not sufficient.
        var object = try XCTUnwrap(JSONSerialization.jsonObject(with: before) as? [String: Any])
        object["name"] = "Changed after listing"
        let replacement = try JSONSerialization.data(withJSONObject: object)
        XCTAssertNoThrow(try store.decodeImport(replacement))
        try replacement.write(to: path)
        XCTAssertThrowsError(try store.export(row, packageID: game.id))
        let fresh = try XCTUnwrap(store.recoverableSummaryList(packageID: game.id).summaries.first)
        XCTAssertNoThrow(try store.export(fresh, packageID: game.id))
    }

    func testExportRejectsWrongPackageAndChangedCurrentWithoutFallingBackToBackup() throws {
        let first = try store.persistLatest(capture(), package: game)
        let row = try XCTUnwrap(store.currentSummary(packageID: game.id))
        // A same-ID named copy must not be used when selected current changes.
        try store.export(first).write(to: file(first.id))
        _ = try store.persistLatest(capture(marker: 3), package: game)
        XCTAssertThrowsError(try store.export(row, packageID: game.id))
        XCTAssertThrowsError(try store.export(row, packageID: UUID()))
        try FileManager.default.removeItem(at: currentFile)
        XCTAssertThrowsError(try store.export(row, packageID: game.id))
        let backup = try XCTUnwrap(store.recoverableSummaryList(packageID: game.id).summaries.first)
        XCTAssertNoThrow(try store.export(backup, packageID: game.id))
    }

    func testExportRejectsSymlinkReplacementAndWrongIdentityOnListing() throws {
        let saved = try store.capture(capture(), package: game, name: "Saved")
        let row = try XCTUnwrap(store.recoverableSummaryList(packageID: game.id).summaries.first)
        let original = file(saved.id), other = file(UUID())
        try FileManager.default.moveItem(at: original, to: other)
        try FileManager.default.createSymbolicLink(at: original, withDestinationURL: other)
        XCTAssertThrowsError(try store.export(row, packageID: game.id))
        let listing = try store.recoverableSummaryList(packageID: game.id)
        XCTAssertTrue(listing.summaries.isEmpty); XCTAssertEqual(listing.invalidFileCount, 2)
    }

    func testEmptyAndCombiningCharacterNamesHaveBoundedDisplayMetadata() throws {
        let name = "A" + String(repeating: "\u{0301}", count: 10_000)
        XCTAssertEqual(name.count, 1)
        let saved = try store.capture(SaveCapture(version: 1, entries: []), package: game, name: name)
        let row = try XCTUnwrap(store.recoverableSummaryList(packageID: game.id).summaries.first)
        XCTAssertEqual(row.objectCount, 0); XCTAssertEqual(row.decodedBytes, 0)
        XCTAssertLessThanOrEqual(row.name.utf8.count, 1027)
        XCTAssertEqual(try store.decodeImport(store.export(row, packageID: game.id)).name, saved.name)
    }

    func testOversizedArchiveIsSkippedWithoutHidingValidMetadata() throws {
        let saved = try store.capture(capture(), package: game, name: "Good")
        let oversized = file(UUID())
        XCTAssertTrue(FileManager.default.createFile(atPath: oversized.path, contents: nil))
        let handle = try FileHandle(forWritingTo: oversized)
        try handle.truncate(atOffset: UInt64(SaveStore.maximumArchiveBytes + 1))
        try handle.close()
        let listing = try store.recoverableSummaryList(packageID: game.id)
        XCTAssertEqual(listing.summaries.map(\.id), [saved.id]); XCTAssertEqual(listing.invalidFileCount, 1)
    }

    func testDirectoryEntryBudgetStillRejectsOversizedListing() throws {
        let directory = root.appendingPathComponent(game.id.uuidString)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        for index in 0..<1025 {
            XCTAssertTrue(FileManager.default.createFile(atPath: directory.appendingPathComponent("ignored-\(index)").path, contents: nil))
        }
        XCTAssertThrowsError(try store.recoverableSummaryList(packageID: game.id))
    }

    func testNamedExportPreservesListedFilenameCaseAndRejectsForgedPath() throws {
        let saved = try store.capture(capture(), package: game, name: "Case-sensitive filename")
        let original = file(saved.id)
        let lowercase = original.deletingLastPathComponent().appendingPathComponent(saved.id.uuidString.lowercased() + ".json")
        // Move via a distinct temporary name so the test also works on volumes
        // where upper/lowercase leaf names refer to the same directory entry.
        let temporary = original.deletingLastPathComponent().appendingPathComponent("case-rename.tmp")
        try FileManager.default.moveItem(at: original, to: temporary)
        try FileManager.default.moveItem(at: temporary, to: lowercase)
        let row = try XCTUnwrap(store.recoverableSummaryList(packageID: game.id).summaries.first)
        XCTAssertEqual(row.archiveFilename, lowercase.lastPathComponent)
        XCTAssertEqual(try store.decodeImport(store.export(row, packageID: game.id)).id, saved.id)
        let forged = SaveSnapshotSummary(id: row.id, packageID: row.packageID, name: row.name,
            createdAt: row.createdAt, objectCount: row.objectCount, decodedBytes: row.decodedBytes,
            source: .backup, archiveFilename: "../" + row.archiveFilename, archiveSHA256: row.archiveSHA256)
        XCTAssertThrowsError(try store.export(forged, packageID: game.id))
    }
}

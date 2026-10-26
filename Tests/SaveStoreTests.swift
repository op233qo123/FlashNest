import XCTest
@testable import FlashNest

final class SaveStoreTests: XCTestCase {
    private var directory: URL!
    private var root: URL!
    private var store: SaveStore!

    override func setUpWithError() throws {
        directory = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        root = directory.appendingPathComponent("Backups")
        store = SaveStore(root: root)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
    }
    override func tearDownWithError() throws { try FileManager.default.removeItem(at: directory) }

    private func package(id: UUID = UUID()) -> GamePackage {
        GamePackage(id: id, title: "Original game", importedAt: Date(), movies: ["main.swf"], selectedMovie: "main.swf")
    }
    private func sol(size: Int = 24) -> Data {
        // Header-only synthetic test data, not a claim of full AMF validity.
        var data = Data(repeating: 0, count: size)
        data[1] = 0xbf
        data.replaceSubrange(6..<10, with: "TCSO".utf8)
        data[11] = 4
        return data
    }
    private func entry(key: String = "progress", bytes: Data? = nil) -> SaveEntry {
        SaveEntry(scope: "origin", key: key, value: (bytes ?? sol()).base64EncodedString())
    }

    func testAtomicCaptureReloadAndPackageFilter() throws {
        let first = package(), second = package()
        let snapshot = try store.capture(SaveCapture(version: 1, entries: [entry()]), package: first, name: "Before boss")
        XCTAssertEqual(snapshot.decodedBytes, 24)
        XCTAssertEqual(snapshot.entries.count, 1)
        XCTAssertEqual(snapshot.entries[0].sha256.count, 64)
        _ = try store.capture(SaveCapture(version: 1, entries: []), package: second, name: "Empty backup")
        let reloaded = try SaveStore(root: root).list(packageID: first.id)
        XCTAssertEqual(reloaded.map(\.id), [snapshot.id])
        XCTAssertEqual(reloaded.first?.entries, snapshot.entries)
        XCTAssertEqual(try store.list().count, 2)
        XCTAssertEqual(try FileManager.default.contentsOfDirectory(atPath: root.path).count, 2)
        let exported = try store.export(snapshot)
        let json = try XCTUnwrap(JSONSerialization.jsonObject(with: exported) as? [String: Any])
        XCTAssertEqual(json["schemaVersion"] as? Int, 1)
        XCTAssertEqual(json["name"] as? String, "Before boss")
    }

    func testEmptyCaptureIsExplicitlyEmpty() throws {
        let snapshot = try store.capture(SaveCapture(version: 1, entries: []), package: package(), name: " ")
        XCTAssertEqual(snapshot.name, "Backup")
        XCTAssertEqual(snapshot.decodedBytes, 0)
        XCTAssertTrue(snapshot.entries.isEmpty)
    }

    func testValidationDoesNotCreateBackupDirectory() throws {
        let invalid: [SaveCapture] = [
            SaveCapture(version: 2, entries: []),
            SaveCapture(version: 1, entries: [entry(), entry()]),
            SaveCapture(version: 1, entries: [SaveEntry(scope: "unknown", key: "x", value: sol().base64EncodedString())]),
            SaveCapture(version: 1, entries: [SaveEntry(scope: "origin", key: "x", value: "not base64")]),
            SaveCapture(version: 1, entries: [SaveEntry(scope: "origin", key: "x", value: sol().base64EncodedString() + "\n")]),
            SaveCapture(version: 1, entries: [entry(bytes: Data("not SOL".utf8))]),
            SaveCapture(version: 1, entries: [entry(key: String(repeating: "x", count: 4097))]),
            SaveCapture(version: 1, entries: (0...256).map { entry(key: "key\($0)") })
        ]
        for capture in invalid {
            XCTAssertThrowsError(try store.capture(capture, package: package(), name: "Test"))
            XCTAssertFalse(FileManager.default.fileExists(atPath: root.path))
        }
    }

    func testObjectAndAggregateByteLimits() throws {
        XCTAssertThrowsError(try store.capture(SaveCapture(version: 1, entries: [entry(bytes: sol(size: 1_048_577))]), package: package(), name: "Too large"))
        let bytes = sol(size: 1_048_576)
        let entries = (0..<9).map { entry(key: "key\($0)", bytes: bytes) }
        XCTAssertThrowsError(try store.capture(SaveCapture(version: 1, entries: entries), package: package(), name: "Too many bytes"))
        XCTAssertFalse(FileManager.default.fileExists(atPath: root.path))
    }

    func testHashAndIdentityTamperingIsRejected() throws {
        let snapshot = try store.capture(SaveCapture(version: 1, entries: [entry()]), package: package(), name: "Original")
        let path = root.appendingPathComponent(snapshot.packageID.uuidString).appendingPathComponent(snapshot.id.uuidString + ".json")
        let original = try Data(contentsOf: path)
        var json = try XCTUnwrap(JSONSerialization.jsonObject(with: original) as? [String: Any])
        var entries = try XCTUnwrap(json["entries"] as? [[String: Any]])
        entries[0]["sha256"] = String(repeating: "0", count: 64)
        json["entries"] = entries
        try JSONSerialization.data(withJSONObject: json).write(to: path)
        XCTAssertThrowsError(try store.list())
        try original.write(to: path)
        json = try XCTUnwrap(JSONSerialization.jsonObject(with: original) as? [String: Any])
        json["id"] = UUID().uuidString
        try JSONSerialization.data(withJSONObject: json).write(to: path)
        XCTAssertThrowsError(try store.list())
    }

    func testWriteFailureDoesNotReportBackupSuccess() throws {
        try Data("not a directory".utf8).write(to: root)
        XCTAssertThrowsError(try store.capture(SaveCapture(version: 1, entries: [entry()]), package: package(), name: "Cannot write"))
        XCTAssertEqual(try Data(contentsOf: root), Data("not a directory".utf8))
    }

    func testSymlinkBackupIsRejected() throws {
        let snapshot = try store.capture(SaveCapture(version: 1, entries: [entry()]), package: package(), name: "Original")
        let path = root.appendingPathComponent(snapshot.packageID.uuidString).appendingPathComponent(snapshot.id.uuidString + ".json")
        let outside = directory.appendingPathComponent("outside.json")
        try FileManager.default.moveItem(at: path, to: outside)
        try FileManager.default.createSymbolicLink(at: path, withDestinationURL: outside)
        XCTAssertThrowsError(try store.list())
    }

    func testLatestAtomicUpdateAndInvalidCapturePreservesCurrent() throws {
        let game = package()
        let original = SaveCapture(version: 1, entries: [entry()])
        _ = try store.persistLatest(original, package: game)
        XCTAssertEqual(try store.latest(packageID: game.id)?.entries, original.entries)
        XCTAssertTrue(try store.list(packageID: game.id).isEmpty, "current.json is not a named snapshot")
        let current = root.appendingPathComponent(game.id.uuidString).appendingPathComponent("current.json")
        let before = try Data(contentsOf: current)
        XCTAssertThrowsError(try store.persistLatest(SaveCapture(version: 99, entries: []), package: game))
        XCTAssertEqual(try Data(contentsOf: current), before)
        var changedBytes = sol(); changedBytes[23] = 1
        _ = try store.persistLatest(SaveCapture(version: 1, entries: [entry(bytes: changedBytes)]), package: game)
        XCTAssertEqual(try store.latest(packageID: game.id)?.entries.first?.value, changedBytes.base64EncodedString())
        XCTAssertTrue(try store.list(packageID: game.id).isEmpty, "ordinary autosaves must not grow backups")
        _ = try store.persistLatest(SaveCapture(version: 1, entries: []), package: game)
        XCTAssertEqual(try store.latest(packageID: game.id)?.entries.count, 0)
        let backups = try store.list(packageID: game.id)
        XCTAssertEqual(backups.count, 1)
        XCTAssertEqual(backups.first?.entries.first?.value, changedBytes.base64EncodedString())
    }

    func testImportMapsOnlyToSelectedPackageAndBacksUpPreviousCurrent() throws {
        let sourceGame = package(), targetGame = package()
        let source = try store.capture(SaveCapture(version: 1, entries: [entry(key: "source")]), package: sourceGame, name: "Source")
        var oldBytes = sol(); oldBytes[23] = 7
        _ = try store.persistLatest(SaveCapture(version: 1, entries: [entry(key: "target", bytes: oldBytes)]), package: targetGame)
        let decoded = try store.decodeImport(store.export(source))
        let imported = try store.importSnapshot(decoded, to: targetGame)
        XCTAssertEqual(imported.packageID, targetGame.id)
        XCTAssertEqual(try store.currentSnapshot(packageID: targetGame.id)?.restoreRequired, true)
        let applied = try XCTUnwrap(store.latest(packageID: targetGame.id))
        _ = try store.persistLatest(applied, package: targetGame)
        XCTAssertNotEqual(try store.currentSnapshot(packageID: targetGame.id)?.restoreRequired, true,
                          "successful capture clears confirmed-import replacement even when entries are unchanged")
        XCTAssertNotEqual(imported.id, source.id)
        XCTAssertEqual(try store.latest(packageID: targetGame.id)?.entries.first?.key, "source")
        XCTAssertNil(try store.latest(packageID: sourceGame.id), "source metadata must not choose the current-save target")
        let backups = try store.list(packageID: targetGame.id)
        XCTAssertEqual(backups.count, 2)
        XCTAssertTrue(backups.contains { $0.name == "Before import" && $0.entries.first?.value == oldBytes.base64EncodedString() })
        XCTAssertEqual(Set(try FileManager.default.contentsOfDirectory(atPath: root.path)), Set([sourceGame.id.uuidString, targetGame.id.uuidString]))
    }

    func testDecodeImportRejectsTamperedAndOversizedArchives() throws {
        let snapshot = try store.capture(SaveCapture(version: 1, entries: [entry()]), package: package(), name: "Original")
        var json = try XCTUnwrap(JSONSerialization.jsonObject(with: store.export(snapshot)) as? [String: Any])
        json["decodedBytes"] = 999
        XCTAssertThrowsError(try store.decodeImport(JSONSerialization.data(withJSONObject: json)))
        json["packageID"] = "../../outside"
        XCTAssertThrowsError(try store.decodeImport(JSONSerialization.data(withJSONObject: json)))
        XCTAssertThrowsError(try store.decodeImport(Data(repeating: 0, count: SaveStore.maximumArchiveBytes + 1)))
    }

    func testRootPackageAndCurrentSymlinksAreRejected() throws {
        let outside = directory.appendingPathComponent("outside", isDirectory: true)
        try FileManager.default.createDirectory(at: outside, withIntermediateDirectories: true)
        try FileManager.default.createSymbolicLink(at: root, withDestinationURL: outside)
        XCTAssertThrowsError(try store.list())
        XCTAssertThrowsError(try store.persistLatest(SaveCapture(version: 1, entries: []), package: package()))
        try FileManager.default.removeItem(at: root)
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        let game = package()
        let folder = root.appendingPathComponent(game.id.uuidString)
        try FileManager.default.createSymbolicLink(at: folder, withDestinationURL: outside)
        XCTAssertThrowsError(try store.latest(packageID: game.id))
        XCTAssertThrowsError(try store.capture(SaveCapture(version: 1, entries: []), package: game, name: "Bad"))
        try FileManager.default.removeItem(at: folder)
        try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
        let outsideFile = outside.appendingPathComponent("untouched.json")
        try Data("untouched".utf8).write(to: outsideFile)
        try FileManager.default.createSymbolicLink(at: folder.appendingPathComponent("current.json"), withDestinationURL: outsideFile)
        XCTAssertThrowsError(try store.persistLatest(SaveCapture(version: 1, entries: []), package: game))
        XCTAssertEqual(try Data(contentsOf: outsideFile), Data("untouched".utf8))
    }

    func testLogicalKeyGrammarPreservesOpaqueNames() throws {
        let valid = [
            SaveEntry(scope: "origin", key: "#folder//name", value: sol().base64EncodedString()),
            SaveEntry(scope: "ancestor", key: "capability/#folder/name", value: sol().base64EncodedString()),
            SaveEntry(scope: "ancestor", key: "games/progress", value: sol().base64EncodedString()),
            SaveEntry(scope: "package", key: "some%2FPath/main.swf/#a//b", value: sol().base64EncodedString())
        ]
        let snapshot = try store.capture(SaveCapture(version: 1, entries: valid), package: package(), name: "Opaque")
        XCTAssertEqual(snapshot.entries.map(\.key), valid.map(\.key))
        for (scope, key) in [("origin", "a/b"), ("ancestor", "wrong/x"), ("ancestor", "games/"), ("package", "a\nname"), ("origin", ".."), ("package", "a/.hidden.swf/name"), ("origin", "a:b"), ("origin", "a\\b")] {
            let capture = SaveCapture(version: 1, entries: [SaveEntry(scope: scope, key: key, value: sol().base64EncodedString())])
            XCTAssertThrowsError(try store.capture(capture, package: package(), name: "Invalid"))
        }
    }


    func testSavedPackageSummariesIncludeCurrentOnlyAndArchivedBackups() throws {
        let currentOnly = package(), backupsOnly = package()
        _ = try store.persistLatest(SaveCapture(version: 1, entries: [entry()]), package: currentOnly)
        _ = try store.capture(SaveCapture(version: 1, entries: [entry()]), package: backupsOnly, name: "Retained")
        let summaries = try store.savedPackages()
        XCTAssertEqual(Set(summaries.map(\.id)), Set([currentOnly.id, backupsOnly.id]))
        let currentSummary = try XCTUnwrap(summaries.first { $0.id == currentOnly.id })
        XCTAssertTrue(currentSummary.hasCurrent)
        XCTAssertEqual(currentSummary.snapshotCount, 0)
        let archivedSummary = try XCTUnwrap(summaries.first { $0.id == backupsOnly.id })
        XCTAssertFalse(archivedSummary.hasCurrent)
        XCTAssertEqual(archivedSummary.snapshotCount, 1)
        XCTAssertEqual(archivedSummary.title, backupsOnly.title)
        // No installed GamePackage or content directory is required to discover/export.
        XCTAssertFalse(FileManager.default.fileExists(atPath: directory.appendingPathComponent("Packages").path))
        let saved = try XCTUnwrap(store.list(packageID: backupsOnly.id).first)
        XCTAssertNoThrow(try store.decodeImport(store.export(saved)))
    }


    func testRestoreAcknowledgmentIsImmediateAtomicAndIdentityGuarded() throws {
        let game = package()
        let source = try store.capture(SaveCapture(version: 1, entries: [entry()]), package: game, name: "Source")
        let imported = try store.importSnapshot(source, to: game)
        XCTAssertEqual(try store.currentSnapshot(packageID: game.id)?.restoreRequired, true)
        XCTAssertThrowsError(try store.markRestoreApplied(packageID: game.id, snapshotID: UUID()))
        XCTAssertEqual(try store.currentSnapshot(packageID: game.id)?.restoreRequired, true)
        try store.markRestoreApplied(packageID: game.id, snapshotID: imported.id)
        XCTAssertEqual(try store.currentSnapshot(packageID: game.id)?.restoreRequired, false)
        XCTAssertEqual(try store.currentSnapshot(packageID: game.id)?.id, imported.id)
        XCTAssertEqual(try store.latest(packageID: game.id)?.entries.first?.key, "progress")
        XCTAssertNoThrow(try store.markRestoreApplied(packageID: game.id, snapshotID: imported.id))
        let newer = try store.importSnapshot(source, to: game)
        XCTAssertThrowsError(try store.markRestoreApplied(packageID: game.id, snapshotID: imported.id))
        XCTAssertEqual(try store.currentSnapshot(packageID: game.id)?.id, newer.id)
        XCTAssertEqual(try store.currentSnapshot(packageID: game.id)?.restoreRequired, true)
    }


    func testCorruptCurrentDoesNotHideValidArchivedBackups() throws {
        let game = package()
        let backup = try store.capture(SaveCapture(version: 1, entries: [entry()]), package: game, name: "Valid backup")
        let current = root.appendingPathComponent(game.id.uuidString).appendingPathComponent("current.json")
        let corrupt = Data("not valid JSON".utf8)
        try corrupt.write(to: current)
        XCTAssertThrowsError(try store.currentSnapshot(packageID: game.id))
        XCTAssertEqual(try store.list(packageID: game.id).map(\.id), [backup.id])
        let summary = try XCTUnwrap(store.savedPackages().first)
        XCTAssertEqual(summary.id, game.id)
        XCTAssertEqual(summary.snapshotCount, 1)
        XCTAssertFalse(summary.hasCurrent)
        XCTAssertNotNil(summary.warning)
        XCTAssertThrowsError(try store.importSnapshot(backup, to: game))
        XCTAssertThrowsError(try store.persistLatest(SaveCapture(version: 1, entries: []), package: game))
        XCTAssertEqual(try Data(contentsOf: current), corrupt)
    }

    func testCorruptImmutableBackupDoesNotSuppressOtherGroupsOrValidExports() throws {
        let first = package(), second = package(), corruptOnly = package()
        let goodA = try store.capture(SaveCapture(version: 1, entries: [entry()]), package: first, name: "Good A")
        let goodB = try store.capture(SaveCapture(version: 1, entries: [entry()]), package: second, name: "Good B")
        let invalid = Data("broken backup JSON".utf8)
        let brokenA = root.appendingPathComponent(first.id.uuidString).appendingPathComponent(UUID().uuidString + ".json")
        try invalid.write(to: brokenA)
        let onlyDirectory = root.appendingPathComponent(corruptOnly.id.uuidString)
        try FileManager.default.createDirectory(at: onlyDirectory, withIntermediateDirectories: true)
        let brokenOnly = onlyDirectory.appendingPathComponent(UUID().uuidString + ".json")
        try invalid.write(to: brokenOnly)
        let summaries = try store.savedPackages()
        XCTAssertEqual(Set(summaries.map(\.id)), Set([first.id, second.id, corruptOnly.id]))
        XCTAssertNotNil(summaries.first(where: { $0.id == first.id })?.warning)
        XCTAssertNil(summaries.first(where: { $0.id == second.id })?.warning)
        XCTAssertNotNil(summaries.first(where: { $0.id == corruptOnly.id })?.warning)
        let recovered = try store.recoverableList(packageID: first.id)
        XCTAssertEqual(recovered.snapshots.map(\.id), [goodA.id])
        XCTAssertEqual(recovered.invalidFileCount, 1)
        XCTAssertNoThrow(try store.decodeImport(store.export(recovered.snapshots[0])))
        XCTAssertEqual(try store.recoverableList(packageID: second.id).snapshots.map(\.id), [goodB.id])
        XCTAssertThrowsError(try store.list(packageID: first.id), "Strict mutation-facing listing remains fail-closed")
        XCTAssertEqual(try Data(contentsOf: brokenA), invalid)
        XCTAssertEqual(try Data(contentsOf: brokenOnly), invalid)
    }

}

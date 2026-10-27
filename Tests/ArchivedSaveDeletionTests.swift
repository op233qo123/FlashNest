import XCTest
import Darwin
@testable import FlashNest

/// Only original synthetic temporary directories; never removes device/user data.
@MainActor final class ArchivedSaveDeletionTests: XCTestCase {
    private var temporary: URL!
    private var store: SaveStore!
    private var game: GamePackage!
    private var library: LibraryStore!
    private var directory: URL { store.root.appendingPathComponent(game.id.uuidString) }

    override func setUpWithError() throws {
        temporary = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        store = SaveStore(root: temporary.appendingPathComponent("save"))
        library = LibraryStore(root: temporary.appendingPathComponent("Packages"), prepareRemoval: { _ in XCTFail("Deletion must never launch a profile") })
        game = GamePackage(id: UUID(), title: "Original archived fixture", importedAt: Date(), movies: ["main.swf"], selectedMovie: "main.swf")
        _ = try store.persistLatest(SaveCapture(version: 1, entries: []), package: game)
        _ = try store.capture(SaveCapture(version: 1, entries: []), package: game, name: "Original backup")
    }
    override func tearDownWithError() throws { try FileManager.default.removeItem(at: temporary) }

    func testPreviewIsReadOnlyAndDeleteRemovesOnlyExplicitArchivedGroup() throws {
        let other = GamePackage(id: UUID(), title: "Other", importedAt: Date(), movies: ["main.swf"], selectedMovie: "main.swf")
        _ = try store.persistLatest(SaveCapture(version: 1, entries: []), package: other)
        let otherFile = store.root.appendingPathComponent(other.id.uuidString).appendingPathComponent("current.json")
        let otherBytes = try Data(contentsOf: otherFile)
        let before = try inventory()
        let token = try library.prepareArchivedSaveDeletion(packageID: game.id, store: store)
        XCTAssertEqual(token.title, game.title); XCTAssertEqual(token.currentFileCount, 1)
        XCTAssertEqual(token.backupFileCount, 1); XCTAssertEqual(token.fileCount, 2)
        XCTAssertEqual(token.totalBytes, before.values.reduce(0) { $0 + $1.count })
        XCTAssertEqual(try inventory(), before, "Preview and cancellation are read-only")
        try library.deleteArchivedSave(token, store: store)
        XCTAssertFalse(FileManager.default.fileExists(atPath: directory.path))
        XCTAssertEqual(try Data(contentsOf: otherFile), otherBytes)
        XCTAssertTrue(try store.savedPackages().contains { $0.id == other.id })
    }

    func testChangedCurrentRejectsBeforeDeletingAnyFile() throws {
        let token = try library.prepareArchivedSaveDeletion(packageID: game.id, store: store)
        try Data("changed but same selected group".utf8).write(to: directory.appendingPathComponent("current.json"))
        let before = try inventory()
        XCTAssertThrowsError(try library.deleteArchivedSave(token, store: store))
        XCTAssertEqual(try inventory(), before)
    }

    func testAddedOrMissingBackupInvalidatesConfirmation() throws {
        var token = try library.prepareArchivedSaveDeletion(packageID: game.id, store: store)
        _ = try store.capture(SaveCapture(version: 1, entries: []), package: game, name: "Added after preview")
        var before = try inventory()
        XCTAssertThrowsError(try library.deleteArchivedSave(token, store: store)); XCTAssertEqual(try inventory(), before)
        token = try library.prepareArchivedSaveDeletion(packageID: game.id, store: store)
        let backup = try XCTUnwrap(before.keys.first { $0 != "current.json" })
        try FileManager.default.removeItem(at: directory.appendingPathComponent(backup))
        before = try inventory()
        XCTAssertThrowsError(try library.deleteArchivedSave(token, store: store)); XCTAssertEqual(try inventory(), before)
    }

    func testByteIdenticalDirectoryReplacementStillInvalidatesIdentity() throws {
        let token = try library.prepareArchivedSaveDeletion(packageID: game.id, store: store)
        let displaced = temporary.appendingPathComponent("displaced")
        try FileManager.default.moveItem(at: directory, to: displaced)
        try FileManager.default.copyItem(at: displaced, to: directory)
        let before = try inventory()
        XCTAssertThrowsError(try library.deleteArchivedSave(token, store: store))
        XCTAssertEqual(try inventory(), before); XCTAssertTrue(FileManager.default.fileExists(atPath: displaced.path))
    }

    func testSymlinkFileAndSymlinkDirectoryNeverFollowTargets() throws {
        let external = temporary.appendingPathComponent("outside.json")
        let bytes = Data("outside original".utf8); try bytes.write(to: external)
        let alias = directory.appendingPathComponent(UUID().uuidString + ".json")
        try FileManager.default.createSymbolicLink(at: alias, withDestinationURL: external)
        XCTAssertThrowsError(try library.prepareArchivedSaveDeletion(packageID: game.id, store: store))
        XCTAssertEqual(try Data(contentsOf: external), bytes)
        try FileManager.default.removeItem(at: alias)
        let token = try library.prepareArchivedSaveDeletion(packageID: game.id, store: store)
        let displaced = temporary.appendingPathComponent("outside-directory")
        try FileManager.default.moveItem(at: directory, to: displaced)
        try FileManager.default.createSymbolicLink(at: directory, withDestinationURL: displaced)
        XCTAssertThrowsError(try library.deleteArchivedSave(token, store: store))
        XCTAssertEqual(try FileManager.default.contentsOfDirectory(atPath: displaced.path).count, 2)
    }

    func testUnknownOrNestedEntriesFailClosedWithoutRecursiveCleanup() throws {
        let nested = directory.appendingPathComponent(UUID().uuidString + ".json", isDirectory: true)
        try FileManager.default.createDirectory(at: nested, withIntermediateDirectories: false)
        try Data("keep".utf8).write(to: nested.appendingPathComponent("keep.txt"))
        XCTAssertThrowsError(try library.prepareArchivedSaveDeletion(packageID: game.id, store: store))
        XCTAssertTrue(FileManager.default.fileExists(atPath: nested.appendingPathComponent("keep.txt").path))
        try FileManager.default.removeItem(at: nested)
        let unknown = directory.appendingPathComponent("notes.txt")
        try Data("keep".utf8).write(to: unknown)
        XCTAssertThrowsError(try library.prepareArchivedSaveDeletion(packageID: game.id, store: store))
        XCTAssertEqual(try Data(contentsOf: unknown), Data("keep".utf8))
    }

    func testCorruptRegularArchiveCanBeExplicitlyDeletedButOversizedOneRefuses() throws {
        let current = directory.appendingPathComponent("current.json")
        try Data("invalid JSON retained until confirmation".utf8).write(to: current)
        let token = try library.prepareArchivedSaveDeletion(packageID: game.id, store: store)
        XCTAssertEqual(token.fileCount, 2)
        let large = directory.appendingPathComponent(UUID().uuidString + ".json")
        XCTAssertTrue(FileManager.default.createFile(atPath: large.path, contents: nil))
        let file = try FileHandle(forWritingTo: large); try file.truncate(atOffset: UInt64(SaveStore.maximumArchiveBytes + 1)); try file.close()
        XCTAssertThrowsError(try library.prepareArchivedSaveDeletion(packageID: game.id, store: store))
        try FileManager.default.removeItem(at: large)
        let refreshed = try library.prepareArchivedSaveDeletion(packageID: game.id, store: store)
        try library.deleteArchivedSave(refreshed, store: store)
        XCTAssertFalse(FileManager.default.fileExists(atPath: directory.path))
    }

    func testInstalledAndBusyLibraryRejectPreviewAndStaleCommit() throws {
        let token = try library.prepareArchivedSaveDeletion(packageID: game.id, store: store)
        let before = try inventory()
        library.packages = [game]
        XCTAssertThrowsError(try library.prepareArchivedSaveDeletion(packageID: game.id, store: store))
        XCTAssertThrowsError(try library.deleteArchivedSave(token, store: store))
        library.packages = []; library.busy = true
        XCTAssertThrowsError(try library.deleteArchivedSave(token, store: store))
        XCTAssertEqual(try inventory(), before)
        XCTAssertThrowsError(try store.deleteArchived(token, installedPackageIDs: [game.id]))
    }

    func testUnreadableInstalledOrUnfinishedPackageCannotMasqueradeAsArchive() throws {
        let token = try library.prepareArchivedSaveDeletion(packageID: game.id, store: store)
        for name in [game.id.uuidString, ".removing-" + game.id.uuidString] {
            let path = library.root.appendingPathComponent(name)
            try FileManager.default.createDirectory(at: path, withIntermediateDirectories: false)
            XCTAssertTrue(library.packages.isEmpty)
            XCTAssertThrowsError(try library.deleteArchivedSave(token, store: store))
            try FileManager.default.removeItem(at: path)
        }
        XCTAssertEqual(try inventory().count, 2)
    }

    func testLinkedRootAndLinkInsertedAfterPreviewAreRejected() throws {
        var token = try library.prepareArchivedSaveDeletion(packageID: game.id, store: store)
        let current = directory.appendingPathComponent("current.json")
        let outside = temporary.appendingPathComponent("outside-current.json")
        try FileManager.default.moveItem(at: current, to: outside)
        try FileManager.default.createSymbolicLink(at: current, withDestinationURL: outside)
        let bytes = try Data(contentsOf: outside)
        XCTAssertThrowsError(try library.deleteArchivedSave(token, store: store))
        XCTAssertEqual(try Data(contentsOf: outside), bytes)
        try FileManager.default.removeItem(at: current)
        try FileManager.default.moveItem(at: outside, to: current)
        token = try library.prepareArchivedSaveDeletion(packageID: game.id, store: store)
        let displaced = temporary.appendingPathComponent("displaced-save-root")
        try FileManager.default.moveItem(at: store.root, to: displaced)
        try FileManager.default.createSymbolicLink(at: store.root, withDestinationURL: displaced)
        XCTAssertThrowsError(try library.deleteArchivedSave(token, store: store))
        XCTAssertTrue(FileManager.default.fileExists(atPath: displaced.appendingPathComponent(game.id.uuidString).appendingPathComponent("current.json").path))
    }

    func testAggregateVerificationBudgetRefusesLargeGroupsWithoutDeleting() throws {
        for _ in 0..<5 {
            let url = directory.appendingPathComponent(UUID().uuidString + ".json")
            XCTAssertTrue(FileManager.default.createFile(atPath: url.path, contents: nil))
            let handle = try FileHandle(forWritingTo: url)
            try handle.truncate(atOffset: UInt64(SaveStore.maximumArchiveBytes))
            try handle.close()
        }
        XCTAssertThrowsError(try library.prepareArchivedSaveDeletion(packageID: game.id, store: store))
        XCTAssertEqual(try FileManager.default.contentsOfDirectory(atPath: directory.path).count, 7)
    }

    func testFailureAfterFirstUnlinkReportsPartialAndRefreshShowsRemainingFiles() throws {
        let other = GamePackage(id: UUID(), title: "Untouched other game", importedAt: Date(), movies: ["main.swf"], selectedMovie: "main.swf")
        _ = try store.persistLatest(SaveCapture(version: 1, entries: []), package: other)
        let otherFile = store.root.appendingPathComponent(other.id.uuidString).appendingPathComponent("current.json")
        let outside = temporary.appendingPathComponent("outside-original.txt")
        try Data("outside original".utf8).write(to: outside)
        let otherBytes = try Data(contentsOf: otherFile), outsideBytes = try Data(contentsOf: outside)
        let token = try library.prepareArchivedSaveDeletion(packageID: game.id, store: store)
        let before = try inventory()
        var calls = 0
        XCTAssertThrowsError(try store.deleteArchived(token, installedPackageIDs: [], removeEntry: { fd, name, flags in
            calls += 1
            if calls == 2 { return -1 }
            return unlinkat(fd, name, flags)
        })) { error in
            guard case ArchivedSaveDeletionError.partial(let removed) = error else { return XCTFail("Must report partial deletion, not preserved-all: \(error)") }
            XCTAssertEqual(removed, 1)
        }
        XCTAssertEqual(calls, 2)
        let remaining = try inventory()
        XCTAssertEqual(remaining.count, before.count - 1)
        for (name, bytes) in remaining { XCTAssertEqual(bytes, before[name]) }
        let refreshed = try library.prepareArchivedSaveDeletion(packageID: game.id, store: store)
        XCTAssertEqual(refreshed.fileCount, 1)
        XCTAssertEqual(refreshed.totalBytes, remaining.values.reduce(0) { $0 + $1.count })
        XCTAssertThrowsError(try library.deleteArchivedSave(token, store: store), "Old confirmation cannot authorize retry")
        XCTAssertEqual(try inventory(), remaining)
        XCTAssertEqual(try Data(contentsOf: otherFile), otherBytes)
        XCTAssertEqual(try Data(contentsOf: outside), outsideBytes)
    }

    func testRmdirFailureReportsAllFilesDeletedButEmptyFolderRemains() throws {
        let other = GamePackage(id: UUID(), title: "Untouched other game", importedAt: Date(), movies: ["main.swf"], selectedMovie: "main.swf")
        _ = try store.persistLatest(SaveCapture(version: 1, entries: []), package: other)
        let otherFile = store.root.appendingPathComponent(other.id.uuidString).appendingPathComponent("current.json")
        let outside = temporary.appendingPathComponent("outside-original.txt")
        try Data("outside original".utf8).write(to: outside)
        let otherBytes = try Data(contentsOf: otherFile), outsideBytes = try Data(contentsOf: outside)
        let token = try library.prepareArchivedSaveDeletion(packageID: game.id, store: store)
        var leafCalls = 0, directoryCalls = 0
        XCTAssertThrowsError(try store.deleteArchived(token, installedPackageIDs: [], removeEntry: { fd, name, flags in
            if flags == AT_REMOVEDIR { directoryCalls += 1; return -1 }
            leafCalls += 1
            return unlinkat(fd, name, flags)
        })) { error in
            guard case ArchivedSaveDeletionError.partial(let removed) = error else { return XCTFail("Must report deleted files even if folder removal failed: \(error)") }
            XCTAssertEqual(removed, token.fileCount)
        }
        XCTAssertEqual(leafCalls, token.fileCount); XCTAssertEqual(directoryCalls, 1)
        XCTAssertTrue(FileManager.default.fileExists(atPath: directory.path))
        XCTAssertTrue(try inventory().isEmpty)
        let refreshed = try library.prepareArchivedSaveDeletion(packageID: game.id, store: store)
        XCTAssertEqual(refreshed.fileCount, 0); XCTAssertEqual(refreshed.totalBytes, 0)
        XCTAssertFalse(try store.savedPackages().contains { $0.id == game.id }, "Refresh must not invent remaining saves")
        XCTAssertEqual(try Data(contentsOf: otherFile), otherBytes)
        XCTAssertEqual(try Data(contentsOf: outside), outsideBytes)
    }

    private func inventory() throws -> [String: Data] {
        try Dictionary(uniqueKeysWithValues: FileManager.default.contentsOfDirectory(at: directory, includingPropertiesForKeys: nil).map {
            ($0.lastPathComponent, try Data(contentsOf: $0))
        })
    }
}

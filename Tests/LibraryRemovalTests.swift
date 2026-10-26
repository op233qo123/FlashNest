import XCTest
@testable import FlashNest

/// All mutations are confined to synthetic temporary directories. Native-save/cache preparation
/// is injected, so these tests never touch an installed game's data profile.
@MainActor final class LibraryRemovalTests: XCTestCase {
    private struct Fixture {
        let directory: URL
        let root: URL
        let source: URL
        let package: GamePackage
        var folder: URL { root.appendingPathComponent(package.id.uuidString) }
        var staged: URL { root.appendingPathComponent(".removing-" + package.id.uuidString) }
    }

    private func fixture() throws -> Fixture {
        let fm = FileManager.default
        let directory = fm.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        let root = directory.appendingPathComponent("Application Support/Packages")
        let source = directory.appendingPathComponent("Original import source")
        try fm.createDirectory(at: source.appendingPathComponent("assets/nested"), withIntermediateDirectories: true)
        try Data("FWSsynthetic game".utf8).write(to: source.appendingPathComponent("main.swf"))
        try Data("original asset".utf8).write(to: source.appendingPathComponent("assets/nested/data.txt"))
        let package = try PackageImporter(root: root).stageAndCommit(source)
        return Fixture(directory: directory, root: root, source: source, package: package)
    }

    func testRemovalDeletesEntireCopiedFolderButPreservesSourceSiblingAndSaves() async throws {
        let fixture = try fixture()
        defer { try? FileManager.default.removeItem(at: fixture.directory) }
        let sibling = try PackageImporter(root: fixture.root).stageAndCommit(fixture.source)
        let save = fixture.directory.appendingPathComponent("Documents/save/\(fixture.package.id.uuidString)/snapshot.json")
        try FileManager.default.createDirectory(at: save.deletingLastPathComponent(), withIntermediateDirectories: true)
        let saveBytes = Data("durable save must remain byte-for-byte".utf8)
        try saveBytes.write(to: save)
        var cleared: [UUID] = []
        let library = LibraryStore(root: fixture.root, prepareRemoval: { cleared.append($0.id) })

        let removed = await library.remove(fixture.package)

        XCTAssertTrue(removed)
        XCTAssertEqual(cleared, [fixture.package.id])
        XCTAssertFalse(FileManager.default.fileExists(atPath: fixture.folder.path))
        XCTAssertFalse(FileManager.default.fileExists(atPath: fixture.staged.path))
        XCTAssertEqual(library.packages.map(\.id), [sibling.id])
        XCTAssertEqual(try Data(contentsOf: save), saveBytes)
        XCTAssertEqual(try Data(contentsOf: fixture.source.appendingPathComponent("main.swf")), Data("FWSsynthetic game".utf8))
        XCTAssertEqual(try Data(contentsOf: fixture.source.appendingPathComponent("assets/nested/data.txt")), Data("original asset".utf8))
        XCTAssertTrue(FileManager.default.fileExists(atPath: fixture.root.appendingPathComponent(sibling.id.uuidString + "/manifest.json").path))
        XCTAssertNotNil(library.deletionMessage)
        XCTAssertNil(library.deletingPackageID)
    }

    func testLegacySavePreparationRunsBeforeRemovalAndItsArchiveRemainsAccessible() async throws {
        let fixture = try fixture()
        defer { try? FileManager.default.removeItem(at: fixture.directory) }
        let saveRoot = fixture.directory.appendingPathComponent("Documents/save")
        let saveStore = SaveStore(root: saveRoot)
        var sol = Data(repeating: 0, count: 24)
        sol[1] = 0xbf
        sol.replaceSubrange(6..<10, with: "TCSO".utf8)
        sol[11] = 4
        let capture = SaveCapture(version: 1, entries: [SaveEntry(scope: "origin", key: "Progress", value: sol.base64EncodedString())])
        var preparedID: UUID?
        let library = LibraryStore(root: fixture.root, prepareRemoval: { verified in
            XCTAssertTrue(FileManager.default.fileExists(atPath: fixture.folder.appendingPathComponent("manifest.json").path))
            XCTAssertFalse(FileManager.default.fileExists(atPath: fixture.staged.path))
            XCTAssertEqual(verified, fixture.package)
            preparedID = try saveStore.capture(capture, package: verified, name: "Before game removal").id
        })
        let removed = await library.remove(fixture.package)
        XCTAssertTrue(removed)
        XCTAssertFalse(FileManager.default.fileExists(atPath: fixture.folder.path))
        let saved = try saveStore.list(packageID: fixture.package.id)
        XCTAssertEqual(saved.map(\.id), [try XCTUnwrap(preparedID)])
        XCTAssertEqual(saved.first?.entries.first?.value, capture.entries.first?.value)
        XCTAssertTrue(FileManager.default.fileExists(atPath: fixture.source.path))
    }

    func testSavePreparationFailureNeverStagesOrDeletesCopiedGame() async throws {
        let fixture = try fixture()
        defer { try? FileManager.default.removeItem(at: fixture.directory) }
        let library = LibraryStore(root: fixture.root, prepareRemoval: { _ in
            throw SaveStoreError.invalid("synthetic legacy save capture failed")
        })
        let removed = await library.remove(fixture.package)
        XCTAssertFalse(removed)
        XCTAssertEqual(library.packages, [fixture.package])
        XCTAssertTrue(FileManager.default.fileExists(atPath: fixture.folder.appendingPathComponent("content/main.swf").path))
        XCTAssertTrue(FileManager.default.fileExists(atPath: fixture.folder.appendingPathComponent("manifest.json").path))
        XCTAssertFalse(FileManager.default.fileExists(atPath: fixture.staged.path))
        XCTAssertNil(library.deletionMessage)
        XCTAssertNotNil(library.error)
    }

    func testCacheCleanupFailureKeepsCopyAndDoesNotStageDeletion() async throws {
        let fixture = try fixture()
        defer { try? FileManager.default.removeItem(at: fixture.directory) }
        let manifest = try Data(contentsOf: fixture.folder.appendingPathComponent("manifest.json"))
        let library = LibraryStore(root: fixture.root, prepareRemoval: { _ in throw CocoaError(.fileWriteNoPermission) })
        let removed = await library.remove(fixture.package)
        XCTAssertFalse(removed)
        XCTAssertEqual(try Data(contentsOf: fixture.folder.appendingPathComponent("manifest.json")), manifest)
        XCTAssertTrue(FileManager.default.fileExists(atPath: fixture.folder.appendingPathComponent("content/assets/nested/data.txt").path))
        XCTAssertFalse(FileManager.default.fileExists(atPath: fixture.staged.path))
        XCTAssertEqual(library.packages, [fixture.package])
        XCTAssertNotNil(library.error)
        XCTAssertNil(library.deletionMessage)
    }

    func testRemovalRejectsActivePlayerAndImportBeforeCleaningAnything() async throws {
        let fixture = try fixture()
        defer { try? FileManager.default.removeItem(at: fixture.directory) }
        var cleaned = false
        let library = LibraryStore(root: fixture.root, prepareRemoval: { _ in cleaned = true })
        try library.beginPlayback(fixture.package)
        let playingRemoval = await library.remove(fixture.package)
        XCTAssertFalse(playingRemoval)
        library.endPlayback()
        library.busy = true
        let importingRemoval = await library.remove(fixture.package)
        XCTAssertFalse(importingRemoval)
        XCTAssertFalse(cleaned)
        XCTAssertTrue(FileManager.default.fileExists(atPath: fixture.folder.path))
        library.busy = false
    }

    func testUnknownUUIDCannotDeleteAnUnlistedDirectory() async throws {
        let fixture = try fixture()
        defer { try? FileManager.default.removeItem(at: fixture.directory) }
        var cleaned = false
        let library = LibraryStore(root: fixture.root, prepareRemoval: { _ in cleaned = true })
        let unknown = GamePackage(id: UUID(), title: "../Original import source", importedAt: Date(),
                                  movies: ["/absolute/path"], selectedMovie: "/absolute/path")
        let removed = await library.remove(unknown)
        XCTAssertFalse(removed)
        XCTAssertFalse(cleaned)
        XCTAssertTrue(FileManager.default.fileExists(atPath: fixture.folder.path))
        XCTAssertTrue(FileManager.default.fileExists(atPath: fixture.source.path))
    }

    func testManifestIdentityChangeFailsClosed() async throws {
        let fixture = try fixture()
        defer { try? FileManager.default.removeItem(at: fixture.directory) }
        var cleaned = false
        let library = LibraryStore(root: fixture.root, prepareRemoval: { _ in cleaned = true })
        let wrong = GamePackage(id: UUID(), title: fixture.package.title, importedAt: Date(),
                                movies: ["main.swf"], selectedMovie: "main.swf")
        try JSONEncoder().encode(wrong).write(to: fixture.folder.appendingPathComponent("manifest.json"))
        let removed = await library.remove(fixture.package)
        XCTAssertFalse(removed)
        XCTAssertFalse(cleaned)
        XCTAssertTrue(FileManager.default.fileExists(atPath: fixture.folder.appendingPathComponent("content/main.swf").path))
    }

    func testPackageDirectorySymlinkIsRejectedWithoutFollowingTarget() async throws {
        let fixture = try fixture()
        defer { try? FileManager.default.removeItem(at: fixture.directory) }
        let fm = FileManager.default
        var cleaned = false
        let library = LibraryStore(root: fixture.root, prepareRemoval: { _ in cleaned = true })
        let outside = fixture.directory.appendingPathComponent("Outside package")
        try fm.moveItem(at: fixture.folder, to: outside)
        try fm.createSymbolicLink(at: fixture.folder, withDestinationURL: outside)
        let removed = await library.remove(fixture.package)
        XCTAssertFalse(removed)
        XCTAssertFalse(cleaned)
        XCTAssertTrue(fm.fileExists(atPath: outside.appendingPathComponent("content/main.swf").path))
        XCTAssertTrue(try fixture.folder.resourceValues(forKeys: [.isSymbolicLinkKey]).isSymbolicLink == true)
    }

    func testNestedSymlinkFailsClosedEvenIfItPointsInsideThePackage() async throws {
        for outside in [false, true] {
            let fixture = try fixture()
            defer { try? FileManager.default.removeItem(at: fixture.directory) }
            var cleaned = false
            let library = LibraryStore(root: fixture.root, prepareRemoval: { _ in cleaned = true })
            let target = outside ? fixture.source : fixture.folder.appendingPathComponent("content/assets")
            let link = fixture.folder.appendingPathComponent("content/linked-assets")
            try FileManager.default.createSymbolicLink(at: link, withDestinationURL: target)
            let removed = await library.remove(fixture.package)
            XCTAssertFalse(removed)
            XCTAssertFalse(cleaned)
            XCTAssertTrue(FileManager.default.fileExists(atPath: fixture.folder.appendingPathComponent("manifest.json").path))
            XCTAssertTrue(FileManager.default.fileExists(atPath: target.path))
        }
    }

    func testManifestAndContentSymlinksAreNotLoadedOrRepaired() throws {
        for name in ["manifest.json", "content"] {
            let fixture = try fixture()
            defer { try? FileManager.default.removeItem(at: fixture.directory) }
            let original = fixture.folder.appendingPathComponent(name)
            let outside = fixture.directory.appendingPathComponent("outside-" + name)
            try FileManager.default.moveItem(at: original, to: outside)
            try FileManager.default.createSymbolicLink(at: original, withDestinationURL: outside)
            let library = LibraryStore(root: fixture.root, prepareRemoval: { _ in XCTFail("No cleanup expected") })
            XCTAssertTrue(library.packages.isEmpty)
            XCTAssertNotNil(library.error)
            XCTAssertTrue(FileManager.default.fileExists(atPath: outside.path))
        }
    }

    func testRootSymlinkAndRootReplacementFailClosed() async throws {
        let fixture = try fixture()
        defer { try? FileManager.default.removeItem(at: fixture.directory) }
        var cleaned = false
        let library = LibraryStore(root: fixture.root, prepareRemoval: { _ in cleaned = true })
        let outside = fixture.directory.appendingPathComponent("Elsewhere")
        try FileManager.default.moveItem(at: fixture.root, to: outside)
        try FileManager.default.createSymbolicLink(at: fixture.root, withDestinationURL: outside)
        let removed = await library.remove(fixture.package)
        XCTAssertFalse(removed)
        XCTAssertFalse(cleaned)
        XCTAssertTrue(FileManager.default.fileExists(atPath: outside.appendingPathComponent(fixture.package.id.uuidString + "/manifest.json").path))
        let reopened = LibraryStore(root: fixture.root, prepareRemoval: { _ in XCTFail("No cleanup expected") })
        XCTAssertTrue(reopened.packages.isEmpty)
        XCTAssertNotNil(reopened.error)
    }

    func testPostAwaitSymlinkChangeIsRevalidatedBeforeDeletingFiles() async throws {
        let fixture = try fixture()
        defer { try? FileManager.default.removeItem(at: fixture.directory) }
        let library = LibraryStore(root: fixture.root, prepareRemoval: { _ in
            try FileManager.default.createSymbolicLink(at: fixture.folder.appendingPathComponent("content/new-link"),
                                                      withDestinationURL: fixture.source)
        })
        let removed = await library.remove(fixture.package)
        XCTAssertFalse(removed)
        XCTAssertTrue(FileManager.default.fileExists(atPath: fixture.folder.appendingPathComponent("manifest.json").path))
        XCTAssertTrue(FileManager.default.fileExists(atPath: fixture.source.appendingPathComponent("main.swf").path))
        XCTAssertNil(library.deletionMessage)
    }

    func testInterruptedRemovalIsDiscoverableAndOnlyDeletedOnExplicitRetry() async throws {
        let fixture = try fixture()
        defer { try? FileManager.default.removeItem(at: fixture.directory) }
        try FileManager.default.moveItem(at: fixture.folder, to: fixture.staged)
        // Model a crash after some game data was already removed. Manifest stays.
        try FileManager.default.removeItem(at: fixture.staged.appendingPathComponent("content"))
        var cleaned: [UUID] = []
        let library = LibraryStore(root: fixture.root, prepareRemoval: { cleaned.append($0.id) })
        XCTAssertTrue(library.packages.isEmpty)
        XCTAssertEqual(library.unfinishedRemovals, [fixture.package])
        XCTAssertTrue(FileManager.default.fileExists(atPath: fixture.staged.path))
        XCTAssertTrue(cleaned.isEmpty)
        let removed = await library.remove(fixture.package)
        XCTAssertTrue(removed)
        XCTAssertEqual(cleaned, [fixture.package.id])
        XCTAssertTrue(library.unfinishedRemovals.isEmpty)
        XCTAssertFalse(FileManager.default.fileExists(atPath: fixture.staged.path))
    }

    func testStagingCollisionIncludingDanglingSymlinkBlocksBeforeCacheCleanup() async throws {
        for dangling in [false, true] {
            let fixture = try fixture()
            defer { try? FileManager.default.removeItem(at: fixture.directory) }
            var cleaned = false
            let library = LibraryStore(root: fixture.root, prepareRemoval: { _ in cleaned = true })
            if dangling {
                try FileManager.default.createSymbolicLink(at: fixture.staged,
                    withDestinationURL: fixture.directory.appendingPathComponent("missing-target"))
            } else {
                try FileManager.default.copyItem(at: fixture.folder, to: fixture.staged)
            }
            let removed = await library.remove(fixture.package)
            XCTAssertFalse(removed)
            XCTAssertFalse(cleaned)
            XCTAssertTrue(FileManager.default.fileExists(atPath: fixture.folder.appendingPathComponent("content/main.swf").path))
        }
    }

    func testRemovalLocksPlaybackImportAndConcurrentRemovalDuringCacheAwait() async throws {
        let fixture = try fixture()
        defer { try? FileManager.default.removeItem(at: fixture.directory) }
        let entered = expectation(description: "Entered cache cleanup")
        var resume: CheckedContinuation<Void, Never>?
        let library = LibraryStore(root: fixture.root, prepareRemoval: { _ in
            await withCheckedContinuation { continuation in
                resume = continuation
                entered.fulfill()
            }
        })
        let first = Task { await library.remove(fixture.package) }
        await fulfillment(of: [entered], timeout: 5)
        XCTAssertEqual(library.deletingPackageID, fixture.package.id)
        XCTAssertThrowsError(try library.beginPlayback(fixture.package))
        let imported = await library.importURLs([fixture.source])
        XCTAssertNil(imported)
        let concurrent = await library.remove(fixture.package)
        XCTAssertFalse(concurrent)
        resume?.resume()
        let removed = await first.value
        XCTAssertTrue(removed)
        XCTAssertNil(library.deletingPackageID)
    }
}

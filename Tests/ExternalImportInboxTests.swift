import XCTest
import ZIPFoundation
import UniformTypeIdentifiers
@testable import FlashNest

@MainActor final class ExternalImportInboxTests: XCTestCase {
    func testColdThenWarmURLsRemainQueuedUntilLibraryIsAvailable() throws {
        let inbox = ExternalImportInbox()
        let cold = URL(fileURLWithPath: "/provider/游戏.zip")
        let warm = URL(fileURLWithPath: "/provider/folder.with.dots")
        XCTAssertTrue(inbox.receive(cold))
        XCTAssertTrue(inbox.receive(warm))
        let first = try XCTUnwrap(inbox.pending.first)
        XCTAssertNil(inbox.begin(first.id, allowed: false), "Active playback/modal/import must not be interrupted")
        XCTAssertEqual(inbox.pending.count, 2)
        let request = try XCTUnwrap(inbox.begin(first.id, allowed: true))
        XCTAssertEqual(request.selection.urls, [cold], "Keep original granted URL, not a reconstructed path")
        XCTAssertNil(inbox.begin(inbox.pending[0].id, allowed: true))
        inbox.finish(request.id)
        XCTAssertNotNil(inbox.begin(inbox.pending[0].id, allowed: true))
    }

    func testDuplicateActiveAndPendingURLsDoNotImportTwiceAndCanBeResharedAfterFinish() throws {
        let inbox = ExternalImportInbox()
        let url = URL(fileURLWithPath: "/provider/main.swf")
        XCTAssertTrue(inbox.receive(url)); XCTAssertFalse(inbox.receive(url))
        let request = try XCTUnwrap(inbox.begin(inbox.pending[0].id, allowed: true))
        XCTAssertFalse(inbox.receive(url))
        inbox.finish(UUID())
        XCTAssertNotNil(inbox.active)
        inbox.finish(request.id)
        XCTAssertTrue(inbox.receive(url))
    }

    func testDismissAndOverflowAreBoundedAndNeverDeleteSource() throws {
        let url = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString + ".zip")
        try Data("original".utf8).write(to: url)
        defer { try? FileManager.default.removeItem(at: url) }
        let inbox = ExternalImportInbox(capacity: 1)
        XCTAssertTrue(inbox.receive(url))
        XCTAssertFalse(inbox.receive(url.appendingPathExtension("another")))
        XCTAssertNotNil(inbox.notice)
        inbox.dismiss(inbox.pending[0].id)
        XCTAssertTrue(inbox.pending.isEmpty)
        XCTAssertEqual(try Data(contentsOf: url), Data("original".utf8))
        XCTAssertTrue(inbox.receive(url))
    }

    func testBundleDeclaresOnlySupportedOpenInDocumentKinds() throws {
        let documents = try XCTUnwrap(Bundle.main.object(forInfoDictionaryKey: "CFBundleDocumentTypes") as? [[String: Any]])
        let kinds = Set(documents.flatMap { $0["LSItemContentTypes"] as? [String] ?? [] })
        XCTAssertEqual(kinds, Set([UTType.zip.identifier, UTType.folder.identifier, "com.adobe.flash"]))
        XCTAssertEqual(UTType(filenameExtension: "swf")?.identifier, "com.adobe.flash")
    }

    func testRemoteURLDoesNotAcquireARequest() {
        let inbox = ExternalImportInbox()
        XCTAssertFalse(inbox.receive(URL(string: "https://example.invalid/game.zip")!))
        XCTAssertTrue(inbox.pending.isEmpty)
        XCTAssertNotNil(inbox.notice)
    }
}

final class ExternalImportCopyTests: XCTestCase {
    func testCoordinatedNestedZIPPreservesUnicodeAssetsAndSource() throws {
        let temporary = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: temporary, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: temporary) }
        let zip = temporary.appendingPathComponent("游戏.ZIP")
        let archive = try Archive(url: zip, accessMode: .create)
        let inventory = ["folder/main.swf": Data("FWSmain".utf8), "folder/sub/子.swf": Data("FWSchild".utf8), "folder/sub/config.xml": Data("asset".utf8)]
        for (path, bytes) in inventory {
            try archive.addEntry(with: path, type: .file, uncompressedSize: Int64(bytes.count)) { position, size in
                bytes.subdata(in: Int(position)..<min(Int(position) + size, bytes.count))
            }
        }
        let original = try Data(contentsOf: zip)
        let root = temporary.appendingPathComponent("Packages")
        let package = try PackageImporter(root: root).importPackage(from: zip)
        XCTAssertEqual(package.movies.count, 2)
        for (path, bytes) in inventory {
            XCTAssertEqual(try Data(contentsOf: root.appendingPathComponent(package.id.uuidString).appendingPathComponent("content").appendingPathComponent(path)), bytes)
        }
        XCTAssertEqual(try Data(contentsOf: zip), original)
    }

    func testMissingProviderItemFailsWithoutCommit() throws {
        let temporary = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: temporary) }
        let root = temporary.appendingPathComponent("Packages")
        XCTAssertThrowsError(try PackageImporter(root: root).importPackage(from: temporary.appendingPathComponent("missing.zip")))
        if FileManager.default.fileExists(atPath: root.path) {
            XCTAssertEqual(try FileManager.default.contentsOfDirectory(atPath: root.path), [], "No committed package or staging residue")
        }
    }

    func testCoordinatedFolderImportCopiesNestedAssetsAndPreservesOriginal() throws {
        let temporary = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: temporary) }
        let source = temporary.appendingPathComponent("共享 游戏")
        let nested = source.appendingPathComponent("sub/场景")
        try FileManager.default.createDirectory(at: nested, withIntermediateDirectories: true)
        try Data("FWSfixture".utf8).write(to: source.appendingPathComponent("main.swf"))
        try Data("FWSchild".utf8).write(to: nested.appendingPathComponent("child.swf"))
        try Data([1, 2, 3]).write(to: nested.appendingPathComponent("asset.bin"))
        let root = temporary.appendingPathComponent("Packages")
        let result = try PackageImporter(root: root).importPackage(from: source)
        XCTAssertEqual(result.movies, ["main.swf", "sub/场景/child.swf"])
        let copy = root.appendingPathComponent(result.id.uuidString).appendingPathComponent("content/sub/场景/asset.bin")
        XCTAssertEqual(try Data(contentsOf: copy), try Data(contentsOf: nested.appendingPathComponent("asset.bin")))
        XCTAssertTrue(FileManager.default.fileExists(atPath: source.appendingPathComponent("main.swf").path))
    }
}

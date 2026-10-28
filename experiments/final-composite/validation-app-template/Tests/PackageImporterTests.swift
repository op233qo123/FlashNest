import XCTest
import ZIPFoundation
@testable import FlashNest

final class PackageImporterTests: XCTestCase {
    var temporary: URL!
    var source: URL!
    var root: URL!
    override func setUpWithError() throws {
        temporary = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        source = temporary.appendingPathComponent("source")
        root = temporary.appendingPathComponent("Packages")
        try FileManager.default.createDirectory(at: source, withIntermediateDirectories: true)
    }
    override func tearDownWithError() throws { try FileManager.default.removeItem(at: temporary) }

    func testNestedUnicodeFolderPreservesAssetsAndManifest() throws {
        let nested = source.appendingPathComponent("游戏 资源")
        try FileManager.default.createDirectory(at: nested, withIntermediateDirectories: true)
        try Data("FWS\u{09}test".utf8).write(to: nested.appendingPathComponent("入口.swf"))
        try Data("asset".utf8).write(to: nested.appendingPathComponent("image.dat"))
        let package = try PackageImporter(root: root).stageAndCommit(source)
        XCTAssertEqual(package.movies, ["游戏 资源/入口.swf"])
        let committed = root.appendingPathComponent(package.id.uuidString)
        XCTAssertEqual(try Data(contentsOf: committed.appendingPathComponent("content/游戏 资源/image.dat")), Data("asset".utf8))
        let decoded = try JSONDecoder().decode(GamePackage.self, from: Data(contentsOf: committed.appendingPathComponent("manifest.json")))
        XCTAssertEqual(decoded.id, package.id)
        XCTAssertTrue(FileManager.default.fileExists(atPath: nested.appendingPathComponent("入口.swf").path))
    }

    func testMissingMovieRollsBack() throws {
        try Data("not a game".utf8).write(to: source.appendingPathComponent("readme.txt"))
        XCTAssertThrowsError(try PackageImporter(root: root).stageAndCommit(source))
        XCTAssertEqual(try FileManager.default.contentsOfDirectory(atPath: root.path), [])
    }

    func testSymlinkRollsBack() throws {
        try FileManager.default.createSymbolicLink(at: source.appendingPathComponent("escape"), withDestinationURL: temporary)
        XCTAssertThrowsError(try PackageImporter(root: root).stageAndCommit(source))
        XCTAssertEqual(try FileManager.default.contentsOfDirectory(atPath: root.path), [])
    }

    func testByteLimitRollsBack() throws {
        try Data("FWSxxxxxxxxx".utf8).write(to: source.appendingPathComponent("main.swf"))
        var importer = PackageImporter(root: root)
        importer.limits.fileBytes = 5
        XCTAssertThrowsError(try importer.stageAndCommit(source))
        XCTAssertEqual(try FileManager.default.contentsOfDirectory(atPath: root.path), [])
    }

    func testTraversalAndCaseCollisionsAreRejected() throws {
        for path in ["../evil.swf", "/evil.swf", "C:/evil", "a\\evil", "a//b", "a/./b"] {
            var registry = ImportPathRegistry()
            XCTAssertThrowsError(try registry.register(path, limits: ImportLimits()), path)
        }
        var registry = ImportPathRegistry()
        _ = try registry.register("Images/a.jpg", limits: ImportLimits())
        XCTAssertThrowsError(try registry.register("images/b.jpg", limits: ImportLimits()))
    }

    func testZIPTraversalRollsBack() throws {
        let zip = temporary.appendingPathComponent("unsafe.zip")
        let archive = try Archive(url: zip, accessMode: .create)
        let data = Data("FWSbad".utf8)
        try archive.addEntry(with: "../escape.swf", type: .file, uncompressedSize: Int64(data.count)) { position, size in
            data.subdata(in: Int(position)..<Int(position) + size)
        }
        XCTAssertThrowsError(try PackageImporter(root: root).stageAndCommit(zip))
        XCTAssertEqual(try FileManager.default.contentsOfDirectory(atPath: root.path), [])
        XCTAssertFalse(FileManager.default.fileExists(atPath: temporary.appendingPathComponent("escape.swf").path))
    }

    func testMalformedLaterZIPHeaderCannotCommitPartialGame() throws {
        let zip = temporary.appendingPathComponent("truncated-entry.zip")
        let archive = try Archive(url: zip, accessMode: .create)
        for (name, bytes) in [("main.swf", Data("FWSfixture".utf8)), ("required.xml", Data("<asset/>".utf8))] {
            try archive.addEntry(with: name, type: .file, uncompressedSize: Int64(bytes.count)) { position, size in
                bytes.subdata(in: Int(position)..<Int(position) + size)
            }
        }
        var bytes = try Data(contentsOf: zip)
        let localSignature = Data([0x50, 0x4b, 0x03, 0x04])
        let second = try XCTUnwrap(bytes.range(of: localSignature, in: 4..<bytes.count))
        bytes[second.lowerBound] = 0 // First valid SWF remains intact; second entry becomes unreadable.
        try bytes.write(to: zip)
        XCTAssertEqual(try ZIPIntegrity.expectedEntryCount(at: zip, maximumEntries: 100), 2)
        XCTAssertThrowsError(try PackageImporter(root: root).stageAndCommit(zip))
        XCTAssertEqual(try FileManager.default.contentsOfDirectory(atPath: root.path), [])
    }

    func testZIPDirectoryCountMismatchRejected() throws {
        let zip = temporary.appendingPathComponent("bad-count.zip")
        let archive = try Archive(url: zip, accessMode: .create)
        let data = Data("FWSfixture".utf8)
        try archive.addEntry(with: "main.swf", type: .file, uncompressedSize: Int64(data.count)) { position, size in
            data.subdata(in: Int(position)..<Int(position) + size)
        }
        var bytes = try Data(contentsOf: zip)
        let end = bytes.count - 22
        bytes[end + 8] = 2; bytes[end + 10] = 2
        try bytes.write(to: zip)
        XCTAssertThrowsError(try ZIPIntegrity.expectedEntryCount(at: zip, maximumEntries: 100))
        XCTAssertThrowsError(try PackageImporter(root: root).stageAndCommit(zip))
        XCTAssertEqual(try FileManager.default.contentsOfDirectory(atPath: root.path), [])
    }

    func testZIPRoundtripAndCRC() throws {
        let zip = temporary.appendingPathComponent("game.zip")
        let archive = try Archive(url: zip, accessMode: .create)
        let data = Data("FWS\u{09}fixture".utf8)
        try archive.addEntry(with: "nested/main.swf", type: .file, uncompressedSize: Int64(data.count), compressionMethod: .deflate) { position, size in
            data.subdata(in: Int(position)..<Int(position) + size)
        }
        let package = try PackageImporter(root: root).stageAndCommit(zip)
        XCTAssertEqual(package.selectedMovie, "nested/main.swf")
    }
}

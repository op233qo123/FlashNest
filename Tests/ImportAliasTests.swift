import XCTest
@testable import FlashNest

final class ImportAliasTests: XCTestCase {
    func testCanonicalAndAliasRootsProduceIdenticalRelativeInventory() throws {
        let fm = FileManager.default
        let temporary = fm.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? fm.removeItem(at: temporary) }
        let real = temporary.appendingPathComponent("real-container")
        let alias = temporary.appendingPathComponent("alias")
        let source = real.appendingPathComponent("source")
        try fm.createDirectory(at: source.appendingPathComponent("content"), withIntermediateDirectories: true)
        try Data("FWSroot".utf8).write(to: source.appendingPathComponent("入口.swf"))
        try Data("FWSnested".utf8).write(to: source.appendingPathComponent("content/本物.swf"))
        try fm.createSymbolicLink(at: alias, withDestinationURL: real)
        let aliasedSource = alias.appendingPathComponent("source")
        let canonicalFile = source.appendingPathComponent("入口.swf").resolvingSymlinksInPath()
        XCTAssertEqual(try PackageImporter.relativePath(of: canonicalFile, under: aliasedSource), "入口.swf")
        XCTAssertEqual(try PackageImporter.relativePath(of: aliasedSource.appendingPathComponent("content/本物.swf"), under: source), "content/本物.swf")
        let sibling = real.appendingPathComponent("source-other/escape.swf")
        XCTAssertThrowsError(try PackageImporter.relativePath(of: sibling, under: source))
        // Alias is an ancestor of the selected folder, not an imported symlink.
        let library = alias.appendingPathComponent("library")
        let package = try PackageImporter(root: library).stageAndCommit(aliasedSource)
        XCTAssertEqual(Set(package.movies), Set(["入口.swf", "content/本物.swf"]))
        let content = library.appendingPathComponent(package.id.uuidString).appendingPathComponent("content")
        for movie in package.movies {
            XCTAssertEqual(try Data(contentsOf: content.appendingPathComponent(movie)),
                           try Data(contentsOf: source.appendingPathComponent(movie)))
        }
        XCTAssertEqual(Set(try PackageImporter(root: library).discoverMovies(content)), Set(package.movies))
    }

    func testImportedSymlinkStillRejectedThroughRootAlias() throws {
        let fm = FileManager.default
        let temporary = fm.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? fm.removeItem(at: temporary) }
        let real = temporary.appendingPathComponent("real")
        let alias = temporary.appendingPathComponent("alias")
        let source = real.appendingPathComponent("source")
        try fm.createDirectory(at: source, withIntermediateDirectories: true)
        try Data("FWSroot".utf8).write(to: source.appendingPathComponent("main.swf"))
        try fm.createSymbolicLink(at: alias, withDestinationURL: real)
        try fm.createSymbolicLink(at: source.appendingPathComponent("linked.swf"), withDestinationURL: source.appendingPathComponent("main.swf"))
        XCTAssertThrowsError(try PackageImporter(root: alias.appendingPathComponent("library"))
            .stageAndCommit(alias.appendingPathComponent("source")))
    }

    func testEightCharacterAliasMismatchExplainsOldContentArtifact() {
        let root = "/var/mobile/Packages/.import-ID/content"
        let enumerated = "/private" + root + "/入口.swf"
        XCTAssertEqual(String(enumerated.dropFirst((root + "/").count)), "content/入口.swf")
        // This is a deterministic reproduction of the old arithmetic, not an
        // assertion about the URL spelling returned by every simulator/device.
    }
}

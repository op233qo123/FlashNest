import XCTest
@testable import FlashNest

final class LocalImportInboxTests: XCTestCase {
    private var temporary: URL!
    override func setUpWithError() throws {
        temporary = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: temporary, withIntermediateDirectories: true)
    }
    override func tearDownWithError() throws { try FileManager.default.removeItem(at: temporary) }

    func testPreparationCreatesInstructionsAndNeverOverwritesExistingFile() throws {
        let inbox = LocalImportInbox(root: temporary.appendingPathComponent("Import"))
        try inbox.prepare()
        let readme = inbox.root.appendingPathComponent("README-IMPORT.txt")
        XCTAssertTrue(FileManager.default.fileExists(atPath: readme.path))
        XCTAssertTrue(try inbox.list().isEmpty)
        let userData = Data("User-owned instructions must survive".utf8)
        try userData.write(to: readme)
        try inbox.prepare()
        XCTAssertEqual(try Data(contentsOf: readme), userData)
    }

    func testListsOnlySupportedTopLevelItemsWithoutFollowingLinks() throws {
        let inbox = LocalImportInbox(root: temporary.appendingPathComponent("Import"))
        try inbox.prepare()
        let nested = inbox.root.appendingPathComponent("游戏/sub/level2")
        try FileManager.default.createDirectory(at: nested, withIntermediateDirectories: true)
        try Data("FWSnested".utf8).write(to: nested.appendingPathComponent("child.swf"))
        for name in ["archive.ZIP", "movie.swf", "notes.txt", ".hidden.swf"] {
            try Data("fixture".utf8).write(to: inbox.root.appendingPathComponent(name))
        }
        let outside = temporary.appendingPathComponent("outside")
        try FileManager.default.createDirectory(at: outside, withIntermediateDirectories: true)
        try FileManager.default.createSymbolicLink(at: inbox.root.appendingPathComponent("linked-folder"), withDestinationURL: outside)
        try FileManager.default.createSymbolicLink(at: inbox.root.appendingPathComponent("linked.swf"), withDestinationURL: nested.appendingPathComponent("child.swf"))
        let entries = try inbox.list()
        XCTAssertEqual(Set(entries.map(\.name)), Set(["游戏", "archive.ZIP", "movie.swf"]))
        XCTAssertTrue(try XCTUnwrap(entries.first { $0.name == "游戏" }).isDirectory)
        XCTAssertFalse(entries.contains { $0.name == "child.swf" })
    }

    func testSymlinkInboxRootIsRejectedWithoutWritingThroughIt() throws {
        let outside = temporary.appendingPathComponent("outside")
        try FileManager.default.createDirectory(at: outside, withIntermediateDirectories: true)
        let root = temporary.appendingPathComponent("Import")
        try FileManager.default.createSymbolicLink(at: root, withDestinationURL: outside)
        XCTAssertThrowsError(try LocalImportInbox(root: root).prepare())
        XCTAssertEqual(try FileManager.default.contentsOfDirectory(atPath: outside.path), [])
    }

    func testTopLevelLimitCountsUnsupportedItemsToo() throws {
        let inbox = LocalImportInbox(root: temporary.appendingPathComponent("Import"), maximumItems: 2)
        try inbox.prepare()
        for name in ["one.txt", "two.txt", ".three.txt"] {
            try Data().write(to: inbox.root.appendingPathComponent(name))
        }
        XCTAssertThrowsError(try inbox.list())
    }

    func testSelectedInboxFolderImportsAllNestedAssetsAndKeepsOriginals() throws {
        let inbox = LocalImportInbox(root: temporary.appendingPathComponent("Import"))
        try inbox.prepare()
        let source = inbox.root.appendingPathComponent("Whole game")
        let files = [
            "main.swf": Data("FWSmain".utf8),
            "sub/a/b/child.swf": Data("FWSchild".utf8),
            "sub/a/b/config.xml": Data("<configuration/>".utf8),
            "sub/images/asset.bin": Data([0, 1, 255])
        ]
        for (path, bytes) in files {
            let file = source.appendingPathComponent(path)
            try FileManager.default.createDirectory(at: file.deletingLastPathComponent(), withIntermediateDirectories: true)
            try bytes.write(to: file)
        }
        let entry = try XCTUnwrap(inbox.list().first)
        let libraryRoot = temporary.appendingPathComponent("Packages")
        let package = try PackageImporter(root: libraryRoot).stageAndCommit(entry.url)
        XCTAssertEqual(Set(package.movies), Set(["main.swf", "sub/a/b/child.swf"]))
        let content = libraryRoot.appendingPathComponent(package.id.uuidString).appendingPathComponent("content")
        for (path, bytes) in files {
            XCTAssertEqual(try Data(contentsOf: content.appendingPathComponent(path)), bytes)
            XCTAssertEqual(try Data(contentsOf: source.appendingPathComponent(path)), bytes)
        }
    }
}

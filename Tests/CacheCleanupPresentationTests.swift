import XCTest
@testable import FlashNest

/// Injected failures only: never clears a real WebKit profile or user package.
@MainActor final class CacheCleanupPresentationTests: XCTestCase {
    func testTypedCleanupFailuresRetainGameAndShowLocalizedFixedCode() async throws {
        let previous = UserDefaults.standard.object(forKey: L10n.preferenceKey)
        let fm = FileManager.default
        let directory = fm.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer {
            try? fm.removeItem(at: directory)
            if let previous { UserDefaults.standard.set(previous, forKey: L10n.preferenceKey) }
            else { UserDefaults.standard.removeObject(forKey: L10n.preferenceKey) }
        }
        let source = directory.appendingPathComponent("Original")
        let root = directory.appendingPathComponent("Packages")
        try fm.createDirectory(at: source, withIntermediateDirectories: true)
        let original = Data("FWSsynthetic cache diagnostic fixture".utf8)
        try original.write(to: source.appendingPathComponent("main.swf"))
        let package = try PackageImporter(root: root).stageAndCommit(source)
        let folder = root.appendingPathComponent(package.id.uuidString)
        let manifest = try Data(contentsOf: folder.appendingPathComponent("manifest.json"))
        let save = directory.appendingPathComponent("Native-save-marker")
        try Data("synthetic save retained".utf8).write(to: save)

        for reason in [CacheCleanupError.Reason.deadline, .active] {
            let failure = CacheCleanupError(reason: reason, elapsedMilliseconds: 12_345, supportedTypeMask: 7)
            L10n.setLanguage("en")
            let library = LibraryStore(root: root, prepareRemoval: { _ in throw failure })
            let removed = await library.remove(package)
            XCTAssertFalse(removed)
            XCTAssertEqual(library.error,
                "Game storage could not be safely cleared. The game copy was kept; saves were not deleted.\nDiagnostic code: " + failure.diagnosticCode)
            XCTAssertEqual(library.packages, [package])
            XCTAssertNil(library.deletionMessage)
            XCTAssertNil(library.deletingPackageID)
            XCTAssertFalse(fm.fileExists(atPath: root.appendingPathComponent(".removing-" + package.id.uuidString).path))
            XCTAssertEqual(try Data(contentsOf: folder.appendingPathComponent("manifest.json")), manifest)
            XCTAssertEqual(try Data(contentsOf: folder.appendingPathComponent("content/main.swf")), original)
            XCTAssertEqual(try Data(contentsOf: source.appendingPathComponent("main.swf")), original)
            XCTAssertEqual(try Data(contentsOf: save), Data("synthetic save retained".utf8))
            L10n.setLanguage("zh-Hans")
            let expected = "无法安全清理游戏缓存。游戏副本和存档均已保留。\n诊断代码：" + failure.diagnosticCode
            XCTAssertEqual(L10n.error(failure), expected)
            XCTAssertFalse(L10n.error(failure).contains("12345"))
            XCTAssertFalse(L10n.error(failure).contains("supportedMask"))
        }
    }
}

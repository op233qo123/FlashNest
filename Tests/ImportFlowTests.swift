import XCTest
import UniformTypeIdentifiers
import UIKit
@testable import FlashNest

final class ImportFlowTests: XCTestCase {
    func testFolderAndFileSelectionUseSeparateContentTypes() {
        XCTAssertEqual(PackagePickerMode.folder.contentTypes, [.folder])
        XCTAssertFalse(PackagePickerMode.files.contentTypes.contains(.folder))
        XCTAssertTrue(PackagePickerMode.files.contentTypes.contains(.zip))
    }

    func testRecursiveFolderInventoryAndLargeMovieArePreserved() throws {
        let temporary = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: temporary) }
        let source = temporary.appendingPathComponent("游戏 folder")
        let root = temporary.appendingPathComponent("Packages")
        let inventory: [String: Data] = [
            "main.swf": Data("FWSlarge".utf8),
            "sub/level 2/第三层/child.swf": Data("FWSchild".utf8),
            "sub/level 2/第三层/config.xml": Data("<fixture/>".utf8),
            "sub/level 2/images/image.bin": Data([0, 1, 2, 255]),
            "sub/audio/sound.dat": Data("audio fixture".utf8),
            "readme.txt": Data("untouched".utf8)
        ]
        for (path, data) in inventory {
            let url = source.appendingPathComponent(path)
            try FileManager.default.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
            try data.write(to: url)
        }
        // Match the reported 43.9 MB class without allocating the entire file.
        let large = source.appendingPathComponent("main.swf")
        let output = try FileHandle(forWritingTo: large)
        try output.seekToEnd()
        let chunk = Data(repeating: 0x35, count: 1_048_576)
        for _ in 0..<44 { try output.write(contentsOf: chunk) }
        try output.close()
        let package = try PackageImporter(root: root).stageAndCommit(source)
        XCTAssertEqual(package.movies.count, 2)
        XCTAssertTrue(package.movies.contains("sub/level 2/第三层/child.swf"))
        let content = root.appendingPathComponent(package.id.uuidString).appendingPathComponent("content")
        for (path, data) in inventory where path != "main.swf" {
            XCTAssertEqual(try Data(contentsOf: content.appendingPathComponent(path)), data)
        }
        XCTAssertEqual(try large.resourceValues(forKeys: [.fileSizeKey]).fileSize,
                       try content.appendingPathComponent("main.swf").resourceValues(forKeys: [.fileSizeKey]).fileSize)
        XCTAssertTrue(FileManager.default.fileExists(atPath: source.appendingPathComponent("sub/level 2/第三层/config.xml").path))
    }

    func testCancelledImportDoesNotCommitOrDeleteSource() throws {
        let temporary = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: temporary) }
        let source = temporary.appendingPathComponent("source")
        let root = temporary.appendingPathComponent("Packages")
        try FileManager.default.createDirectory(at: source, withIntermediateDirectories: true)
        try Data("FWSfixture".utf8).write(to: source.appendingPathComponent("main.swf"))
        let control = ImportControl()
        control.cancel()
        XCTAssertThrowsError(try PackageImporter(root: root, control: control).stageAndCommit(source)) { error in
            XCTAssertTrue(error is CancellationError)
        }
        XCTAssertFalse(FileManager.default.fileExists(atPath: root.path))
        XCTAssertTrue(FileManager.default.fileExists(atPath: source.appendingPathComponent("main.swf").path))
    }
}

@MainActor final class DocumentPickerDelegateTests: XCTestCase {
    func testSelectionIsDeliveredOnceAndNotLostOnSubsequentCancellation() {
        var received: [URL] = []
        var cancellations = 0
        let coordinator = PackageDocumentPicker.Coordinator(selected: { received = $0.urls }, cancelled: { cancellations += 1 })
        let picker = UIDocumentPickerViewController(forOpeningContentTypes: [.folder], asCopy: false)
        let url = FileManager.default.temporaryDirectory.appendingPathComponent("selected game")
        coordinator.documentPicker(picker, didPickDocumentsAt: [url])
        coordinator.documentPickerWasCancelled(picker)
        coordinator.documentPicker(picker, didPickDocumentsAt: [])
        XCTAssertEqual(received, [url])
        XCTAssertEqual(cancellations, 0)
    }

    func testCancellationWithoutSelectionIsReported() {
        var selected = false
        var cancellations = 0
        let coordinator = PackageDocumentPicker.Coordinator(selected: { _ in selected = true }, cancelled: { cancellations += 1 })
        let picker = UIDocumentPickerViewController(forOpeningContentTypes: [.folder], asCopy: false)
        coordinator.documentPickerWasCancelled(picker)
        coordinator.documentPickerWasCancelled(picker)
        XCTAssertFalse(selected)
        XCTAssertEqual(cancellations, 1)
    }
}

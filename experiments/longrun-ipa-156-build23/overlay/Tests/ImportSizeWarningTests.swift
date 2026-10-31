import XCTest
import ZIPFoundation
@testable import FlashNest

final class ImportSizeWarningTests: XCTestCase {
    private var temporary: URL!
    private var root: URL!
    override func setUpWithError() throws {
        temporary = FileManager.default.temporaryDirectory.resolvingSymlinksInPath().appendingPathComponent(UUID().uuidString)
        root = temporary.appendingPathComponent("Packages")
        try FileManager.default.createDirectory(at: temporary, withIntermediateDirectories: true)
    }
    override func tearDownWithError() throws { try FileManager.default.removeItem(at: temporary) }
    private func movie(_ name: String = "main.swf", bytes: Int = 12) throws -> URL {
        let url = temporary.appendingPathComponent(name)
        try FileManager.default.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
        try (Data("FWS".utf8) + Data(repeating: 1, count: bytes - 3)).write(to: url)
        return url
    }
    private func importer(file: UInt64 = 8, total: UInt64 = 64) -> PackageImporter {
        var value = PackageImporter(root: root)
        value.limits.fileBytes = file; value.limits.totalBytes = total
        return value
    }
    private func warning(_ importer: PackageImporter, _ source: URL) throws -> ImportSizeWarning {
        do { _ = try importer.stageAndCommit(source); XCTFail("Expected size confirmation before copying") }
        catch let warning as ImportSizeWarning { return warning }
        throw NSError(domain: "ExpectedImportSizeWarning", code: 1)
    }
    private func assertEmpty(_ file: StaticString = #filePath, _ line: UInt = #line) throws {
        XCTAssertEqual(try FileManager.default.contentsOfDirectory(atPath: root.path), [], file: file, line: line)
    }
    private func archive(_ name: String = "game.zip", entries: [(String, Data)], compression: CompressionMethod = .none) throws -> URL {
        let url = temporary.appendingPathComponent(name)
        let zip = try Archive(url: url, accessMode: .create)
        for (path, data) in entries {
            try zip.addEntry(with: path, type: .file, uncompressedSize: Int64(data.count), compressionMethod: compression) { position, size in
                data.subdata(in: Int(position)..<Int(position) + size)
            }
        }
        return url
    }
    func testSingleSWFRequiresWarningBeforeAnyStageAndConfirmedImportSucceeds() throws {
        let source = try movie(); var value = importer()
        let notice = try warning(value, source)
        XCTAssertEqual(notice.totalBytes, 12); XCTAssertEqual(notice.largestFileBytes, 12)
        XCTAssertEqual(notice.oversizedFileCount, 1); XCTAssertEqual(notice.fileThreshold, 8)
        try assertEmpty()
        value.sizeApproval = notice.approval
        let package = try value.stageAndCommit(source)
        XCTAssertEqual(package.movies, ["main.swf"])
        XCTAssertEqual(try Data(contentsOf: root.appendingPathComponent(package.id.uuidString + "/content/main.swf")), try Data(contentsOf: source))
    }
    func testExactThresholdDoesNotWarn() throws {
        let source = try movie(bytes: 8)
        _ = try importer(file: 8, total: 8).stageAndCommit(source)
    }
    func testFolderTotalOnlyWarningAndApproval() throws {
        _ = try movie("folder/main.swf", bytes: 8); _ = try movie("folder/child.swf", bytes: 8)
        let source = temporary.appendingPathComponent("folder")
        var value = importer(file: 8, total: 15)
        let notice = try warning(value, source)
        XCTAssertEqual(notice.totalBytes, 16); XCTAssertEqual(notice.oversizedFileCount, 0)
        try assertEmpty()
        value.sizeApproval = notice.approval
        XCTAssertEqual(try value.stageAndCommit(source).movies.count, 2)
    }
    func testZIPUsesExpandedSizesAndConfirmationPreservesAllEntries() throws {
        let source = try archive(entries: [("main.swf", Data("FWSfixture12".utf8)), ("asset.dat", Data(repeating: 1, count: 9))])
        var value = importer(file: 8, total: 16)
        let notice = try warning(value, source)
        XCTAssertEqual(notice.totalBytes, 21); XCTAssertEqual(notice.oversizedFileCount, 2)
        try assertEmpty()
        value.sizeApproval = notice.approval
        let package = try value.stageAndCommit(source)
        XCTAssertTrue(FileManager.default.fileExists(atPath: root.appendingPathComponent(package.id.uuidString + "/content/asset.dat").path))
    }
    func testApprovalCannotTransferToDifferentSelection() throws {
        let first = try movie("first.swf"), second = try movie("second.swf")
        var value = importer(); value.sizeApproval = try warning(value, first).approval
        XCTAssertThrowsError(try value.stageAndCommit(second)) { XCTAssertTrue($0 is PackageError) }
        try assertEmpty()
    }
    func testChangedSelectionOrThresholdRequiresFreshReview() throws {
        let source = try movie(); var value = importer()
        value.sizeApproval = try warning(value, source).approval
        _ = try movie(bytes: 13)
        XCTAssertThrowsError(try value.stageAndCommit(source)) { XCTAssertTrue($0 is PackageError) }
        try assertEmpty()
        value.sizeApproval = nil
        value.sizeApproval = try warning(value, source).approval
        value.limits.fileBytes = 9
        XCTAssertThrowsError(try value.stageAndCommit(source)) { XCTAssertTrue($0 is PackageError) }
        try assertEmpty()
    }
    func testChangedZIPInventoryInvalidatesApproval() throws {
        let source = try archive(entries: [("main.swf", Data("FWSfixture12".utf8))])
        var value = importer(); value.sizeApproval = try warning(value, source).approval
        let zip = try Archive(url: source, accessMode: .update)
        try zip.addEntry(with: "new.dat", type: .file, uncompressedSize: Int64(1)) { _, _ in Data([1]) }
        XCTAssertThrowsError(try value.stageAndCommit(source)) { XCTAssertTrue($0 is PackageError) }
        try assertEmpty()
    }
    func testGrowthAndShrinkBetweenPreflightAndCopyRollBack() throws {
        for size in [7, 17] {
            let source = try movie(); var value = importer()
            value.sizeApproval = try warning(value, source).approval
            value.control = ImportControl { progress in
                if progress.phase == "import.copying" { try? (Data("FWS".utf8) + Data(repeating: 2, count: size - 3)).write(to: source) }
            }
            XCTAssertThrowsError(try value.stageAndCommit(source)) { XCTAssertTrue($0 is PackageError) }
            try assertEmpty()
        }
    }
    func testSymlinkReplacementAtCopyCheckpointIsRejected() throws {
        let source = try movie(), target = try movie("target.swf")
        var value = importer(); value.sizeApproval = try warning(value, source).approval
        value.control = ImportControl { progress in
            if progress.phase == "import.copying" {
                try? FileManager.default.removeItem(at: source)
                try? FileManager.default.createSymbolicLink(at: source, withDestinationURL: target)
            }
        }
        XCTAssertThrowsError(try value.stageAndCommit(source)) { XCTAssertTrue($0 is PackageError) }
        try assertEmpty()
    }
    func testStructuralLimitsStillRejectBeforeWarning() throws {
        _ = try movie("folder/main.swf"); _ = try movie("folder/second.swf")
        var value = importer(file: 1, total: 1); value.limits.files = 1
        XCTAssertThrowsError(try value.stageAndCommit(temporary.appendingPathComponent("folder"))) { XCTAssertTrue($0 is PackageError) }
        try assertEmpty()
        let zip = try archive(entries: [("../escape.swf", Data("FWSfixture12".utf8))])
        XCTAssertThrowsError(try importer().stageAndCommit(zip)) { XCTAssertTrue($0 is PackageError) }
        try assertEmpty()
    }
    func testCompressionRatioRemainsHardSafetyCheck() throws {
        let zip = try archive(entries: [("main.swf", Data("FWS".utf8) + Data(repeating: 0, count: 10000))], compression: .deflate)
        var value = importer(); value.limits.compressionRatio = 1
        XCTAssertThrowsError(try value.stageAndCommit(zip)) { XCTAssertTrue($0 is PackageError) }
        try assertEmpty()
    }
    func testCancelledConfirmedRetryDoesNotCopy() throws {
        let source = try movie(); var value = importer()
        value.sizeApproval = try warning(value, source).approval
        let control = ImportControl(); control.cancel(); value.control = control
        XCTAssertThrowsError(try value.stageAndCommit(source)) { XCTAssertTrue($0 is CancellationError) }
        try assertEmpty()
    }
    func testDefaultThresholdWarningUsesSparseMetadataWithoutLargeAllocation() throws {
        let source = try movie()
        let handle = try FileHandle(forWritingTo: source)
        try handle.truncate(atOffset: 268_435_457); try handle.close()
        let notice = try warning(PackageImporter(root: root), source)
        XCTAssertEqual(notice.largestFileBytes, 268_435_457)
        XCTAssertEqual(notice.fileThreshold, 268_435_456)
        XCTAssertEqual(notice.totalThreshold, 1_073_741_824)
        try assertEmpty()

        // Exercise the real total threshold using metadata only. No sparse file
        // content is copied or read into memory at either boundary.
        let folder = temporary.appendingPathComponent("total-boundary")
        for index in 0..<4 {
            let file = try movie("total-boundary/part-\(index).swf")
            let output = try FileHandle(forWritingTo: file)
            try output.truncate(atOffset: 268_435_456)
            try output.close()
        }
        let value = PackageImporter(root: root)
        let exact = try value.sizePreflight(folder)
        XCTAssertEqual(exact.totalBytes, 1_073_741_824)
        XCTAssertEqual(exact.oversizedFileCount, 0)
        XCTAssertNil(exact.warning)
        try Data([1]).write(to: folder.appendingPathComponent("extra.dat"))
        let totalNotice = try warning(value, folder)
        XCTAssertEqual(totalNotice.totalBytes, 1_073_741_825)
        XCTAssertEqual(totalNotice.largestFileBytes, 268_435_456)
        XCTAssertEqual(totalNotice.oversizedFileCount, 0)
        try assertEmpty()
    }
    func testCheckedTotalsAndBatchProgressCannotOverflow() throws {
        XCTAssertEqual(try PackageImporter.checkedImportTotal(Int64.max - 1, adding: 1), Int64.max)
        XCTAssertThrowsError(try PackageImporter.checkedImportTotal(Int64.max, adding: 1))
        XCTAssertThrowsError(try PackageImporter.checkedImportTotal(0, adding: -1))
        let control = ImportControl()
        try control.checkpoint(addingBytes: UInt64.max)
        XCTAssertThrowsError(try control.checkpoint(addingBytes: 1))
        // Failed arithmetic must unlock the control rather than deadlocking cancellation.
        control.cancel()
        XCTAssertThrowsError(try control.checkpoint()) { XCTAssertTrue($0 is CancellationError) }
    }
}

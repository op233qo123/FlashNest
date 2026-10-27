import XCTest
import WebKit
@testable import FlashNest

@MainActor final class CacheCleanupTests: XCTestCase {
    override func setUpWithError() throws { executionTimeAllowance = 120 }

    func testCacheTypesExcludeSaveBearingStorageAndMaskOnlyRequestedTypes() {
        XCTAssertEqual(CacheCleanupError.requestedTypes,
                       [WKWebsiteDataTypeDiskCache, WKWebsiteDataTypeMemoryCache, WKWebsiteDataTypeOfflineWebApplicationCache])
        XCTAssertFalse(CacheCleanupError.requestedTypes.contains(WKWebsiteDataTypeLocalStorage))
        XCTAssertFalse(CacheCleanupError.requestedTypes.contains(WKWebsiteDataTypeIndexedDBDatabases))
        XCTAssertEqual(CacheCleanupError.supportedMask([]), 0)
        XCTAssertEqual(CacheCleanupError.supportedMask(CacheCleanupError.requestedTypes), 7)
        XCTAssertEqual(CacheCleanupError.supportedMask([WKWebsiteDataTypeMemoryCache, WKWebsiteDataTypeLocalStorage]), 2)
    }

    func testFixedDiagnosticDoesNotIncludeRecordNamesOrPaths() {
        let error = CacheCleanupError(reason: .deadline, elapsedMilliseconds: 15000, supportedTypeMask: 7)
        XCTAssertEqual(error.diagnosticCode, "CACHE-CLEANUP-DEADLINE")
        XCTAssertEqual(error.redactedSummary, "CACHE-CLEANUP-DEADLINE elapsedMs=15000 supportedMask=7")
    }

    func testFreshProfileCacheRemovalCompletesWithoutOpeningMovie() async throws {
        try await removeCaches(UUID())
    }

    func testStoppedStorageOnlyProfileCacheRemovalCompletesWithoutOpeningMovie() async throws {
        let package = GamePackage(id: UUID(), title: "Original cache cleanup fixture", importedAt: Date(),
                                  movies: ["unused.swf"], selectedMovie: "unused.swf")
        let packageRoot = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("Packages").appendingPathComponent(package.id.uuidString)
        let nativeRoot = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: packageRoot.appendingPathComponent("content"), withIntermediateDirectories: true)
        defer {
            try? FileManager.default.removeItem(at: packageRoot)
            try? FileManager.default.removeItem(at: nativeRoot)
        }
        let store = SaveStore(root: nativeRoot)
        try await PlayerSession.preserveLegacySave(package: package, store: store)
        let snapshot = try XCTUnwrap(store.currentSnapshot(packageID: package.id))
        try await removeCaches(package.id)
        XCTAssertEqual(try store.currentSnapshot(packageID: package.id)?.id, snapshot.id,
                       "Cache clearing must not replace the native snapshot")
    }

    private func removeCaches(_ id: UUID) async throws {
        do { try await PlayerSession.clearPackageCaches(packageID: id) }
        catch let error as CacheCleanupError { XCTFail(error.redactedSummary); throw error }
    }
}

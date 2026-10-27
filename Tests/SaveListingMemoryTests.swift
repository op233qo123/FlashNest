import XCTest
@testable import FlashNest

/// Standalone opt-in benchmark. Large original synthetic JSON fixtures are
/// generated on the runner before build, never allocated by test setup.
final class SaveListingMemoryTests: XCTestCase {
#if SAVE_METADATA_LISTING
    private var current: SaveSnapshotSummary?
    private var rows: [SaveSnapshotSummary] = []
#else
    private var current: SaveSnapshot?
    private var rows: [SaveSnapshot] = []
#endif

    func testMeasurePopulatedSaveListingMemory() throws {
        guard ProcessInfo.processInfo.environment["FLASHNEST_MEASURE_SAVE_LISTING"] == "1" else {
            throw XCTSkip("Opt-in populated save-listing benchmark")
        }
        let fixtures = try XCTUnwrap(Bundle(for: Self.self).url(forResource: "fixtures", withExtension: nil))
        let root = fixtures.appendingPathComponent("save-listing-memory/save")
        let store = SaveStore(root: root)
        let id = try XCTUnwrap(UUID(uuidString: "a1111111-1111-4111-8111-111111111111"))
        let options = XCTMeasureOptions()
        options.iterationCount = 5
        options.invocationOptions = [.manuallyStart, .manuallyStop]
        measure(metrics: [XCTMemoryMetric(), XCTClockMetric()], options: options) {
            current = nil; rows = []
            var invalidCount = -1
            startMeasuring()
            do {
                try autoreleasepool {
#if SAVE_METADATA_LISTING
                    current = try store.currentSummary(packageID: id)
                    let listing = try store.recoverableSummaryList(packageID: id)
                    rows = listing.summaries
#else
                    current = try store.currentSnapshot(packageID: id)
                    let listing = try store.recoverableList(packageID: id)
                    rows = listing.snapshots
#endif
                    invalidCount = listing.invalidFileCount
                }
            } catch {
                stopMeasuring()
                XCTFail("Synthetic listing failed: \(error)")
                return
            }
            // Keep all returned rows alive through metric end, as SwiftUI state
            // does. Release before the NEXT measured interval, not during this one.
            stopMeasuring()
            XCTAssertNotNil(current)
            XCTAssertEqual(rows.count, 5)
            XCTAssertEqual(invalidCount, 1, "The sixth full archive exceeds the unchanged 64 MiB listing budget")
        }
#if SAVE_METADATA_LISTING
        XCTAssertTrue(rows.allSatisfy { $0.objectCount == 8 && $0.decodedBytes == SaveStore.maximumTotalBytes })
        print("FLASHNEST_SAVE_LISTING mode=metadata rows=5 current=1 invalid=1 retainedSOLUTF8Bytes=0")
#else
        let retained = (rows + (current.map { [$0] } ?? [])).reduce(0) { total, snapshot in
            total + snapshot.entries.reduce(0) { $0 + $1.value.utf8.count }
        }
        XCTAssertEqual(retained, 67_108_992)
        print("FLASHNEST_SAVE_LISTING mode=full rows=5 current=1 invalid=1 retainedSOLUTF8Bytes=\(retained)")
#endif
    }
}

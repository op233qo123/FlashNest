import XCTest
import CryptoKit
@testable import FlashNest

/// Synthetic SOL-header fixtures only; never loads or runs a game.
final class SaveStoreMemoryTests: XCTestCase {
    private func capture(count: Int = 8) -> SaveCapture {
        SaveCapture(version: 1, entries: (0..<count).map { index in
            var bytes = Data(repeating: UInt8(index), count: SaveStore.maximumObjectBytes)
            bytes[0] = 0; bytes[1] = 0xbf
            bytes.replaceSubrange(6..<10, with: "TCSO".utf8)
            bytes.replaceSubrange(10..<16, with: [0, 4, 0, 0, 0, 0])
            return SaveEntry(scope: "origin", key: "object\(index)", value: bytes.base64EncodedString())
        })
    }

    private func package() -> GamePackage {
        GamePackage(id: UUID(), title: "Synthetic memory fixture", importedAt: Date(),
                    movies: ["main.swf"], selectedMovie: "main.swf")
    }

    func testMaximumDecodedPayloadRoundTripsWithIndependentChecksums() throws {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: root) }
        let store = SaveStore(root: root), game = package(), input = capture()
        let snapshot = try store.persistLatest(input, package: game)
        XCTAssertEqual(snapshot.decodedBytes, SaveStore.maximumTotalBytes)
        XCTAssertEqual(snapshot.entries.count, 8)
        for (actual, expected) in zip(snapshot.entries, input.entries) {
            let bytes = try XCTUnwrap(Data(base64Encoded: expected.value))
            let checksum = SHA256.hash(data: bytes).map { String(format: "%02x", $0) }.joined()
            XCTAssertEqual(actual.sha256, checksum)
            XCTAssertEqual(actual.value, expected.value)
        }
        let exported = try store.export(snapshot)
        XCTAssertEqual(try store.decodeImport(exported).entries, snapshot.entries)
        XCTAssertEqual(try store.currentSnapshot(packageID: game.id)?.entries, snapshot.entries)

        let current = root.appendingPathComponent(game.id.uuidString).appendingPathComponent("current.json")
        let before = try Data(contentsOf: current)
        XCTAssertThrowsError(try store.persistLatest(capture(count: 9), package: game))
        XCTAssertEqual(try Data(contentsOf: current), before, "Over-limit capture must leave prior saves byte-identical")
    }

    /// Opt in on the same simulator/device and build configuration for both
    /// revisions: FLASHNEST_MEASURE_SAVE_MEMORY=1. Compare xcresult metrics;
    /// fixture creation is outside measurement. No fixed RSS reduction claimed.
    func testMeasureMaximumCaptureMemory() throws {
        guard ProcessInfo.processInfo.environment["FLASHNEST_MEASURE_SAVE_MEMORY"] == "1" else {
            throw XCTSkip("Opt-in synthetic save memory benchmark")
        }
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: root) }
        let store = SaveStore(root: root), game = package(), input = capture()
        // Measure the same unchanged-current path in every iteration.
        _ = try store.persistLatest(input, package: game)
        let options = XCTMeasureOptions()
        options.iterationCount = 5
        measure(metrics: [XCTMemoryMetric(), XCTClockMetric()], options: options) {
            do {
                let saved = try store.persistLatest(input, package: game)
                XCTAssertEqual(saved.decodedBytes, SaveStore.maximumTotalBytes)
            } catch { XCTFail("Synthetic capture failed: \(error)") }
        }
    }
}

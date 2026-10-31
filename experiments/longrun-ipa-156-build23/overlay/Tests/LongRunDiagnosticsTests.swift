import XCTest
@testable import FlashNest

final class LongRunDiagnosticsTests: XCTestCase {
    private let date = Date(timeIntervalSince1970: 1_800_000_000)
    private func body(_ session: UUID, epoch: Int = 1, seq: Int = 1) -> [String: Any] {
        ["type": "longRunDiagnostics", "schema": 1, "session": session.uuidString,
         "wkEpoch": epoch, "seq": seq, "webElapsedMs": seq * 10_000, "contexts": 1,
         "contextLost": 0, "contextRestored": 0, "texturesCreated": 16,
         "texturesDeleted": 0, "textureUploads": 16, "drawCalls": seq,
         "textureBytesEstimate": 16_777_216, "unknownUploads": 0,
         "overflow": false, "hookFailures": 0, "sendFailures": 0]
    }
    private func temporaryRoot() throws -> URL {
        let url = FileManager.default.temporaryDirectory.resolvingSymlinksInPath()
            .appendingPathComponent(UUID().uuidString, isDirectory: true)
        try FileManager.default.createDirectory(at: url, withIntermediateDirectories: true)
        addTeardownBlock { try? FileManager.default.removeItem(at: url) }
        return url
    }
    func testDefaultOffAndSeparatePreference() {
        let suite = "long-run-tests-" + UUID().uuidString
        let defaults = UserDefaults(suiteName: suite)!
        defer { defaults.removePersistentDomain(forName: suite) }
        XCTAssertFalse(defaults.bool(forKey: LongRunDiagnostics.preferenceKey))
        XCTAssertNotEqual(LongRunDiagnostics.preferenceKey, LoadingPhaseDiagnostics.preferenceKey)
    }
    func testStrictAnonymousEnvelopeAndSessionEpoch() {
        let id = UUID(); let value = body(id)
        XCTAssertNotNil(LongRunSample.client(value, session: id, wkEpoch: 1))
        XCTAssertNil(LongRunSample.client(value, session: UUID(), wkEpoch: 1))
        XCTAssertNil(LongRunSample.client(value, session: id, wkEpoch: 2))
        var secret = value; secret["url"] = "private-content"
        XCTAssertNil(LongRunSample.client(secret, session: id, wkEpoch: 1))
        var missing = value; missing.removeValue(forKey: "drawCalls")
        XCTAssertNil(LongRunSample.client(missing, session: id, wkEpoch: 1))
    }
    func testRejectsBoolFractionNegativeAndOversizedIntegers() {
        let id = UUID()
        let badValues: [Any] = [true, 1.5, -1, Double.infinity, Double.nan, 2_147_483_648.0, "1", NSNull()]
        for bad in badValues {
            var value = body(id); value["drawCalls"] = bad
            XCTAssertNil(LongRunSample.client(value, session: id, wkEpoch: 1))
        }
        var value = body(id); value["overflow"] = 1
        XCTAssertNil(LongRunSample.client(value, session: id, wkEpoch: 1))
        value = body(id); value["wasmBytes"] = 1_099_511_627_777.0
        XCTAssertNil(LongRunSample.client(value, session: id, wkEpoch: 1))
        value = body(id); value["texturesDeleted"] = 17
        XCTAssertNil(LongRunSample.client(value, session: id, wkEpoch: 1))
    }
    func testRollingBeyondOldFirst256CapAndTerminalPreservation() {
        let id = UUID(); var snapshot = LongRunSnapshot(session: id, wkEpoch: 1)
        XCTAssertTrue(snapshot.record(.sessionStart, at: date))
        for seq in 1...1000 { XCTAssertTrue(snapshot.receive(body(id, seq: seq), at: date)) }
        XCTAssertEqual(snapshot.observed, 1001)
        XCTAssertEqual(snapshot.events.count, 120)
        XCTAssertEqual(snapshot.evicted, 881)
        XCTAssertTrue(snapshot.record(.webProcessTerminated, at: date))
        XCTAssertEqual(snapshot.events.last?.kind, .webProcessTerminated)
        let terminal = snapshot
        XCTAssertFalse(snapshot.receive(body(id, seq: 1001), at: date))
        XCTAssertFalse(snapshot.record(.userMarker, at: date))
        XCTAssertEqual(snapshot, terminal)
        XCTAssertTrue(snapshot.isValid)
    }
    func testSequenceGapsDuplicateAndCounterReset() {
        let id = UUID(); var snapshot = LongRunSnapshot(session: id, wkEpoch: 1)
        XCTAssertTrue(snapshot.receive(body(id, seq: 3), at: date))
        XCTAssertEqual(snapshot.sequenceGaps, 2)
        XCTAssertTrue(snapshot.receive(body(id, seq: 7), at: date))
        XCTAssertEqual(snapshot.sequenceGaps, 5)
        XCTAssertFalse(snapshot.receive(body(id, seq: 7), at: date))
        var reset = body(id, seq: 8); reset["texturesCreated"] = 0
        XCTAssertFalse(snapshot.receive(reset, at: date))
        XCTAssertEqual(snapshot.rejected, 2)
        XCTAssertEqual(snapshot.lastSample?.seq, 7)
        XCTAssertTrue(snapshot.isValid)
    }
    func testCounterSaturationDoesNotBlockTerminal() {
        var snapshot = LongRunSnapshot(session: UUID(), wkEpoch: 1)
        snapshot.observed = LongRunSample.counterLimit
        snapshot.evicted = LongRunSample.counterLimit
        XCTAssertTrue(snapshot.record(.webProcessTerminated, at: date))
        XCTAssertTrue(snapshot.countersSaturated)
        XCTAssertEqual(snapshot.observed, LongRunSample.counterLimit)
        XCTAssertTrue(snapshot.isValid)
    }
    func testInvalidNativeDateAndNoSampleInjection() {
        var snapshot = LongRunSnapshot(session: UUID(), wkEpoch: 1)
        XCTAssertFalse(snapshot.record(.sample, at: date))
        XCTAssertFalse(snapshot.record(.userMarker, at: Date(timeIntervalSince1970: -.infinity)))
        XCTAssertFalse(snapshot.record(.userMarker, at: Date(timeIntervalSince1970: 4_102_444_801)))
        XCTAssertEqual(snapshot.rejected, 3)
        XCTAssertEqual(snapshot.observed, 0)
        XCTAssertTrue(snapshot.isValid)
    }
    func testOptionalWasmAndBooleanOverflow() {
        let id = UUID(); var value = body(id)
        value["wasmBytes"] = 65_536
        value["overflow"] = true
        XCTAssertEqual(LongRunSample.client(value, session: id, wkEpoch: 1)?.wasmBytes, 65_536)
        var snapshot = LongRunSnapshot(session: id, wkEpoch: 1)
        XCTAssertTrue(snapshot.receive(value, at: date))
        XCTAssertFalse(snapshot.receive(body(id, seq: 2), at: date))
        value = body(id, seq: 2); value["overflow"] = true
        XCTAssertTrue(snapshot.receive(value, at: date))
    }
    func testTwoSessionsAtomicCheckpointAndClear() throws {
        let root = try temporaryRoot(); let store = LongRunDiagnostics(root: root)
        var ids: [UUID] = []
        for _ in 0..<3 {
            let id = UUID(); ids.append(id)
            var snapshot = LongRunSnapshot(session: id, wkEpoch: 1)
            XCTAssertTrue(snapshot.record(.sessionStart, at: date))
            try store.record(snapshot)
        }
        XCTAssertEqual(store.read().map(\.session), [ids[2], ids[1]])
        let file = root.appendingPathComponent("long-run.json")
        XCTAssertLessThan(try Data(contentsOf: file).count, LongRunDiagnostics.maximumBytes)
        try store.clear(); XCTAssertEqual(store.read(), [])
    }
    func testMaximumNormalCheckpointFitsHardLimit() throws {
        let root = try temporaryRoot(); let store = LongRunDiagnostics(root: root)
        for _ in 0..<2 {
            let id = UUID(); var snapshot = LongRunSnapshot(session: id, wkEpoch: 9_999_999)
            for seq in 1...300 {
                var value = body(id, epoch: 9_999_999, seq: seq)
                for key in ["contextLost", "contextRestored", "texturesCreated", "texturesDeleted", "textureUploads", "drawCalls", "unknownUploads", "hookFailures", "sendFailures"] { value[key] = LongRunSample.counterLimit }
                value["textureBytesEstimate"] = LongRunSample.byteLimit
                value["wasmBytes"] = LongRunSample.byteLimit
                value["webElapsedMs"] = LongRunSample.elapsedLimit
                value["overflow"] = true
                XCTAssertTrue(snapshot.receive(value, at: date))
            }
            XCTAssertTrue(snapshot.record(.webProcessTerminated, at: date))
            try store.record(snapshot)
        }
        XCTAssertEqual(store.read().count, 2)
        XCTAssertLessThanOrEqual(try Data(contentsOf: root.appendingPathComponent("long-run.json")).count, LongRunDiagnostics.maximumBytes)
    }
    func testCorruptOversizedAndInvalidStoredDataFailClosed() throws {
        let root = try temporaryRoot(); let store = LongRunDiagnostics(root: root)
        let file = root.appendingPathComponent("long-run.json")
        try Data("not-json".utf8).write(to: file); XCTAssertEqual(store.read(), [])
        try Data(repeating: 32, count: LongRunDiagnostics.maximumBytes + 1).write(to: file)
        XCTAssertEqual(store.read(), [])
        let invalid = LongRunSnapshot(session: UUID(), wkEpoch: 0)
        try JSONEncoder().encode([invalid]).write(to: file)
        XCTAssertEqual(store.read(), [])
        XCTAssertThrowsError(try store.record(invalid))
    }
    func testRejectsSymlinkFileIncludingDanglingLink() throws {
        let root = try temporaryRoot(); let target = root.appendingPathComponent("target")
        let file = root.appendingPathComponent("long-run.json")
        try FileManager.default.createSymbolicLink(at: file, withDestinationURL: target)
        let store = LongRunDiagnostics(root: root)
        XCTAssertEqual(store.read(), [])
        XCTAssertThrowsError(try store.clear())
        XCTAssertFalse(FileManager.default.fileExists(atPath: target.path))
    }
    func testRejectsDirectoryAndAncestorSymlinks() throws {
        let root = try temporaryRoot()
        let target = root.appendingPathComponent("target", isDirectory: true)
        try FileManager.default.createDirectory(at: target, withIntermediateDirectories: true)
        let link = root.appendingPathComponent("link", isDirectory: true)
        try FileManager.default.createSymbolicLink(at: link, withDestinationURL: target)
        for candidate in [link, link.appendingPathComponent("nested")] {
            let store = LongRunDiagnostics(root: candidate)
            XCTAssertThrowsError(try store.clear()); XCTAssertEqual(store.read(), [])
        }
        XCTAssertEqual(try FileManager.default.contentsOfDirectory(atPath: target.path), [])
    }
    func testUnknownPayloadIsNotPersistedOrExported() throws {
        let root = try temporaryRoot(); let store = LongRunDiagnostics(root: root)
        let id = UUID(); var snapshot = LongRunSnapshot(session: id, wkEpoch: 1)
        var value = body(id); value["private"] = "SECRET_GAME_PATH"
        XCTAssertFalse(snapshot.receive(value, at: date))
        XCTAssertTrue(snapshot.record(.userMarker, at: date))
        try store.record(snapshot)
        XCTAssertFalse(snapshot.summary.contains("SECRET"))
        XCTAssertFalse(String(decoding: try Data(contentsOf: root.appendingPathComponent("long-run.json")), as: UTF8.self).contains("SECRET"))
    }
}

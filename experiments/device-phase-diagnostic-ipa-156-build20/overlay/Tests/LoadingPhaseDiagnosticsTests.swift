import XCTest
@testable import FlashNest

final class LoadingPhaseDiagnosticsTests: XCTestCase {
    func testClientOnlyAcceptsBoundedScalarsAndCurrentSession() {
        let session = UUID()
        let valid: [String: Any] = ["phaseSession": session.uuidString, "phase": "clientBodyFulfilled", "seq": 1, "requestID": 2, "bytes": 100]
        XCTAssertNotNil(LoadingPhaseEvent.client(valid, session: session))
        XCTAssertNil(LoadingPhaseEvent.client(valid, session: UUID()))
        var noSequence = valid; noSequence.removeValue(forKey: "seq")
        XCTAssertNil(LoadingPhaseEvent.client(noSequence, session: session))
        var noBytes = valid; noBytes.removeValue(forKey: "bytes")
        XCTAssertNil(LoadingPhaseEvent.client(noBytes, session: session))
        for (key, value) in [("bytes", -1 as Any), ("seq", true as Any), ("requestID", 1.5 as Any), ("phase", "serverSendCompleted" as Any)] {
            var invalid = valid; invalid[key] = value
            XCTAssertNil(LoadingPhaseEvent.client(invalid, session: session))
        }
    }
    func testCapStillAllowsTerminationAndRejectsLaterEvents() {
        var snapshot = LoadingPhaseSnapshot(session: UUID(), wkEpoch: 1)
        let event = LoadingPhaseEvent(phase: .clientHeaders, receivedAt: Date())
        for _ in 0..<256 { XCTAssertTrue(snapshot.append(event)) }
        XCTAssertFalse(snapshot.append(event)); XCTAssertEqual(snapshot.events.count, 32)
        XCTAssertTrue(snapshot.append(LoadingPhaseEvent(phase: .webProcessTerminated, receivedAt: Date())))
        XCTAssertFalse(snapshot.append(event)); XCTAssertEqual(snapshot.eventCount, 257)
        XCTAssertTrue(snapshot.isValid); XCTAssertTrue(snapshot.terminated)
    }
    func testAtomicRoundtripTwoSessionsAndClear() throws {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: root) }
        let store = LoadingPhaseDiagnostics(root: root)
        var last: LoadingPhaseSnapshot?
        for _ in 0..<3 {
            var snapshot = LoadingPhaseSnapshot(session: UUID(), wkEpoch: 1)
            XCTAssertTrue(snapshot.append(LoadingPhaseEvent(phase: .clientHeaders, receivedAt: Date())))
            try store.record(snapshot); last = snapshot
        }
        XCTAssertEqual(store.read().count, 2)
        XCTAssertEqual(store.read().first, last)
        let freshStore = LoadingPhaseDiagnostics(root: root)
        XCTAssertEqual(freshStore.read(), store.read())
        try freshStore.clear(); XCTAssertTrue(store.read().isEmpty)
    }
    func testEncodedMetadataNeverContainsUntrustedExtraValues() throws {
        let session = UUID()
        let payload: [String: Any] = ["phaseSession": session.uuidString, "phase": "clientHeaders", "seq": 1, "status": 200,
            "url": "PRIVATE_URL", "trace": "PRIVATE_TRACE", "save": "PRIVATE_SAVE"]
        let event = try XCTUnwrap(LoadingPhaseEvent.client(payload, session: session))
        let encoded = String(decoding: try JSONEncoder().encode(event), as: UTF8.self)
        XCTAssertFalse(encoded.contains("PRIVATE_"))
    }
    func testOversizedMalformedAndSymlinkFilesRejected() throws {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: root) }
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        let file = root.appendingPathComponent("loading-phases.json")
        let store = LoadingPhaseDiagnostics(root: root)
        try Data(repeating: 32, count: LoadingPhaseDiagnostics.maximumBytes + 1).write(to: file)
        XCTAssertTrue(store.read().isEmpty)
        try Data("invalid".utf8).write(to: file)
        XCTAssertTrue(store.read().isEmpty)
        try FileManager.default.removeItem(at: file)
        let target = root.appendingPathComponent("target.json")
        try Data("[]".utf8).write(to: target)
        try FileManager.default.createSymbolicLink(at: file, withDestinationURL: target)
        XCTAssertTrue(store.read().isEmpty)
        XCTAssertThrowsError(try store.clear())
        XCTAssertEqual(try Data(contentsOf: target), Data("[]".utf8))
        XCTAssertEqual(try FileManager.default.attributesOfItem(atPath: file.path)[.type] as? FileAttributeType, .typeSymbolicLink)
        let freshStore = LoadingPhaseDiagnostics(root: root)
        XCTAssertTrue(freshStore.read().isEmpty)
        XCTAssertThrowsError(try freshStore.clear())
        XCTAssertEqual(try Data(contentsOf: target), Data("[]".utf8))

        // A dangling link is an existing unsafe item, not a missing output file.
        try FileManager.default.removeItem(at: target)
        XCTAssertTrue(freshStore.read().isEmpty)
        XCTAssertThrowsError(try freshStore.clear())
        XCTAssertFalse(FileManager.default.fileExists(atPath: target.path))
        XCTAssertEqual(try FileManager.default.attributesOfItem(atPath: file.path)[.type] as? FileAttributeType, .typeSymbolicLink)

        // Reject a linked direct parent before createDirectory or atomic write.
        let actualDirectory = root.appendingPathComponent("actual", isDirectory: true)
        let linkedDirectory = root.appendingPathComponent("linked", isDirectory: true)
        try FileManager.default.createDirectory(at: actualDirectory, withIntermediateDirectories: false)
        try FileManager.default.createSymbolicLink(at: linkedDirectory, withDestinationURL: actualDirectory)
        let linkedStore = LoadingPhaseDiagnostics(root: linkedDirectory)
        XCTAssertTrue(linkedStore.read().isEmpty)
        XCTAssertThrowsError(try linkedStore.clear())
        XCTAssertTrue(try FileManager.default.contentsOfDirectory(atPath: actualDirectory.path).isEmpty)
    }
    func testPreferenceDefaultsOff() {
        let name = UUID().uuidString
        let defaults = UserDefaults(suiteName: name)!
        defer { defaults.removePersistentDomain(forName: name) }
        XCTAssertFalse(defaults.bool(forKey: LoadingPhaseDiagnostics.preferenceKey))
    }
}

import XCTest
@testable import FlashNest

final class LegacySavePreservationDiagnosticsTests: XCTestCase {
    func testColdHandshakeDeadlineClassificationDoesNotTreatNotReadyAsSuccess() {
        let deadline = Date(timeIntervalSince1970: 100)
        XCTAssertNil(LegacySavePreservationError.handshakeOutcome(ready: false, failed: false, terminated: false,
            now: deadline.addingTimeInterval(-0.001), deadline: deadline))
        XCTAssertEqual(LegacySavePreservationError.handshakeOutcome(ready: false, failed: false, terminated: false,
            now: deadline, deadline: deadline), .deadline)
        XCTAssertNil(LegacySavePreservationError.handshakeOutcome(ready: true, failed: true, terminated: false,
            now: deadline.addingTimeInterval(1), deadline: deadline))
    }
    func testFailureAndTerminationAreNotMislabelledAsColdStart() {
        let now = Date(timeIntervalSince1970: 100)
        XCTAssertEqual(LegacySavePreservationError.handshakeOutcome(ready: false, failed: true, terminated: false,
            now: now, deadline: now), .failed)
        XCTAssertEqual(LegacySavePreservationError.handshakeOutcome(ready: false, failed: true, terminated: true,
            now: now, deadline: now), .terminated)
    }
    func testDiagnosticContainsOnlyFixedCodesAndNumericEvidence() {
        let error = LegacySavePreservationError(stage: .capture, outcome: .failed, elapsedMilliseconds: 15000,
            acceptedMessages: 2, rejectedIdentity: 1, rejectedEnvelope: 0, receivedSaveReady: true)
        XCTAssertEqual(error.diagnosticCode, "SAVE-PRESERVE-CAPTURE-FAILED")
        XCTAssertEqual(error.redactedSummary, "SAVE-PRESERVE-CAPTURE-FAILED elapsedMs=15000 accepted=2 rejectedIdentity=1 rejectedEnvelope=0 receivedSaveReady=true")
    }
}

@MainActor final class LegacySavePreservationWebKitTests: XCTestCase {
    func testActualStorageOnlyPreservationCapturesVerifiedEmptyProfileWithoutMovie() async throws {
        executionTimeAllowance = 120
        let package = GamePackage(id: UUID(), title: "Original preservation fixture", importedAt: Date(),
                                  movies: ["unused.swf"], selectedMovie: "unused.swf")
        let packageRoot = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("Packages").appendingPathComponent(package.id.uuidString)
        let content = packageRoot.appendingPathComponent("content")
        let nativeRoot = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: content, withIntermediateDirectories: true)
        defer {
            try? FileManager.default.removeItem(at: packageRoot)
            try? FileManager.default.removeItem(at: nativeRoot)
        }
        let store = SaveStore(root: nativeRoot)
        XCTAssertNil(try store.currentSnapshot(packageID: package.id))
        // The production 15-second deadline is unchanged. No movie is present:
        // this probes the same off-window page/close/capture path as SaveArea.
        do { try await PlayerSession.preserveLegacySave(package: package, store: store) }
        catch let error as LegacySavePreservationError {
            XCTFail(error.redactedSummary)
            throw error
        }
        let snapshot = try XCTUnwrap(store.currentSnapshot(packageID: package.id))
        XCTAssertTrue(snapshot.entries.isEmpty)
        XCTAssertEqual(snapshot.packageID, package.id)
    }
}

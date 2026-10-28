import XCTest
@testable import FlashNest

final class SamplingAppliedStatusTests: XCTestCase {
    private func body(requested: Double = 0.75, applied: Double = 0.75,
                      status: String = "applied", sequence: Int = 1) -> [String: Any] {
        ["type": "samplingStatus", "session": "current", "sequence": sequence,
         "status": status, "requested": requested, "applied": applied,
         "renderer": "webgl", "viewport": [1200, 900],
         "canvas": [Int((1200 * applied).rounded()), Int((900 * applied).rounded())],
         "dpr": 3, "reason": status == "fallback" ? "original-fallback" : "observed"]
    }
    func testMatchingEvidenceReportsApplied() {
        let result = SamplingAppliedStatus.decode(body(), expectedRequest: 0.75)
        XCTAssertEqual(result.state, .applied)
        XCTAssertEqual(result.applied, 0.75)
    }
    func testOriginalFallbackIsDistinctFromSupportedLow() {
        let result = SamplingAppliedStatus.decode(body(applied: 1, status: "fallback"), expectedRequest: 0.75)
        XCTAssertEqual(result.state, .fallback)
        XCTAssertEqual(result.requested, 0.75)
        XCTAssertEqual(result.applied, 1)
    }
    func testUnknownOrMissingEvidenceDoesNotEchoPreference() {
        var message = body(); message["status"] = "unknown"; message["applied"] = NSNull()
        XCTAssertEqual(SamplingAppliedStatus.decode(message, expectedRequest: 0.75), .unknown)
        message = body(); message.removeValue(forKey: "canvas")
        XCTAssertEqual(SamplingAppliedStatus.decode(message, expectedRequest: 0.75), .unknown)
        XCTAssertEqual(SamplingAppliedStatus.decode(body(), expectedRequest: nil), .unknown)
    }
    func testInvalidCurrentEvidenceBecomesUnknown() {
        var tracker = SamplingStatusTracker()
        XCTAssertTrue(tracker.receive(body(), session: "current", expectedRequest: 0.75))
        var message = body(sequence: 2); message["canvas"] = [1200, 900]
        XCTAssertTrue(tracker.receive(message, session: "current", expectedRequest: 0.75))
        XCTAssertEqual(tracker.status, .unknown)
    }
    func testWrongSessionAndOldSequenceCannotOverwrite() {
        var tracker = SamplingStatusTracker()
        tracker.receive(body(sequence: 2), session: "current", expectedRequest: 0.75)
        let current = tracker.status
        var stale = body(applied: 1, status: "fallback", sequence: 3); stale["session"] = "old"
        XCTAssertFalse(tracker.receive(stale, session: "current", expectedRequest: 0.75))
        XCTAssertFalse(tracker.receive(body(applied: 1, status: "fallback", sequence: 1), session: "current", expectedRequest: 0.75))
        XCTAssertEqual(tracker.status, current)
        tracker.reset()
        XCTAssertEqual(tracker.status, .unknown)
        XCTAssertEqual(tracker.lastSequence, 0)
    }
    func testInvalidBoundsTypesAndClaimsFailClosed() {
        let bad: [(String, Any)] = [("requested", 0.5), ("applied", 0.5), ("applied", true),
            ("renderer", "arbitrary"), ("viewport", [0, 900]), ("viewport", [65_537, 900]),
            ("canvas", [900.5, 675]), ("dpr", Double.infinity), ("dpr", 8.01), ("dpr", true),
            ("status", "fallback"), ("reason", "original-fallback")]
        for (key, value) in bad {
            var message = body(); message[key] = value
            XCTAssertEqual(SamplingAppliedStatus.decode(message, expectedRequest: 0.75), .unknown, key)
        }
    }
    func testInvalidSequenceClearsCurrentConfirmation() {
        for invalid in [0, -1, 1.5, 1_000_000_001, true, "3"] as [Any] {
            var tracker = SamplingStatusTracker(); tracker.receive(body(), session: "current", expectedRequest: 0.75)
            var message = body(); message["sequence"] = invalid
            XCTAssertTrue(tracker.receive(message, session: "current", expectedRequest: 0.75))
            XCTAssertEqual(tracker.status, .unknown)
        }
    }
    func testCanvasFallbackAndOriginalAreNotReportedAsLow() {
        var message = body(applied: 1, status: "fallback"); message["renderer"] = "canvas"
        XCTAssertEqual(SamplingAppliedStatus.decode(message, expectedRequest: 0.75).state, .fallback)
        XCTAssertEqual(SamplingAppliedStatus.decode(body(requested: 1, applied: 1), expectedRequest: 1).state, .applied)
    }
}


final class SamplingDocumentBindingTests: XCTestCase {
    func testInitialProvisionalAndRedirectPhaseRequiresCommit() {
        var binding = SamplingDocumentBinding()
        XCTAssertFalse(binding.acceptsReports)
        binding.provisionalStarted(); binding.provisionalStarted()
        XCTAssertFalse(binding.acceptsReports)
        binding.committed()
        XCTAssertTrue(binding.acceptsReports)
    }
    func testReloadPermanentlyDisablesOldAndReplacementReports() {
        var binding = SamplingDocumentBinding()
        binding.committed(); binding.provisionalStarted()
        XCTAssertFalse(binding.acceptsReports)
        binding.committed(); binding.provisionalStarted(); binding.committed()
        XCTAssertFalse(binding.acceptsReports)
    }
    func testUnexpectedSecondCommitCannotRebind() {
        var binding = SamplingDocumentBinding()
        binding.committed(); binding.committed()
        XCTAssertFalse(binding.acceptsReports)
    }
    func testFailureCannotRebindButFreshViewResetCan() {
        var binding = SamplingDocumentBinding()
        binding.invalidate(); binding.provisionalStarted(); binding.committed()
        XCTAssertFalse(binding.acceptsReports)
        binding.reset(); binding.provisionalStarted(); binding.committed()
        XCTAssertTrue(binding.acceptsReports)
    }
}

import XCTest
import WebKit
@testable import FlashNest

/// Uses real WK references but suppresses navigation through the synchronous
/// internal seam, making cancellation/late delegate order deterministic.
@MainActor final class CacheCleanupLeaseLifecycleTests: XCTestCase {
    override func setUpWithError() throws { executionTimeAllowance = 30 }

    func testCancellationWhilePreparingReleasesOwnedViewAndRejectsLateCallback() async throws {
        let lease = CacheCleanupWarmLease(profile: .nonPersistent())
        var oldView: WKWebView?
        let task = Task { @MainActor in
            defer { lease.close() }
            try await lease.prepare(before: Date().addingTimeInterval(15)) { oldView = $0 }
        }
        try await requirePending(lease)
        let old = try XCTUnwrap(oldView)
        task.cancel()
        do { try await task.value; XCTFail("Cancelled preparation must not authorize cache removal") }
        catch { XCTAssertTrue(error is CancellationError) }
        XCTAssertFalse(lease.isPreparing)
        XCTAssertFalse(lease.ownsView)
        lease.webView(old, didFinish: nil)
        lease.webViewWebContentProcessDidTerminate(old)
        XCTAssertFalse(lease.isPreparing)
        XCTAssertFalse(lease.ownsView)
    }

    func testDuplicateCompletionResumesOnlyOnceAndCloseIsIdempotent() async throws {
        let lease = CacheCleanupWarmLease(profile: .nonPersistent())
        var oldView: WKWebView?
        let task = Task { @MainActor in
            defer { lease.close() }
            try await lease.prepare(before: Date().addingTimeInterval(15)) { oldView = $0 }
        }
        try await requirePending(lease)
        let old = try XCTUnwrap(oldView)
        lease.webView(old, didFinish: nil)
        lease.webView(old, didFinish: nil)
        try await task.value
        lease.close()
        lease.webView(old, didFail: nil, withError: NSError(domain: "Synthetic", code: 1))
        XCTAssertFalse(lease.isPreparing)
        XCTAssertFalse(lease.ownsView)
    }

    func testCloseWhilePreparingFailsClosedAndIgnoresLateSuccess() async throws {
        let lease = CacheCleanupWarmLease(profile: .nonPersistent())
        var oldView: WKWebView?
        let task = Task { @MainActor in
            defer { lease.close() }
            try await lease.prepare(before: Date().addingTimeInterval(15)) { oldView = $0 }
        }
        try await requirePending(lease)
        let old = try XCTUnwrap(oldView)
        lease.close()
        lease.webView(old, didFinish: nil)
        do { try await task.value; XCTFail("Closing a pending lease must not become success") }
        catch { /* Expected fixed private closed error; no content is logged. */ }
        XCTAssertFalse(lease.isPreparing)
        XCTAssertFalse(lease.ownsView)
    }

    private func requirePending(_ lease: CacheCleanupWarmLease) async throws {
        let deadline = Date().addingTimeInterval(2)
        while !lease.isPreparing, Date() < deadline { try await Task.sleep(nanoseconds: 10_000_000) }
        XCTAssertTrue(lease.isPreparing)
    }
}

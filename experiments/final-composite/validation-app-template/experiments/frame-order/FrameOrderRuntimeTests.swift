import CryptoKit
import Foundation
import XCTest
import UIKit
import WebKit
@testable import FlashNest

/// Opt-in diagnostic only. Keep this file outside Tests until an explicitly
/// authorized diagnostic run stages it in a disposable checkout (HARNESS.md).
///
/// These tests measure pinned Ruffle, not Adobe Flash. They assert capture
/// completeness, never that a particular nested-goto outcome is correct.
@MainActor final class FrameOrderRuntimeTests: XCTestCase {
    private static var priorCleanupFailure: String?

    func testCaptureNestedChildGoto() async throws {
        try await captureFixture(named: "nested-child-goto")
    }

    func testCaptureControlWithoutChildGoto() async throws {
        try await captureFixture(named: "control-no-child-goto")
    }

    private let pinnedRuntimeHashes = [
        "ruffle.js": "26036a94567088dfb3de88a759e8ed10a4cea07b29500af36f345eef42420098",
        "172de42e6619eac8f371.wasm": "1ed33b9b71a6b01b9aafafed660be343ffeb2d246c5d79e6425a32bf93e38207",
        "878d548199cddef07035.wasm": "af9b6a13a8f5e8d305bc3ce28a4edf3f6242df1183e8576ad4ca086e9f21eaea"
    ]

    private func captureFixture(named name: String) async throws {
        executionTimeAllowance = 120
        try XCTSkipIf(Self.priorCleanupFailure != nil,
            "A prior diagnostic could not confirm stable-port cleanup: \(Self.priorCleanupFailure ?? "")")
        let fixtures = try XCTUnwrap(Bundle(for: FrameOrderRuntimeTests.self)
            .url(forResource: "fixtures", withExtension: nil))
        let fixtureURL = fixtures.appendingPathComponent("frame-order-experiment")
            .appendingPathComponent(name + ".swf")
        let fixtureHash = try sha256(fixtureURL)
        let webRoot = try XCTUnwrap(Bundle.main.url(forResource: "Web", withExtension: nil))
        let runtime = webRoot.appendingPathComponent("runtime")
        let packageJSON = try JSONSerialization.jsonObject(with: Data(contentsOf:
            runtime.appendingPathComponent("package.json"))) as? [String: Any]
        XCTAssertEqual(packageJSON?["version"] as? String, "0.7.1")
        var observedRuntimeHashes: [String: String] = [:]
        for filename in pinnedRuntimeHashes.keys.sorted() {
            let hash = try sha256(runtime.appendingPathComponent(filename))
            observedRuntimeHashes[filename] = hash
            guard hash == pinnedRuntimeHashes[filename] else {
                XCTFail("Refusing to label another runtime as the pinned experiment: \(filename) = \(hash)")
                return
            }
        }

        let temporaryRoot = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: temporaryRoot) }
        let package = try PackageImporter(root: temporaryRoot).stageAndCommit(fixtureURL)
        let session = PlayerSession()
        let scene = try XCTUnwrap(UIApplication.shared.connectedScenes.compactMap { $0 as? UIWindowScene }.first)
        let previousKeyWindow = scene.windows.first(where: { $0.isKeyWindow })
        let window = UIWindow(windowScene: scene)
        let controller = UIViewController()
        window.rootViewController = controller
        window.makeKeyAndVisible()
        defer {
            window.isHidden = true
            previousKeyWindow?.makeKey()
        }
        await session.start(package: package, contentRoot: temporaryRoot
            .appendingPathComponent(package.id.uuidString).appendingPathComponent("content"))

        var operationalError: String?
        var snapshotError: String?
        var view: WKWebView?
        var started = false
        do {
            let activeView = try XCTUnwrap(session.webView, session.failure ?? "Missing WebView")
            view = activeView
            activeView.frame = controller.view.bounds
            activeView.autoresizingMask = [.flexibleWidth, .flexibleHeight]
            controller.view.addSubview(activeView)
            let loaded = try await waitUntil(seconds: 80) { session.isLoaded || session.failure != nil }
            if !loaded || session.failure != nil {
                operationalError = session.failure ?? "The fixture did not reach loadeddata within 80 seconds"
            } else {
                // Install before Play. The public API's trace observer is used
                // directly: production native diagnostics drop traces after
                // 20/s and retain only 60 rows, so they are NOT our trace source.
                // Hook later assignments too, in case the shell's load promise
                // finishes after loadeddata and assigns its own observer.
                let installed = try await evaluate(Self.installObserver, in: activeView,
                    before: Date().addingTimeInterval(3), operation: "install observer") as? Bool
                guard installed == true else { throw CaptureError.observerUnavailable }
                _ = try await evaluate("document.getElementById('start').click(); true", in: activeView,
                    before: Date().addingTimeInterval(3), operation: "start fixture")
                started = true
                let completed = try await waitUntilAsync(seconds: 12) { deadline in
                    let done = try await self.evaluate("Boolean(window.__frameOrderCapture?.done)", in: activeView,
                        before: min(deadline, Date().addingTimeInterval(2)), operation: "poll completion") as? Bool
                    return done == true || session.failure != nil
                }
                if !completed || session.failure != nil {
                    operationalError = session.failure ?? "No complete FO_DONE marker within the observation window"
                }
            }
        } catch {
            operationalError = String(describing: error)
        }

        // Always retain evidence of an observed outcome, including timeout,
        // verifier/runtime error, hidden view, or missed early trace. A timeout
        // is an incomplete measurement, not evidence for either frame order.
        var captureText: String?
        if let view {
            do {
                captureText = try await evaluate(Self.snapshot, in: view,
                    before: Date().addingTimeInterval(2), operation: "final snapshot") as? String
                if captureText == nil { snapshotError = "Snapshot did not return a string" }
            } catch {
                // Keep the original failure: a second error while collecting
                // evidence must not replace the operation that actually failed.
                snapshotError = String(describing: error)
            }
        } else {
            snapshotError = "No WebView was available for a snapshot"
        }
        let captureData = captureText?.data(using: .utf8)
        let capture = captureData.flatMap { try? JSONSerialization.jsonObject(with: $0) } as? [String: Any]
        let rows = capture?["traces"] as? [[String: Any]] ?? []
        let lines = rows.compactMap { $0["line"] as? String }
        let report: [String: Any] = [
            "fixture": name,
            "fixtureSHA256": fixtureHash,
            "runtimeVersion": packageJSON?["version"] as? String ?? "unknown",
            "runtimeSHA256": observedRuntimeHashes,
            "pinnedSourceCommit": "89a7049965f3090e706265670df309a5128233ac",
            "timestampUTC": ISO8601DateFormatter().string(from: Date()),
            "platform": UIDevice.current.systemName + " " + UIDevice.current.systemVersion,
            "purpose": "Measure original fixture on pinned Ruffle; no Adobe reference run; no user-game causality claim",
            "assertionScope": "Capture completeness only; target/closed/open trace ordering is not asserted",
            "started": started,
            "attachedToWindow": view?.window != nil,
            "sceneActivationState": scene.activationState.rawValue,
            "operationalError": (operationalError as Any?) ?? NSNull(),
            "snapshotError": (snapshotError as Any?) ?? NSNull(),
            "sessionDiagnostics": session.diagnostics,
            "capture": capture ?? ["snapshotUnavailable": true],
            "observations": [
                "targetTraceSeen": lines.contains { $0.hasPrefix("FO_P2_TARGET") },
                "closedStopTraceSeen": lines.contains { $0.hasPrefix("FO_B_CLOSED_STOP") },
                "openingTraceSeen": lines.contains { $0.hasPrefix("FO_B_OPENING") }
            ]
        ]
        // No throwing path after starting the session may bypass the awaited
        // server drain below. Retain even a JSON-serialization failure as text.
        let reportData = try? JSONSerialization.data(withJSONObject: report, options: [.prettyPrinted, .sortedKeys])
        let reportText = reportData.map { String(decoding: $0, as: UTF8.self) }
            ?? "Report serialization failed. Original error: \(operationalError ?? "none"); snapshot error: \(snapshotError ?? "none"); report: \(report)"
        let attachment = XCTAttachment(string: reportText)
        attachment.name = "frame-order-\(name).json"
        attachment.lifetime = .keepAlways
        add(attachment)
        let rawAttachment = XCTAttachment(string: lines.joined(separator: "\n") + "\n")
        rawAttachment.name = "frame-order-\(name).trace.txt"
        rawAttachment.lifetime = .keepAlways
        add(rawAttachment)
        print("FRAME_ORDER_CAPTURE_BEGIN \(name)\n\(reportText)\nFRAME_ORDER_CAPTURE_END \(name)")

        // Evidence is retained before cleanup, even if WebKit is unresponsive.
        // stop() alone is asynchronous and races reuse of the stable port.
        // closeWithoutSaving awaits LoopbackServer.stopAndWait (5-second bound)
        // on success AND every caught load/JS/snapshot failure above.
        var cleanupError: String?
        do {
            try await session.closeWithoutSaving()
        } catch {
            cleanupError = String(describing: error)
            Self.priorCleanupFailure = cleanupError
        }
        let cleanupText = "fixture=\(name); serverDrained=\(cleanupError == nil); cleanupError=\(cleanupError ?? "none"); originalOperationalError=\(operationalError ?? "none"); snapshotError=\(snapshotError ?? "none")"
        let cleanupAttachment = XCTAttachment(string: cleanupText)
        cleanupAttachment.name = "frame-order-\(name).cleanup.txt"
        cleanupAttachment.lifetime = .keepAlways
        add(cleanupAttachment)
        print("FRAME_ORDER_CLEANUP \(cleanupText)")

        XCTAssertNil(operationalError, "Incomplete diagnostic capture; inspect retained JSON and raw traces")
        XCTAssertNil(snapshotError, "Evidence snapshot unavailable; original failure retained separately")
        XCTAssertNil(cleanupError, "The stable-port server did not confirm drainage before the next test")
        XCTAssertNotNil(reportData, "Evidence could not be serialized as JSON; fallback text retained")
        XCTAssertEqual(capture?["overflow"] as? Bool, false, "Trace buffer overflow: the observation is incomplete")
        XCTAssertEqual(capture?["truncatedLines"] as? Int, 0, "Trace payload truncated: the observation is incomplete")
        XCTAssertTrue(lines.contains { $0.hasPrefix("FO_P1_BEGIN") }, "First parent script marker missing; do not infer an execution order")
        let states = lines.filter { $0.hasPrefix("FO_STATE ") }.compactMap { Int($0.split(separator: " ").dropFirst().first ?? "") }
        XCTAssertEqual(states, Array(1...12), "The independent 12-enterFrame observation was not captured completely")
        XCTAssertTrue(lines.contains { $0.hasPrefix("FO_DONE 12 ") }, "Missing complete tick-12 marker")
        // Deliberately no assertion about FO_P2_TARGET, FO_P3_REACHED,
        // FO_B_CLOSED_STOP, FO_B_OPENING, parent/child frames, or isPlaying.
    }

    private enum CaptureError: Error {
        case observerUnavailable
        case javascriptTimedOut(String)
    }

    /// Use the longstanding callback API rather than an unbounded async WebKit
    /// overlay. Both the deadline and callback settle on MainActor; only the
    /// winner resumes the continuation, so a late callback after timeout is safe.
    /// This mirrors the production SaveWebKitBridge deadline pattern. Do not use
    /// a task group here: cancelling a child awaiting WebKit need not end it.
    private func evaluate(_ script: String, in view: WKWebView, before deadline: Date,
                          operation: String) async throws -> Any {
        let remaining = deadline.timeIntervalSinceNow
        guard remaining > 0 else { throw CaptureError.javascriptTimedOut(operation) }
        try Task.checkCancellation()
        return try await withCheckedThrowingContinuation { (continuation: CheckedContinuation<Any, Error>) in
            var completed = false
            view.evaluateJavaScript(script) { value, error in
                Task { @MainActor in
                    guard !completed else { return }
                    completed = true
                    if let error { continuation.resume(throwing: error) }
                    else { continuation.resume(returning: value ?? NSNull()) }
                }
            }
            Task { @MainActor in
                try? await Task.sleep(nanoseconds: UInt64(remaining * 1_000_000_000))
                guard !completed else { return }
                completed = true
                continuation.resume(throwing: CaptureError.javascriptTimedOut(operation))
            }
        }
    }

    private func waitUntil(seconds: TimeInterval, condition: () -> Bool) async throws -> Bool {
        let deadline = Date().addingTimeInterval(seconds)
        while Date() < deadline {
            if condition() { return true }
            try await Task.sleep(nanoseconds: 100_000_000)
        }
        return condition()
    }

    private func waitUntilAsync(seconds: TimeInterval, condition: (Date) async throws -> Bool) async throws -> Bool {
        let deadline = Date().addingTimeInterval(seconds)
        while Date() < deadline {
            if try await condition(deadline) { return true }
            try await Task.sleep(nanoseconds: 100_000_000)
        }
        // Never start one final unbounded JS evaluation after the deadline.
        return false
    }

    private func sha256(_ url: URL) throws -> String {
        let handle = try FileHandle(forReadingFrom: url)
        defer { try? handle.close() }
        var digest = SHA256()
        while let data = try handle.read(upToCount: 1_048_576), !data.isEmpty { digest.update(data: data) }
        return digest.finalize().map { String(format: "%02x", $0) }.joined()
    }

    private static let installObserver = """
    (() => {
      const player = document.querySelector('ruffle-player');
      if (!player || typeof player.ruffle !== 'function') return false;
      const api = player.ruffle();
      const proto = Object.getPrototypeOf(api);
      const descriptor = Object.getOwnPropertyDescriptor(proto, 'traceObserver');
      if (!descriptor?.set || !descriptor.configurable) return false;
      const capture = window.__frameOrderCapture = {
        traces: [], overflow: false, truncatedLines: 0, done: false,
        observerInstalls: 0, startedAt: performance.now()
      };
      function observe(message) {
        const text = String(message);
        if (capture.traces.length >= 512) { capture.overflow = true; return; }
        if (text.length > 2048) capture.truncatedLines++;
        capture.traces.push({sequence: capture.traces.length + 1,
          elapsedMS: performance.now() - capture.startedAt, line: text.slice(0, 2048)});
        if (/^FO_DONE 12 \\d+ \\d+$/.test(text)) capture.done = true;
      }
      // Only this isolated diagnostic WebView's public observer setter is
      // wrapped. No SWF code, timeline state, or bundled source is modified.
      Object.defineProperty(proto, 'traceObserver', {...descriptor, set(observer) {
        capture.observerInstalls++;
        descriptor.set.call(this, message => {
          observe(message);
          if (typeof observer === 'function') observer(message);
        });
      }});
      api.traceObserver = () => {};
      return true;
    })();
    """

    private static let snapshot = """
    JSON.stringify({
      ...window.__frameOrderCapture,
      hidden: document.hidden,
      readyState: document.readyState,
      status: document.getElementById('status')?.textContent,
      startDisabled: document.getElementById('start')?.disabled
    });
    """
}

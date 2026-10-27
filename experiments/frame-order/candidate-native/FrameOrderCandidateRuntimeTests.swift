import CryptoKit
import Foundation
import XCTest
import UIKit
import WebKit
@testable import FlashNest

/// Opt-in experimental derivative validation, NOT the official 0.7.1 harness.
/// The original capture harness remains unchanged. A generated compiled SHA
/// authenticates the artifact-derived pin before any candidate bytes execute.
/// Capture completeness and frozen experimental sequence contracts are distinct.
/// These original fixtures are not Adobe-reference outputs or user-game proof.
@MainActor final class FrameOrderCandidateRuntimeTests: XCTestCase {
    private static var priorCleanupFailure: String?

    func testCandidateNestedRepairContract() async throws {
        guard let observation = try await captureFixture(named: "nested-child-goto"), observation.captureComplete else { return }
        XCTAssertTrue(observation.contractPassed,
            "Experimental repair contract failed (not an Adobe assertion): \(observation.contractReason)")
    }

    func testCandidateControlContract() async throws {
        guard let observation = try await captureFixture(named: "control-no-child-goto"), observation.captureComplete else { return }
        XCTAssertTrue(observation.contractPassed,
            "Unchanged recorded control contract failed: \(observation.contractReason)")
    }

    private struct Observation {
        let captureComplete: Bool
        let contractPassed: Bool
        let contractReason: String
    }

    private func captureFixture(named name: String) async throws -> Observation? {
        executionTimeAllowance = 120
        try XCTSkipIf(Self.priorCleanupFailure != nil,
            "A prior diagnostic could not confirm stable-port cleanup: \(Self.priorCleanupFailure ?? "")")
        let resource = try XCTUnwrap(Bundle(for: FrameOrderCandidateRuntimeTests.self)
            .url(forResource: "frame-order-candidate", withExtension: nil))
        let webRoot = try XCTUnwrap(Bundle.main.url(forResource: "Web", withExtension: nil))
        let pin: [String: Any]
        let expectedLines: [String]
        do {
            (pin, expectedLines) = try attest(resource: resource, webRoot: webRoot, fixture: name)
        } catch {
            let text = "CANDIDATE_ATTESTATION_FAILED \(name): \(error). Candidate execution refused."
            let attachment = XCTAttachment(string: text)
            attachment.name = "candidate-\(name).attestation-failure.txt"
            attachment.lifetime = .keepAlways
            add(attachment)
            print(text)
            XCTFail(text)
            return nil
        }
        let fixtureURL = resource.appendingPathComponent(name + ".swf")
        let fixtureHash = try sha256(fixtureURL)
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
        let sequences = rows.compactMap { $0["sequence"] as? Int }
        let rowsIntact = rows.count == lines.count && sequences == rows.indices.map { $0 + 1 }
        let stateLines = lines.filter { $0.hasPrefix("FO_STATE ") }
        let states = stateLines.compactMap { Int($0.split(separator: " ").dropFirst().first ?? "") }
        let stateRowsIntact = stateLines.count == states.count && stateLines.allSatisfy {
            $0.range(of: "^FO_STATE [0-9]+ [0-9]+ [0-9]+$", options: .regularExpression) != nil
        }
        let captureComplete = operationalError == nil && snapshotError == nil &&
            (capture?["overflow"] as? Bool) == false && (capture?["truncatedLines"] as? Int) == 0 &&
            rowsIntact && stateRowsIntact &&
            lines.contains { $0.hasPrefix("FO_P1_BEGIN") } && states == Array(1...12) &&
            lines.filter { $0.hasPrefix("FO_DONE 12 ") }.count == 1
        let contract = captureComplete ? compareContract(lines, expected: expectedLines) : [
            "passed": false, "status": "not-evaluated-capture-incomplete",
            "reason": "A complete capture is required before judging the experimental contract"
        ] as [String: Any]
        let report: [String: Any] = [
            "fixture": name,
            "fixtureSHA256": fixtureHash,
            "runtimeKind": "flashnest-frame-order-experimental",
            "upstreamBaseVersion": "0.7.1",
            "experimentalVersionName": pin["experimentalVersionName"] ?? NSNull(),
            "candidatePinSHA256": FrameOrderCandidateIdentity.pinSHA256,
            "candidateLockSHA256": FrameOrderCandidateIdentity.lockSHA256,
            "attestation": pin,
            "captureComplete": captureComplete,
            "experimentalContract": contract,
            "timestampUTC": ISO8601DateFormatter().string(from: Date()),
            "platform": UIDevice.current.systemName + " " + UIDevice.current.systemVersion,
            "purpose": "Measure an explicitly modified experimental Ruffle derivative; no Adobe reference run; no user-game causality claim",
            "assertionScope": "Capture completeness and frozen experimental repair/control contract are reported separately; neither is Adobe equivalence",
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
        attachment.name = "candidate-frame-order-\(name).json"
        attachment.lifetime = .keepAlways
        add(attachment)
        let rawAttachment = XCTAttachment(string: lines.joined(separator: "\n") + "\n")
        rawAttachment.name = "candidate-frame-order-\(name).trace.txt"
        rawAttachment.lifetime = .keepAlways
        add(rawAttachment)
        print("FRAME_ORDER_CANDIDATE_CAPTURE_BEGIN \(name)\n\(reportText)\nFRAME_ORDER_CANDIDATE_CAPTURE_END \(name)")

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
        cleanupAttachment.name = "candidate-frame-order-\(name).cleanup.txt"
        cleanupAttachment.lifetime = .keepAlways
        add(cleanupAttachment)
        print("FRAME_ORDER_CANDIDATE_CLEANUP \(cleanupText)")

        XCTAssertNil(operationalError, "Incomplete diagnostic capture; inspect retained JSON and raw traces")
        XCTAssertNil(snapshotError, "Evidence snapshot unavailable; original failure retained separately")
        XCTAssertNil(cleanupError, "The stable-port server did not confirm drainage before the next test")
        XCTAssertNotNil(reportData, "Evidence could not be serialized as JSON; fallback text retained")
        XCTAssertTrue(captureComplete, "Incomplete/corrupt capture must not silently bypass the semantic assertion")
        XCTAssertTrue(rowsIntact, "Raw trace rows or sequence numbers were lost/malformed")
        XCTAssertTrue(stateRowsIntact, "Malformed state markers must not be silently filtered")
        XCTAssertEqual(capture?["overflow"] as? Bool, false, "Trace buffer overflow: the observation is incomplete")
        XCTAssertEqual(capture?["truncatedLines"] as? Int, 0, "Trace payload truncated: the observation is incomplete")
        XCTAssertTrue(lines.contains { $0.hasPrefix("FO_P1_BEGIN") }, "First parent script marker missing; do not infer an execution order")
        XCTAssertEqual(states, Array(1...12), "The independent 12-enterFrame observation was not captured completely")
        XCTAssertTrue(lines.contains { $0.hasPrefix("FO_DONE 12 ") }, "Missing complete tick-12 marker")
        // The caller separately asserts the explicitly labeled experimental
        // sequence contract. Never reinterpret a capture failure as semantics.
        return Observation(captureComplete: captureComplete && cleanupError == nil && reportData != nil,
            contractPassed: contract["passed"] as? Bool == true,
            contractReason: contract["reason"] as? String ?? "unknown contract status")
    }

    /// The pin hash is compiled from the offline verifier's output, rather than
    /// trusting an editable manifest to authorize its own runtime file hashes.
    private func attest(resource: URL, webRoot: URL, fixture: String) throws -> ([String: Any], [String]) {
        func require(_ condition: Bool, _ message: String) throws {
            if !condition { throw CaptureError.attestationFailed(message) }
        }
        let pinURL = resource.appendingPathComponent("candidate-pin.json")
        try require(try sha256(pinURL) == FrameOrderCandidateIdentity.pinSHA256, "Pin differs from compiled identity")
        let pin = try XCTUnwrap(try JSONSerialization.jsonObject(with: Data(contentsOf: pinURL)) as? [String: Any])
        let constants = [
            "runtimeKind": "flashnest-frame-order-experimental",
            "upstreamBaseVersion": "0.7.1",
            "upstreamSourceCommit": "89a7049965f3090e706265670df309a5128233ac",
            "originalSourceSHA256": "fc229d96ab6fced20391cf810d9d89a2118803cb7f5ce48ddf6967e52e35700a",
            "patchedSourceSHA256": "af780dae48b842e0756b8cd23f50a539737d0bcbbbdca970feb90f27725e96b0",
            "patchSHA256": "de0acabdf957fccbc11966b67defd0a7f577cdc5a147db949e0a4f0e56c6331f",
            "experimentalVersionName": "FlashNest experimental Ruffle 0.7.1 frame-order guard de0acabdf957"
        ]
        try require(pin["schemaVersion"] as? Int == 1, "Unsupported candidate pin schema")
        for (key, value) in constants { try require(pin[key] as? String == value, "Unexpected candidate identity: \(key)") }
        try require(pin["lockSHA256"] as? String == FrameOrderCandidateIdentity.lockSHA256, "Lock differs from compiled identity")
        try require(try sha256(resource.appendingPathComponent("candidate.lock.json")) == FrameOrderCandidateIdentity.lockSHA256, "Bundled lock bytes changed")
        let lock = try XCTUnwrap(try JSONSerialization.jsonObject(with: Data(contentsOf:
            resource.appendingPathComponent("candidate.lock.json"))) as? [String: Any])
        let sourceBuild = try XCTUnwrap(pin["sourceBuild"] as? [String: Any])
        try require(NSDictionary(dictionary: sourceBuild).isEqual(to: lock), "Run/artifact identity differs from reviewed lock")
        try require(lock["repository"] as? String == "op233qo123/FlashNest" &&
                    lock["workflowPath"] as? String == ".github/workflows/experiment-frame-order-engine.yml", "Foreign candidate build")

        let resourceFiles = try XCTUnwrap(pin["resourceFiles"] as? [String: [String: Any]])
        let runtimeFiles = try XCTUnwrap(pin["runtimeFiles"] as? [String: [String: Any]])
        let shellFiles = try XCTUnwrap(pin["shellFiles"] as? [String: [String: Any]])
        try verifyInventory(root: resource, expected: resourceFiles, excluding: ["candidate-pin.json"])
        try verifyInventory(root: webRoot.appendingPathComponent("runtime"), expected: runtimeFiles)
        try verifyInventory(root: webRoot, expected: shellFiles, excludedPrefix: "runtime/")
        try require(runtimeFiles.keys.filter { $0.hasSuffix(".wasm") }.count == 2, "Both candidate WASM variants are required")
        let provenanceHash = try sha256(resource.appendingPathComponent("provenance.json"))
        try require(pin["provenanceSHA256"] as? String == provenanceHash && lock["provenanceSHA256"] as? String == provenanceHash,
                    "Provenance no longer matches the locked artifact")
        let provenance = try XCTUnwrap(try JSONSerialization.jsonObject(with: Data(contentsOf:
            resource.appendingPathComponent("provenance.json"))) as? [String: Any])
        try require(provenance["upstreamCommit"] as? String == constants["upstreamSourceCommit"] &&
                    provenance["patchSHA256"] as? String == constants["patchSHA256"] &&
                    provenance["modifiedFileSHA256"] as? String == constants["patchedSourceSHA256"] &&
                    provenance["originalFileSHA256"] as? String == constants["originalSourceSHA256"] &&
                    provenance["status"] as? String == "experimental-unpromoted", "Incorrect source correspondence")
        try require(try sha256(resource.appendingPathComponent("source-correspondence/core/src/display_object/movie_clip.rs")) == constants["patchedSourceSHA256"], "Patched source bytes differ")
        try require(try sha256(resource.appendingPathComponent("source-correspondence/queued-goto-guard.patch")) == constants["patchSHA256"], "Patch bytes differ")
        let versionSeal = try XCTUnwrap(pin["versionSeal"] as? [String: Any])
        try require(versionSeal["version_channel"] as? String == "flashnest-frame-order-experimental" &&
                    versionSeal["version_name"] as? String == constants["experimentalVersionName"], "Official/ambiguous version identity rejected")

        let fixtures = [
            "nested-child-goto": "ae3e561e8695a0be147e2192cd6d067eaa9462daedf92213bed86c9e4c4a4d8b",
            "control-no-child-goto": "dd85e9f2b63b32199b7d04def4efbd80ccf68fb42da63cfe987e94358c49f030"
        ]
        let expectedFixtureHash = try XCTUnwrap(fixtures[fixture], "Unknown original fixture")
        try require(try sha256(resource.appendingPathComponent(fixture + ".swf")) == expectedFixtureHash, "Original SWF changed")
        let golden = fixture == "nested-child-goto" ? "nested-repair-target.txt" : "control.txt"
        let goldenHash = fixture == "nested-child-goto" ?
            "57648847e013eb2aaa9e45a91eb0a55c66c97862defd8e3c1cd5b74ef4e3c2ae" :
            "cb1f8c5a8f0770d7ed9c92fd3219dc11294746258fa9a4ec8558c82eda9626c0"
        try require(try sha256(resource.appendingPathComponent(golden)) == goldenHash, "Frozen experimental contract changed")
        let expectations = try XCTUnwrap(pin["expectations"] as? [String: [String: Any]])
        try require(expectations[fixture]?["file"] as? String == golden && expectations[fixture]?["sha256"] as? String == goldenHash,
                    "Pin selects another semantic expectation")
        let text = try String(contentsOf: resource.appendingPathComponent(golden), encoding: .utf8)
        try require(text.hasSuffix("\n"), "Frozen trace lacks final newline")
        var lines = text.components(separatedBy: "\n")
        lines.removeLast()
        return (pin, lines)
    }

    private func verifyInventory(root: URL, expected: [String: [String: Any]],
                                 excluding: Set<String> = [], excludedPrefix: String? = nil) throws {
        func require(_ condition: Bool, _ message: String) throws {
            if !condition { throw CaptureError.attestationFailed(message) }
        }
        let keys: Set<URLResourceKey> = [.isRegularFileKey, .isDirectoryKey, .isSymbolicLinkKey, .fileSizeKey]
        let enumerator = try XCTUnwrap(FileManager.default.enumerator(at: root,
            includingPropertiesForKeys: Array(keys)))
        let prefix = root.standardizedFileURL.path + "/"
        var observed = Set<String>()
        for case let url as URL in enumerator {
            let values = try url.resourceValues(forKeys: keys)
            try require(values.isSymbolicLink != true, "Bundled symlink rejected")
            if values.isDirectory == true { continue }
            try require(values.isRegularFile == true && url.standardizedFileURL.path.hasPrefix(prefix), "Unexpected bundled file type/path")
            let name = String(url.standardizedFileURL.path.dropFirst(prefix.count))
            if excluding.contains(name) || excludedPrefix.map({ name.hasPrefix($0) }) == true { continue }
            try require(!name.hasPrefix("/") && !name.contains("\\") && !name.contains(":") &&
                        !name.split(separator: "/", omittingEmptySubsequences: false).contains(where: { $0.isEmpty || $0 == "." || $0 == ".." }), "Noncanonical bundled path")
            let row = try XCTUnwrap(expected[name], "Unlisted bundled candidate file: \(name)")
            let size = try XCTUnwrap(row["bytes"] as? Int)
            let hash = try XCTUnwrap(row["sha256"] as? String)
            try require(values.fileSize == size && size >= 0, "Candidate file size mismatch: \(name)")
            try require(try sha256(url) == hash, "Candidate file hash mismatch: \(name)")
            observed.insert(name)
        }
        try require(observed == Set(expected.keys), "Candidate files are missing or unexpected")
    }

    /// No filtering, sorting, or searching past a surprising row. The first
    /// complete tick-12 frame consists of the exact prefix through FO_DONE and
    /// its immediately queued LOOP/OPEN pair. Later complete loop pairs are
    /// recorded explicitly; FO_DONE itself is not a settled-state observation.
    private func compareContract(_ lines: [String], expected: [String]) -> [String: Any] {
        func failure(_ reason: String) -> [String: Any] {
            ["passed": false, "status": "mismatch", "reason": reason,
             "expectationKind": "experimental repair/unchanged-control contract, not Adobe output"]
        }
        let boundaries = lines.indices.filter { lines[$0].hasPrefix("FO_DONE ") }
        guard boundaries.count == 1, let boundary = boundaries.first,
              lines[boundary].hasPrefix("FO_DONE 12 ") else { return failure("Missing/repeated/invalid tick-12 boundary") }
        let end = boundary + 3
        guard lines.count >= end && Array(lines[(boundary + 1)..<end]) == ["FO_B_LOOP 7", "FO_B_OPENING 5"] else {
            return failure("Missing/reordered immediate post-DONE queued-script pair")
        }
        let canonical = Array(lines[..<end])
        guard canonical == expected else { return failure("Exact experimental sequence differs; no pre-DONE rows were discarded") }
        let tail = Array(lines[end...])
        guard tail.count.isMultiple(of: 2) && stride(from: 0, to: tail.count, by: 2).allSatisfy({
            tail[$0] == "FO_B_LOOP 7" && tail[$0 + 1] == "FO_B_OPENING 5"
        }) else { return failure("Unexpected post-window trace tail; full raw trace retained") }
        return ["passed": true, "status": "matched-experimental-contract", "reason": "Exact first complete tick-12 window matched",
                "expectationKind": "experimental repair/unchanged-control contract, not Adobe output",
                "canonicalRowCount": canonical.count, "canonicalLines": canonical,
                "postWindowLoopPairs": tail.count / 2, "postWindowTail": tail]
    }

    private enum CaptureError: Error {
        case attestationFailed(String)
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

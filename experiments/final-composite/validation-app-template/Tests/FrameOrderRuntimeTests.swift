import CryptoKit
import Foundation
import XCTest
import UIKit
import WebKit
@testable import FlashNest

/// Default regression for the exact bundled FlashNest experimental derivative.
/// Intentionally repeats only the measured diagnostic's capture mechanics:
/// the standalone provenance/source attestor and historical oracle remain
/// unchanged. Observer JS and sequence boundaries are checked for equivalence.
/// These original fixtures are neither Adobe goldens nor proof about a user game.
@MainActor final class FrameOrderRuntimeTests: XCTestCase {
    // Generated from the reviewed, shipped identity bytes, not from runtime input.
    private static let identitySHA256 = "bdb97b8e97e3c1bb0213d83ea5c541891643454cea347961c60038670d0f06dd"
    private static var priorCleanupFailure: String?

    func testNestedChildGotoPreservesParentTarget() async throws {
        try await exercise("nested-child-goto")
    }

    func testControlPreservesRecordedFrameOrder() async throws {
        try await exercise("control-no-child-goto")
    }

    private enum Failure: Error {
        case invalid(String)
        case javascriptTimedOut(String)
    }

    private func require(_ condition: Bool, _ message: String) throws {
        if !condition { throw Failure.invalid(message) }
    }

    private func exercise(_ name: String) async throws {
        executionTimeAllowance = 120
        try XCTSkipIf(Self.priorCleanupFailure != nil,
            "Prior regression could not confirm server drainage: \(Self.priorCleanupFailure ?? "")")
        let resources = try XCTUnwrap(Bundle(for: FrameOrderRuntimeTests.self).url(forResource: "fixtures", withExtension: nil))
            .appendingPathComponent("frame-order")
        let web = try XCTUnwrap(Bundle.main.url(forResource: "Web", withExtension: nil))
        let identity: [String: Any]
        let expected: [String]
        do {
            (identity, expected) = try attest(web: web, resources: resources, fixture: name)
        } catch {
            retain("Runtime execution refused: \(error)", name: name + ".attestation-failure.txt")
            throw error
        }
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: root) }
        let fixture = resources.appendingPathComponent(name + ".swf")
        let package = try PackageImporter(root: root).stageAndCommit(fixture)
        let session = PlayerSession()
        let scene = try XCTUnwrap(UIApplication.shared.connectedScenes.compactMap { $0 as? UIWindowScene }.first)
        let previousKeyWindow = scene.windows.first(where: { $0.isKeyWindow })
        let window = UIWindow(windowScene: scene)
        let controller = UIViewController()
        window.rootViewController = controller
        window.makeKeyAndVisible()
        defer { window.isHidden = true; previousKeyWindow?.makeKey() }
        await session.start(package: package, contentRoot: root
            .appendingPathComponent(package.id.uuidString).appendingPathComponent("content"))

        var operationError: String?
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
            try require(loaded && session.failure == nil, session.failure ?? "No loadeddata within 80 seconds")
            // Native diagnostics rate-limit traces; use the real public observer
            // before Play, including any late assignment by the unchanged shell.
            let installed = try await evaluate(Self.installObserver, in: activeView,
                before: Date().addingTimeInterval(3), operation: "install observer") as? Bool
            try require(installed == true, "Public trace observer unavailable")
            _ = try await evaluate("document.getElementById('start').click(); true", in: activeView,
                before: Date().addingTimeInterval(3), operation: "start fixture")
            started = true
            let completed = try await waitUntilAsync(seconds: 12) { deadline in
                let done = try await self.evaluate("Boolean(window.__frameOrderCapture?.done)", in: activeView,
                    before: min(deadline, Date().addingTimeInterval(2)), operation: "poll completion") as? Bool
                return done == true || session.failure != nil
            }
            try require(completed && session.failure == nil, session.failure ?? "No FO_DONE within 12 seconds")
        } catch { operationError = String(describing: error) }

        // No throwing path after start bypasses the awaited cleanup below.
        var snapshotText: String?
        if let view {
            do {
                snapshotText = try await evaluate(Self.snapshot, in: view,
                    before: Date().addingTimeInterval(2), operation: "final snapshot") as? String
                if snapshotText == nil { snapshotError = "Snapshot did not return a string" }
            } catch { snapshotError = String(describing: error) }
        } else { snapshotError = "No WebView available for snapshot" }
        let snapshotData = snapshotText?.data(using: .utf8)
        let capture = snapshotData.flatMap {
            try? JSONSerialization.jsonObject(with: $0)
        } as? [String: Any]
        let rows = capture?["traces"] as? [[String: Any]] ?? []
        let lines = rows.compactMap { $0["line"] as? String }
        let sequences = rows.compactMap { $0["sequence"] as? Int }
        let rowsIntact = rows.count == lines.count && sequences == rows.indices.map { $0 + 1 }
        let stateLines = lines.filter { $0.hasPrefix("FO_STATE ") }
        let states = stateLines.compactMap { Int($0.split(separator: " ").dropFirst().first ?? "") }
        let stateRowsIntact = stateLines.count == states.count && stateLines.allSatisfy {
            $0.range(of: "^FO_STATE [0-9]+ [0-9]+ [0-9]+$", options: .regularExpression) != nil
        }
        let captureComplete = operationError == nil && snapshotError == nil &&
            (capture?["overflow"] as? Bool) == false && (capture?["truncatedLines"] as? Int) == 0 &&
            rowsIntact && stateRowsIntact && states == Array(1...12) &&
            lines.contains { $0.hasPrefix("FO_P1_BEGIN") } &&
            lines.filter { $0.hasPrefix("FO_DONE 12 ") }.count == 1
        var contractError: String?
        var canonical: [String] = []
        var tail: [String] = []
        if captureComplete {
            do { (canonical, tail) = try compareContract(lines, expected: expected) }
            catch { contractError = String(describing: error) }
        } else { contractError = "Not evaluated: capture incomplete" }
        let report: [String: Any] = [
            "fixture": name, "runtimeIdentitySHA256": Self.identitySHA256,
            "runtimeIdentity": identity, "captureComplete": captureComplete,
            "contractPassed": captureComplete && contractError == nil,
            "contractError": contractError as Any? ?? NSNull(),
            "canonicalLines": canonical, "canonicalRowCount": canonical.count,
            "postWindowTail": tail, "postWindowLoopPairs": tail.count / 2,
            "assertionScope": "Bundled derivative regression, not Adobe equivalence or user-game causality",
            "timestampUTC": ISO8601DateFormatter().string(from: Date()),
            "platform": UIDevice.current.systemName + " " + UIDevice.current.systemVersion,
            "started": started, "attachedToWindow": view?.window != nil,
            "sceneActivationState": scene.activationState.rawValue,
            "operationalError": operationError as Any? ?? NSNull(),
            "snapshotError": snapshotError as Any? ?? NSNull(),
            "sessionDiagnostics": session.diagnostics,
            "capture": capture ?? ["snapshotUnavailable": true]
        ]
        let reportData = try? JSONSerialization.data(withJSONObject: report, options: [.prettyPrinted, .sortedKeys])
        let reportText = reportData.map { String(decoding: $0, as: UTF8.self) }
            ?? "JSON serialization failed; operation=\(operationError ?? "none"); snapshot=\(snapshotError ?? "none"); report=\(report)"
        retain(reportText, name: name + ".json")
        retain(lines.joined(separator: "\n") + "\n", name: name + ".trace.txt")
        print("FRAME_ORDER_REGRESSION_CAPTURE_BEGIN \(name)\n\(reportText)\nFRAME_ORDER_REGRESSION_CAPTURE_END \(name)")
        // Retain raw evidence first. stop() alone races reuse of the stable port.
        var cleanupError: String?
        do { try await session.closeWithoutSaving() }
        catch {
            cleanupError = String(describing: error)
            Self.priorCleanupFailure = cleanupError
        }
        let cleanup = "fixture=\(name); serverDrained=\(cleanupError == nil); cleanupError=\(cleanupError ?? "none")"
        retain(cleanup, name: name + ".cleanup.txt")
        print("FRAME_ORDER_REGRESSION_CLEANUP \(cleanup)")
        XCTAssertNil(operationError)
        XCTAssertNil(snapshotError)
        XCTAssertNil(cleanupError)
        XCTAssertNotNil(reportData, "Raw/fallback evidence retained, but JSON report is invalid")
        XCTAssertTrue(captureComplete, "Incomplete capture must not silently bypass semantic assertions")
        // Capture correctness and the frozen semantic sequence are separate gates.
        if captureComplete { XCTAssertNil(contractError, "Exact frame-order regression contract failed") }
    }

    private func attest(web: URL, resources: URL, fixture: String) throws -> ([String: Any], [String]) {
        let identityURL = web.appendingPathComponent("runtime-identity.json")
        let identityType = try identityURL.resourceValues(forKeys: [.isRegularFileKey, .isSymbolicLinkKey])
        try require(identityType.isRegularFile == true && identityType.isSymbolicLink != true, "Invalid runtime identity file")
        try require(try sha256(identityURL) == Self.identitySHA256, "Runtime identity differs from compiled pin")
        let identity = try XCTUnwrap(try JSONSerialization.jsonObject(with: Data(contentsOf: identityURL)) as? [String: Any])
        try require(identity["schemaVersion"] as? Int == 2, "Unsupported runtime identity")
        let fixed = [
            "runtimeKind": "flashnest-audio-recovery-experimental",
            "upstreamBaseVersion": "0.7.1",
            "experimentalVersionName": "FlashNest experimental Ruffle 0.7.1 audio-recovery 3eea9c1603f4",
            "upstreamSourceCommit": "89a7049965f3090e706265670df309a5128233ac",
            "buildSourceCommit": "5d2cdcc6757d65194bd55c4a0395b76b0176d224",
            "patchSetSHA256": "3eea9c1603f46966d4de835325484d5433d8999998e6fb9baadf98c56b9fab2e",
            "artifactArchiveSHA256": "3befcb048669c074a017e2bfb6d3ccc283028ef90d7960695bbf0964a2634e9a",
            "provenanceSHA256": "01838aff92eb05cde33babb8153c82de2d9c2889a2795c2f2f2c72a65e3eed59"
        ]
        for (key, value) in fixed { try require(identity[key] as? String == value, "Runtime identity mismatch: \(key)") }
        try require(identity["buildRunID"] as? Int == 40614335019, "Runtime build run mismatch")
        let patches = try XCTUnwrap(identity["patches"] as? [[String: String]])
        let expectedPatches: [[String: String]] = [
            ["path": "experiments/frame-order/engine-patch/queued-goto-guard.patch", "sha256": "de0acabdf957fccbc11966b67defd0a7f577cdc5a147db949e0a4f0e56c6331f"],
            ["path": "experiments/audio-lifecycle/engine-patch/audio-lifecycle.patch", "sha256": "89dfadc1b9d113adb01f08582237559c71a5c0e04fe712cb0e31d80f077b07b9"],
            ["path": "experiments/audio-recovery/audio-recovery.patch", "sha256": "631027394ab35c7ff5b8bd1da1402a649c38e913dd2b788d1a9ef514fc6aee60"]
        ]
        try require(patches == expectedPatches, "Ordered runtime patch set differs")
        let sources = try XCTUnwrap(identity["modifiedSources"] as? [[String: Any]])
        let expectedSources: [(path: String, original: String?, modified: String, bytes: Int)] = [
            ("core/src/display_object/movie_clip.rs", "fc229d96ab6fced20391cf810d9d89a2118803cb7f5ce48ddf6967e52e35700a", "af780dae48b842e0756b8cd23f50a539737d0bcbbbdca970feb90f27725e96b0", 189360),
            ("web/packages/core/src/internal/audio-operation.ts", nil, "32986bab21da5cc3417ce2b67dfd6a3f829fa2b5c5910805e4a833fb1843a2cb", 6286),
            ("web/packages/core/src/internal/player/inner.tsx", "3161d60d8470c23cb93b99efcb4027ec53854ef6c7a304f2d7127ecaca1d8120", "657d499e59031824cc1e976fa21f3b74d72f9d855ff7a0e3f016676932b3df77", 92823),
            ("web/packages/core/src/ruffle-imports.ts", "d27cfb70999e57de053cc8caf6a5c7a925affa7a77059342319da039d0fbcb5e", "0cd19f0f895e3a3534dbb4ec29567cc569e871b8d8b4593b367fc35455f31111", 1652),
            ("web/src/audio.rs", "0cca2bc14a593060a233ec68a2ae725efc381c9068626a92a82c67a3bc732b8b", "e03078285ccccc4734837f6bb79559e008a307e7acd2a0d6649c617d1dcb9dc1", 12785)
        ]
        try require(sources.count == expectedSources.count, "Modified source inventory differs")
        for (source, expected) in zip(sources, expectedSources) {
            try require(Set(source.keys) == Set(["path", "originalSHA256", "modifiedSHA256", "bytes"]), "Unexpected source record fields")
            try require(source["path"] as? String == expected.path &&
                source["modifiedSHA256"] as? String == expected.modified &&
                source["bytes"] as? Int == expected.bytes, "Modified source record differs")
            if let original = expected.original {
                try require(source["originalSHA256"] as? String == original, "Original source digest differs")
            } else {
                try require(source["originalSHA256"] is NSNull, "New source must have null original digest")
            }
        }
        let files = try XCTUnwrap(identity["runtimeFiles"] as? [String: [String: Any]])
        try require(files.count == 12 && files.keys.filter { $0.hasSuffix(".wasm") }.count == 2,
                    "Expected complete dual-WASM runtime inventory")
        try verifyInventory(root: web.appendingPathComponent("runtime"), expected: files)
        let originals = [
            "nested-child-goto": ("ae3e561e8695a0be147e2192cd6d067eaa9462daedf92213bed86c9e4c4a4d8b",
                "nested-repair-target.txt", "57648847e013eb2aaa9e45a91eb0a55c66c97862defd8e3c1cd5b74ef4e3c2ae"),
            "control-no-child-goto": ("dd85e9f2b63b32199b7d04def4efbd80ccf68fb42da63cfe987e94358c49f030",
                "control.txt", "cb1f8c5a8f0770d7ed9c92fd3219dc11294746258fa9a4ec8558c82eda9626c0")
        ]
        let original = try XCTUnwrap(originals[fixture], "Unknown original fixture")
        try require(try sha256(resources.appendingPathComponent(fixture + ".swf")) == original.0, "Original SWF changed")
        let golden = resources.appendingPathComponent(original.1)
        try require(try sha256(golden) == original.2, "Frozen regression sequence changed")
        let text = try String(contentsOf: golden, encoding: .utf8)
        try require(text.hasSuffix("\n"), "Frozen trace lacks final newline")
        var expected = text.components(separatedBy: "\n")
        expected.removeLast()
        return (identity, expected)
    }

    private func verifyInventory(root: URL, expected: [String: [String: Any]]) throws {
        let keys: Set<URLResourceKey> = [.isRegularFileKey, .isDirectoryKey, .isSymbolicLinkKey, .fileSizeKey]
        let rootType = try root.resourceValues(forKeys: keys)
        try require(rootType.isDirectory == true && rootType.isSymbolicLink != true, "Invalid runtime directory")
        let enumerator = try XCTUnwrap(FileManager.default.enumerator(at: root, includingPropertiesForKeys: Array(keys)))
        let prefix = root.standardizedFileURL.path + "/"
        var observed = Set<String>()
        for case let url as URL in enumerator {
            let values = try url.resourceValues(forKeys: keys)
            try require(values.isSymbolicLink != true, "Runtime symlink rejected")
            if values.isDirectory == true { continue }
            try require(values.isRegularFile == true && url.standardizedFileURL.path.hasPrefix(prefix), "Invalid runtime file")
            let name = String(url.standardizedFileURL.path.dropFirst(prefix.count))
            try require(!name.contains("\\") && !name.contains(":") &&
                !name.split(separator: "/", omittingEmptySubsequences: false).contains(where: { $0.isEmpty || $0 == "." || $0 == ".." }), "Noncanonical runtime path")
            let row = try XCTUnwrap(expected[name], "Unlisted runtime file: \(name)")
            let size = try XCTUnwrap(row["bytes"] as? Int)
            let hash = try XCTUnwrap(row["sha256"] as? String)
            try require(size >= 0 && values.fileSize == size, "Runtime size mismatch: \(name)")
            try require(try sha256(url) == hash, "Runtime hash mismatch: \(name)")
            observed.insert(name)
        }
        try require(observed == Set(expected.keys), "Runtime files missing or unexpected")
    }

    private func compareContract(_ lines: [String], expected: [String]) throws -> ([String], [String]) {
        let boundaries = lines.indices.filter { lines[$0].hasPrefix("FO_DONE ") }
        try require(boundaries.count == 1, "Missing/repeated completion boundary")
        let boundary = boundaries[0]
        try require(lines[boundary].hasPrefix("FO_DONE 12 "), "Invalid tick-12 boundary")
        let end = boundary + 3
        try require(lines.count >= end, "Missing queued scripts after FO_DONE")
        try require(Array(lines[(boundary + 1)..<end]) == ["FO_B_LOOP 7", "FO_B_OPENING 5"], "Reordered immediate post-DONE scripts")
        // FO_DONE is emitted inside ENTER_FRAME, before queued child scripts.
        // Never filter unexpected rows or treat DONE as a settled final state.
        let canonical = Array(lines[..<end])
        try require(canonical == expected, "Exact first complete tick-12 window differs")
        let tail = Array(lines[end...])
        try require(tail.count.isMultiple(of: 2) && stride(from: 0, to: tail.count, by: 2).allSatisfy {
            tail[$0] == "FO_B_LOOP 7" && tail[$0 + 1] == "FO_B_OPENING 5"
        }, "Unexpected post-window trace tail")
        return (canonical, tail)
    }

    private func retain(_ text: String, name: String) {
        let attachment = XCTAttachment(string: text)
        attachment.name = "frame-order-" + name
        attachment.lifetime = .keepAlways
        add(attachment)
    }

    // Callback + deadline settle on MainActor; a late callback cannot resume twice.
    // Cancellation of a task group alone does not terminate a hung WebKit call.
    private func evaluate(_ script: String, in view: WKWebView, before deadline: Date,
                          operation: String) async throws -> Any {
        let remaining = deadline.timeIntervalSinceNow
        guard remaining > 0 else { throw Failure.javascriptTimedOut(operation) }
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
                continuation.resume(throwing: Failure.javascriptTimedOut(operation))
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
        return false
    }

    private func sha256(_ url: URL) throws -> String {
        let handle = try FileHandle(forReadingFrom: url)
        defer { try? handle.close() }
        var digest = SHA256()
        while let data = try handle.read(upToCount: 1_048_576), !data.isEmpty { digest.update(data: data) }
        return digest.finalize().map { String(format: "%02x", $0) }.joined()
    }

    // Observer/snapshot literals below are byte-identical to the measured
    // standalone candidate harness, including buffer and per-line limits.
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

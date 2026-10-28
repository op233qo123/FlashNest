import XCTest
import UIKit
import WebKit
@testable import FlashNest

/// Test-only addition: real synthetic AVM1 SharedObject bytes across settings,
/// pause/background methods and reopen. Not trusted audio or OS Home evidence.
@MainActor final class NativeSaveSettingsPreservationTests: XCTestCase {
    private enum Failure: Error { case fixture(String), javascriptDeadline }

    func testNonemptySOLBytesSurviveSamplingRendererChangesPauseBackgroundAndReopen() async throws {
        executionTimeAllowance = 180
        let deadline = Date().addingTimeInterval(160)
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        let packages = root.appendingPathComponent("packages")
        let fixtures = try XCTUnwrap(Bundle(for: Self.self).url(forResource: "fixtures", withExtension: nil))
        var package = try PackageImporter(root: packages).stageAndCommit(fixtures.appendingPathComponent("shared-object"))
        package.selectedMovie = "explicit-flush.swf"
        let content = packages.appendingPathComponent(package.id.uuidString).appendingPathComponent("content")
        let originalFiles = try fixtureFiles(content)
        let store = SaveStore(root: root.appendingPathComponent("saves"))
        let session = PlayerSession(saveStore: store,
            incidentStore: LastSessionDiagnostics(root: root.appendingPathComponent("incidents")))
        let samplingKey = RenderSamplingSettings.preferenceKey(for: package.id)
        let rendererKey = RendererSettings.preferenceKey(for: package.id)
        let scene = try XCTUnwrap(UIApplication.shared.connectedScenes.compactMap { $0 as? UIWindowScene }.first)
        let previous = scene.windows.first(where: \.isKeyWindow)
        let window = UIWindow(windowScene: scene), controller = UIViewController()
        window.rootViewController = controller; window.makeKeyAndVisible()
        defer {
            session.stop(); window.isHidden = true; previous?.makeKey()
            UserDefaults.standard.removeObject(forKey: samplingKey)
            UserDefaults.standard.removeObject(forKey: rendererKey)
            try? FileManager.default.removeItem(at: root)
        }
        do {
            let first = try await open(session, package: package, content: content,
                                       controller: controller, expected: "undefined", deadline: deadline)
            let checkpoint = await session.checkpointWrittenSaves()
            XCTAssertTrue(checkpoint)
            let baseline = try XCTUnwrap(store.currentSnapshot(packageID: package.id))
            XCTAssertEqual(baseline.entries.count, 1)
            let object = try XCTUnwrap(baseline.entries.first)
            XCTAssertEqual(object.scope, "origin"); XCTAssertEqual(object.key, "FlashNestFixture")
            let sol = try XCTUnwrap(Data(base64Encoded: object.value))
            XCTAssertEqual(try RawSOLDocument.parse(sol).bytes, sol)
            let current = store.root.appendingPathComponent(package.id.uuidString).appendingPathComponent("current.json")
            let nativeBytes = try Data(contentsOf: current)
            let liveBefore = try await capture(first)
            XCTAssertEqual(liveBefore.entries, baseline.entries)
            let initialURL = first.url
            _ = try await evaluate("window.__saveSettingsSceneMarker = 'synthetic-same-page'; true", in: first)

            // All preferences change only future page requests. No auto-save,
            // restart, key migration or guessed live density/backend is allowed.
            for tier in RenderSamplingSettings.Mode.allCases {
                XCTAssertTrue(RenderSamplingSettings(mode: tier).save(for: package.id))
                XCTAssertTrue(RendererSettings(mode: .webgl).save(for: package.id))
                XCTAssertTrue(session.webView === first)
                XCTAssertEqual(first.url, initialURL)
                XCTAssertEqual(session.requestedSamplingSettings, RenderSamplingSettings())
                XCTAssertEqual(session.requestedRendererSettings, RendererSettings())
                XCTAssertEqual(try Data(contentsOf: current), nativeBytes)
                let live = try await capture(first)
                XCTAssertEqual(live.entries, baseline.entries)
            }
            XCTAssertTrue(RenderSamplingSettings(mode: .half).save(for: package.id))
            // Corrupt preference bytes are kept, not migrated or rewritten; the
            // save namespace remains entirely separate from both preference keys.
            let corrupt = Data("{not valid preference}".utf8)
            UserDefaults.standard.set(corrupt, forKey: samplingKey)
            XCTAssertEqual(RenderSamplingSettings.load(for: package.id), RenderSamplingSettings())
            XCTAssertEqual(UserDefaults.standard.data(forKey: samplingKey), corrupt)
            XCTAssertEqual(try Data(contentsOf: current), nativeBytes)
            XCTAssertTrue(RenderSamplingSettings(mode: .half).save(for: package.id))

            session.setPaused(true)
            for _ in 0..<2 {
                await session.suspendAndSave()
                await session.resumeAfterSuspension()
                XCTAssertTrue(session.paused, "Foreground must not override an explicit menu pause")
                XCTAssertTrue(session.webView === first)
                XCTAssertNil(session.failure); XCTAssertNil(session.saveFailure)
                XCTAssertEqual(try Data(contentsOf: current), nativeBytes)
                let marker = try await evaluate("window.__saveSettingsSceneMarker", in: first) as? String
                XCTAssertEqual(marker, "synthetic-same-page")
            }
            session.setPaused(false)
            XCTAssertFalse(session.paused)
            let afterLifecycle = try await capture(first)
            XCTAssertEqual(afterLifecycle.entries, baseline.entries)
            let closed = await session.closeAndSave()
            XCTAssertTrue(closed); XCTAssertNil(session.webView)
            XCTAssertEqual(try Data(contentsOf: current), nativeBytes)
            first.removeFromSuperview()

            package.selectedMovie = "read-only.swf"
            let second = try await open(session, package: package, content: content,
                                        controller: controller, expected: "42", deadline: deadline)
            XCTAssertFalse(first === second)
            XCTAssertEqual(session.requestedRendererSettings, RendererSettings(mode: .webgl))
            let requested = RenderSamplingSettings.runtimeValidated ? RenderSamplingSettings(mode: .half) : RenderSamplingSettings()
            XCTAssertEqual(session.requestedSamplingSettings, requested)
            XCTAssertEqual(RenderSamplingSettings.load(for: package.id).mode, .half)
            let reopened = try await capture(second)
            XCTAssertEqual(reopened.entries, baseline.entries)
            XCTAssertEqual(try Data(contentsOf: current), nativeBytes)
            XCTAssertEqual(try fixtureFiles(content), originalFiles)
            try await session.closeWithoutSaving()
        } catch {
            // Bound failure cleanup and drain the stable server port before any
            // following XCTest; never turn a cleanup failure into a passing test.
            do { try await session.closeWithoutSaving() }
            catch { XCTFail("Synthetic save-settings cleanup failed") }
            throw error
        }
    }

    private func open(_ session: PlayerSession, package: GamePackage, content: URL,
                      controller: UIViewController, expected: String, deadline: Date) async throws -> WKWebView {
        let traceStart = session.diagnostics.count
        await session.start(package: package, contentRoot: content)
        let view = try XCTUnwrap(session.webView)
        view.frame = controller.view.bounds; view.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        controller.view.addSubview(view)
        var started = false
        let end = min(deadline, Date().addingTimeInterval(65))
        while Date() < end {
            if session.failure != nil { throw Failure.fixture("Real SharedObject fixture failed") }
            if session.isLoaded && !started {
                started = true
                // Synthetic DOM activation is sufficient for this save fixture;
                // it is explicitly not a trusted native audio activation test.
                _ = try await evaluate("document.getElementById('start').click(); true", in: view)
            }
            let recent = session.diagnostics.dropFirst(min(traceStart, session.diagnostics.count))
            if recent.contains(where: { $0.contains("FLASHNEST_SAVE_READY") }) {
                guard recent.contains(where: { $0.contains("FLASHNEST_SAVE_BEFORE:" + expected) }) else {
                    throw Failure.fixture("Real SharedObject value mismatch")
                }
                return view
            }
            try await Task.sleep(nanoseconds: 100_000_000)
        }
        throw Failure.fixture("SharedObject fixture deadline")
    }

    private func capture(_ view: WKWebView) async throws -> SaveCapture {
        // Read only: do not call shutdownAndCapture merely to check live bytes.
        let object = try await evaluate("window.FlashNestSaveBridge.create({storage:localStorage, location:location.href, packageID:new URLSearchParams(location.search).get('package')}).capture()", in: view)
        return try JSONDecoder().decode(SaveCapture.self, from: JSONSerialization.data(withJSONObject: object))
    }

    private func evaluate(_ script: String, in view: WKWebView) async throws -> Any {
        try await withCheckedThrowingContinuation { continuation in
            var completed = false
            view.evaluateJavaScript(script) { value, error in
                Task { @MainActor in
                    guard !completed else { return }; completed = true
                    if let error { continuation.resume(throwing: error) }
                    else { continuation.resume(returning: value ?? NSNull()) }
                }
            }
            Task { @MainActor in
                try? await Task.sleep(nanoseconds: 3_000_000_000)
                guard !completed else { return }; completed = true
                continuation.resume(throwing: Failure.javascriptDeadline)
            }
        }
    }

    private func fixtureFiles(_ root: URL) throws -> [String: Data] {
        let enumerator = try XCTUnwrap(FileManager.default.enumerator(at: root,
            includingPropertiesForKeys: [.isRegularFileKey], options: []))
        var result: [String: Data] = [:]
        for case let file as URL in enumerator {
            if try file.resourceValues(forKeys: [.isRegularFileKey]).isRegularFile == true {
                result[String(file.path.dropFirst(root.path.count + 1))] = try Data(contentsOf: file)
            }
        }
        return result
    }
}

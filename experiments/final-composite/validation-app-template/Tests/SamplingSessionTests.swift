import XCTest
import UIKit
import WebKit
@testable import FlashNest

/// Real WK page/configuration lifecycle, not actual-sampling or OS Home/rotation proof.
/// The separate native renderer experiment covers trusted input/OS transitions.
@MainActor final class SamplingSessionTests: XCTestCase {
    private enum Failure: Error { case invalid(String), javascriptDeadline }

    func testRequestedSamplingChangesOnlyOnNewPlayerPage() async throws {
        executionTimeAllowance = 150
        let deadline = Date().addingTimeInterval(130)
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: root) }
        let fixtures = try XCTUnwrap(Bundle(for: SamplingSessionTests.self).url(forResource: "fixtures", withExtension: nil))
        let packages = root.appendingPathComponent("packages")
        let package = try PackageImporter(root: packages).stageAndCommit(
            fixtures.appendingPathComponent("frame-order/control-no-child-goto.swf"))
        let content = packages.appendingPathComponent(package.id.uuidString).appendingPathComponent("content")
        let preferenceKey = RenderSamplingSettings.preferenceKey(for: package.id)
        defer { UserDefaults.standard.removeObject(forKey: preferenceKey) }
        let store = SaveStore(root: root.appendingPathComponent("saves"))
        let session = PlayerSession(saveStore: store,
                                    incidentStore: LastSessionDiagnostics(root: root.appendingPathComponent("incidents")))
        let scene = try XCTUnwrap(UIApplication.shared.connectedScenes.compactMap { $0 as? UIWindowScene }.first)
        let oldWindow = scene.windows.first(where: { $0.isKeyWindow })
        let window = UIWindow(windowScene: scene), controller = UIViewController()
        window.rootViewController = controller; window.makeKeyAndVisible()
        defer { window.isHidden = true; oldWindow?.makeKey() }
        var originalError: Error?
        do {
            let first = try await open(session, package: package, content: content, controller: controller, deadline: deadline)
            try require(session.requestedSamplingSettings == RenderSamplingSettings(), "Initial request is not Original")
            try require(samplingQuery(first) == nil, "Original changed launch query")
            try require(session.activeRendererBackend == nil, "Requested mode was misreported as actual sampling")

            try require(RenderSamplingSettings(mode: .half).save(for: package.id), "Preference save failed")
            // Exercise the same native methods used by the scene-phase callback;
            // this is not a claim that this XCTest pressed the OS Home button.
            await session.suspendAndSave()
            await session.resumeAfterSuspension()
            session.setPaused(false)
            try require(session.webView === first, "Background return replaced the live page")
            try require(session.requestedSamplingSettings == RenderSamplingSettings(), "Preference changed the current request")
            try require(samplingQuery(first) == nil, "Preference mutated the current page URL")
            // The control fixture deliberately writes no SOL; an empty checkpoint
            // must not fabricate an archive or be mistaken for a renderer failure.
            try require(session.checkpointFailure == L10n.text("No game-written save is available yet. Existing backups were kept."),
                        "Unexpected empty-checkpoint outcome")
            try require(session.saveFailure == nil && session.failure == nil && session.checkpointDidChange == nil,
                        "Empty checkpoint changed live/save state")
            try require(try store.currentSnapshot(packageID: package.id) == nil, "Empty checkpoint created an archive")

            try await session.closeWithoutSaving()
            first.removeFromSuperview()
            try require(session.requestedSamplingSettings == nil, "Closed page retained a live request")
            let second = try await open(session, package: package, content: content, controller: controller, deadline: deadline)
            try require(second !== first, "New opening reused the old page")
            let expected = RenderSamplingSettings.runtimeValidated ? RenderSamplingSettings(mode: .half) : RenderSamplingSettings()
            try require(session.requestedSamplingSettings == expected, "New page ignored runtime validation gate")
            try require(samplingQuery(second) == expected.mode.queryValue, "Launch query bypassed runtime validation gate")
            try require(RenderSamplingSettings.load(for: package.id).mode == .half, "Gate destroyed saved preference")
            try require(session.activeRendererBackend == nil, "Public requested config is not actual sampling attestation")
        } catch { originalError = error }
        // Await real port drainage on every path; retain the first failure.
        var cleanupError: String?
        do { try await session.closeWithoutSaving() }
        catch { cleanupError = String(describing: error); if originalError == nil { originalError = error } }
        if let originalError {
            let note = XCTAttachment(string: String(describing: originalError) + "\ncleanup=" + (cleanupError ?? "drained") + "\n" + session.diagnostics.suffix(30).joined(separator: "\n"))
            note.name = "sampling-session-failure.txt"; note.lifetime = .keepAlways; add(note)
            throw originalError
        }
    }

    private func open(_ session: PlayerSession, package: GamePackage, content: URL,
                      controller: UIViewController, deadline: Date) async throws -> WKWebView {
        await session.start(package: package, contentRoot: content)
        let view = try XCTUnwrap(session.webView, session.failure ?? "No player page")
        view.frame = controller.view.bounds; view.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        controller.view.addSubview(view)
        let end = min(deadline, Date().addingTimeInterval(55))
        while !session.isLoaded && session.failure == nil && Date() < end {
            try await Task.sleep(nanoseconds: 100_000_000)
        }
        try require(session.isLoaded && session.failure == nil, session.failure ?? "Bounded page load timeout")
        return view
    }

    private func samplingQuery(_ view: WKWebView) -> String? {
        guard let url = view.url else { return nil }
        return URLComponents(url: url, resolvingAgainstBaseURL: false)?.queryItems?.first(where: { $0.name == "renderScale" })?.value
    }

    private func require(_ condition: Bool, _ message: String) throws {
        if !condition { throw Failure.invalid(message) }
    }
}

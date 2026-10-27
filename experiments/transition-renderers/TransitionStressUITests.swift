import XCTest
import UIKit

/// Isolated renderer-observation experiment. The comparison workflow mounts this
/// file in UITests; it is deliberately absent from the normal UI test target.
/// Every scene/input action goes through UIKit and the production player. A
/// persistent boot token plus advancing child state is evidence of a retained
/// live runtime, not direct inspection of a private WKWebView object pointer.
final class TransitionStressUITests: XCTestCase {
    private let fixtureTitle = "FlashNest Transition Fixture"
    private var expectedKeys = 0

    override func setUpWithError() throws {
        continueAfterFailure = false
        executionTimeAllowance = 480
        expectedKeys = 0
        XCUIDevice.shared.orientation = .portrait
    }

    func testThreeSceneLoadsWithRotationAndBackgroundPreserveLiveState() throws {
        phase("import", cycle: 0)
        let app = importFixture()
        // Do not add an extra live-player orientation change in cleanup. Earlier
        // simulator evidence showed XCTest stalling in redundant cleanup calls.
        defer { app.terminate() }
        phase("startup", cycle: 0)
        let play = app.webViews.buttons["Play / enable audio"].firstMatch
        XCTAssertTrue(play.waitForExistence(timeout: 60), "Startup gate: trusted Play must become available")
        XCTAssertTrue(wait { play.isEnabled && play.isHittable })
        try requireRenderer(phase: "startup", in: app)
        play.tap()
        let firstReady = try waitForRecord("READY", generation: 0, pointers: 0, in: app)
        let boot = firstReady.boot
        var state = try requestState(generation: 0, pointers: 0, boot: boot,
                                     phase: "initial-input", in: app)
        XCTAssertGreaterThan(state.childHeartbeat, 0, "The child must actually execute, not merely finish downloading")

        for cycle in 1...3 {
            phase("trusted-scene-advance", cycle: cycle)
            requireLiveSurface(in: app)
            // Exactly one trusted tap, never retried. The original movie's
            // center stage CLICK unloads the old child and asynchronously loads
            // its successor. Native control/menu hit regions are not here.
            app.webViews.firstMatch.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.5)).tap()
            let ready = try waitForRecord("READY", generation: cycle, pointers: cycle, in: app)
            assertIdentity(ready, generation: cycle, pointers: cycle, boot: boot)
            state = try requestState(generation: cycle, pointers: cycle, boot: boot,
                                     phase: "scene-ready", in: app)

            phase("rotate-landscape", cycle: cycle)
            XCUIDevice.shared.orientation = .landscapeLeft
            XCTAssertTrue(wait { app.frame.width > app.frame.height && app.buttons["player-menu"].isHittable },
                          "The OS must finish the real landscape transition")
            state = try requestState(generation: cycle, pointers: cycle, boot: boot,
                                     phase: "after-landscape", after: state, in: app)

            showHomeAndRequireBackground(app, cycle: cycle, label: "running-child")
            phase("activate", cycle: cycle)
            app.activate()
            XCTAssertTrue(wait { app.buttons["player-menu"].isHittable })
            state = try requestState(generation: cycle, pointers: cycle, boot: boot,
                                     phase: "after-background", after: state, in: app)

            phase("rotate-portrait", cycle: cycle)
            XCUIDevice.shared.orientation = .portrait
            XCTAssertTrue(wait { app.frame.height > app.frame.width && app.buttons["player-menu"].isHittable },
                          "The OS must finish the real portrait transition")
            state = try requestState(generation: cycle, pointers: cycle, boot: boot,
                                     phase: "after-portrait", after: state, in: app)

            if cycle == 2 {
                phase("paused-menu", cycle: cycle)
                app.buttons["player-menu"].tap()
                let resume = app.buttons["player-resume"].firstMatch
                XCTAssertTrue(resume.waitForExistence(timeout: 10) && resume.isHittable)
                showHomeAndRequireBackground(app, cycle: cycle, label: "paused-menu")
                app.activate()
                XCTAssertTrue(wait { resume.exists && resume.isHittable },
                              "Foreground must preserve the open menu, not silently resume/restart")
                resume.tap()
                state = try requestState(generation: cycle, pointers: cycle, boot: boot,
                                         phase: "after-paused-background", after: state, in: app)
            }
        }

        XCTAssertEqual(state.generation, 3)
        XCTAssertEqual(state.pointers, 3)
        XCTAssertEqual(state.unloadCalls, 3)
        XCTAssertEqual(state.unloadEvents, 3, "Require actual LoaderInfo UNLOAD callbacks, not just calls to unload()")
        XCTAssertEqual(state.keys, 14, "One initial query, four per cycle, one paused-menu query")
        XCTAssertEqual(state.errors, 0)
        phase("diagnostics", cycle: 3)
        assertNoRuntimeErrors(in: app)
        print("FLASHNEST_TRANSITION_COMPLETE cycles=3 keys=14 pointers=3 unloadCalls=3 unloadEvents=3 errors=0")
    }

    private struct Record {
        let kind: String
        let boot: String
        let generation: Int
        let rootHeartbeat: Int
        let pointers: Int
        let keys: Int
        let ready: Int
        let childGeneration: Int
        let childHeartbeat: Int
        let errors: Int
        let unloadCalls: Int
        let unloadEvents: Int

        init?(_ label: String) {
            guard let range = label.range(of: "LT|") else { return nil }
            let fields = label[range.lowerBound...].trimmingCharacters(in: .whitespacesAndNewlines)
                .split(separator: "|", omittingEmptySubsequences: false).map(String.init)
            guard fields.count == 13, fields[0] == "LT", !fields[2].isEmpty,
                  let generation = Int(fields[3]), let rootHeartbeat = Int(fields[4]),
                  let pointers = Int(fields[5]), let keys = Int(fields[6]), let ready = Int(fields[7]),
                  let childGeneration = Int(fields[8]), let childHeartbeat = Int(fields[9]),
                  let errors = Int(fields[10]), let unloadCalls = Int(fields[11]),
                  let unloadEvents = Int(fields[12]) else { return nil }
            self.kind = fields[1]; self.boot = fields[2]; self.generation = generation
            self.rootHeartbeat = rootHeartbeat; self.pointers = pointers; self.keys = keys
            self.ready = ready; self.childGeneration = childGeneration; self.childHeartbeat = childHeartbeat
            self.errors = errors; self.unloadCalls = unloadCalls; self.unloadEvents = unloadEvents
        }
    }

    private func requestState(generation: Int, pointers: Int, boot: String, phase label: String,
                              after previous: Record? = nil, in app: XCUIApplication) throws -> Record {
        phase(label, cycle: generation)
        requireLiveSurface(in: app)
        let enter = app.buttons["touch-key-default-5"].firstMatch
        XCTAssertTrue(wait { enter.exists && enter.isEnabled && enter.isHittable }, "Actual native Enter control must be usable")
        expectedKeys += 1
        enter.tap()
        let record = try waitForRecord("STATE", generation: generation, pointers: pointers,
                                       keys: expectedKeys, in: app)
        assertIdentity(record, generation: generation, pointers: pointers, boot: boot)
        XCTAssertEqual(record.keys, expectedKeys, "A fresh real key callback is required; an old trace is not evidence")
        if let previous {
            XCTAssertGreaterThan(record.rootHeartbeat, previous.rootHeartbeat, "Root must continue executing after transition")
            XCTAssertGreaterThan(record.childHeartbeat, previous.childHeartbeat, "The same loaded child must continue executing")
        }
        print("FLASHNEST_TRANSITION_STATE phase=\(label) boot=\(record.boot) generation=\(record.generation) heartbeat=\(record.rootHeartbeat) pointers=\(record.pointers) keys=\(record.keys) ready=\(record.ready) childGeneration=\(record.childGeneration) childHeartbeat=\(record.childHeartbeat) errors=\(record.errors) unloadCalls=\(record.unloadCalls) unloadEvents=\(record.unloadEvents)")
        try requireRenderer(phase: label, in: app)
        return record
    }

    /// Read only the diagnostic observer's visible output. It observes the
    /// existing context; this test never evaluates JS or requests a GL context.
    /// The external arm verifier additionally requires the exact chosen backend.
    private struct RendererObservation: Decodable {
        let backend: String
        let context: String
        let lost: Bool?
        let width: Int?
        let height: Int?
        let nativeDPR: Double
        let lossEvents: Int
        let bannerCount: Int
    }

    private func requireRenderer(phase: String, in app: XCUIApplication) throws {
        let prefix = "FLASHNEST_RENDERER "
        let output = app.webViews.staticTexts.matching(
            NSPredicate(format: "label BEGINSWITH %@", prefix)).firstMatch
        XCTAssertTrue(output.waitForExistence(timeout: 10), "Actual renderer observation must be exposed")
        let label = output.label
        XCTAssertTrue(label.hasPrefix(prefix))
        let raw = String(label.dropFirst(prefix.count)).trimmingCharacters(in: .whitespacesAndNewlines)
        XCTAssertLessThanOrEqual(raw.utf8.count, 1_024, "Observer output must remain bounded")
        // Print the observed data before validation so a failed/lost context is
        // evidence, not silently replaced by an expected backend or fresh page.
        print("FLASHNEST_RENDERER_STATE phase=\(phase) \(raw)")
        let observation = try JSONDecoder().decode(RendererObservation.self, from: Data(raw.utf8))
        XCTAssertTrue(["wgpu-webgl", "webgl"].contains(observation.backend), "No unknown or unsupported actual backend")
        XCTAssertTrue(["webgl", "webgl2", "experimental-webgl"].contains(observation.context))
        XCTAssertEqual(observation.lost, false, "Require the actual context to be alive, not merely a live SWF counter")
        let width = try XCTUnwrap(observation.width, "Actual drawing buffer width is unavailable")
        let height = try XCTUnwrap(observation.height, "Actual drawing buffer height is unavailable")
        XCTAssertTrue((1...32_768).contains(width) && (1...32_768).contains(height))
        XCTAssertTrue(observation.nativeDPR.isFinite && observation.nativeDPR > 0 && observation.nativeDPR <= 10)
        XCTAssertEqual(observation.lossEvents, 0, "Any observed context loss fails the arm, even if it later recovers")
        XCTAssertEqual(observation.bannerCount, 1, "No implicit replacement renderer instance")
    }

    private func assertIdentity(_ record: Record, generation: Int, pointers: Int, boot: String) {
        XCTAssertEqual(record.boot, boot, "A new root token means the live runtime restarted; do not accept recovery as continuity")
        XCTAssertEqual(record.generation, generation)
        XCTAssertEqual(record.childGeneration, generation, "The active child must be the expected loaded generation")
        XCTAssertEqual(record.pointers, pointers)
        XCTAssertEqual(record.ready, 1)
        XCTAssertEqual(record.errors, 0, "Original fixture reported a load/runtime error")
        XCTAssertEqual(record.unloadCalls, generation)
        XCTAssertEqual(record.unloadEvents, generation, "Require an actual unload event for every preceding scene")
    }

    private func waitForRecord(_ kind: String, generation: Int, pointers: Int, keys: Int? = nil,
                               in app: XCUIApplication) throws -> Record {
        let status = app.webViews.staticTexts.matching(NSPredicate(format: "label CONTAINS %@", "LT|" + kind + "|")).firstMatch
        var result: Record?
        let matched = wait(timeout: 25) {
            guard status.exists, let record = Record(status.label) else { return false }
            guard record.kind == kind, record.generation == generation, record.pointers == pointers,
                  keys == nil || record.keys == keys else { return false }
            result = record
            return true
        }
        if !matched {
            let context = "Missing \(kind), generation \(generation), key \(keys ?? -1)"
            // XCTest snapshot failures can abort despite continueAfterFailure.
            // Record the primary failure FIRST so secondary evidence collection
            // cannot replace it in the result, as happened in the 18.5 A/B run.
            let previousPolicy = continueAfterFailure
            continueAfterFailure = true
            defer { continueAfterFailure = previousPolicy }
            XCTFail("Missing fresh real SWF record: \(kind), generation=\(generation), pointers=\(pointers), keys=\(keys ?? -1)")
            captureAccessibility(context, in: app)
            captureFailureDiagnostics(context, in: app)
        }
        return try XCTUnwrap(result, "Missing fresh real SWF record: \(kind), generation=\(generation), pointers=\(pointers), keys=\(keys ?? -1)")
    }

    /// Best-effort evidence AFTER the unchanged record deadline has expired.
    /// Never resumes, restarts, retries the action, or substitutes for its error.
    /// XCUI actions report XCTest failures rather than Swift throws, so allow
    /// secondary capture failures locally. The primary failure is recorded
    /// before entering this helper, since a fatal XCUI snapshot may still abort.
    /// The normal journey retains continueAfterFailure=false.
    private func captureFailureDiagnostics(_ context: String, in app: XCUIApplication) {
        let previousPolicy = continueAfterFailure
        continueAfterFailure = true
        defer { continueAfterFailure = previousPolicy }
        let deadline = Date().addingTimeInterval(20)
        var notes = ["Original failure: " + context, "Evidence only; no recovery or retry"]
        var hierarchy = ""
        defer {
            let text = (notes + [hierarchy]).joined(separator: "\n")
            let evidence = XCTAttachment(string: String(text.prefix(40_000)))
            evidence.name = context + " retained native diagnostics"
            evidence.lifetime = .keepAlways; add(evidence)
            print("FLASHNEST_TRANSITION_FAILURE_DIAGNOSTICS\n" + String(text.prefix(40_000)))
        }
        let menu = app.buttons["player-menu"].firstMatch
        guard Date() < deadline, menu.exists, menu.isEnabled, menu.isHittable else {
            notes.append("Capture unavailable: native menu not interactive")
            return
        }
        menu.tap()
        let resume = app.buttons["player-resume"].firstMatch
        guard Date() < deadline, resume.exists, resume.isHittable else {
            // Never send an evidence-scroll to the live game if the native
            // menu failed to present. No game action is retried here.
            notes.append("Capture unavailable: native menu did not present")
            return
        }
        let diagnostics = app.buttons["Diagnostics"].firstMatch
        for _ in 0..<4 {
            guard Date() < deadline else { break }
            if diagnostics.exists && diagnostics.isEnabled && diagnostics.isHittable { break }
            app.swipeUp()
        }
        guard Date() < deadline, diagnostics.exists, diagnostics.isEnabled, diagnostics.isHittable else {
            notes.append("Capture unavailable: Diagnostics action not reachable within evidence budget")
            return
        }
        diagnostics.tap()
        guard Date() < deadline, app.navigationBars["Diagnostics"].exists else {
            notes.append("Capture unavailable: Diagnostics page did not open")
            return
        }
        guard Date() < deadline else {
            notes.append("Capture incomplete: evidence budget expired before snapshot")
            return
        }
        // One immutable hierarchy string avoids re-resolving stale indexed
        // StaticText elements while SwiftUI updates its live diagnostics list.
        // No evidence-only scroll; this is a partial retained-list snapshot.
        hierarchy = String(app.debugDescription.prefix(32_000))
        notes.append("Partial retained diagnostics hierarchy; no complete-history claim")
    }

    private func requireLiveSurface(in app: XCUIApplication) {
        XCTAssertTrue(app.buttons["player-menu"].exists && app.buttons["player-menu"].isHittable)
        XCTAssertTrue(app.webViews.firstMatch.exists && app.webViews.firstMatch.isHittable)
        XCTAssertFalse(app.webViews.buttons["Play / enable audio"].firstMatch.exists, "No implicit new page or title restart")
        XCTAssertFalse(app.staticTexts["Unable to play"].exists)
        XCTAssertEqual(app.alerts.count, 0, "No failure/recovery dialog may be silently dismissed by the test")
        let library = app.buttons["import-menu"].firstMatch
        XCTAssertFalse(library.exists && library.isHittable, "Player must remain the interactive foreground surface")
    }

    private func showHomeAndRequireBackground(_ app: XCUIApplication, cycle: Int, label: String) {
        phase("home-" + label, cycle: cycle)
        XCUIDevice.shared.press(.home)
        let home = XCUIApplication(bundleIdentifier: "com.apple.springboard")
        let icon = home.icons.matching(NSPredicate(format: "label == %@", "FlashNest")).firstMatch
        // Earlier 18.2 video proved Home was visible while app.state remained
        // stale. A real hittable SpringBoard icon is the background proof.
        XCTAssertTrue(icon.waitForExistence(timeout: 15))
        XCTAssertTrue(wait { icon.isHittable }, "The actual Home screen must cover the game")
        print("FLASHNEST_TRANSITION_HOME cycle=\(cycle) phase=\(label) visibleHomeIcon=true reportedAppState=\(app.state.rawValue)")
        captureAccessibility("Home \(label), cycle \(cycle)", in: home)
    }

    private func assertNoRuntimeErrors(in app: XCUIApplication) {
        requireLiveSurface(in: app)
        app.buttons["player-menu"].tap()
        let diagnostics = app.buttons["Diagnostics"].firstMatch
        for _ in 0..<7 {
            if diagnostics.exists && diagnostics.isHittable { break }
            app.swipeUp()
        }
        XCTAssertTrue(diagnostics.isHittable); diagnostics.tap()
        XCTAssertTrue(app.navigationBars["Diagnostics"].waitForExistence(timeout: 10))
        let footer = app.staticTexts.matching(NSPredicate(format: "label BEGINSWITH %@", "No external network access.")).firstMatch
        var labels = Set<String>()
        for _ in 0..<24 {
            app.staticTexts.allElementsBoundByIndex.forEach { labels.insert($0.label) }
            if footer.exists && footer.isHittable { break }
            app.swipeUp()
        }
        XCTAssertTrue(footer.exists && footer.isHittable, "Read the entire bounded diagnostics list, not just its initial visible rows")
        let text = labels.sorted().joined(separator: "\n")
        let evidence = XCTAttachment(string: text); evidence.name = "Transition complete native diagnostics"
        evidence.lifetime = .keepAlways; add(evidence)
        print("FLASHNEST_TRANSITION_DIAGNOSTICS\n" + text)
        for failure in ["Unable to load movie:", "Runtime error:", "JavaScript/resource error:",
                        "SWF fetch failed", "Renderer event: webglcontextlost", "WebContent process terminated",
                        "Web content process terminated", "Web process terminated:",
                        "The web player stopped unexpectedly.", "Saving did not finish safely", "LT|ERROR|"] {
            XCTAssertFalse(text.localizedCaseInsensitiveContains(failure), "Forbidden diagnostic: \(failure)")
        }
    }

    private func importFixture() -> XCUIApplication {
        let source = XCUIApplication(bundleIdentifier: "com.flashnest.fixture-source")
        source.launchArguments = ["-AppleLanguages", "(en)", "-AppleLocale", "en_US"]
        source.launch()
        XCTAssertTrue(source.staticTexts["source-ready"].waitForExistence(timeout: 30))
        source.terminate()
        let app = XCUIApplication()
        app.launchArguments = ["-FlashNest.language", "en", "-AppleLanguages", "(en)", "-AppleLocale", "en_US"]
        app.launch()
        LibraryNavigation.openSourceFolder(named: fixtureTitle, in: app)
        LibraryNavigation.requireEntry("sub/child.swf", in: app)
        LibraryNavigation.requireEntry("main.swf", in: app, towardTop: true).tap()
        return app
    }

    private func phase(_ name: String, cycle: Int) {
        print("FLASHNEST_TRANSITION_PHASE phase=\(name) cycle=\(cycle)")
    }

    private func captureAccessibility(_ name: String, in app: XCUIApplication) {
        let attachment = XCTAttachment(string: String(app.debugDescription.prefix(100_000)))
        attachment.name = name; attachment.lifetime = .keepAlways; add(attachment)
    }

    private func wait(timeout: TimeInterval = 15, _ condition: () -> Bool) -> Bool {
        let deadline = Date().addingTimeInterval(timeout)
        repeat {
            if condition() { return true }
            Thread.sleep(forTimeInterval: 0.2)
        } while Date() < deadline
        return false
    }
}

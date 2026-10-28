import XCTest
import UIKit
import WebKit
@testable import FlashNest

/// Real pinned Ruffle/WASM. A child movie's AVM1 Key callback, not just a DOM
/// event observer, must execute after focus has moved outside the player.
@MainActor final class InputFocusRuntimeTests: XCTestCase {
    func testVirtualKeyRefocusesPlayerAfterChildSceneAndExternalBlur() async throws {
        executionTimeAllowance = 120
        let fixtures = try XCTUnwrap(Bundle(for: InputFocusRuntimeTests.self).url(forResource: "fixtures", withExtension: nil))
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: root) }
        let package = try PackageImporter(root: root).stageAndCommit(fixtures.appendingPathComponent("input-focus"))
        XCTAssertTrue(package.movies.contains("sub/scene.swf"))
        let session = PlayerSession()
        let scene = try XCTUnwrap(UIApplication.shared.connectedScenes.compactMap { $0 as? UIWindowScene }.first)
        let previousKeyWindow = scene.windows.first(where: { $0.isKeyWindow })
        let window = UIWindow(windowScene: scene)
        let controller = UIViewController()
        window.rootViewController = controller
        window.makeKeyAndVisible()
        defer {
            session.stop(); window.isHidden = true; previousKeyWindow?.makeKey()
        }
        await session.start(package: package, contentRoot: root.appendingPathComponent(package.id.uuidString).appendingPathComponent("content"))
        let view = try XCTUnwrap(session.webView, session.failure ?? "Missing WebView")
        view.frame = controller.view.bounds
        view.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        controller.view.addSubview(view)
        guard try await waitUntil(seconds: 75, condition: { session.isLoaded }) else {
            XCTFail(session.failure ?? "Input fixture did not load: \(session.diagnostics)"); return
        }
        _ = try await view.evaluateJavaScript("document.getElementById('start').click(); true")
        guard try await waitForTrace("FOCUS_ROOT_READY", session: session) else { return }

        // A positive control: while focused, the root consumes a real bridge
        // key and loads the child SWF. The child must independently register.
        _ = try await view.evaluateJavaScript("document.querySelector('ruffle-player').focus(); true")
        session.key("Enter", down: true); session.key("Enter", down: false)
        guard try await waitForTrace("FOCUS_ROOT_KEY", session: session),
              try await waitForTrace("FOCUS_CHILD_READY", session: session) else { return }

        // Exercise the child's pointer event handler independently. This is a
        // synthetic DOM pointer through real Ruffle, not proof of UIKit routing.
        _ = try await view.evaluateJavaScript("""
        const player = document.querySelector('ruffle-player');
        const canvas = player.shadowRoot.querySelector('canvas');
        const rect = canvas.getBoundingClientRect();
        const event = {bubbles:true, composed:true, pointerId:1, pointerType:'mouse',
          isPrimary:true, button:0, clientX:rect.left + rect.width / 2,
          clientY:rect.top + rect.height / 2};
        canvas.dispatchEvent(new PointerEvent('pointerdown', {...event, buttons:1}));
        canvas.dispatchEvent(new PointerEvent('pointerup', {...event, buttons:0}));
        true;
        """)
        guard try await waitForTrace("FOCUS_CHILD_POINTER", session: session) else { return }

        // Reproduce the actual focus precondition: canvas has no tabindex and
        // focus belongs to an ordinary DOM control outside the Ruffle host.
        let blurred = try await view.evaluateJavaScript("""
        const probe = document.createElement('button');
        probe.id = 'native-focus-probe'; probe.textContent = 'Outside focus';
        document.body.append(probe); probe.focus();
        document.activeElement === probe;
        """) as? Bool
        XCTAssertEqual(blurred, true)
        let canvasTabIndex = try await view.evaluateJavaScript("document.querySelector('ruffle-player').shadowRoot.querySelector('canvas').hasAttribute('tabindex')") as? Bool
        XCTAssertEqual(canvasTabIndex, false, "Pinned canvas itself is not a focusable input target")

        // Negative control: reproduce the old bridge exactly (canvas.focus,
        // then bubbled/composed key events). It must leave focus outside and
        // must NOT reach the child's AVM1 Key listener. This establishes the
        // regression precondition before exercising the repaired bridge.
        let oldBridgeStillBlurred = try await view.evaluateJavaScript("""
        (() => {
          const target = document.querySelector('ruffle-player').shadowRoot.querySelector('canvas');
          target.focus();
          const event = {key:'b', code:'KeyB', keyCode:66, which:66,
            bubbles:true, composed:true, cancelable:true};
          target.dispatchEvent(new KeyboardEvent('keydown', event));
          target.dispatchEvent(new KeyboardEvent('keyup', event));
          return document.activeElement.id === 'native-focus-probe';
        })();
        """) as? Bool
        XCTAssertEqual(oldBridgeStillBlurred, true, "Old canvas focus must demonstrate the unfocused-host precondition")
        try await Task.sleep(nanoseconds: 1_000_000_000)
        XCTAssertFalse(session.diagnostics.contains { $0.contains("FOCUS_CHILD_KEY:66") }, "Unfocused old bridge unexpectedly reached the child listener")

        session.key("KeyA", down: true); session.key("KeyA", down: false)
        guard try await waitForTrace("FOCUS_CHILD_KEY:65", session: session) else { return }
        let refocused = try await view.evaluateJavaScript("document.activeElement === document.querySelector('ruffle-player')") as? Bool
        XCTAssertEqual(refocused, true, "Virtual keydown must restore host focus, not focus a non-focusable canvas")
        try await session.closeWithoutSaving()
    }

    private func waitForTrace(_ marker: String, session: PlayerSession) async throws -> Bool {
        let found = try await waitUntil(seconds: 8) { session.diagnostics.contains { $0.contains(marker) } }
        if !found { XCTFail("Missing real SWF trace \(marker). \(session.failure ?? "") \(session.diagnostics)") }
        return found
    }

    private func waitUntil(seconds: TimeInterval, condition: () -> Bool) async throws -> Bool {
        let deadline = Date().addingTimeInterval(seconds)
        while Date() < deadline {
            if condition() { return true }
            try await Task.sleep(nanoseconds: 100_000_000)
        }
        return condition()
    }
}

import XCTest
import UIKit

/// Real Files and trusted UIKit actions; requested mode is not backend attestation.
final class RendererCompatibilityUITests: XCTestCase {
    override func setUpWithError() throws {
        continueAfterFailure = false
        executionTimeAllowance = 360
        XCUIDevice.shared.orientation = .portrait
    }

    func testPerGameChoiceDefersUntilExplicitRestartAndPreservesLiveScene() {
        let source = XCUIApplication(bundleIdentifier: "com.flashnest.fixture-source")
        source.launchArguments = ["-AppleLanguages", "(en)", "-AppleLocale", "en_US"]
        source.launch()
        XCTAssertTrue(source.staticTexts["source-ready"].waitForExistence(timeout: 30))
        source.terminate()
        let app = XCUIApplication()
        app.launchArguments = ["-FlashNest.language", "en", "-AppleLanguages", "(en)", "-AppleLocale", "en_US"]
        app.launch()
        defer { app.terminate() }
        LibraryNavigation.openSourceFolder(named: "FlashNest Lifecycle Fixture", in: app)
        LibraryNavigation.requireEntry("sub/scene.swf", in: app)
        LibraryNavigation.requireEntry("main.swf", in: app, towardTop: true).tap()
        start(app)
        trace("LIFECYCLE_ROOT_READY:undefined", app)
        tap("touch-key-default-5", app)
        trace("LIFECYCLE_CHILD_READY", app)
        tap("touch-key-default-4", app)
        trace("LIFECYCLE_CHILD_KEY:32:1", app)

        tap("player-menu", app)
        tap("player-renderer-settings", app)
        let automatic = app.buttons["renderer-mode-automatic"].firstMatch
        reveal(automatic, app)
        XCTAssertEqual(automatic.value as? String, "Selected for next opening or reload")
        // Require the real visible warning, not merely a hidden section identifier.
        let warning = app.staticTexts["WebGL compatibility may change the picture"].firstMatch
        reveal(warning, app, upwards: false)
        XCTAssertTrue(warning.isHittable)
        let enhancedWarningText = "Enhanced rendering may show a blank screen or stop unexpectedly on some devices. Neither policy is a general crash fix, and WebGL compatibility is not guaranteed to work with every game."
        let enhancedWarning = app.staticTexts[enhancedWarningText].firstMatch
        reveal(enhancedWarning, app)
        XCTAssertTrue(enhancedWarning.isHittable)
        XCTAssertEqual(enhancedWarning.label, enhancedWarningText)
        tap("renderer-mode-enhanced", app)
        XCTAssertEqual(app.buttons["renderer-mode-enhanced"].firstMatch.value as? String,
                       "Selected for next opening or reload")
        requireCurrent("Automatic (compatibility first)", app)
        evidence("Enhanced is saved for a later opening; live Automatic page unchanged", app)
        // Current-player details are below the choices; return upward before selecting.
        reveal(app.buttons["renderer-mode-webgl"].firstMatch, app, upwards: false)
        tap("renderer-mode-webgl", app)
        XCTAssertEqual(app.buttons["renderer-mode-webgl"].firstMatch.value as? String,
                       "Selected for next opening or reload")
        let pending = app.staticTexts["renderer-settings-pending"].firstMatch
        reveal(pending, app)
        XCTAssertEqual(pending.label, "Change pending. The current scene is unchanged.")
        requireCurrent("Automatic (compatibility first)", app)
        evidence("Selected WebGL without changing current Automatic page", app)
        back(app)
        reveal(app.buttons["player-resume"].firstMatch, app, upwards: false)
        tap("player-resume", app)
        XCTAssertFalse(app.webViews.buttons["Play / enable audio"].firstMatch.exists)
        tap("touch-key-default-4", app)
        trace("LIFECYCLE_CHILD_KEY:32:2", app)

        tap("player-menu", app)
        tap("player-saves", app)
        tap("save-entry-restart", app)
        start(app)
        trace("LIFECYCLE_ROOT_READY:420", app)
        tap("touch-key-default-5", app)
        trace("LIFECYCLE_CHILD_READY", app)
        tap("touch-key-default-4", app)
        trace("LIFECYCLE_CHILD_KEY:32:1", app)
        tap("player-menu", app)
        tap("player-renderer-settings", app)
        reveal(app.buttons["renderer-mode-webgl"].firstMatch, app)
        XCTAssertEqual(app.buttons["renderer-mode-webgl"].firstMatch.value as? String,
                       "Selected for next opening or reload")
        XCTAssertFalse(app.staticTexts["renderer-settings-pending"].firstMatch.exists)
        requireCurrent("WebGL compatibility", app)
        evidence("Explicit restart applies saved request, actual renderer remains unconfirmed", app)
    }

    private func requireCurrent(_ requested: String, _ app: XCUIApplication) {
        let title = app.staticTexts["Requested for this opening"].firstMatch
        reveal(title, app)
        // SwiftUI can propagate a VStack identifier to its separate Text nodes.
        // Preserve current-request scoping; never match the selectable mode row.
        evidence("Current requested renderer before assertion: " + requested, app)
        let nodes = app.descendants(matching: .any).matching(identifier: "renderer-settings-requested")
            .allElementsBoundByIndex
        XCTAssertFalse(nodes.isEmpty)
        XCTAssertTrue(nodes.contains { $0.label == requested || $0.staticTexts[requested].exists },
                      "The current-opening value must occur within the requested-value AX scope")
        for other in ["Automatic (compatibility first)", "WebGL compatibility", "Enhanced rendering (original automatic path)"] where other != requested {
            XCTAssertFalse(nodes.contains { $0.label == other || $0.staticTexts[other].exists },
                           "Current-opening scope must not report another renderer request")
        }
        let unconfirmed = app.staticTexts["Not yet confirmed by the renderer"].firstMatch
        reveal(unconfirmed, app)
        XCTAssertTrue(unconfirmed.isHittable)
        XCTAssertFalse(app.staticTexts["renderer-settings-error"].exists)
    }
    private func back(_ app: XCUIApplication) {
        let back = app.navigationBars["Graphics compatibility"].buttons.firstMatch
        XCTAssertTrue(back.exists && back.isHittable); back.tap()
        XCTAssertTrue(app.buttons["player-resume"].waitForExistence(timeout: 10))
    }
    private func tap(_ id: String, _ app: XCUIApplication) {
        let button = app.buttons[id].firstMatch
        reveal(button, app); XCTAssertTrue(button.isEnabled); button.tap()
    }
    private func reveal(_ element: XCUIElement, _ app: XCUIApplication, upwards: Bool = true) {
        for _ in 0..<8 {
            if element.exists && element.isHittable { return }
            if upwards { app.swipeUp() } else { app.swipeDown() }
        }
        evidence("Required compatibility control unavailable", app)
        XCTAssertTrue(element.exists && element.isHittable)
    }
    private func start(_ app: XCUIApplication) {
        let play = app.webViews.buttons["Play / enable audio"].firstMatch
        XCTAssertTrue(play.waitForExistence(timeout: 60))
        XCTAssertTrue(LibraryNavigation.wait { play.isEnabled && play.isHittable }); play.tap()
    }
    private func trace(_ value: String, _ app: XCUIApplication) {
        XCTAssertTrue(app.webViews.staticTexts.matching(NSPredicate(format: "label CONTAINS %@", value))
            .firstMatch.waitForExistence(timeout: 15), "Missing real game trace: \(value)")
    }
    private func evidence(_ name: String, _ app: XCUIApplication) {
        let ax = XCTAttachment(string: app.debugDescription)
        ax.name = name; ax.lifetime = .keepAlways; add(ax)
        let image = XCTAttachment(screenshot: XCUIScreen.main.screenshot())
        image.name = name; image.lifetime = .keepAlways; add(image)
    }
}

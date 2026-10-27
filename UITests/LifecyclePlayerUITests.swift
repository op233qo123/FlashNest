import XCTest
import UIKit

/// Trusted UIKit actions through the production app and real Files import.
/// The separate no-vector fixture covers lifecycle/save behavior only; it does
/// not replace the parked rendering experiment's unresolved geometry gates.
final class LifecyclePlayerUITests: XCTestCase {
    private let fixtureTitle = "FlashNest Lifecycle Fixture"

    override func setUpWithError() throws {
        continueAfterFailure = false
        executionTimeAllowance = 420
        XCUIDevice.shared.orientation = .portrait
    }

    func testBackgroundDirectSaveCancelManagementAndRestartSameGame() {
        let app = importFixture()
        defer { capture("Lifecycle final screen"); XCUIDevice.shared.orientation = .portrait }
        startMovie(app)
        trace("LIFECYCLE_ROOT_READY:undefined", in: app)
        let menu = app.buttons["player-menu"].firstMatch
        let enter = app.buttons["touch-key-default-5"].firstMatch
        let space = app.buttons["touch-key-default-4"].firstMatch
        XCTAssertTrue(enter.waitForExistence(timeout: 10)); XCTAssertTrue(enter.isHittable); enter.tap()
        trace("LIFECYCLE_CHILD_READY", in: app)
        tapChildPointer(count: 1, in: app)

        XCUIDevice.shared.press(.home)
        XCTAssertTrue(wait { app.state != .runningForeground })
        app.activate()
        XCTAssertTrue(menu.waitForExistence(timeout: 15))
        XCTAssertFalse(app.webViews.buttons["Play / enable audio"].firstMatch.exists,
                       "App switching must retain the live scene, not reload the title")
        XCTAssertTrue(space.isHittable); space.tap()
        trace("LIFECYCLE_CHILD_KEY:32:1", in: app)
        tapChildPointer(count: 2, in: app)
        capture("App switching retains child state and trusted input")

        // Opening a menu is a pause intent, which background/foreground must
        // not turn into playback or an implicit new page.
        menu.tap()
        XCUIDevice.shared.press(.home)
        XCTAssertTrue(wait { app.state != .runningForeground })
        app.activate()
        XCTAssertTrue(app.buttons["player-resume"].firstMatch.waitForExistence(timeout: 15))
        app.buttons["player-saves"].firstMatch.tap()
        let direct = app.buttons["save-entry-direct"].firstMatch
        XCTAssertTrue(direct.waitForExistence(timeout: 10)); direct.tap()
        let result = app.staticTexts["save-entry-result"].firstMatch
        XCTAssertTrue(result.waitForExistence(timeout: 20)); reveal(result, in: app)
        let successMessages = ["Game-written save data was copied. The current scene was not restarted.",
                               "No newly written save data. Existing backup unchanged."]
        // Background may already have copied identical game-flushed SOL. An
        // empty/unready/read/write failure must not count as either success.
        XCTAssertTrue(wait { successMessages.contains(result.label) })
        capture("Direct save copies game-written data without restarting")

        let manage = app.buttons["save-entry-manage"].firstMatch
        reveal(manage, in: app); manage.tap()
        XCTAssertTrue(app.staticTexts["save-entry-warning"].firstMatch.waitForExistence(timeout: 10))
        let cancelManagement = app.buttons["save-management-cancel"].firstMatch
        reveal(cancelManagement, in: app); cancelManagement.tap()
        let cancelOptions = app.buttons["save-entry-cancel"].firstMatch
        reveal(cancelOptions, in: app); cancelOptions.tap()
        XCTAssertTrue(app.buttons["player-resume"].firstMatch.waitForExistence(timeout: 10)); done(app)
        XCTAssertTrue(space.isHittable); space.tap()
        trace("LIFECYCLE_CHILD_KEY:32:2", in: app)
        tapChildPointer(count: 3, in: app)
        XCTAssertFalse(app.webViews.buttons["Play / enable audio"].firstMatch.exists,
                       "Direct save and cancelled management must preserve the same child counters")
        capture("Cancelled management retains live child and counters")

        menu.tap(); setSwitch("controls-visible", enabled: false, in: app)
        let saves = app.buttons["player-saves"].firstMatch
        reveal(saves, in: app); saves.tap()
        let restart = app.buttons["save-entry-restart"].firstMatch
        reveal(restart, in: app); restart.tap()
        startMovie(app)
        trace("LIFECYCLE_ROOT_READY:420", in: app)
        XCTAssertFalse(app.buttons["import-folder"].firstMatch.exists,
                       "Save and restart must stay in the same game, not exit to Library")
        XCTAssertEqual(app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH %@", "touch-key-")).count, 0,
                       "Restart retains this game's touch-control settings")
        XCTAssertTrue(menu.isHittable)
        // A newly loaded root reads the child's saved progress. This is an
        // ordinary game restart/load, explicitly NOT an instant scene restore.
        capture("Save and restart returns to same game with written save")
    }

    private func tapChildPointer(count: Int, in app: XCUIApplication) {
        app.webViews.firstMatch.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.5)).tap()
        trace("LIFECYCLE_CHILD_POINTER:\(count)", in: app)
    }

    private func trace(_ value: String, in app: XCUIApplication) {
        let marker = app.webViews.staticTexts.matching(NSPredicate(format: "label CONTAINS %@", value)).firstMatch
        XCTAssertTrue(marker.waitForExistence(timeout: 10), "Missing real SWF callback: \(value)")
    }

    private func startMovie(_ app: XCUIApplication) {
        let play = app.webViews.buttons["Play / enable audio"].firstMatch
        XCTAssertTrue(play.waitForExistence(timeout: 60)); XCTAssertTrue(wait { play.isEnabled }); play.tap()
    }

    private func setSwitch(_ identifier: String, enabled: Bool, in app: XCUIApplication) {
        let toggle = app.switches[identifier].firstMatch
        reveal(toggle, in: app)
        let expected = enabled ? "1" : "0"
        if (toggle.value as? String) != expected {
            // SwiftUI exposes the whole Form row as a switch in iOS 18.2.
            toggle.coordinate(withNormalizedOffset: CGVector(dx: 0.95, dy: 0.5)).tap()
        }
        XCTAssertTrue(wait { (toggle.value as? String) == expected })
    }

    private func done(_ app: XCUIApplication) { app.navigationBars.buttons["Done"].firstMatch.tap() }

    private func reveal(_ element: XCUIElement, in app: XCUIApplication) {
        for _ in 0..<7 { if element.exists && element.isHittable { return }; app.swipeUp() }
        XCTAssertTrue(element.isHittable)
    }

    private func importFixture() -> XCUIApplication {
        let source = XCUIApplication(bundleIdentifier: "com.flashnest.fixture-source")
        source.launchArguments = ["-AppleLanguages", "(en)", "-AppleLocale", "en_US"]
        source.launch(); XCTAssertTrue(source.staticTexts["source-ready"].waitForExistence(timeout: 30)); source.terminate()
        let app = XCUIApplication()
        defer {
            capture("Lifecycle Files import final state")
            let hierarchy = XCTAttachment(string: app.debugDescription)
            hierarchy.name = "Lifecycle Files import accessibility"; hierarchy.lifetime = .keepAlways; add(hierarchy)
        }
        app.launchArguments = ["--flashnest-cross-container-ui-test", "-FlashNest.language", "en", "-AppleLanguages", "(en)", "-AppleLocale", "en_US"]
        app.launch()
        let importButton = app.buttons["import-folder"].firstMatch
        XCTAssertTrue(importButton.waitForExistence(timeout: 15)); XCTAssertTrue(wait { importButton.isHittable }); importButton.tap()
        XCTAssertTrue(app.navigationBars["FullDocumentManagerViewControllerNavigationBar"].waitForExistence(timeout: 15))
        let title = app.navigationBars.buttons[fixtureTitle + ", Actions Menu"].firstMatch
        for _ in 0..<12 {
            if title.exists { break }
            var navigated = false
            for label in [fixtureTitle, "FlashNest Source", "On My iPhone"] {
                let cell = fileCell(named: label, in: app)
                if cell.exists && cell.isHittable { cell.tap(); navigated = true; break }
            }
            if navigated { continue }
            let back = app.navigationBars["FullDocumentManagerViewControllerNavigationBar"].buttons.allElementsBoundByIndex.first {
                ["FlashNest Source", "On My iPhone", "Browse"].contains($0.label) && $0.isHittable
            }
            if let back { back.tap(); continue }
            let browse = app.tabBars.buttons["Browse"].firstMatch
            if browse.exists && browse.isHittable && !browse.isSelected { browse.tap(); continue }
            // Do not repeatedly tap an already-selected Browse tab. Preserve
            // the real picker hierarchy when no recognized route is present.
            break
        }
        XCTAssertTrue(title.waitForExistence(timeout: 10))
        XCTAssertTrue(fileCell(named: "main.swf", in: app).waitForExistence(timeout: 5))
        XCTAssertTrue(fileCell(named: "sub", in: app).exists)
        app.buttons["Open"].firstMatch.tap()
        let entry = app.buttons["entry-main.swf"].firstMatch
        XCTAssertTrue(entry.waitForExistence(timeout: 45))
        XCTAssertTrue(app.buttons["entry-sub/scene.swf"].exists)
        entry.tap()
        return app
    }

    private func fileCell(named name: String, in app: XCUIApplication) -> XCUIElement {
        // iOS18.2 evidence shows the actual remote cell identifiers are
        // "FlashNest Source, Container" / "<name>, Folder". The prior nested
        // containing(staticText:) query missed this visible cell and looped on
        // Browse. Match the cell itself, never a screen-absolute coordinate.
        app.cells.matching(NSPredicate(format:
            "identifier == %@ OR identifier BEGINSWITH %@ OR label == %@ OR label BEGINSWITH %@",
            name, name + ",", name, name + ",")).firstMatch
    }

    private func wait(_ condition: () -> Bool) -> Bool {
        let deadline = Date().addingTimeInterval(15)
        repeat { if condition() { return true }; Thread.sleep(forTimeInterval: 0.2) } while Date() < deadline
        return condition()
    }

    private func capture(_ name: String) {
        let attachment = XCTAttachment(screenshot: XCUIScreen.main.screenshot())
        attachment.name = name; attachment.lifetime = .keepAlways; add(attachment)
    }
}

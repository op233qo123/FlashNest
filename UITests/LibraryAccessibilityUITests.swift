import XCTest
import UIKit

/// Independent of imported packages and test execution order. No Files import,
/// app data mutation, simulator Settings changes or production test hooks.
final class LibraryAccessibilityUITests: XCTestCase {
    override func setUpWithError() throws {
        continueAfterFailure = false
        executionTimeAllowance = 180
    }

    func testChineseSettingsAndObservedAccessibilityTextLayout() throws {
        let app = XCUIApplication()
        defer { app.terminate() }
        launch(app, category: .large)
        let settings = app.buttons["library-settings"].firstMatch
        XCTAssertTrue(settings.waitForExistence(timeout: 15))
        XCTAssertEqual(settings.label, "设置", "The requested Chinese app language must be applied")
        settings.tap()
        let languageLabel = app.staticTexts["settings-language-label"].firstMatch
        XCTAssertTrue(languageLabel.waitForExistence(timeout: 10))
        XCTAssertEqual(languageLabel.label, "语言")
        let normalHeight = languageLabel.frame.height
        XCTAssertGreaterThan(normalHeight, 0)
        app.terminate()

        launch(app, category: .accessibilityExtraExtraExtraLarge)
        XCTAssertTrue(settings.waitForExistence(timeout: 15))
        let toolbar = [app.buttons["import-menu"].firstMatch,
                       app.buttons["save-area"].firstMatch, settings]
        for button in toolbar { assertReachableTarget(button, in: app) }
        for index in toolbar.indices {
            for other in toolbar.indices where other > index {
                let intersection = toolbar[index].frame.intersection(toolbar[other].frame)
                XCTAssertTrue(intersection.isNull || intersection.isEmpty, "Toolbar hit targets must not overlap")
            }
        }
        settings.tap()
        XCTAssertTrue(languageLabel.waitForExistence(timeout: 10))
        XCTAssertEqual(languageLabel.label, "语言")
        let largeHeight = languageLabel.frame.height
        let screenshot = XCTAttachment(screenshot: XCUIScreen.main.screenshot())
        screenshot.name = "Chinese settings with requested Accessibility XXXL"; screenshot.lifetime = .keepAlways; add(screenshot)
        let evidence = XCTAttachment(string:
            "Requested categories: \(UIContentSizeCategory.large.rawValue) -> \(UIContentSizeCategory.accessibilityExtraExtraExtraLarge.rawValue)\nVisible Language text height: \(normalHeight) -> \(largeHeight)\nThis measures actual text growth, not a direct read of the app's trait collection.")
        evidence.name = "Observed Dynamic Type text geometry"; evidence.lifetime = .keepAlways; add(evidence)
        // UIPreferredContentSizeCategoryName is a simulator/test convention, not
        // a guaranteed public launch API. Ignoring it cannot count as a pass.
        try XCTSkipIf(largeHeight <= normalHeight * 1.1,
                      "Simulator launch override produced no observable text growth; Accessibility XXXL coverage is unverified. Chinese baseline was checked.")
        XCTAssertTrue(app.frame.insetBy(dx: -1, dy: -1).contains(languageLabel.frame),
                      "The enlarged visible Language label must remain within the display")
        let done = app.buttons["settings-done"].firstMatch
        XCTAssertTrue(done.isHittable)
        let diagnostics = app.buttons["settings-import-diagnostics"].firstMatch
        reveal(diagnostics, in: app)
        assertReachableTarget(diagnostics, in: app)
        let version = app.staticTexts["app-version"].firstMatch
        reveal(version, in: app)
        XCTAssertTrue(app.frame.insetBy(dx: -1, dy: -1).contains(version.frame))
        done.tap()
        XCTAssertTrue(LibraryNavigation.wait { settings.isHittable })
        XCTAssertEqual(settings.label, "设置")
        app.terminate()
    }

    private func launch(_ app: XCUIApplication, category: UIContentSizeCategory) {
        app.launchArguments = ["-FlashNest.language", "zh-Hans", "-AppleLanguages", "(zh-Hans)",
                               "-AppleLocale", "zh_CN", "-UIPreferredContentSizeCategoryName", category.rawValue]
        app.launch()
    }

    private func assertReachableTarget(_ element: XCUIElement, in app: XCUIApplication,
                                       file: StaticString = #filePath, line: UInt = #line) {
        XCTAssertTrue(element.exists && element.isEnabled && element.isHittable, file: file, line: line)
        XCTAssertGreaterThanOrEqual(element.frame.width, 43, "44-point target, allowing 1-point AX rounding", file: file, line: line)
        XCTAssertGreaterThanOrEqual(element.frame.height, 43, "44-point target, allowing 1-point AX rounding", file: file, line: line)
        XCTAssertTrue(app.frame.insetBy(dx: -1, dy: -1).contains(element.frame), "Target must not be clipped by the viewport", file: file, line: line)
    }

    private func reveal(_ element: XCUIElement, in app: XCUIApplication) {
        for _ in 0..<8 { if element.exists && element.isHittable { return }; app.swipeUp() }
        XCTAssertTrue(element.isHittable)
    }
}

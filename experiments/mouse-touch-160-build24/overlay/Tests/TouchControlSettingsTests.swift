import XCTest
import SwiftUI
@testable import FlashNest

final class TouchControlSettingsTests: XCTestCase {
    func testDefaultControlsAreOneSixButtonSetWithVisibleTranslucentOverlay() {
        let settings = TouchControlSettings()
        XCTAssertFalse(settings.mouseTouchEnabled)
        XCTAssertTrue(settings.isVisible)
        XCTAssertEqual(settings.opacity, 0.6)
        XCTAssertEqual(settings.buttons.map(\.key), ["ArrowUp", "ArrowLeft", "ArrowDown", "ArrowRight", "Space", "Enter"])
        XCTAssertEqual(Set(settings.buttons.map(\.id)).count, 6)
    }

    func testLegacyPreferencesKeepCustomControlsAndDefaultMouseTouchOff() throws {
        var original = TouchControlSettings()
        original.opacity = 0.35
        original.isVisible = false
        original.buttons[0].portrait = TouchControlPoint(x: 0.2, y: 0.8)
        var legacy = try XCTUnwrap(JSONSerialization.jsonObject(with: JSONEncoder().encode(original)) as? [String: Any])
        legacy.removeValue(forKey: "mouseTouchEnabled")
        let decoded = try JSONDecoder().decode(TouchControlSettings.self, from: JSONSerialization.data(withJSONObject: legacy))
        XCTAssertEqual(decoded, original)
        XCTAssertFalse(decoded.mouseTouchEnabled)
    }

    func testMenuRemainsInsideSafeAreaAcrossRotationAndExtremeDrags() {
        let portrait = PlayerMenuGeometry(size: CGSize(width: 390, height: 844), safeArea: EdgeInsets(top: 59, leading: 0, bottom: 34, trailing: 0))
        let landscape = PlayerMenuGeometry(size: CGSize(width: 844, height: 390), safeArea: EdgeInsets(top: 0, leading: 59, bottom: 21, trailing: 59))
        for layout in [portrait, landscape] {
            for point in [CGPoint(x: -1000, y: -1000), CGPoint(x: 3000, y: 3000)] {
                let clamped = layout.center(layout.normalized(point))
                XCTAssertGreaterThanOrEqual(clamped.x - 22, layout.safeArea.leading)
                XCTAssertLessThanOrEqual(clamped.x + 22, layout.size.width - layout.safeArea.trailing)
                XCTAssertGreaterThanOrEqual(clamped.y - 22, layout.safeArea.top)
                XCTAssertLessThanOrEqual(clamped.y + 22, layout.size.height - layout.safeArea.bottom)
            }
        }
        let moved = portrait.normalized(CGPoint(x: 100, y: 700))
        let rotated = landscape.center(moved)
        XCTAssertEqual(landscape.normalized(rotated).x, moved.x, accuracy: 0.0001)
        XCTAssertEqual(landscape.normalized(rotated).y, moved.y, accuracy: 0.0001)
        let tiny = PlayerMenuGeometry(size: CGSize(width: 20, height: 20), safeArea: EdgeInsets())
        XCTAssertTrue(tiny.normalized(CGPoint.zero).x.isFinite)
        XCTAssertTrue(tiny.normalized(CGPoint.zero).y.isFinite)
    }

    func testOpacityAndStoredPositionsAreClamped() {
        var settings = TouchControlSettings()
        settings.opacity = -10
        settings.buttons[0].portrait = TouchControlPoint(x: -5, y: 8)
        XCTAssertEqual(settings.sanitized().opacity, 0.1)
        XCTAssertEqual(settings.sanitized().buttons[0].portrait, TouchControlPoint(x: 0, y: 1))
        settings.opacity = 10
        XCTAssertEqual(settings.sanitized().opacity, 1)
        settings.opacity = .nan
        XCTAssertEqual(settings.sanitized().opacity, 0.6)
    }

    func testPreferencesRoundTripAndAreIsolatedByGame() throws {
        let suite = "FlashNest.TouchTests." + UUID().uuidString
        let defaults = try XCTUnwrap(UserDefaults(suiteName: suite))
        defer { defaults.removePersistentDomain(forName: suite) }
        let first = UUID(), second = UUID()
        var settings = TouchControlSettings()
        settings.opacity = 0.1; settings.isVisible = false; settings.mouseTouchEnabled = true
        settings.buttons[0].portrait = TouchControlPoint(x: 0.3, y: 0.7)
        settings.buttons[0].landscape = TouchControlPoint(x: 0.8, y: 0.2)
        settings.save(for: first, defaults: defaults)
        XCTAssertEqual(TouchControlSettings.load(for: first, defaults: defaults), settings)
        XCTAssertEqual(TouchControlSettings.load(for: second, defaults: defaults), TouchControlSettings())
        defaults.set(Data("invalid JSON".utf8), forKey: TouchControlSettings.preferenceKey(for: first))
        XCTAssertEqual(TouchControlSettings.load(for: first, defaults: defaults), TouchControlSettings())
    }

    func testAdditionalButtonsAreBoundedAndInvalidKeyPreferencesRecover() {
        var settings = TouchControlSettings()
        for _ in 0..<20 { _ = settings.addButton() }
        XCTAssertEqual(settings.buttons.count, TouchControlSettings.maximumButtons)
        XCTAssertNil(settings.addButton())
        settings.buttons = [TouchControlBinding(id: "bad", key: "javascript:alert(1)", slot: 0)]
        XCTAssertEqual(settings.sanitized().buttons, TouchControlSettings.defaultButtons)
    }

    func testOrientationSpecificPositionsAndSafeAreaClamping() {
        var button = TouchControlSettings.defaultButtons[0]
        button.portrait = TouchControlPoint(x: 0, y: 1)
        button.landscape = TouchControlPoint(x: 1, y: 0)
        let portrait = TouchControlGeometry(size: CGSize(width: 390, height: 844), safeArea: EdgeInsets(top: 59, leading: 0, bottom: 34, trailing: 0))
        let landscape = TouchControlGeometry(size: CGSize(width: 844, height: 390), safeArea: EdgeInsets(top: 0, leading: 59, bottom: 21, trailing: 59))
        XCTAssertEqual(portrait.center(for: button).x, portrait.bounds.minX)
        XCTAssertEqual(portrait.center(for: button).y, portrait.bounds.maxY)
        XCTAssertEqual(landscape.center(for: button).x, landscape.bounds.maxX)
        XCTAssertEqual(landscape.center(for: button).y, landscape.bounds.minY)
        XCTAssertEqual(landscape.normalized(CGPoint(x: -100, y: 2000)), TouchControlPoint(x: 0, y: 1))
        for layout in [portrait, landscape] {
            for control in TouchControlSettings.defaultButtons {
                let center = layout.center(for: control)
                XCTAssertGreaterThanOrEqual(center.x, layout.bounds.minX)
                XCTAssertLessThanOrEqual(center.x, layout.bounds.maxX)
                XCTAssertGreaterThanOrEqual(center.y, layout.bounds.minY)
                XCTAssertLessThanOrEqual(center.y, layout.bounds.maxY)
            }
        }
    }

    func testSameKeyHasIndependentOwnersAndOnlyLastReleaseSendsKeyUp() {
        var ledger = TouchKeyLedger()
        XCTAssertEqual(ledger.press(owner: "first", code: "Space"), [.init(code: "Space", down: true)])
        XCTAssertEqual(ledger.press(owner: "first", code: "Space"), [])
        XCTAssertEqual(ledger.press(owner: "second", code: "Space"), [])
        XCTAssertEqual(ledger.release(owner: "first"), [])
        XCTAssertEqual(ledger.release(owner: "second"), [.init(code: "Space", down: false)])
        XCTAssertEqual(ledger.release(owner: "second"), [])
    }

    func testDirectionAndActionCanBeHeldTogetherAndCancelReleasesEachOnce() {
        var ledger = TouchKeyLedger()
        _ = ledger.press(owner: "left-thumb", code: "ArrowLeft")
        _ = ledger.press(owner: "right-thumb", code: "Space")
        XCTAssertEqual(ledger.releaseAll(), [.init(code: "ArrowLeft", down: false), .init(code: "Space", down: false)])
        XCTAssertTrue(ledger.owners.isEmpty)
        XCTAssertEqual(ledger.releaseAll(), [])
        XCTAssertEqual(ledger.release(owner: "left-thumb"), [])
    }

    func testForegroundCannotRestartPlayerUnderSaveSheetEditorOrClose() {
        XCTAssertTrue(PlayerResumePolicy.allowsResume(sceneIsActive: true, panelOpen: false, editingControls: false, closing: false))
        XCTAssertFalse(PlayerResumePolicy.allowsResume(sceneIsActive: true, panelOpen: true, editingControls: false, closing: false), "Save import must not race a foreground runtime restart")
        XCTAssertFalse(PlayerResumePolicy.allowsResume(sceneIsActive: true, panelOpen: false, editingControls: false, closing: true))
        XCTAssertFalse(PlayerResumePolicy.allowsResume(sceneIsActive: true, panelOpen: false, editingControls: true, closing: false))
        XCTAssertFalse(PlayerResumePolicy.allowsResume(sceneIsActive: false, panelOpen: false, editingControls: false, closing: false))
    }

    func testInactiveAndBackgroundPreservePlayingOrManualPauseIntent() {
        let wasPlaying = PlayerResumePolicy.playbackIntent(previous: false, leavingActive: true, wasPaused: false)
        XCTAssertTrue(wasPlaying)
        XCTAssertTrue(PlayerResumePolicy.playbackIntent(previous: wasPlaying, leavingActive: false, wasPaused: true),
                      "The automatic inactive pause must not replace the original playback intent")
        let wasManuallyPaused = PlayerResumePolicy.playbackIntent(previous: true, leavingActive: true, wasPaused: true)
        XCTAssertFalse(wasManuallyPaused)
        XCTAssertFalse(PlayerResumePolicy.playbackIntent(previous: wasManuallyPaused, leavingActive: false, wasPaused: true))
        XCTAssertFalse(PlayerResumePolicy.allowsResume(sceneIsActive: true, panelOpen: true, editingControls: false, closing: false),
                       "Returning from Control Center or Home cannot resume behind an open menu")
    }

    func testChangingHeldOwnerMappingReleasesOldKeyBeforeNewKey() {
        var ledger = TouchKeyLedger()
        _ = ledger.press(owner: "button", code: "Enter")
        XCTAssertEqual(ledger.press(owner: "button", code: "KeyZ"),
                       [.init(code: "Enter", down: false), .init(code: "KeyZ", down: true)])
    }
}

import XCTest

/// A portrait-only home journey using a genuine cross-container Files import.
/// This is not a seeded-library shortcut and does not claim the separate
/// fullscreen/orientation or lifecycle suites have passed.
final class LibraryHomeUITests: XCTestCase {
    private let fixtureTitle = "FlashNest Lifecycle Fixture"

    override func setUpWithError() throws {
        continueAfterFailure = false
        executionTimeAllowance = 420
    }

    func testGameFirstSearchFavoritesSettingsAndQuickPlay() throws {
        let source = XCUIApplication(bundleIdentifier: "com.flashnest.fixture-source")
        source.launchArguments = ["-AppleLanguages", "(en)", "-AppleLocale", "en_US"]
        source.launch()
        XCTAssertTrue(source.staticTexts["source-ready"].waitForExistence(timeout: 30))
        source.terminate()

        let app = XCUIApplication()
        app.launchArguments = ["--flashnest-cross-container-ui-test", "-FlashNest.language", "en",
                               "-AppleLanguages", "(en)", "-AppleLocale", "en_US"]
        app.launch()
        LibraryNavigation.openSourceFolder(named: fixtureTitle, in: app)
        XCTAssertEqual(app.buttons["entry-main.swf"].firstMatch.value as? String, "Current entry",
                       "Quick Play must later use this explicitly displayed selected entry")
        LibraryNavigation.requireEntry("sub/scene.swf", in: app)
        let selector = app.descendants(matching: .any).matching(NSPredicate(format:
            "identifier BEGINSWITH %@", "entry-selector-")).firstMatch
        XCTAssertTrue(selector.waitForExistence(timeout: 5))
        let packageID = String(selector.identifier.dropFirst("entry-selector-".count))
        XCTAssertNotNil(UUID(uuidString: packageID), "Target this exact new package, not an older same-title import")
        cancelEntryPicker(app)
        setFavoritesOnly(false, in: app)

        let quickPlay = app.buttons["play-" + packageID].firstMatch
        let entries = app.buttons["entries-" + packageID].firstMatch
        let favorite = app.buttons["favorite-" + packageID].firstMatch
        XCTAssertTrue(quickPlay.waitForExistence(timeout: 10))
        XCTAssertTrue(quickPlay.isEnabled && quickPlay.isHittable, "Imported game must be actionable without scrolling past settings/help")
        XCTAssertTrue(entries.isHittable, "Entry selection remains a separate visible action")
        XCTAssertFalse(app.buttons["import-folder"].exists && app.buttons["import-folder"].isHittable,
                       "The full import menu must not permanently occupy the library")
        XCTAssertFalse(app.otherElements["settings-language"].exists && app.otherElements["settings-language"].isHittable)

        entries.tap()
        LibraryNavigation.requireEntry("main.swf", in: app)
        LibraryNavigation.requireEntry("sub/scene.swf", in: app)
        XCTAssertFalse(app.buttons["player-menu"].exists && app.buttons["player-menu"].isHittable,
                       "Opening the secondary entry chooser must not start playback")
        cancelEntryPicker(app)
        XCTAssertTrue(quickPlay.isHittable)

        // Exercise native menus as real controls, not just their visible labels.
        let sort = app.buttons["library-sort"].firstMatch
        LibraryNavigation.captureControlState("library-sort", in: app, context: "Sort before genuine menu action")
        XCTAssertTrue(sort.isEnabled && sort.isHittable); sort.tap()
        let titleSort = app.buttons["Title"].firstMatch
        XCTAssertTrue(titleSort.waitForExistence(timeout: 5)); titleSort.tap()
        XCTAssertTrue(LibraryNavigation.wait { sort.label.contains("Title") })
        sort.tap()
        let importedSort = app.buttons["Recently imported"].firstMatch
        XCTAssertTrue(importedSort.waitForExistence(timeout: 5)); importedSort.tap()
        XCTAssertTrue(LibraryNavigation.wait { sort.label.contains("Recently imported") })
        XCTAssertTrue(LibraryNavigation.wait { quickPlay.isHittable })

        let options = app.buttons["game-options-" + packageID].firstMatch
        XCTAssertTrue(options.isHittable); options.tap()
        let optionsSheet = app.descendants(matching: .any)["game-options-sheet-" + packageID].firstMatch
        XCTAssertTrue(optionsSheet.waitForExistence(timeout: 5))
        let cancelOptions = app.buttons["game-options-cancel"].firstMatch
        XCTAssertTrue(cancelOptions.isEnabled && cancelOptions.isHittable); cancelOptions.tap()
        XCTAssertTrue(LibraryNavigation.wait { quickPlay.isHittable && options.isHittable })
        XCTAssertFalse(app.buttons["player-menu"].exists && app.buttons["player-menu"].isHittable,
                       "Cancelling game options must not launch playback")
        options.tap()
        XCTAssertTrue(optionsSheet.waitForExistence(timeout: 5))
        let menuChoice = app.buttons["game-options-choose-entry"].firstMatch
        XCTAssertTrue(menuChoice.waitForExistence(timeout: 5))
        XCTAssertTrue(menuChoice.isEnabled && menuChoice.isHittable)
        menuChoice.tap()
        LibraryNavigation.requireEntry("main.swf", in: app)
        let entryOptions = app.buttons["entry-options"].firstMatch
        XCTAssertTrue(entryOptions.isHittable); entryOptions.tap()
        let requestRemoval = app.buttons["remove-game"].firstMatch
        XCTAssertTrue(requestRemoval.waitForExistence(timeout: 5)); requestRemoval.tap()
        let confirmRemoval = app.buttons["Remove game, keep saves"].firstMatch
        XCTAssertTrue(confirmRemoval.waitForExistence(timeout: 10), "Removal is only a confirmation request, never immediate deletion")
        XCTAssertTrue(confirmRemoval.isHittable)
        let cancelRemoval = app.buttons["Cancel"].firstMatch
        XCTAssertTrue(cancelRemoval.isHittable); cancelRemoval.tap()
        XCTAssertTrue(LibraryNavigation.wait { quickPlay.exists && quickPlay.isEnabled && quickPlay.isHittable },
                      "Cancelled removal must retain the exact package and its quick-open action")
        XCTAssertFalse(app.descendants(matching: .any)["removal-progress"].exists)
        XCTAssertFalse(app.buttons["player-menu"].exists && app.buttons["player-menu"].isHittable,
                       "Options, entry selection and removal cancellation must not start playback")

        let search = app.textFields["library-search"].firstMatch
        XCTAssertTrue(search.waitForExistence(timeout: 5))
        search.tap(); search.typeText("lifecycle\n")
        XCTAssertTrue(LibraryNavigation.wait { quickPlay.exists && quickPlay.isHittable },
                      "Search matches the imported game without changing its identity")
        entries.tap()
        LibraryNavigation.requireEntry("main.swf", in: app)
        cancelEntryPicker(app)
        XCTAssertEqual(search.value as? String, "lifecycle", "Chooser cancel must preserve the current query")
        XCTAssertTrue(quickPlay.isHittable)
        XCTAssertFalse(app.buttons["player-menu"].exists && app.buttons["player-menu"].isHittable)
        clearSearch(in: app)
        search.tap(); search.typeText("no-such-flashnest-game-9d7a\n")
        XCTAssertTrue(LibraryNavigation.wait { self.visiblePlayButtons(in: app).count == 0 },
                      "A nonmatching query must show no playable rows, not stale results")
        clearSearch(in: app)
        XCTAssertTrue(LibraryNavigation.wait { quickPlay.exists && quickPlay.isHittable },
                      "Clear search must recover the same package without reimport")

        XCTAssertEqual(favorite.value as? String, "Not favorited", "A freshly imported UUID starts unfavorited")
        favorite.tap()
        XCTAssertTrue(LibraryNavigation.wait { favorite.value as? String == "Favorited" })
        setFavoritesOnly(true, in: app)
        XCTAssertTrue(quickPlay.isHittable)
        favorite.tap()
        XCTAssertTrue(LibraryNavigation.wait { !quickPlay.exists }, "Removing a favorite immediately removes it from the favorites-only list")
        setFavoritesOnly(false, in: app)
        XCTAssertTrue(quickPlay.waitForExistence(timeout: 5))
        favorite.tap()
        XCTAssertTrue(LibraryNavigation.wait { favorite.value as? String == "Favorited" })
        setFavoritesOnly(true, in: app)

        app.terminate(); app.launch()
        XCTAssertTrue(quickPlay.waitForExistence(timeout: 15), "The exact imported game remains visible after relaunch")
        XCTAssertEqual(app.buttons["library-favorites-filter"].firstMatch.value as? String, "Favorites only")
        XCTAssertEqual(favorite.value as? String, "Favorited", "Favorites persist independently of game content and saves")
        XCTAssertTrue(quickPlay.isHittable)
        let screenshot = XCTAttachment(screenshot: XCUIScreen.main.screenshot())
        screenshot.name = "Game-first library with persisted favorite"; screenshot.lifetime = .keepAlways; add(screenshot)

        search.tap(); search.typeText("lifecycle\n")
        XCTAssertTrue(LibraryNavigation.wait { quickPlay.isHittable })
        app.buttons["library-settings"].firstMatch.tap()
        let settingsDone = app.buttons["settings-done"].firstMatch
        XCTAssertTrue(settingsDone.waitForExistence(timeout: 5))
        XCTAssertTrue(app.descendants(matching: .any)["settings-language"].firstMatch.exists)
        let diagnostics = app.buttons["settings-import-diagnostics"].firstMatch
        reveal(diagnostics, in: app)
        let version = app.staticTexts["app-version"].firstMatch
        reveal(version, in: app)
        XCTAssertFalse(version.label.isEmpty)
        XCTAssertFalse(quickPlay.isHittable, "Settings must be a separate presentation, not accidental playback")
        settingsDone.tap()
        XCTAssertTrue(LibraryNavigation.wait { quickPlay.isHittable })
        XCTAssertEqual(search.value as? String, "lifecycle", "Settings dismissal preserves the current query")
        XCTAssertEqual(app.buttons["library-favorites-filter"].firstMatch.value as? String, "Favorites only")

        quickPlay.tap()
        let audioPlay = app.webViews.buttons["Play / enable audio"].firstMatch
        XCTAssertTrue(audioPlay.waitForExistence(timeout: 60), "Quick Play opens the selected main SWF without the entry chooser")
        XCTAssertFalse(app.buttons["entry-main.swf"].exists && app.buttons["entry-main.swf"].isHittable)
        XCTAssertTrue(LibraryNavigation.wait { audioPlay.isEnabled }); audioPlay.tap()
        let trace = app.webViews.staticTexts.matching(NSPredicate(format: "label CONTAINS %@", "LIFECYCLE_ROOT_READY:")).firstMatch
        XCTAssertTrue(trace.waitForExistence(timeout: 20), "The real SWF must execute; a visible web view alone is not success")
        LibraryNavigation.captureControlState("player-menu", in: app, context: "Quick Play foreground accessibility tree")
        let outerWeb = app.webViews.firstMatch
        let webAreaCount = app.webViews.count
        XCTAssertGreaterThanOrEqual(webAreaCount, 1)
        XCTAssertEqual(outerWeb.descendants(matching: .webView).count, webAreaCount - 1,
                       "Every web accessibility area must belong to one foreground root, not sibling players; this is not a native WK instance count")
        let stage = app.webViews["player-stage"].firstMatch
        XCTAssertTrue(stage.exists && stage.isHittable)
        XCTAssertFalse(stage.frame.isEmpty)
        XCTAssertTrue(app.frame.insetBy(dx: -1, dy: -1).contains(stage.frame))
        XCTAssertEqual(app.buttons.matching(identifier: "player-menu").count, 1)
        let menu = app.buttons["player-menu"].firstMatch
        XCTAssertTrue(menu.isHittable); menu.tap()
        let close = app.buttons["player-close"].firstMatch
        reveal(close, in: app); close.tap()
        XCTAssertTrue(LibraryNavigation.wait({ quickPlay.exists && quickPlay.isHittable }, timeout: 30),
                      "Close returns to the same interactive library and retains the package")
        XCTAssertEqual(favorite.value as? String, "Favorited")
        XCTAssertEqual(search.value as? String, "lifecycle", "Closing the game preserves the library query")
        // Leave unrelated imported games untouched and restore a neutral filter.
        setFavoritesOnly(false, in: app)
        favorite.tap()
        XCTAssertTrue(LibraryNavigation.wait { favorite.value as? String == "Not favorited" })
        clearSearch(in: app)
    }

    private func visiblePlayButtons(in app: XCUIApplication) -> XCUIElementQuery {
        app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH %@", "play-"))
    }

    private func clearSearch(in app: XCUIApplication) {
        let clear = app.buttons["clear-search"].firstMatch
        XCTAssertTrue(clear.waitForExistence(timeout: 5)); clear.tap()
        let search = app.textFields["library-search"].firstMatch
        XCTAssertTrue(LibraryNavigation.wait {
            let value = search.value as? String ?? ""
            return value.isEmpty || value == search.placeholderValue
        })
    }

    private func setFavoritesOnly(_ enabled: Bool, in app: XCUIApplication) {
        let toggle = app.buttons["library-favorites-filter"].firstMatch
        XCTAssertTrue(toggle.waitForExistence(timeout: 10))
        let expected = enabled ? "Favorites only" : "All games"
        if toggle.value as? String != expected { toggle.tap() }
        XCTAssertTrue(LibraryNavigation.wait { toggle.value as? String == expected })
    }

    private func cancelEntryPicker(_ app: XCUIApplication) {
        let cancel = app.navigationBars.buttons["Cancel"].firstMatch
        XCTAssertTrue(cancel.isHittable); cancel.tap()
        XCTAssertTrue(app.buttons["library-settings"].waitForExistence(timeout: 10))
        XCTAssertTrue(LibraryNavigation.wait { app.buttons["library-settings"].isHittable })
    }

    private func reveal(_ element: XCUIElement, in app: XCUIApplication) {
        for _ in 0..<5 { if element.exists && element.isHittable { return }; app.swipeUp() }
        XCTAssertTrue(element.isHittable)
    }
}

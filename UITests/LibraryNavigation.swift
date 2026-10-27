import XCTest

/// Only drives public UI. No data seeding, import callbacks or app launch hooks.
/// Shared by the existing real Files journeys and home-screen acceptance.
enum LibraryNavigation {
    static func wait(_ condition: () -> Bool, timeout: TimeInterval = 15) -> Bool {
        let deadline = Date().addingTimeInterval(timeout)
        repeat {
            if condition() { return true }
            Thread.sleep(forTimeInterval: 0.2)
        } while Date() < deadline
        return condition()
    }

    static func captureControlState(_ identifier: String, in app: XCUIApplication, context: String) {
        let matches = app.buttons.matching(identifier: identifier)
        var lines = ["Context: \(context)", "App state: \(app.state.rawValue)", "App bounds: \(app.frame)",
                     "Button matches: \(matches.count)",
                     "All AX type matches: \(app.descendants(matching: .any).matching(identifier: identifier).count)"]
        for (index, element) in matches.allElementsBoundByIndex.prefix(10).enumerated() {
            lines.append("match[\(index)] identifier=\(element.identifier) label=\(element.label) value=\(String(describing: element.value)) exists=\(element.exists) enabled=\(element.isEnabled) hittable=\(element.isHittable) frame=\(element.frame)")
        }
        let state = lines.joined(separator: "\n")
        print("FLASHNEST_CONTROL_STATE\n" + state)
        let hierarchy = String(app.debugDescription.prefix(75_000))
        print("FLASHNEST_CONTROL_AX\n" + hierarchy)
        XCTContext.runActivity(named: context) { activity in
            let detail = XCTAttachment(string: state + "\n\n" + hierarchy)
            detail.name = "Control state and accessibility — " + identifier
            detail.lifetime = .keepAlways
            activity.add(detail)
        }
    }

    static func revealFolderImport(in app: XCUIApplication, file: StaticString = #filePath, line: UInt = #line) -> XCUIElement {
        let folder = app.buttons["import-folder"].firstMatch
        if folder.exists && folder.isHittable { return folder }
        let menu = app.buttons["import-menu"].firstMatch
        XCTAssertTrue(menu.waitForExistence(timeout: 15), file: file, line: line)
        let interactive = wait { menu.isHittable && menu.isEnabled }
        if !interactive { captureControlState("import-menu", in: app, context: "Import menu interaction guard failed") }
        XCTAssertTrue(interactive, file: file, line: line)
        menu.tap()
        XCTAssertTrue(folder.waitForExistence(timeout: 5), file: file, line: line)
        XCTAssertTrue(wait { folder.isHittable && folder.isEnabled }, file: file, line: line)
        return folder
    }

    @discardableResult static func requireEntry(_ path: String, in app: XCUIApplication, towardTop: Bool = false,
                                               file: StaticString = #filePath, line: UInt = #line) -> XCUIElement {
        let selector = app.descendants(matching: .any).matching(NSPredicate(format:
            "identifier BEGINSWITH %@", "entry-selector-")).firstMatch
        XCTAssertTrue(selector.waitForExistence(timeout: 45), "Import must finish and show its app-owned selector", file: file, line: line)
        let row = app.buttons["entry-" + path].firstMatch
        for _ in 0..<5 {
            if row.exists && row.isHittable { break }
            if towardTop { app.swipeDown() } else { app.swipeUp() }
        }
        XCTAssertTrue(row.exists && row.isHittable, "Required entry must be present and reachable: \(path)", file: file, line: line)
        return row
    }

    static func fileCell(named name: String, in app: XCUIApplication) -> XCUIElement {
        app.cells.matching(NSPredicate(format:
            "identifier == %@ OR identifier BEGINSWITH %@ OR label == %@ OR label BEGINSWITH %@",
            name, name + ",", name, name + ",")).firstMatch
    }

    static func openSourceFolder(named name: String, in app: XCUIApplication,
                                 file: StaticString = #filePath, line: UInt = #line) {
        revealFolderImport(in: app, file: file, line: line).tap()
        let navigation = app.navigationBars["FullDocumentManagerViewControllerNavigationBar"]
        XCTAssertTrue(navigation.waitForExistence(timeout: 15), file: file, line: line)
        let title = app.navigationBars.buttons[name + ", Actions Menu"].firstMatch
        for _ in 0..<12 {
            if title.exists && title.isHittable { break }
            var navigated = false
            for label in [name, "FlashNest Source", "On My iPhone"] {
                let cell = fileCell(named: label, in: app)
                if cell.exists && cell.isHittable { cell.tap(); navigated = true; break }
            }
            if navigated { continue }
            if let back = navigation.buttons.allElementsBoundByIndex.first(where: {
                ["FlashNest Source", "On My iPhone", "Browse"].contains($0.label) && $0.isHittable
            }) { back.tap(); continue }
            let browse = app.tabBars.buttons["Browse"].firstMatch
            if browse.exists && browse.isHittable && !browse.isSelected { browse.tap(); continue }
            break
        }
        XCTAssertTrue(title.waitForExistence(timeout: 10), "Select the exact source fixture, not an arbitrary Files location", file: file, line: line)
        XCTAssertTrue(title.isHittable, file: file, line: line)
        XCTAssertTrue(fileCell(named: "main.swf", in: app).waitForExistence(timeout: 5), file: file, line: line)
        XCTAssertTrue(fileCell(named: "sub", in: app).exists, file: file, line: line)
        let open = app.buttons["Open"].firstMatch
        XCTAssertTrue(open.isEnabled && open.isHittable, file: file, line: line)
        open.tap()
        requireEntry("main.swf", in: app, file: file, line: line)
    }
}

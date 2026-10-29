    // EXTRA diagnostic only: never part of the 161-method acceptance selection.
    func testDiagnosticCandidateAutomaticContextWindow() throws {
        guard identity["arm"] as? String == "candidate" else { throw Failure.invalid("Candidate diagnostic identity required") }
        // Preserve evidence after observation/crop helper assertions; existing methods are unchanged.
        continueAfterFailure = true
        let app = XCUIApplication()
        app.launchArguments = ["-FlashNest.language", "en", "-AppleLanguages", "(en)", "-AppleLocale", "en_US",
            "--renderer", "automatic", "--scale", "original", "--fixture", "noScale-center.swf"]
        app.launch(); defer { app.terminate() }
        let launchedAt = ProcessInfo.processInfo.systemUptime
        var records: [[String: Any]] = []
        func capture(_ snapshot: [String: Any], label: String, target: Double, anchor: Double, error: String = "") throws {
            let observedAt = ProcessInfo.processInfo.systemUptime
            var record: [String: Any] = ["schema": "flashnest-candidate-context-window-v1", "diagnosticOnly": true,
                "nativeAcceptance": false, "label": label, "targetElapsedSeconds": target,
                "anchorUptimeSeconds": anchor, "observedUptimeSeconds": observedAt,
                "elapsedSeconds": observedAt - anchor, "snapshot": snapshot, "observationError": error]
            // Preserve raw state BEFORE invoking crop helpers that can assert or throw.
            var raw = record; raw["schema"] = "flashnest-candidate-context-window-raw-v1"
            try attachJSON(raw, name: "candidate-context-" + label + "-raw")
            if let m = snapshot["measurement"] as? [String: Any], let css = m["css"] as? [Double],
               css.count == 4, css[2] > 0, css[3] > 0,
               (snapshot["viewport"] as? [Double])?.count == 4,
               (snapshot["screenBounds"] as? [Double])?.count == 2 {
                do { record["cropSHA256"] = try screenshot(app, before: snapshot, name: "candidate-context-" + label) }
                catch { record["cropError"] = String(describing: error) }
            } else { record["cropError"] = "Measurement/geometry unavailable; no invented crop" }
            if record["cropSHA256"] == nil {
                let full = XCTAttachment(screenshot: XCUIScreen.main.screenshot())
                full.name = "candidate-context-" + label + "-full-screen"; full.lifetime = .keepAlways; add(full)
            }
            record["captureFinishedUptimeSeconds"] = ProcessInfo.processInfo.systemUptime
            try attachJSON(record, name: "candidate-context-" + label)
            records.append(record)
        }
        let play = app.webViews.buttons["Play / enable audio"].firstMatch
        guard play.waitForExistence(timeout: 90), wait({ play.isEnabled && play.isHittable }) else {
            try capture([:], label: "activation-unavailable", target: 0, anchor: launchedAt, error: "Play unavailable")
            XCTFail("Diagnostic activation unavailable; evidence retained"); return
        }
        play.tap() // Only required user activation; no taps into the SWF fixture.
        let readyDeadline = ProcessInfo.processInfo.systemUptime + 90
        var first: [String: Any] = [:]
        var firstError = ""
        repeat {
            do { first = try snapshot(app, allowingFailure: true) }
            catch { firstError = String(describing: error); break }
            if trace(first, "READY").count == 1 && first["measurement"] is [String: Any] { break }
            Thread.sleep(forTimeInterval: 0.2)
        } while ProcessInfo.processInfo.systemUptime < readyDeadline
        let anchor = ProcessInfo.processInfo.systemUptime
        guard trace(first, "READY").count == 1, first["measurement"] is [String: Any], firstError.isEmpty else {
            try capture(first, label: "ready-unavailable", target: 0, anchor: anchor,
                        error: firstError.isEmpty ? "Bounded READY/measurement deadline" : firstError)
            XCTFail("Diagnostic READY unavailable; evidence retained"); return
        }
        try capture(first, label: "ready", target: 0, anchor: anchor)
        for (label, target) in [("after-5s", 5.0), ("after-15s", 15.0)] {
            while ProcessInfo.processInfo.systemUptime < anchor + target { Thread.sleep(forTimeInterval: 0.1) }
            do { try capture(snapshot(app, allowingFailure: true), label: label, target: target, anchor: anchor) }
            catch { try capture([:], label: label, target: target, anchor: anchor, error: String(describing: error)) }
        }
        // Assert only after all bounded snapshots/crops are attached. Context loss
        // cannot stop collection of the later same-player diagnostic sample.
        XCTAssertEqual(records.count, 3)
        for record in records {
            XCTAssertEqual(record["observationError"] as? String, "")
            let state = record["snapshot"] as? [String: Any] ?? [:]
            XCTAssertEqual(state["epoch"] as? Int, first["epoch"] as? Int)
            XCTAssertEqual(state["failure"] as? String, "")
            XCTAssertNotNil(state["measurement"] as? [String: Any])
        }
    }

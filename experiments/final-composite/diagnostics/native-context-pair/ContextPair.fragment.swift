    // EXTRA paired diagnostic only, never native matrix/IPA acceptance.
    func testDiagnosticContextPairWindowAndRotation() throws {
        guard let arm = identity["arm"] as? String, ["baseline", "candidate"].contains(arm) else {
            throw Failure.invalid("Externally staged diagnostic arm required")
        }
        let renderer = arm == "baseline" ? "webgl" : "automatic"
        // Preserve evidence after observation/crop helper assertions; existing methods are unchanged.
        continueAfterFailure = true
        let app = XCUIApplication()
        app.launchArguments = ["-FlashNest.language", "en", "-AppleLanguages", "(en)", "-AppleLocale", "en_US",
            "--renderer", renderer, "--scale", "original", "--fixture", "noScale-center.swf"]
        app.launch(); defer { app.terminate() }
        let launchedAt = ProcessInfo.processInfo.systemUptime
        var records: [[String: Any]] = []
        var rotationRequestedAt: Double?
        func capture(_ snapshot: [String: Any], label: String, target: Double, anchor: Double, error: String = "") throws {
            let observedAt = ProcessInfo.processInfo.systemUptime
            var record: [String: Any] = ["schema": "flashnest-paired-context-window-v1", "diagnosticOnly": true,
                "nativeAcceptance": false, "arm": arm, "rendererPolicy": renderer, "label": label, "targetElapsedSeconds": target,
                "anchorUptimeSeconds": anchor, "observedUptimeSeconds": observedAt,
                "elapsedSeconds": observedAt - anchor, "snapshot": snapshot, "observationError": error]
            if let rotationRequestedAt { record["rotationRequestedUptimeSeconds"] = rotationRequestedAt }
            // Preserve raw state BEFORE invoking crop helpers that can assert or throw.
            var raw = record; raw["schema"] = "flashnest-paired-context-window-raw-v1"
            try attachJSON(raw, name: "paired-context-" + label + "-raw")
            if let m = snapshot["measurement"] as? [String: Any], let css = m["css"] as? [Double],
               css.count == 4, css[2] > 0, css[3] > 0,
               (snapshot["viewport"] as? [Double])?.count == 4,
               (snapshot["screenBounds"] as? [Double])?.count == 2 {
                do {
                    let capture = try pairedOrientedScreenshot(before: snapshot, name: "paired-context-" + label)
                    record["cropSHA256"] = capture.hash
                    record["cropGeometry"] = capture.geometry
                }
                catch { record["cropError"] = String(describing: error) }
            } else { record["cropError"] = "Measurement/geometry unavailable; no invented crop" }
            if record["cropSHA256"] == nil {
                let full = XCTAttachment(screenshot: XCUIScreen.main.screenshot())
                full.name = "paired-context-" + label + "-full-screen"; full.lifetime = .keepAlways; add(full)
            }
            record["captureFinishedUptimeSeconds"] = ProcessInfo.processInfo.systemUptime
            try attachJSON(record, name: "paired-context-" + label)
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
        // ONE trusted OS portrait-to-landscape change, with no fixture input or restart.
        rotationRequestedAt = ProcessInfo.processInfo.systemUptime
        XCUIDevice.shared.orientation = .landscapeLeft
        let rotationDeadline = rotationRequestedAt! + 30
        var rotated: [String: Any] = [:]
        var rotationError = ""
        repeat {
            do { rotated = try snapshot(app, allowingFailure: true) }
            catch { rotationError = String(describing: error); break }
            if let m = rotated["measurement"] as? [String: Any], let css = m["css"] as? [Double],
               css.count == 4, css[2] > css[3] { break }
            Thread.sleep(forTimeInterval: 0.2)
        } while ProcessInfo.processInfo.systemUptime < rotationDeadline
        if rotationError.isEmpty {
            let css = (rotated["measurement"] as? [String: Any])?["css"] as? [Double] ?? []
            if css.count != 4 || css[2] <= css[3] { rotationError = "Bounded rotation geometry deadline" }
        }
        try capture(rotated, label: "landscape", target: -1, anchor: anchor, error: rotationError)
        // Assert only after all bounded snapshots/crops are attached. Context loss
        // cannot stop collection of the later same-player diagnostic sample.
        XCTAssertEqual(records.count, 4)
        for record in records {
            XCTAssertEqual(record["observationError"] as? String, "")
            let state = record["snapshot"] as? [String: Any] ?? [:]
            XCTAssertEqual(state["epoch"] as? Int, first["epoch"] as? Int)
            XCTAssertEqual(state["failure"] as? String, "")
            XCTAssertNotNil(state["measurement"] as? [String: Any])
        }
    }
    // Test-only normalization; existing screenshot helper and historical artifacts stay untouched.
    private func pairedOrientedScreenshot(before: [String: Any], name: String) throws -> (hash: String, geometry: [String: Any]) {
        let image = XCUIScreen.main.screenshot().image
        let raw = try XCTUnwrap(image.cgImage)
        let rawAttachment = XCTAttachment(image: image)
        rawAttachment.name = name + "-raw-full"; rawAttachment.lifetime = .keepAlways; add(rawAttachment)
        try attachJSON(["rawCGPixels": [raw.width, raw.height], "imageOrientation": image.imageOrientation.rawValue,
            "imagePointSize": [image.size.width, image.size.height], "imageScale": image.scale,
            "screenBounds": before["screenBounds"] ?? [], "viewport": before["viewport"] ?? []], name: name + "-raw-image-geometry")
        let swapsAxes: Bool
        switch image.imageOrientation {
        case .left, .right, .leftMirrored, .rightMirrored: swapsAxes = true
        default: swapsAxes = false
        }
        let width = swapsAxes ? raw.height : raw.width
        let height = swapsAxes ? raw.width : raw.height
        let format = UIGraphicsImageRendererFormat(); format.scale = 1; format.opaque = true; format.preferredRange = .standard
        let normalized = UIGraphicsImageRenderer(size: CGSize(width: CGFloat(width), height: CGFloat(height)), format: format).image { _ in
            image.draw(in: CGRect(x: 0, y: 0, width: CGFloat(width), height: CGFloat(height)))
        }
        let cg = try XCTUnwrap(normalized.cgImage)
        let normalizedAttachment = XCTAttachment(image: normalized)
        normalizedAttachment.name = name + "-normalized-full"; normalizedAttachment.lifetime = .keepAlways; add(normalizedAttachment)
        let viewport = try XCTUnwrap(before["viewport"] as? [Double])
        let screen = try XCTUnwrap(before["screenBounds"] as? [Double])
        let dpr = try XCTUnwrap(before["screenScale"] as? Double)
        let css = try XCTUnwrap((before["measurement"] as? [String: Any])?["css"] as? [Double])
        guard screen.count == 2, viewport.count == 4, css.count == 4,
              abs(Double(cg.width) - screen[0] * dpr) <= 1,
              abs(Double(cg.height) - screen[1] * dpr) <= 1 else {
            throw Failure.invalid("Oriented screenshot does not match independent screen/DPR")
        }
        let rect = CGRect(x: (viewport[0] + css[0]) * dpr, y: (viewport[1] + css[1]) * dpr,
                          width: css[2] * dpr, height: css[3] * dpr).integral
        let geometry: [String: Any] = ["rawCGPixels": [raw.width, raw.height],
            "imageOrientation": image.imageOrientation.rawValue, "normalization": "UIImage.draw-oriented-scale1-v1",
            "normalizedPixels": [cg.width, cg.height], "cropRectPixels": [rect.origin.x, rect.origin.y, rect.width, rect.height]]
        try attachJSON(geometry, name: name + "-crop-geometry")
        guard rect.minX >= 0, rect.minY >= 0, rect.maxX <= CGFloat(cg.width), rect.maxY <= CGFloat(cg.height) else {
            throw Failure.invalid("Oriented crop outside screen")
        }
        let crop = try XCTUnwrap(cg.cropping(to: rect))
        guard crop.width == Int(rect.width), crop.height == Int(rect.height) else {
            throw Failure.invalid("Oriented crop was clipped")
        }
        let bytes = try XCTUnwrap(UIImage(cgImage: crop).pngData())
        let attachment = XCTAttachment(data: bytes, uniformTypeIdentifier: "public.png")
        attachment.name = name + "-canvas.png"; attachment.lifetime = .keepAlways; add(attachment)
        return (SHA256.hash(data: bytes).map { String(format: "%02x", $0) }.joined(), geometry)
    }

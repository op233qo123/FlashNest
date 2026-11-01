#if DEBUG
import XCTest
import UIKit
import WebKit
import CryptoKit
@testable import FlashNest

/// Test-target-only neutral SWFs and observation. No production observer/resource changes.
@MainActor final class UnloadWKSmokeTests: XCTestCase {
    private static let runtimeFiles: [String: String] = [
        "36b3cbd33c368ba3e094.wasm": "65bfde20229c0ea07a944dbb6a61f8de438826ea8fa7c3dc98a7d5ab60cab685",
        "81a207f7dca57201d407.wasm": "b65fd06f17f68b1c30417dc19cd406016f445c3ff7ff93c1ce9286527f65be7b",
        "LICENSE_APACHE": "62c7a1e35f56406896d7aa7ca52d0cc0d272ac022b5d2796e7d6905db8a3636a",
        "LICENSE_MIT": "4de9338a7879c68e911742a7d691f0797ff1ef8d8a6fb978b0c711e258fe959c",
        "README.md": "cdbeefd04e27a2fe80f735210fa4c054e376802eb43a16d9b6eeae78500f2bde",
        "core.ruffle.b37b03400c42af4f2df8.js": "1643fa872c336e5a920a5ab5f0e89d8d0f19f6fe3af9dbd6812e94832d7c6c70",
        "core.ruffle.b37b03400c42af4f2df8.js.map": "6908db6111d775763a979c772b54a2cb450a0d9ea24d1937f2ef006279928e0a",
        "core.ruffle.b66cd8f7f9bc4f6102a5.js": "97583a8ea68de971dde69fd12c8aa86a3ac2c5e4556b29d675dec292cb840d1c",
        "core.ruffle.b66cd8f7f9bc4f6102a5.js.map": "5b3fc8490d7714667d08fd2c7c59efb08425cfe7f0be847a4f9bd44a437e58ed",
        "package.json": "822dd0fe6f6a84d4ab41351acd2a789aa9ef75b3fe454ab846c0858157c48d89",
        "ruffle.js": "659463197f43c2232ee6047d078c2b19e094a3feb63c6e86534b7799dad9e552",
        "ruffle.js.map": "5b01b95ac87730e011ef9cbc2793b48f2b5ac03102d6f234de6946e31f7c5144"
    ]
    private static let fixtures: [String: (String, String)] = [
        "attached-fresh.swf": ("RldTJZUJAABoABkAAASwAAAYAQBEEQgAAABDAiAwQL8UYQkAAAAAAABuZXV0cmFsLWxvYWRlci1jaGFpbgAQAC4AAQEBXgdzdGFydGVkCm5lc3RlZE9uY2UFdHJhY2UTTU9ERTphdHRhY2hlZC1mcmVzaA1mbGFzaC5kaXNwbGF5BkxvYWRlcgZsb2FkZXIRY29udGVudExvYWRlckluZm8EaW5pdAZvbkluaXQQYWRkRXZlbnRMaXN0ZW5lcghjb21wbGV0ZQpvbkNvbXBsZXRlBnVubG9hZAhvblVubG9hZAdpb0Vycm9yB29uRXJyb3INc2VjdXJpdHlFcnJvcghhZGRDaGlsZAlmaXJzdC5zd2YHUkVRVUVTVAlmbGFzaC5uZXQKVVJMUmVxdWVzdARsb2FkCk1haW4kaWluaXQEdm9pZA5GSVJTVF9DT01QTEVURQdjb250ZW50BGhlbGQGcGFyZW50GVBSRV9DT05URU5UX1BBUkVOVF9MT0FERVIKbG9hZGVySW5mbxZQUkVfQ09OVEVOVF9JTkZPX01BVENIBXRva2VuD1BSRV9GSVJTVF9UT0tFTgplbnRlckZyYW1lDG9uVHJhbnNpdGlvbg1jdXJyZW50VGFyZ2V0DG5leHRDYXB0dXJlZA1ORVhUX0NPTVBMRVRFFE5FWFRfQ09OVEVOVF9QUkVTRU5UEk5FWFRfUEFSRU5UX0xPQURFUg9ORVhUX0lORk9fTUFUQ0gZTkVYVF9MT0FERVJfQ09OVEVOVF9NQVRDSAtudW1DaGlsZHJlbhRORVhUX0NISUxEX0NPVU5UX09ORRdPTERfQ0hJTERfTk9UX0lOX0xPQURFUgpORVhUX1RPS0VOE0NPTVBMRVRFX0lORk9fTUFUQ0gPTWFpbiRvbkNvbXBsZXRlE3JlbW92ZUV2ZW50TGlzdGVuZXIWVFJBTlNJVElPTl9FTlRFUl9GUkFNRSJQUkVfQVRUQUNIRURfQ09OVEVOVF9QQVJFTlRfTE9BREVSC3JlbW92ZUNoaWxkFlBSRV9MT0FERVJfUEFSRU5UX05VTEwRVU5MT0FEX0NBTExfQkVHSU4NdW5sb2FkQW5kU3RvcBRVTkxPQURfQ0FMTF9SRVRVUk5FRAxVTkxPQURfQkVHSU4RVU5MT0FEX0lORk9fTUFUQ0gWVU5MT0FEX0NP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", "3d5490c638617f8fc870e7c1d793e1a001cc7887661bb991b6f4d8c3ac6630f4"),
        "moved-removed-fresh.swf": ("RldTJe4JAABoABkAAASwAAAYAQBEEQgAAABDAiAwQL8UugkAAAAAAABuZXV0cmFsLWxvYWRlci1jaGFpbgAQAC4AAQEBYQdzdGFydGVkCm5lc3RlZE9uY2UFdHJhY2UYTU9ERTptb3ZlZC1yZW1vdmVkLWZyZXNoDWZsYXNoLmRpc3BsYXkGTG9hZGVyBmxvYWRlchFjb250ZW50TG9hZGVySW5mbwRpbml0Bm9uSW5pdBBhZGRFdmVudExpc3RlbmVyCGNvbXBsZXRlCm9uQ29tcGxldGUGdW5sb2FkCG9uVW5sb2FkB2lvRXJyb3IHb25FcnJvcg1zZWN1cml0eUVycm9yCGFkZENoaWxkCWZpcnN0LnN3ZgdSRVFVRVNUCWZsYXNoLm5ldApVUkxSZXF1ZXN0BGxvYWQKTWFpbiRpaW5pdAR2b2lkDkZJUlNUX0NPTVBMRVRFB2NvbnRlbnQEaGVsZAZwYXJlbnQZUFJFX0NPTlRFTlRfUEFSRU5UX0xPQURFUgpsb2FkZXJJbmZvFlBSRV9DT05URU5UX0lORk9fTUFUQ0gFdG9rZW4PUFJFX0ZJUlNUX1RPS0VOBlNwcml0ZQZob2xkZXIZUFJFX0NPTlRFTlRfUEFSRU5UX0hPTERFUgplbnRlckZyYW1lDG9uVHJhbnNpdGlvbg1jdXJyZW50VGFyZ2V0DG5leHRDYXB0dXJlZA1ORVhUX0NPTVBMRVRFFE5FWFRfQ09OVEVOVF9QUkVTRU5UEk5FWFRfUEFSRU5UX0xPQURFUg9ORVhUX0lORk9fTUFUQ0gZTkVYVF9MT0FERVJfQ09OVEVOVF9NQVRDSAtudW1DaGlsZHJlbhRORVhUX0NISUxEX0NPVU5UX09ORRdPTERfQ0hJTERfTk9UX0lOX0xPQURFUgpORVhUX1RPS0VOE0NPTVBMRVRFX0lORk9fTUFUQ0gPTWFpbiRvbkNvbXBsZXRlE3JlbW92ZUV2ZW50TGlzdGVuZXIWVFJBTlNJVElPTl9FTlRFUl9GUkFNRQRzdG9wC3JlbW92ZUNoaWxkFVBSRV9NT1ZFRF9QQVJFTlRfTlVMTBZQUkVfTE9BREVSX1BBUkVOVF9OVUxMEVVOTE9BRF9DQUxMX0JFR0lODXVubG9hZEFuZFN0b3AUVU5MT0FEX0NBTExfUkVUVVJORUQMVU5M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", "1143a768d220882e6fa45e57a2d549af810c2c0b27bbff48a60ca5ce7aa5613c"),
        "first.swf": ("RldTJVUCAABoABkAAASwAAAYAQBEEQgAAABDAiAwQBsJAQAFEAAQAHic+/9MLur/KB7Fo3hEYgDVBF0fIQgCAFAAoAAKAAFBAQDZQAAFAAAAABAUJ4FA4VA4LA4bAAC/FNgBAAAAAAAAbmV1dHJhbC1sb2FkZXItY2hhaW4AEAAuAAEBARYIZ3JhcGhpY3MJYmVnaW5GaWxsCGRyYXdSZWN0B2VuZEZpbGwFdG9rZW4FdHJhY2UXRklSU1RfQ0hJTERfQ09OU1RSVUNURUQLQ2hpbGQkaWluaXQEdm9pZAtDaGlsZCRjaW5pdAVDaGlsZAZPYmplY3QMZmxhc2guZXZlbnRzD0V2ZW50RGlzcGF0Y2hlcg1mbGFzaC5kaXNwbGF5DURpc3BsYXlPYmplY3QRSW50ZXJhY3RpdmVPYmplY3QWRGlzcGxheU9iamVjdENvbnRhaW5lcgZTcHJpdGUJTW92aWVDbGlwDHByb2JlJHNjcmlwdAQWABYNFg8BEAcBAQcBAgcBAwcBBAcBBQcBBgcBCQcBCwcBDAcCDgcDEAcDEQcDEgcDEwcDFAMABwgAAAcKAAAHFQAAAQgPAAAAAAEAAQIBCAQBAAMAFAEJCi7QMNBJANAkJWEF0GYBJX9PAgHQZgEkACQAJHgkWk8DBNBmAU8EAF0GLAdPBgFHAAABFAEICQPQMEcAAAIUAQAIJ9AwZQBgCTBgCjBgCzBgDDBgDTBgDjBgDzBgD1gAHR0dHR0dHWgIRwAAChMBAAAAQ2hpbGQAhgYGAQACAABAAAAA", "d6df252cec9df57f0f7dfe75329396a90568b33a803e6ca9adc24956e13acfe4"),
        "next.swf": ("RldTJVYCAABoABkAAASwAAAYAQBEEQgAAABDAiAwQBsJAQAFEAAQAHic+y9n8+z/KB7Fo3hEYgB9cT8fIQgCAFAAoAAKAAFBAQDZQAAFAAAAABAUJ4FA4VA4LA4bAAC/FNkBAAAAAAAAbmV1dHJhbC1sb2FkZXItY2hhaW4AEAAuAAEBARYIZ3JhcGhpY3MJYmVnaW5GaWxsCGRyYXdSZWN0B2VuZEZpbGwFdG9rZW4FdHJhY2UWTkVYVF9DSElMRF9DT05TVFJVQ1RFRAtDaGlsZCRpaW5pdAR2b2lkC0NoaWxkJGNpbml0BUNoaWxkBk9iamVjdAxmbGFzaC5ldmVudHMPRXZlbnREaXNwYXRjaGVyDWZsYXNoLmRpc3BsYXkNRGlzcGxheU9iamVjdBFJbnRlcmFjdGl2ZU9iamVjdBZEaXNwbGF5T2JqZWN0Q29udGFpbmVyBlNwcml0ZQlNb3ZpZUNsaXAMcHJvYmUkc2NyaXB0BBYAFg0WDwEQBwEBBwECBwEDBwEEBwEFBwEGBwEJBwELBwEMBwIOBwMQBwMRBwMSBwMTBwMUAwAHCAAABwoAAAcVAAABCA8AAAAAAQABAgEIBAEAAwAUAQkKMNAw0EkA0CRKYQXQZgElgP4BTwIB0GYBJAAkACR4JFpPAwTQZgFPBABdBiwHTwYBRwAAARQBCAkD0DBHAAACFAEACCfQMGUAYAkwYAowYAswYAwwYA0wYA4wYA8wYA9YAB0dHR0dHR1oCEcAAAoTAQAAAENoaWxkAIYGBgEAAgAAQAAAAA==", "0fd738094cabcbd910be73d76d47dd4b152833fed9b15b6fd2f6046225b2cc36")
    ]

    func testAttachedLoaderUnloadsAndContinuesInWKWebView() async throws {
        try await exercise(mode: "attached-fresh")
    }
    func testMovedRemovedLoaderUnloadsAndContinuesInWKWebView() async throws {
        try await exercise(mode: "moved-removed-fresh")
    }

    private func digest(_ data: Data) -> String {
        SHA256.hash(data: data).map { String(format: "%02x", $0) }.joined()
    }

    private func exercise(mode: String) async throws {
        executionTimeAllowance = 180
        let web = try XCTUnwrap(Bundle.main.url(forResource: "Web", withExtension: nil))
        let runtime = web.appendingPathComponent("runtime", isDirectory: true)
        let listed = try FileManager.default.contentsOfDirectory(at: runtime, includingPropertiesForKeys: [.isRegularFileKey])
        XCTAssertEqual(Set(listed.map(\.lastPathComponent)), Set(Self.runtimeFiles.keys))
        XCTAssertEqual(Self.runtimeFiles.count, 12)
        for (name, expected) in Self.runtimeFiles {
            let url = runtime.appendingPathComponent(name)
            XCTAssertEqual(try url.resourceValues(forKeys: [.isRegularFileKey]).isRegularFile, true)
            XCTAssertEqual(digest(try Data(contentsOf: url)), expected, "Bundled candidate runtime differs: \(name)")
        }

        let temporary = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        let source = temporary.appendingPathComponent("neutral")
        let library = temporary.appendingPathComponent("library")
        try FileManager.default.createDirectory(at: source, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: temporary) }
        var fixtureHashes: [String: String] = [:]
        for (sourceName, destinationName) in [(mode + ".swf", "main.swf"), ("first.swf", "first.swf"), ("next.swf", "next.swf")] {
            let fixture = try XCTUnwrap(Self.fixtures[sourceName])
            let data = try XCTUnwrap(Data(base64Encoded: fixture.0))
            XCTAssertEqual(digest(data), fixture.1)
            try data.write(to: source.appendingPathComponent(destinationName))
            fixtureHashes[sourceName] = fixture.1
        }
        var package = try PackageImporter(root: library).stageAndCommit(source)
        // Importer sorts entries; explicitly choose the neutral root, not first.swf.
        XCTAssertTrue(package.movies.contains("main.swf"))
        package.selectedMovie = "main.swf"
        let session = PlayerSession()
        let scene = try XCTUnwrap(UIApplication.shared.connectedScenes.compactMap { $0 as? UIWindowScene }.first)
        let previousWindow = scene.windows.first(where: { $0.isKeyWindow })
        let window = UIWindow(windowScene: scene)
        let controller = UIViewController()
        window.rootViewController = controller
        window.makeKeyAndVisible()
        controller.loadViewIfNeeded()
        defer {
            session.webView?.removeFromSuperview()
            session.stop()
            window.isHidden = true
            previousWindow?.makeKey()
        }
        await session.start(package: package, contentRoot: library.appendingPathComponent(package.id.uuidString).appendingPathComponent("content"))
        let view = try XCTUnwrap(session.webView)
        view.frame = controller.view.bounds
        view.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        controller.view.addSubview(view)
        let startupDeadline = Date().addingTimeInterval(100)
        while !session.isLoaded && Date() < startupDeadline {
            if let failure = session.failure { XCTFail(failure); return }
            try await Task.sleep(nanoseconds: 100_000_000)
        }
        XCTAssertTrue(session.isLoaded, "WKWebView did not load the actual neutral root SWF: \(session.diagnostics)")
        guard session.isLoaded else { return }
        XCTAssertFalse(view.isHidden)
        XCTAssertNotNil(view.window)

        // Require the actual loaded/paused player and enabled Start button on two
        // successive main-loop observations before replacing the test observer.
        var stableReady = 0
        let readyDeadline = Date().addingTimeInterval(5)
        while stableReady < 2 && Date() < readyDeadline {
            let ready = (try await view.evaluateJavaScript("!document.getElementById('start').disabled && !!document.querySelector('ruffle-player').ruffle().metadata && document.querySelector('ruffle-player').ruffle().isPlaying === false") as? Bool) == true
            stableReady = ready ? stableReady + 1 : 0
            try await Task.sleep(nanoseconds: 100_000_000)
        }
        XCTAssertEqual(stableReady, 2, "Actual paused WK instance was not ready for the observer")
        guard stableReady == 2 else { return }

        // Install only after the actual Ruffle instance exists, before playback.
        // Avoid production trace rate limiting without changing the app's shell.
        _ = try await view.evaluateJavaScript("""
        window.__unloadWK = {traces:[],errors:[],responses:[],overflow:false};
        const probe = window.__unloadWK;
        document.querySelector('ruffle-player').ruffle().traceObserver = message => {
          if (probe.traces.length < 100) probe.traces.push(String(message)); else probe.overflow=true;
        };
        window.addEventListener('error', event => { if(probe.errors.length<20) probe.errors.push(String(event.message)); });
        window.addEventListener('unhandledrejection', event => { if(probe.errors.length<20) probe.errors.push(String(event.reason)); });
        for (const name of ['error','log']) {
          const original = console[name];
          console[name] = function(...args) {
            if(name==='error' || args.some(value=>typeof value==='string' && value.includes('%cERROR%c'))) {
              if(probe.errors.length<20) probe.errors.push(args.map(String).join(' ').slice(0,1000)); else probe.overflow=true;
            }
            return original.apply(console,args);
          };
        }
        const oldFetch = window.fetch.bind(window);
        window.fetch = async (...args) => {
          const response = await oldFetch(...args);
          const name = new URL(response.url).pathname.split('/').pop();
          if(name?.endsWith('.swf') && probe.responses.length<10) probe.responses.push({name,status:response.status});
          return response;
        };
        document.getElementById('start').click(); true;
        """)
        let transitionDeadline = Date().addingTimeInterval(30)
        var completed = false
        while Date() < transitionDeadline {
            if let failure = session.failure { XCTFail(failure); return }
            completed = (try await view.evaluateJavaScript("window.__unloadWK.traces.includes('NEXT_TOKEN true')") as? Bool) == true
            if completed { break }
            try await Task.sleep(nanoseconds: 100_000_000)
        }
        // Observe beyond completion for duplicate notification/late process failure.
        let observationStart = ProcessInfo.processInfo.systemUptime
        try await Task.sleep(nanoseconds: 5_500_000_000)
        let raw = try await view.evaluateJavaScript("""
        JSON.stringify((() => {
          const player=document.querySelector('ruffle-player');
          const canvas=player?.shadowRoot?.querySelector('canvas');
          const gl=canvas && (canvas.getContext('webgl2') || canvas.getContext('webgl') || canvas.getContext('experimental-webgl'));
          return {...window.__unloadWK,metadata:player?.ruffle().metadata,
            actualWebGL:!!gl,glVersion:gl ? gl.getParameter(gl.VERSION) : null,
            wasm:performance.getEntriesByType('resource').map(r=>new URL(r.name).pathname.split('/').pop()).filter(n=>n?.endsWith('.wasm')),
            documentHidden:document.hidden};
        })());
        """) as? String
        let observationElapsed = ProcessInfo.processInfo.systemUptime - observationStart
        let text = try XCTUnwrap(raw)
        let data = try XCTUnwrap(text.data(using: .utf8))
        let observation = try XCTUnwrap(JSONSerialization.jsonObject(with: data) as? [String: Any])
        var receipt = observation
        receipt["mode"] = mode
        receipt["completionObserved"] = completed
        if completed { receipt["observationSecondsAfterCompletion"] = observationElapsed }
        else { receipt["observationSecondsAfterCompletion"] = NSNull() }
        receipt["runtimeFiles"] = Self.runtimeFiles
        receipt["fixtureFiles"] = fixtureHashes
        receipt["scope"] = "Actual WKWebView neutral Loader smoke; not physical device or private game acceptance"
        receipt["physicalDeviceCertified"] = false
        receipt["productionFixtureShipping"] = false
        let receiptData = try JSONSerialization.data(withJSONObject: receipt, options: [.sortedKeys])
        let attachment = XCTAttachment(data: receiptData, uniformTypeIdentifier: "public.json")
        attachment.name = "neutral-unload-wk-" + mode
        attachment.lifetime = .keepAlways
        add(attachment)
        print("FLASHNEST_UNLOAD_WK_EVIDENCE " + String(decoding: receiptData, as: UTF8.self))
        XCTAssertNil(session.failure)
        XCTAssertGreaterThanOrEqual(observationElapsed, 5.5)
        XCTAssertTrue(completed, "WK continuation did not finish: \(text)")
        let traces = try XCTUnwrap(observation["traces"] as? [String])
        XCTAssertEqual(observation["overflow"] as? Bool, false)
        XCTAssertEqual(observation["documentHidden"] as? Bool, false)
        XCTAssertEqual(observation["actualWebGL"] as? Bool, true)
        XCTAssertEqual(observation["errors"] as? [String], [])
        for marker in ["FIRST_COMPLETE", "PRE_CONTENT_PARENT_LOADER true", "PRE_CONTENT_INFO_MATCH true", "PRE_FIRST_TOKEN true", "TRANSITION_ENTER_FRAME", "PRE_LOADER_PARENT_NULL true", "UNLOAD_BEGIN", "UNLOAD_INFO_MATCH true", "UNLOAD_LISTENER_REMOVED", "FRESH_LOADER_CREATED", "UNLOAD_END", "UNLOAD_CALL_RETURNED", "NEXT_CHILD_CONSTRUCTED", "NEXT_COMPLETE", "NEXT_CONTENT_PRESENT true", "NEXT_PARENT_LOADER true", "NEXT_INFO_MATCH true", "NEXT_LOADER_CONTENT_MATCH true", "NEXT_CHILD_COUNT_ONE true", "OLD_CHILD_NOT_IN_LOADER true", "NEXT_TOKEN true"] {
            XCTAssertEqual(traces.filter { $0 == marker }.count, 1, "Marker differs: \(marker); \(text)")
        }
        XCTAssertEqual(traces.filter { $0 == "INIT" }.count, 2)
        XCTAssertEqual(traces.filter { $0 == "INIT_INFO_MATCH true" }.count, 2)
        XCTAssertEqual(traces.filter { $0 == "COMPLETE_INFO_MATCH true" }.count, 2)
        XCTAssertFalse(traces.contains { $0.hasPrefix("LOAD_ERROR") || $0.hasSuffix(" false") })
        if mode == "moved-removed-fresh" {
            XCTAssertTrue(traces.contains("PRE_CONTENT_PARENT_HOLDER true"))
            XCTAssertTrue(traces.contains("PRE_MOVED_PARENT_NULL true"))
        } else { XCTAssertTrue(traces.contains("PRE_ATTACHED_CONTENT_PARENT_LOADER true")) }
        let sequence = ["FIRST_COMPLETE", "TRANSITION_ENTER_FRAME", "PRE_LOADER_PARENT_NULL true", "UNLOAD_CALL_BEGIN", "UNLOAD_BEGIN", "UNLOAD_LISTENER_REMOVED", "NEXT_BEGIN", "REQUEST next.swf", "NEXT_LOAD_RETURNED", "UNLOAD_END", "UNLOAD_CALL_RETURNED", "NEXT_CHILD_CONSTRUCTED", "NEXT_COMPLETE"]
        let indices = try sequence.map { try XCTUnwrap(traces.firstIndex(of: $0), "Missing \($0)") }
        XCTAssertTrue(zip(indices, indices.dropFirst()).allSatisfy { pair in pair.0 < pair.1 })
        let initIndices = traces.indices.filter { traces[$0] == "INIT" }
        if initIndices.count == 2 {
            let nextConstructed = try XCTUnwrap(traces.firstIndex(of: "NEXT_CHILD_CONSTRUCTED"))
            let nextComplete = try XCTUnwrap(traces.firstIndex(of: "NEXT_COMPLETE"))
            XCTAssertLessThan(nextConstructed, initIndices[1])
            XCTAssertLessThan(initIndices[1], nextComplete)
        }
        let responses = try XCTUnwrap(observation["responses"] as? [[String: Any]])
        XCTAssertEqual(responses.compactMap { $0["name"] as? String }, ["first.swf", "next.swf"])
        XCTAssertTrue(responses.allSatisfy { ($0["status"] as? Int) == 200 })
        let wasm = try XCTUnwrap(observation["wasm"] as? [String])
        XCTAssertFalse(wasm.isEmpty, "No actual WK WASM resource observed")
        XCTAssertTrue(wasm.allSatisfy { Self.runtimeFiles[$0] != nil && $0.hasSuffix(".wasm") })
        try await session.closeWithoutSaving()
    }
}
#endif

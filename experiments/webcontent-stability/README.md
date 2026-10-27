# WebContent stability: separate evidence, not a memory/crash-fix claim

## Observations

Archived simulator runs [40499879626](https://github.com/op233qo123/FlashNest/actions/runs/40499879626) and [40489494277](https://github.com/op233qo123/FlashNest/actions/runs/40489494277) contain WebContent main-thread `EXC_BAD_ACCESS / SIGBUS / KERN_PROTECTION_FAILURE` reports with wasm indirect/wide16 frames. Process launch-to-crash intervals are approximately 0.84 s and 3.08 s. Both report JavaScriptCore image UUID `2a5d8fdd-97c9-3ca4-bd81-6bf42408de17`. Their large virtual Gigacage reservations are not resident-memory measurements or jetsam evidence.

The later run failed a repeated save/import/readback launch; later save/restart cases in that same run passed. These simulator startup failures do **not** establish the cause of reported device scene/orientation/foreground transitions. Lower backing resolution is a separate memory/rendering feature, not this investigation's repair.

## Minimal independent native hardening

`PlayerSession` previously checked message main-frame origin/path but not which `WKWebView` sent it. A replacement page uses the same shell path. Stale callbacks could therefore set loaded/error state or enter the save-ready acknowledgement branch for the successor. Generation checks inside an acknowledgement task do not reject a stale message that first arrives after the generation changed.

The change requires the current WK object before accepting a script message or navigation callback. Nil/stopped/terminated/foreign views are rejected; active-page errors remain visible. No reload, timeout extension, automatic restart, cache purge, save-format change or WebKit private API is added.

Apple's public [WKScriptMessage.webView contract](https://developer.apple.com/documentation/webkit/wkscriptmessage/webview) identifies the sending web view. The [WebKit header](https://github.com/WebKit/WebKit/blob/main/Source/WebKit/UIProcess/API/Cocoa/WKScriptMessage.h) exposes that weak reference. [WKFrameInfo](https://github.com/WebKit/WebKit/blob/main/Source/WebKit/UIProcess/API/Cocoa/WKFrameInfo.h) explicitly does not uniquely identify a frame across delegate calls. These API contracts justify object identity fencing; they do not identify the SIGBUS cause.

Three native tests use actual WK pages plus structured synthetic input. One retains an old, stopped storage-only page, starts a replacement, forwards real `WKScriptMessage` objects from both pages through the production adapter, and verifies rejection/acceptance. Other cases verify nil/nonmain/foreign/stopped messages and stale navigation errors. The tests do not recreate a full pending-import race, real OS process death, or wasm crash.

Manual `test-player-callbacks.yml` uses the standard macOS-14 runner, pinned Xcode 16.2 / iOS 18.2 and exact three-case/no-skip validation. Storage-only bootstrap returns before injecting Ruffle, so this focused gate is independent of wasm initialization. It retains raw xcresults, logs, crash reports and source hashes. Test-only bootstrap allowance is 30 seconds (cold WK startup exceeded 15 seconds in earlier CI); production handshake limits stay unchanged. No native result is claimed until the workflow actually runs.

## Next bounded transition measurement

Use an original fixture with explicit child load/unload and input/save counters. Keep engine, renderer, dimensions and simulator fixed between control and callback-fenced builds. Run a fixed mixed sequence: child load → portrait/landscape rotation → actual Home → activate → input-counter check → child unload/reload. Include a paused-menu branch and verify no implicit reload or title reset. Preserve logs/phase markers/xcresults/crashes, count all failures, and never retry until green. A successful callback test is not a transition-stress result.

A separate source-backed hypothesis remains open: pinned Ruffle [WebAudio construction/callbacks](https://github.com/ruffle-rs/ruffle/blob/89a7049965f3090e706265670df309a5128233ac/web/src/audio.rs) schedule buffers even for silent movies. Audio resume/suspend/callback ordering during transitions deserves instrumented measurement; no audio patch or causal claim is made here.

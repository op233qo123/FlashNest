# Corrected original fixture: iOS 18.5 diagnostic failed in both arms

Run **40544811982**, driver `2c5e65c0a6d7e67018898f0835193a571e991237`, job122332447834. Xcode16.4 (16F6), arm64 iPhone16 simulator iOS18.5 (22F77), same UDID erased between arms. Terminal workflow failure; raw `outcomes.txt` is `baseline=failure`, `guarded=failure`. The step UI's post-`continue-on-error` success conclusions are **not** passing test results.

Each raw xcresult summary reports **0 passed / 1 failed / 0 skipped**. Source inventories differ only in pinned `App/Player/PlayerSession.swift`; corrected root SHA256 is `9e6f0768d08018c2ae324dbc61d33eb1d62378f8c7de7b30bc054e1a74a63878`, identical to the accepted original Chrome fixture. No engine change was compared.

## Actual progress and failure

Both arms produced a genuine generation0 STATE after native Enter, with executing root/child heartbeat, keys1, pointers0, ready1, childGeneration0 and errors0. Both attempted the first trusted scene-advance tap; neither produced the required fresh READY1. No rotation or Home phase was reached. This is not a successful transition or a general stability test pass.

- Baseline STATE at17:01:54.817UTC: rootHeartbeat196, childHeartbeat191. Scene-advance phase17:01:54.841. Missing READY1 assertion17:02:49; test failed after163.666s. Failure-only Diagnostics capture did not reach the retained-list footer.
- Guarded STATE at17:11:37.424UTC: rootHeartbeat70, childHeartbeat66. Scene-advance phase17:11:37.435. Failure-only diagnostics encountered an XCTest accessibility snapshot mismatch at17:12:26; test failed after144.339s. That secondary capture failure limits the retained UI evidence; it does not turn the missing READY1 into a pass or establish that the SWF received the tap.

Both pre-capture AX trees show the Ruffle panic heading `Something went wrong :(` and `JavaScript/resource error: RuntimeError: Unreachable code should not be executed`, referring to a WASM closure export with an `f64` argument. Baseline attachment `EE0BD0DC-3592-4399-AC39-8B9CAD6A89BA.txt` and guarded `27B4283F-0FC7-4DCF-98CF-EA093B5D4575.txt` retain this evidence. This is an in-page runtime trap, not a WebContent process crash report. Neither tree proves receipt of pointer1. Guarded indexed-label collection tried to resolve element22 after the matching query had shrunk to six elements, masking the final original assertion in that summary.

## Crash chronology: simulator GPU failure already present before the tap

The retained reports contain **no WebContent process crash**. Baseline has one SimMetalHost and one WebKit.GPU report; guarded has four SimMetalHost and two WebKit.GPU reports. The final catch-all repeats those eight reports; do not double-count them.

| Arm | First host failure (UTC) | First GPU failure (UTC) | First scene tap phase (UTC) |
| --- | --- | --- | --- |
| Baseline |17:01:32.6499, SimMetalHost PID3523 SIGABRT|17:01:33.5366, GPU PID17239 SIGABRT|17:01:54.841|
| Guarded |17:11:22.4843, SimMetalHost PID22685 SIGABRT|17:11:22.5057, GPU PID33606 SIGABRT|17:11:37.435|

First host stacks include `MTLReportFailure` and `_MTLDeserializer argumentEncoderSetValues`; GPU termination namespace METAL/code102 explicitly reports lost SimMetalHost XPC connection, with MTLSimArgumentEncoder/ANGLE draw frames. Guarded later host SIGSEGVs occur at17:11:31.8628,17:11:47.8088 and17:11:51.0371; a second GPU METAL102 termination occurs17:11:47.8115. These are capture timestamps, not delayed report filenames.

The first GPU/host failures **precede the first scene tap in both arms**, despite JavaScript/SWF state still responding. Consequently this run cannot establish that scene unload caused a crash: the simulator graphics path was already damaged. It does not reproduce the user's phone WebContent termination, establish OOM, or justify an App workaround for simulator Metal. Native callback identity hardening has no demonstrated crash-prevention effect here.

## Narrow source correspondence (inference, not root-cause proof)

Pinned Ruffle `web/src/lib.rs` defines `AnimationHandler = Closure<dyn FnMut(f64)>` (line65), creates the timestamp callback invoking `ruffle.tick(timestamp)` (594–598), schedules it with `requestAnimationFrame` (1205–1213), and calls `core.tick` then conditional `core.render` (1245–1250). The reported f64 trampoline is present in the unchanged bundled JS. This is consistent with an animation tick/render trap after the already observed graphics failure; the generic trampoline does not identify the failing instruction. It does not establish a direct WebAudio callback, Loader unload bug, or phone crash cause.

## Evidence and limits

Artifact12753717431:227,649,321bytes, verified ZIP SHA256 `4c90eb9627f070e81302e70011878a56554b77f6dba62ea2e41b2febc8ba5197`; CRC/path checks passed. Retained per-arm raw xcresults, test logs, AX/screenshots, crash reports, source inventories, comparison metadata, raw outcomes and runner identity are the evidence of record. Local inspection root: `/tmp/transition18-40544811982/extracted` (not a public download link).

The historical18.2 comparison used an earlier invalid ABC fixture and also failed in simulator GPU startup. This corrected18.5 run is separately labeled, not a clean OS-only comparison or replacement of those failures. Three intended cycles were never completed. No pressure fixture was executed, no timeout was relaxed, and no automatic page restart was added.

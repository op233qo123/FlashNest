# Renderer isolation run40554346689: useful split, both tests failed

Driver `1674e34bc875f103007c1dce4f49e4d7575d01c0`, job122366265976, Xcode16.4/iOS18.5. Raw outcomes are **default=failure, webgl=failure**. Both summaries contain0passed/1failed/0skipped; neither is retrospectively counted as passing. Verified source inventories differ only in generated `App/Resources/Web/shell.js`, specifically the public WebGL preference. Both use the same guarded Session, corrected original fixture and common observer.

## Actual observations

| Arm | Actual renderer/context | Fresh SWF states | Renderer samples | Home actions | Result |
|---|---|---:|---:|---:|---|
|Default|wgpu-webgl / webgl2|1|2|0|Context lost before scene1; fails live-context assertion|
|Explicit WebGL|webgl / webgl2|14|15|4|All3 scene changes/rotations/Home sequences observed; final diagnostic collector fails|

Default startup observation17:58:57UTC was alive with550×400 buffer. By initial-input observation17:59:25 it reported `lost=true`,0×0,lossEvents1, while generation0 SWF counters still advanced. Reports retain SimMetalHost SIGABRT PID1946 at17:59:03.6470, GPU SIGABRT/METAL102 PID13314 at17:59:05.3240 (lost SimMetalHost XPC connection), and SimMetalHost SIGSEGV PID13899 at17:59:06.6423. No WebContent crash report was collected. No scene tap, rotation or Home was attempted in this arm after the failed context check.

WebGL observations retain one boot token, one renderer banner, zero context-loss events, positive buffers throughout, generation0→3, pointers0→3, keys1→14, unloadCalls/unloadEvents0→3, zero fixture errors and advancing child heartbeats. All four actual Home actions and portrait/landscape transitions were recorded. No test-window WebKit/SimMetalHost crash reports were collected for this arm. These are bounded observed facts, not the final test outcome.

The WebGL test failed at final diagnostics line319 with stale indexed accessibility collection (element23 no longer present), after all transition observations. It did not emit `FLASHNEST_TRANSITION_COMPLETE`, and the full retained diagnostic footer/error inspection did not finish. A narrowly reviewed test-only immutable-snapshot repair is required for a clean gate; no assertion, timeout or runtime behavior should be weakened to manufacture a pass.

## Pixel inspection

The retained WebGL video shows the original pink child on the dark-blue stage at80s and140/195s (landscape), and again at218s near the final portrait observation. A215s sample briefly lacked the pink child during rotation; it was present at218s, so the earlier frame does not establish persistent projection failure. These sampled images corroborate visible rendering at those times, not every frame. The default lost-context sample at90s shows the blue stage without the child. Backend/context counters alone are not pixel proof.

## Evidence and limits

Artifact12757123086:322,009,588bytes; verified ZIP SHA256 `bc24c3c84c359ff203284d319a244b08619729e9ebb1aad5a0ca67c8335d2108`; CRC/path checks passed. Local inspection root `/tmp/renderer-40554346689/extracted`. Raw summaries, per-arm logs, source manifests, xcresults, crash reports and video remain unmodified. The final catch-all repeats the three default-arm reports; do not double-count them.

This is a small original fixture on a hosted simulator, with sequential host/order noise. It narrows a simulator rendering failure; it does not establish the user's phone termination cause, OOM, or a general stability fix. Direct WebGL has renderer feature limitations, so these observations alone do not justify silently changing the App default. No user game assets were executed or uploaded.

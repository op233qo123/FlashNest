# Opt-in native capture harness

`FrameOrderRuntimeTests.swift` is deliberately **not** in `Tests`, and these
original SWFs are deliberately **not** in the normal `fixtures` resources.
The default app and test targets remain unchanged. The separate manual-only
`diagnose-frame-order.yml` workflow stages this harness in a disposable checkout
and captures measurements without producing an IPA. Its `variant` choice defaults to
`both`; `control` and `nested` select only the named test without weakening checks.
Completed native measurements are recorded in [NATIVE_RESULTS.md](NATIVE_RESULTS.md).

## What it measures

- Imports each original SWF through `PackageImporter`, then runs the actual
  `PlayerSession` → `LoopbackServer` → bundled shell → Ruffle/WASM path in a
  visible iOS `WKWebView`.
- Checks package version `0.7.1` and the SHA-256 of `ruffle.js` and both bundled
  WASM files against the existing `runtime.files.json` pins. The manual gate
  should also run `scripts/test_static.py` to verify all runtime files.
- Installs a public `traceObserver` before pressing Play. Its test-only wrapper
  captures later observer assignments too, so the shell finishing `load()`
  cannot silently replace it. This modifies only the diagnostic page's observer
  setter, not SWF bytecode, frame state, app sources, or runtime files.
- Captures up to 512 ordered raw trace strings with sequence and elapsed time.
  Production diagnostics are **not** the trace source: the shell caps traces at
  20/second and `PlayerSession` keeps only 60 diagnostics. Those diagnostics are
  retained separately for context.
- Requires `FO_P1_BEGIN`, all `FO_STATE` ticks 1 through 12, and `FO_DONE 12 P B`.
  Buffer overflow, line truncation, missing first trace, or missing completion
  is an **incomplete measurement**, not a timeline-order result.
- Saves success and failure captures as always-retained XCTest attachments:
  `frame-order-<variant>.json` and `frame-order-<variant>.trace.txt`. The JSON is
  also printed between `FRAME_ORDER_CAPTURE_BEGIN/END` markers in `test.log`.
- Every diagnostic JavaScript evaluation uses a callback/continuation deadline:
  observer installation and Play get 3 seconds each, completion polling gets at
  most 2 seconds per call and shares the 12-second observation deadline, and the
  final snapshot gets 2 seconds. Late callbacks cannot resume a timed-out
  continuation twice. Snapshot failure is reported separately from the original
  operation failure; fallback native evidence is still attached.
- Evidence is attached **before** teardown. Both success and caught failure paths
  await `session.closeWithoutSaving()` to drain the stable-port server; that
  server's `stopAndWait` has a 5-second timeout. Cleanup gets its own retained
  `.cleanup.txt` attachment and does not replace the original failure. If drain
  confirmation fails, the next test in this diagnostic class is skipped rather
  than reusing an unconfirmed port. Synchronous `session.stop()` is not used as a
  substitute for awaited teardown.

**A passing test means the observation was captured completely.** It does not
mean the nested-goto implementation is Flash-compatible. No assertion requires
`FO_P2_TARGET`, `FO_P3_REACHED`, `FO_B_CLOSED_STOP`, or `FO_B_OPENING`, and no
`isPlaying` assertion is made. Sampled P/B frame numbers come from the original
fixture's trace, not a guessed Ruffle inspection API. `FO_DONE` occurs during
ENTER_FRAME12, not after all its scripts: queued scripts can still execute and
restart playback afterward. Compare both raw outputs.

There has been **no Adobe Flash execution** of this original fixture. An engine
corner case reproduced here would still not prove the user's full game follows
that path. Upstream Flash-reference test outputs are separate evidence.

## Manual staging in a disposable checkout

Use the pinned Xcode 16.2, XcodeGen 2.42.0, exact Swift dependency,
runtime-fetch/checksum, and installed iOS Simulator 18.2 selection documented in
`.github/workflows/diagnose-frame-order.yml` (`macos-14`). Keep this diagnostic
separate from release workflows; do not run IPA release steps for a capture.

After approval, stage these files **before** `xcodegen generate`:

```bash
set -euo pipefail
test ! -e Tests/FrameOrderRuntimeTests.swift
test ! -e fixtures/frame-order-experiment
cleanup() {
  rm -f Tests/FrameOrderRuntimeTests.swift
  rm -rf fixtures/frame-order-experiment
}
trap cleanup EXIT
cp experiments/frame-order/FrameOrderRuntimeTests.swift Tests/
mkdir fixtures/frame-order-experiment
cp experiments/frame-order/fixtures/nested-child-goto.swf \
   experiments/frame-order/fixtures/control-no-child-goto.swf \
   fixtures/frame-order-experiment/

# Use the project's existing exact/runtime verification setup, then:
python3 scripts/test_static.py
"$XCODEGEN" generate
mkdir -p FlashNest.xcodeproj/project.xcworkspace/xcshareddata/swiftpm
cp Package.resolved FlashNest.xcodeproj/project.xcworkspace/xcshareddata/swiftpm/
xcodebuild -resolvePackageDependencies -project FlashNest.xcodeproj \
  -scheme FlashNest -disableAutomaticPackageResolution

# SIMULATOR_ID must come from the existing select_simulator.py helper, not a
# hard-coded or unavailable device. Fresh output paths avoid old result reuse.
set -o pipefail
xcodebuild test -project FlashNest.xcodeproj -scheme FlashNest \
  -configuration Debug -sdk iphonesimulator \
  -destination "platform=iOS Simulator,id=$SIMULATOR_ID" \
  -destination-timeout 90 -derivedDataPath frame-order-build \
  -resultBundlePath FrameOrderResults.xcresult \
  -disableAutomaticPackageResolution -parallel-testing-enabled NO \
  -maximum-concurrent-test-simulator-destinations 1 \
  -test-timeouts-enabled YES \
  -default-test-execution-time-allowance 120 \
  -maximum-test-execution-time-allowance 120 \
  -only-testing:FlashNestTests/FrameOrderRuntimeTests \
  CODE_SIGNING_ALLOWED=NO CODE_SIGNING_REQUIRED=NO | tee frame-order-test.log
```

In CI, put attachment export in an `if: always()` step; in a local shell, export
after the test command even if its exit status was nonzero:

```bash
mkdir -p frame-order-evidence
xcrun xcresulttool get test-results summary --path FrameOrderResults.xcresult \
  > frame-order-evidence/summary.json
xcrun xcresulttool export attachments --path FrameOrderResults.xcresult \
  --output-path frame-order-evidence/attachments
```

Retain the result bundle or the exported attachments plus
`frame-order-test.log`, the tested commit, simulator/Xcode versions, and
`structural-validation.json`. Do not label a source check or a Chromium run as
an iOS/WebKit pass. Do not publish or upload user SWFs as part of this harness.

## Validation status

- Native compile/execution: **completed in standard GitHub macOS runners**,
  using iPhone 16 arm64 iOS Simulator 18.2. Both variants have complete captures
  across the two runs documented in [NATIVE_RESULTS.md](NATIVE_RESULTS.md).
  No native execution occurred in the Linux authoring workspace.
- `python3 experiments/frame-order/test_harness_js.py` passes embedded observer
  JavaScript syntax/unit checks (late setter replacement, ordered 12-tick
  capture, completion validation, snapshot, truncation, overflow, missing
  player), plus source-only bounded-evaluation/awaited-teardown contracts.
  These validate capture plumbing, not Swift compilation, actual callback
  deadlines, Ruffle, or the fixture.
- A passing capture is measured simulator behavior, not physical-device or
  Adobe-equivalence validation. Exact Adobe reference remains unmeasured.

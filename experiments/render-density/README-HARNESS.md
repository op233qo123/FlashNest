# Isolated render-density browser gate

**Prepared, not yet executed in a real browser.** These files do not enter the
app, default XCTest schemes, bundled runtime or IPA. No game assets are used.
This tests rendering geometry, not game compatibility, Adobe behavior or OOM.

## Run

Use the reviewed engine builder's baseline/candidate runtime directories and
complete flat `.js`/`.wasm` SHA-256 manifest maps. Both manifests are checked
before either payload is served. Use the pinned upstream `npm ci` installation
of **webdriverio 9.32.0** and already-installed matching Chrome/ChromeDriver:

```sh
python3 experiments/render-density/scripts/test_fixture.py
node experiments/render-density/browser-tests/test_helpers.mjs
node experiments/render-density/browser-tests/test_page.mjs
node experiments/render-density/browser-tests/run.mjs \
  --baseline "$DENSITY_BASELINE_DIR/runtime" \
  --candidate "$DENSITY_CANDIDATE_DIR/runtime" \
  --baseline-manifest "$DENSITY_BASELINE_DIR/runtime.browser-manifest.json" \
  --candidate-manifest "$DENSITY_CANDIDATE_DIR/runtime.browser-manifest.json" \
  --webdriverio "$RUFFLE_SOURCE_DIR/web/node_modules/webdriverio" \
  --chrome /path/to/already-installed/google-chrome \
  --driver /path/to/already-installed/chromedriver \
  --backend wgpu-webgl \
  --output "$DENSITY_EVIDENCE_DIR/wgpu-webgl"
```

Run again with `--backend webgl` and a separate output directory. No alternate
browser/driver download, renderer fallback substitution or reduced matrix counts
are accepted. Explicit backend selection and `quality: low` exist **only in this
diagnostic page**, not in the production shell. Chrome's supported
`--force-device-scale-factor` provides separate DPR 1/2/3 sessions; JavaScript
`devicePixelRatio` is never overwritten. Browser capabilities are recorded.
[WebdriverIO binary configuration](https://v9.webdriver.io/docs/driverbinaries/)
requires both browser and driver paths to avoid automatic downloads.

## Required evidence per backend

- 1,080 original geometry runs: 4 scaleModes × 9 align values × 2 odd viewports
  (443×287, 319×481) × 3 DPR values × 5 arms (unchanged runtime at 1, candidate at
  1/.75/.5/.25). Only complete counts can pass. A 60-minute overall deadline and
  bounded WebDriver commands prevent an unlimited diagnostic run.
- Actual canvas dimensions, CSS bounds, client size, WebGL drawing-buffer size,
  runtime-reported backend, requested/effective metadata. Expected backing is
  `max(1, round(floor(clientSize * nativeDPR) * scale))`. A wrong/unsupported target
  backend is a failure, not a passing fallback.
- Five trusted WebDriver corner/center pointer sequences plus a hit-tested drag
  for every geometry case. Values come from real AVM1 `_xmouse`, `_ymouse`,
  `hitTest`, `startDrag` and `stopDrag`, not JavaScript-simulated Stage data.
  Stage width/height/mode/align must match the unchanged runtime exactly;
  pointer/drag coordinates use 0.1 logical-pixel tolerance for serialization.
- Thirty host-element PNG screenshots per backend. RGB pixel differences against
  the unchanged runtime are reported for the showAll/center representative in
  both viewports/all DPRs. Original green-vector/background pixels must exist and the green silhouette
  bounds remain within four CSS pixels of baseline (the coarsest .25 tier
  raster-edge tolerance). Candidate scale 1 additionally requires zero changed
  pixels and zero RGB error against baseline. Lower-tier RGB differences are
  reported; identical antialiasing is **not** asserted for lower-resolution output.
- Ten original nested/control frame-order runs (DPR 1), pinned fixture and golden
  hashes, 12 ordered ticks, one DONE, exact canonical 32/31-row prefix including
  the immediate post-DONE LOOP/OPEN pair. Only additional complete LOOP/OPEN
  pairs after that window are allowed and reported, never silently filtered.
- Canvas-low and WebGL-high negative cases explicitly require effective scale 1
  and unchanged backing after a .5 request. These are separate fallback tests;
  they cannot satisfy a reduced-density target-backend gate.

`results.json` includes all completed cases, actual browser capabilities,
provenance, active failing case, bounded last trace/canvas snapshot and failure.
An incrementally flushed `cases.jsonl` (maximum 16 MiB), atomic `active-case.json`
and upfront `provenance.json` preserve evidence even if the runner is killed.
Allow 65 minutes for the CI step around the 60-minute harness budget.
One extra failure screenshot is retained. Logs and screenshots contain only
original fixtures. Early preflight rejection exits nonzero; preserve runner logs.

## Fixture and limits

`make_fixture.py` deterministically assembles original SWF7/AVM1 movies using a
320×240 logical Stage, a drawn green rectangle, Stage listeners and root mouse
handlers. `test_fixture.py` checks headers, hashes, action lengths, anonymous
functions and branch boundaries. Those checks are **not** a substitute for real
AVM execution. `test_page.mjs` only verifies API/lifecycle wiring with mocks;
`test_helpers.mjs` only tests bounded PNG processing.

This matrix does **not** yet establish BitmapData.draw/cache/filter invalidation,
blend/PixelBender/perspective, Stage3D, focus outlines, UIKit trusted input or
actual iOS device behavior. Those remain separate acceptance gates. No JS heap,
process RSS, GPU texture memory or WebContent memory is measured here. Canvas
pixel counts and screenshot differences must never be presented as measured RAM
savings or a crash/OOM fix. Hosted Chrome may use a software adapter; the recorded
backend is not evidence of physical-GPU acceleration.

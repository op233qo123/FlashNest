# Corrected original geometry, immutable compiled candidate

This manual-only gate reuses experimental build run
[40514553456](https://github.com/op233qo123/FlashNest/actions/runs/40514553456),
commit `a744b8b75ae9eacec28332b0ccf87822ddaae265`, artifact `12738984800`.
The ZIP is 21,929,162 bytes, SHA256
`0d9d638cc1777764342d0a21395906b9a26f7eb53286f231938645775dd8eae2`.
It is **not promoted**, official upstream-approved, or proven iOS-compatible.

## Why the original matrix stopped

Both backends loaded the unchanged full-resolution control successfully and
reported a real 443×287 canvas/GL drawing buffer. Its only trace was
`NaN|showAll|`; zero geometry cases completed. The original assembler incorrectly
included the function bytecode body in DefineFunction's ActionLength. The
[pinned parser](https://github.com/ruffle-rs/ruffle/blob/89a7049965f3090e706265670df309a5128233ac/swf/src/avm1/read.rs)
adds CodeSize separately and then resynchronizes to that combined boundary.
The malformed header therefore skipped later outer instructions. The correction
keeps the header at five bytes, emits the separately sized body afterward, and
updates the independent structural decoder and negative tests. Add2 and all
renderer code are unchanged. Only an actual rerun can establish corrected
fixture execution and geometry results.

## Corrected-fixture run and harness repair

Geometry-only run
[40521059412](https://github.com/op233qo123/FlashNest/actions/runs/40521059412),
harness commit `bfa826dd9b0b1fec306a3902bf8c28a941e2162a`, verified and reused
that exact compiled artifact. The corrected AVM1 fixture produced valid READY
and pointer traces. No complete matrix or candidate tier was validated:

- The first full-resolution WebGL control completed its Stage/pointer/hit-test/
  drag observations, then failed screenshot capture. The runner had imported
  WebdriverIO's browser entry rather than its pinned Node entry.
- The first WGPU-WebGL control received only the last two of five click pairs.
  That timeout did not establish an engine failure or successful input coverage.

The repaired harness now requires the exact
[WebdriverIO 9.32.0 Node export](https://github.com/webdriverio/webdriverio/blob/v9.32.0/packages/webdriverio/package.json),
uses the raw WebDriver screenshot protocol, validates the native viewport/DPR,
and crops exact physical pixels without resizing. It waits for actual visible
original vector/background pixels, then requires each single trusted click's
own DOWN/UP acknowledgements before continuing; it never retries a click.
Bounded trusted DOM pointer observations and actual pinned overlay hit stacks
are retained on failure. Capture errors are retained independently.

The drag start is selected from the visible intersection of the original vector
using its observed SWF coordinate transform. A hard-coded center is invalid for
some portrait/noBorder/edge-alignment controls even when the vector is visible.
All modes and alignments remain in the matrix, with real SWF hitTest and drag
assertions unchanged. Local helper checks cover 72 mode/alignment/aspect
transforms, DPR 1/2/3 crops, transparent-pixel rejection, and bounds. These are
harness checks, not an executed renderer pass. Completed-case counts now include
all applicable visual assertions, not only input observations.

## Verified WebGL result and isolated WGPU warning repair

Run [40526061814](https://github.com/op233qo123/FlashNest/actions/runs/40526061814),
harness commit `d28433d12169b9dabdcc1b27b2887dd4e830db86`, completed all
**1,080 WebGL geometry cases, 10 nested-frame-order cases and two fallback cases**.
The candidate scale-1 representative images were pixel-identical to the unchanged
control; lower tiers passed the bounded vector-silhouette and logical/input gates.
Its retained artifact `12745437329` is 22,430,992 bytes, SHA256
`a340471e13b72e0ea77fa7a84333d0b1903bc740c78f03c9da30e9fc2096f5cb`.

WGPU-WebGL completed **zero cases**: the first unchanged control's trusted click
hit the pinned runtime's visible hardware-acceleration warning rather than the
canvas. The screenshot, shadow hit stack and trusted pointer path agree. This is
not evidence that a candidate tier passed or that engine input failed.

The narrow repair recognizes only that exact warning ID, full text and FAQ link.
It retains the warning text and full/cropped screenshots before one trusted click
on the verified topmost close control, waits for dismissal, then runs the same
backend, real drawing-buffer and visible-pixel checks. Unknown warnings are not
dismissed; clicks are never retried and overlays are not hidden by script or CSS.
Actual bounded GL vendor/renderer strings and optional debug-renderer metadata are
recorded without treating the warning alone as hardware-state proof.

The manual workflow now accepts `both` (default), `webgl` or `wgpu-webgl` and records
the selection. A WGPU-only retry does not rerun or replace the earlier WebGL result;
each selected backend retains its full 1,080/10/2 requirements. The engine patches,
candidate bytes and original fixture bytes are unchanged. WGPU success remains
unestablished until the corrected real browser gate completes, and a software-GPU
Ubuntu result would not establish native iOS GPU compatibility.

## Source-correct hover ordering

The WGPU-only run [40533798697](https://github.com/op233qo123/FlashNest/actions/runs/40533798697)
(commit `44bd5d02452301c5e8ade702aba713c0522867e5`) also completed zero cases.
No warning acknowledgement occurred before the first input; the raw trusted
pointer path again hit the hardware-acceleration modal. Actual GL debug metadata
identified ANGLE SwiftShader. The retained artifact `12747976686` has SHA256
`f197651b6562b1b9287be664d2965b9e420cd84576cfc8fbdac12b5d618df0a8`.

The [pinned frontend](https://github.com/ruffle-rs/ruffle/blob/89a7049965f3090e706265670df309a5128233ac/web/packages/core/src/internal/player/inner.tsx#L743-L752)
registers a **one-shot mouseover** listener for a CPU adapter. Thus the combined
pointerMove+pointerDown action itself opened the modal between hover and press;
this was not an arbitrary asynchronous timer. The corrected harness first sends
one trusted hover-only action, then captures and acknowledges only the exact
known modal. It rechecks backend/backing and visible pixels. Before every game
pointerDown, a separate hover and composed hit-test require the real canvas to be
topmost. A reappearing/unknown overlay fails; no game click or acknowledgement is
retried. No timeout, engine byte, fixture, matrix count or assertion is relaxed.

## Evidence that is reused, not rerun

`verify_artifact.py` verifies the exact ZIP before safe bounded extraction, the
build run/commit/job/API artifact identity, all candidate source/runtime files,
unchanged patch hashes, and baseline/runtime inventories. It then checks raw
logs and exact canonical traces for both headless phases (2 original plus 31
adjacent gates each), and the 63/63 core JS summary with zero pending/failures.
The 31 adjacent gates mean 29 Flash-reference outputs and two preservation tests
for already-known upstream differences, not 31 claims of Adobe equivalence.
The build's failed geometry is explicitly **not** inherited as passing evidence.

The separate workflow `.github/workflows/experiment-render-density-geometry.yml`
uses only read-only repository/Actions permissions and a standard Ubuntu runner.
It downloads only the fixed existing artifact through GitHub's normal API,
checks pinned dependency locks, installs WebDriver dependencies without lifecycle
scripts, and requires the runner's already-installed Chrome and ChromeDriver.
An expired/missing/mismatched artifact fails closed; there is no substitute runtime.
The old runtime build commit and new harness commit are recorded separately.

Each backend must still complete all 1,080 geometry cases, 10 original nested
frame-order cases and two explicit backend fallback cases. This remains an
original synthetic test suite, not a user-game test. Native iOS execution,
additional effects/readback/focus/Stage3D coverage and actual process-memory
measurements remain separate promotion requirements. No shipped runtime, default
application, save data or game assets are modified by this workflow.

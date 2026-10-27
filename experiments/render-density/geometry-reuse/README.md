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

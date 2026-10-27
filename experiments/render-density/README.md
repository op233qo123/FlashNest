# Experimental onscreen rendering density — not shipped

This isolated experiment adds sampling tiers 100%, 75%, 50% and 25% per axis
on top of the exact existing queued-goto guard. It does not alter the current
runtime lock, vendored runtime ZIP, default application, game files or save data.
The original full-resolution path remains the default.

## Contract

The stage's logical viewport, native devicePixelRatio, input coordinates and
ActionScript geometry remain at the original resolution. A separate physical
onscreen backing size is rounded from the original pixel dimensions. WGPU keeps
the original projection across reduced onscreen surfaces and nested blends/masks.
WebGL supports the non-custom-MSAA path. Canvas and custom-MSAA WebGL requests
fail closed to Original; no production backend is forced. Configuration result
metadata is not proof of a functioning GPU: tests additionally inspect actual
canvas/drawing-buffer dimensions, real SWF input and visible output.

This is **not** the archived CSS half-resolution experiment. No CSS shrink,
inverse transform, DPR override or pointer-coordinate shim is used. The earlier
normal-mode viewport mismatch and Simulator Metal-host crash remain historical
failures, not retroactively passed tests.

Only onscreen render targets are reduced. Bitmap assets, filter/cache surfaces,
`BitmapData.draw`, game-created Stage3D buffers, ActionScript heap and game CPU
work are not claimed to shrink. Pixel area is measured separately from memory;
the experiment makes no measured total-RAM or crash-fix claim.

## Evidence status and first gate

Source/fixture/helper checks have been run locally. Rust compilation, actual
browser/GPU execution and native iOS execution have **not** yet run for this
patch. The manual workflow draft first verifies the unchanged queued-goto
control and 31 adjacent upstream cases, then the additive patch, 63 core JS
tests, and full original-geometry browser matrices on standard runners.

The browser control is the unchanged verified queued-goto runtime ZIP, not an
unmodified official Ruffle release. The new candidate is separately named and
retained with exact patches, modified source, dependency locks, build recipe,
license/NOTICE texts and provenance. It is never automatically promoted.

The first geometry gate does not establish all renderer compatibility. Before
shipping any tiers, additional visual gates remain required for filters and
cache invalidation, BitmapData.draw, focus, nested masks/blends, PixelBender,
Stage3D/perspective, context loss, quality changes and real iOS rotation/touch.
Default-output equality, geometry and reduced pixel counts must not be
misrepresented as full visual or memory equivalence.

See `engine-patch/wgpu-density-notes.md` for primary-source scope and risks,
`engine-build/README.md` for the pinned recipe, and `README-HARNESS.md`
for the original fixture matrix and its explicit coverage limits.

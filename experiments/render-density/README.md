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

Run [40514553456](https://github.com/op233qo123/FlashNest/actions/runs/40514553456),
source `a744b8b75ae9eacec28332b0ccf87822ddaae265`, compiled both WASM variants
and passed 63 core JS tests. Both guard-only and density headless phases passed
the two original frame-order cases and 31 adjacent upstream gates (29 strict
reference outputs plus two existing known-failure preservation cases).

Both browser matrices then failed on the first unchanged control: the original
geometry fixture encoded DefineFunction ActionLength incorrectly, so no geometry
case completed. This is not a passing renderer result. The corrected assembler
and stronger boundary checks are now supplied. The separate manual geometry
workflow reuses that exact checksum-locked compiled artifact rather than rebuilding
identical source. Its full matrices and native iOS validation remain pending;
see `geometry-reuse/README.md` for the exact inherited evidence and limitations.

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

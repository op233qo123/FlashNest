# Eight neutral JPEG3/static-shape definitions — local-only mechanism control

The 6,809-byte FWS defines eight independent 16×16 JPEG3 bitmaps (IDs1–8,
opaque zlib alpha) and eight DefineShape3 bitmap-filled rectangles (IDs101–108).
Frame1 has no PlaceObject tag; the root draws only a small solid-color vector
and stops. One Space (keyCode32) moves to stopped frame2, which places only
Shape101 at (32,32). Seven images remain unshown. Repeated input is ignored.

This is NOT a pressure test or a private-game reproduction. No private asset,
name, font, save, or log is embedded. It distinguishes initial registration from
first-use behavior only. Backend counters must report actual bitmap decode/
register requests and pixel hashes rather than presuming 8→0→1. Null rendering
alone does not exercise bitmap-source requests or prove actual GPU uploads.

`neutral-forward-reference.swf` is a separate 1,947-byte compatibility negative
control: Shape101 is defined before its referenced JPEG3 bitmap1. It retains the
same compiled root, so the root's human-readable eight/seven trace numbers are
NOT its count oracle; the binary has exactly one shape/bitmap. Observe rather
than assume baseline/candidate behavior for this ordering.

`generate.py` reconstructs both movies from pinned tiny JPEG byte files and ABC.
The JPEG files were generated from eight simple public solid RGB colors; Pillow
version/options and ASC/import/source/ABC hashes are in provenance.json. Frozen
JPEG inputs avoid depending on cross-version JPEG encoder byte stability.

Six Python controls verify exact tag sequence, character IDs, forward-reference
order, real JPEG decoding, dimensions, nontransparent alpha, corruption rejection
and deterministic regeneration. `core-smoke.log` records actual prior null-core
ready and one input marker; it intentionally fails an empty Flash golden. This
is semantic smoke evidence only, not a Flash-reference or WebKit/render pass.
No engine source, external repository, CI or IPA is changed by this fixture.

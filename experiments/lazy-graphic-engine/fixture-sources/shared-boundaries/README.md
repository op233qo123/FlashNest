# Shared static Graphic boundary fixture — local-only preparation

A separate 2,745-byte public synthetic SWF; original eight-image fixture unchanged.
One 16×16 JPEG3 (opaque alpha), one static DefineShape3 referring to it, and two
placements of the SAME shape ID101. No new pressure axis or private inputs.

320×240 white stage, NO_SCALE/TOP_LEFT. Trusted S shows placements at32,32 and80,32;
R hides both and waits two ENTER_FRAME callbacks before showing both again;
M applies a pure-vector8×16 mask to the left placement; H calls shapeFlag=true
hitTestPoint on the right placement at84,36 (true),100,36 (false). Keys are ordered
and bounded. Named timeline-child properties are explicitly declared to avoid
AS3 ReferenceError. Local first invalid unbound-property log is not accepted.

Finite traces: NEUTRAL_SHARED ready / shown / redrawn / masked /
hit inside=true outside=false. Native/browser verifier must observe these, not
infer results from intended input. R's two callbacks permit a hidden render frame;
actual renderer activity still requires browser evidence.

Suggested interior pixel points:36,36;44,36;84,36. Ready allwhite; shown/redrawn
allimage; masked image/white/image. Frozen JPEG's Pillow center RGBA20,200,49,255;
actual WASM decoding may require small explicit tolerance. Compare baseline and
candidate pixels independently; don't treat Pillow as actual renderer evidence.

Five local Python controls passed. Existing pinned null-core produced all five
trace markers without runtime errors, but intentionally empty Flash golden still
fails; not a native, GPU, pixel, or Flash-reference pass. Browser run awaits actual
candidate engine and separate authorization. No external actions or IPA here.

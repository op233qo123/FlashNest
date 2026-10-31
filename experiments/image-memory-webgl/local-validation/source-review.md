# Independent reconstructed-candidate source review

Reviewed the current `candidate/render/src/utils.rs` against untouched `baseline/render/src/utils.rs` on 2026-10-31. This is reconstructed source, not a claim that the prior lost patch was recovered byte-for-byte.

Finding fixed during review: plain `Vec::resize(4N)` can amortize RGB capacity from 3N to 6N, defeating the intended moving-realloc peak. Candidate now calls `reserve_exact(rgba_len.saturating_sub(rgb.len()))` before resize. Actual allocator results still require measurement; reserve_exact cannot promise physical in-place growth.

No remaining source correctness blocker identified:
- Reverse expansion snapshots each RGB triplet before overlapping writes. Larger indices have already been read. Trailing non-triplet bytes are ignored, matching original chunks-of-three behavior.
- The first alpha pass reaches decoder EOF/error before RGB mutation. Interrupted reads retry. Count mismatch preserves the RGB buffer and original fallback format.
- Both paths use the same flate2 bufread ZlibDecoder. Replay uses the same immutable compressed slice. Original JPEG normalization, grayscale/CMYK conversion, size validation, and Bitmap::new stay unchanged.
- Alpha validation decoder is dropped before RGB allocation growth. Replay decoder is dropped before shrink and Bitmap construction.
- Small images retain the original branch. 512² is an experimental pixel-count threshold, not a universally optimized cutoff.

Required evidence before adoption: actual decoder pixels/errors across valid alpha, short/long alpha, late checksum corruption, accepted truncation, trailing/concatenated streams, JPEG errors, threshold formats and sparse capacity/tails; host and real WASM allocator/page measurements. Shrinking spare capacity may itself move and overlap buffers. No iOS RSS, latency, WebGL, or release claim is established by source review alone.

## Final harness and evidence review (02:26 UTC)

Reviewed `harness/src/lib.rs`, `generate.py`, `host_test.py`, `run.mjs` and actual output files. Harness defects addressed before final measurements: allocation counter underflow is now detected explicitly; repeated decode calls compare full bytes, status and dimensions/format against the cold oracle; timing calls assert successful decode and zero tracked live/underflow after drop.

Independently checked:
- All 91 standalone lock packages retain original baseline versions/source/checksums (excluding the new local harness package).
- `baseline_utils.rs` is byte-identical to original baseline utils, and unit-test candidate utils matches measured candidate utils.
- Actual WASM SHA256 is `ebe798e13b22ac0f748525b31b418a60a17a96f4393085b1c45fa2b89d634c14`, matching results; no imports.
- 37 cold baseline/candidate full-output or exact-error pairs match. All 130 allocation records have tracked live zero after output drop and zero counter underflows. Repeated measurements retain variant-specific instances rather than polluting candidate pages with baseline decoding first.
- Host comparisons pass, with one recorded 48-byte retention on baseline first 511² case. Initialization is a hypothesis, not proven allocation attribution.
- 54 render unit tests pass, including the new tail/capacity and malformed-alpha tests.

Input buffers are allocated before tracking and kept constant. WASM pages include those inputs; allocator metrics do not. Output copying for equality happens into Node-owned buffers, outside WASM and outside the timed decode. This is not zero-copy application performance or process RSS. `OVERLAP` is a moved-reallocation requested-size estimate, not allocator-internal physical allocation measurement. Timing includes the diagnostic allocator; final timing samples also include output drop.

1024² cold linear memory is 33 pages lower for both random and opaque alpha; 512² is 9 pages lower and 511² unchanged. Absolute cold pages vary with compressed input size. Fresh median timing deltas are approximately +6.16% for 1024² random alpha, +19.66% for opaque alpha, +0.15% for 512², and -6.09% for unchanged 511² control. Ranges are noisy and overlap. Do not reuse historical 10–15% figures as the result of this reconstruction, or claim a universal speed outcome.

Recommendation: eligible for the next bounded actual-engine WebGL comparison, not production adoption or iPhone/whole-process memory claims.

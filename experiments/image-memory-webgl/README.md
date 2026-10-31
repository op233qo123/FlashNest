# Image decode memory: isolated WebGL experiment

This branch is an experiment, not an app release or an IPA. It does not modify main or v1.5.6. All fixtures are synthetic.

The baseline reconstructs the exact lazy-Graphic source used for FlashNest 1.5.6 build 22 from upstream `89a7049965f3090e706265670df309a5128233ac` and the six locked patches under `experiments/lazy-graphic-engine`.

The candidate changes only `render/src/utils.rs`: for the experimental >=512×512 pixel-count threshold, validate compressed alpha with bounded scratch space, expand the owned RGB buffer backwards, then replay alpha into RGBA. Smaller images retain the original branch. This trades an extra alpha inflate for avoiding a full alpha plane during RGB buffer growth. This threshold is experimental, not a universally optimal choice; no app setting is implemented here.

The earlier local candidate was not persisted when its execution workspace was reset. This is a newly reconstructed candidate with new source hashes and fresh validation. Historical numerical results are not evidence for these bytes.

## Gates

1. Exact public source/fixture/workflow manifest and source lock, no private game material.
2. Existing official Chrome with its sandbox enabled and no unsafe SwiftShader opt-in. If normal WebGL is unavailable, stop before toolchain installation or expensive builds. Do not silently weaken sandbox/security settings.
3. Build baseline and candidate from the same checkout, toolchain, locks, JPEG-XR feature and dual extensions/MVP recipe. Source manifests must differ only at `render/src/utils.rs`; runtime hashes and actual compiled loader flavor mapping are recorded.
4. Run neutral SWFs with small, threshold-boundary and large JPEG3 images. Compare complete uploaded RGBA bytes as well as rendered canvas pixels, first draw, repeated visibility, mask/hit controls, selected WASM and WebGL renderer.
5. Observe controlled context loss/recovery separately. Parity with an existing failure is not proof that recovery works. Explicit cacheAsBitmap rebuild is not covered unless separately recorded.

WASM exported-memory capacity is not peak allocator usage, JS heap, GPU memory, iOS RSS or WebKit memory. Instrumented key-to-settled timings include browser scheduling and diagnostic work; they are descriptive, not a mobile benchmark. A focused WebGL pass is not native acceptance and does not authorize release.

Generated engine and browser evidence is retained as a bounded CI artifact, including failures when available. No IPA is built.

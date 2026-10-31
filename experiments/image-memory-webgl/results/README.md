# Source-bound focused results

- Original build/browser run: https://github.com/op233qo123/FlashNest/actions/runs/41160325754
- Browser-only corrected-capture run: https://github.com/op233qo123/FlashNest/actions/runs/41162734046

The original run failed its browser gate. Both engines had successfully built, with exact source and runtime receipts. The retry reused those exact bytes, not newly built engines. Its 10 pages × 5 states (ready, shown, redrawn, masked, hit) passed complete canvas RGBA and full uploaded-image RGBA comparisons. Both source-resolution texture bytes and nonblank rendered patterns were checked. The preserved 64,197-byte browser archive is the original downloaded CI artifact, SHA256 `9afe62c282e623f633eb4e1a07f71fb7ae97d5f440a0eb3c758505606cb4ca1a`.

## Memory result and limits

In this complete WebGL engine, 512² shown capacity fell from 299 to 282 WASM pages (1.0625 MiB less). The 64² and 511² controls were unchanged. Both 1024² samples remained 420 pages in both arms: the isolated-decoder memory reduction did not translate into a lower complete-engine high-water capacity here. Stage snapshots measure exported linear-memory capacity, not live allocation peak, RSS, GPU usage, or iPhone behavior. The code does not use a fixed 420-page heap: smaller cases demonstrate lower capacities and growth; what dominates the larger case remains unproven.

Single instrumented key-to-settled timings include scheduling/readiness and diagnostic overhead. They are not a benchmark and do not establish speed improvement. Fresh isolated decoder timing showed mixed costs, documented separately.

## Explicit unpassed / untested gates

Controlled WebGL context restoration did not succeed in either arm. Both supported the loss extension and emitted a lost event, but neither emitted a restored event within the bounded observation, and both remained white. This is recorded as `contextRecoveryLimitation`, not restoration success. The unchanged web handler only reloads a canvas renderer when at least eight instances exist; the single-instance fixture does not exercise that fallback. This is not a test of WebContent process termination, nor proof of a real-device crash cause.

Hide/show covered cache reuse. Explicit cacheAsBitmap rebuilding was not run. Native WebKit, physical-device RSS/latency and IPA acceptance were not tested.

Recommendation: retain the experiment, do not default-enable or ship it on these results. Investigate complete loading/texture-staging occupancy before adopting an optional memory-priority path. No main, release tag or IPA was changed.

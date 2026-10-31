# JPEG decoder lifetime: verified WebGL results

[Run41168894684](https://github.com/op233qo123/FlashNest/actions/runs/41168894684) completed successfully for commit `b9bfe3e79e76a6d8fe23987066c07fb158d58c5e`. The exact conclusion is **pixel and loading parity, with a separate context-recovery limitation**. It is not overall stability or device acceptance.

The product change is only `drop(decoder)` after successful JPEG decode, against the released lazy-Graphic baseline. It does not include the earlier two-pass alpha experiment. Both full engines built with the same pinned dual-WASM/JPEGXR recipe and passed63 existing core JavaScript tests each. Source inventories differ only at `render/src/utils.rs`; selected runtime identities are recorded in the browser contract.

## Actual browser observations

Chrome156.0.8078.47, sandbox enabled, actual WebGL2, no unsafe software-rendering override. Nine neutral synthetic assets,18 separate pages and90 preload/show/redraw/mask/hit states. Full original-resolution RGBA uploads and rendered screenshot pixels match between baseline and candidate.

| JPEG3 synthetic fixture | Baseline pages after first draw | Candidate pages | Difference |
|---|---:|---:|---:|
| Sequential64² |254|254|0|
| Sequential511² |297|297|0|
| Sequential512² |299|299|0|
| Sequential1024² pattern/opaque |420|420|0|
| Progressive RGB1024²,subsampling0 |519|454|65pages /4.0625MiB|
| Progressive RGB1024²,subsampling2 |474|441|33pages /2.0625MiB|
| Progressive gray1024² |482|451|31pages /1.9375MiB|
| Progressive RGB512²,subsampling2 |311|302|9pages /0.5625MiB|

These are exported WASM linear-memory capacities at observed states. They are not requested live allocation, allocator peak, GPU memory, process RSS, or iPhone memory. Repeated show/mask/hit states preserved these capacities; this short per-page sequence is **not a long-duration or many-scene soak test**. Single instrumented page timings do not establish a speedup or slowdown.

## Remaining limits

- Controlled context loss was supported in four1024² pattern cases. Both arms in all cases failed to receive restore within the observation window and remained unrecovered. This pre-existing baseline behavior is explicitly unpassed; no claim that this decoder change fixes context loss.
- Explicit cacheAsBitmap rebuild, long-session resource accumulation/reclamation, WebKit, and physical iPhone behavior were not tested.
- Progressive-specific benefits do not establish universal savings for ordinary JPEGs or actual content. No production cache eviction was implemented.
- Main, release1.5.6, and IPA assets were not changed. No new IPA was built.

## Durable evidence

`browser-41168894684.zip` preserves all synthetic browser screenshots, raw scalar observations, source/runtime contract and sandbox preflight. `summary.json` provides counts/page values and all controlled-recovery outcomes. Baseline/candidate provenance and runtime inventories identify both engines. Full build artifact13031330054 SHA256 is `e29bb886db50dda890ecb10e5de4c444af2dce937b3b40acc0e413c6f50b701d` (24,568,795B).

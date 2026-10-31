# JPEG decoder lifetime experiment — not IPA

This independently tests one change against the released lazy-Graphic engine source: drop the owned JPEG decoder immediately after it successfully returns decoded pixels. It does not include the earlier two-pass alpha experiment, a size threshold, or a new app setting.

The decoder owns progressive coefficient planes and metadata after returning the RGB buffer. Their earlier release can reduce overlap with RGB conversion and alpha composition. Metadata and returned pixels are independently owned; all pixel and error behavior is intended to remain identical.

Source binding fixes upstream commit, released overlay identity, and exact baseline/candidate file hashes. The product patch changes only render/src/utils.rs by one line. Both full engines use the same pinned dual-WASM, JPEGXR-enabled recipe and version metadata. Engine build receipts verify source inventory and existing core JS tests. Browser uses installed Chrome with its sandbox enabled, no unsafe software-rendering override, and verifies actual WebGL plus selected extensions WASM identity.

Local decode evidence under local-proof is from the actual decoder in a miniature Node/WASM module, not the complete renderer:45 full output/error case pairs, repeated progressive cases, and52 original render unit tests passed. Progressive samples reduced capacity; ordinary1024² control capacity did not. Timing is instrumented and mixed. Host contains one48B retained initialization observation; all measured WASM records released tracked allocations. This does not establish iOS/RSS/GPU savings.

CI uses neutral generated synthetic assets only. Five existing sequential JPEG controls are unchanged; four progressive JPEG cases cover RGB subsampling0/2, gray, and512². Each separate page measures preload/firstshow/repeatedhide-show/mask/hit states with full original-resolution upload SHA and screenshot RGBA parity. Cold/retained linear-memory capacity is not logical live allocation or peak RSS. Timings are descriptive, not a speed benchmark. Controlled context loss/restoration remains a separate observed limitation, never silently counted as passed; explicit cacheAsBitmap reconstruction and WebKit/iPhone remain untested.

No release/tag/main change or IPA is requested by this workflow. Results must distinguish picture/load parity from recovery observations and untested native gates.

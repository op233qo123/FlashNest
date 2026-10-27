# Native EventHandler normalization — observer-only correction

Historical [run 40540513351](https://github.com/op233qo123/FlashNest/actions/runs/40540513351) built the experimental audio candidate and passed eleven baseline cases. Candidate-normal0 failed the observer's `Native onended identity changed` assertion. Its captured page had no runtime errors, 351 created/started sources, all function-attach identity checks true and all 349 detach equality checks false. It had only the first Resume action: no Pause, Remove or close entry had occurred. This is not a measured candidate teardown result or a successful 22-case gate.

The old observer compared every native getter result with the original setter argument using strict equality. This is appropriate for a function attachment, but not for a nullable Web IDL event-handler removal:

- [Web Audio AudioScheduledSourceNode](https://webaudio.github.io/web-audio-api/#AudioScheduledSourceNode) declares onended as EventHandler.
- [HTML's EventHandler type](https://html.spec.whatwg.org/multipage/webappapis.html#eventhandler) is a nullable callback with LegacyTreatNonObjectAsNull.
- [Web IDL nullable conversion](https://webidl.spec.whatwg.org/#es-nullable-type) converts a null/undefined assignment to IDL null; the getter representation of that IDL value is JavaScript null.

The source/ABI chain supports undefined as the expected Rust-None setter input:

1. Pinned wasm-bindgen0.2.127 [web-sys declaration](https://github.com/wasm-bindgen/wasm-bindgen/blob/0.2.127/crates/web-sys/src/features/gen_AudioScheduledSourceNode.rs#L44) takes `Option<&js_sys::Function>`.
2. Its [imported-type Option ABI generation](https://github.com/wasm-bindgen/wasm-bindgen/blob/0.2.127/crates/macro-support/src/codegen.rs#L1289-L1293) maps None to ABI zero.
3. Actual candidate extended glue initializes externref slot zero to undefined and directly assigns `e.onended = _`. MVP glue initializes heap slot zero to undefined and assigns the looked-up value. These exact candidate JS hashes were inspected:
   - extended core.ruffle.4bf43128d442d808d913.js: `63177252735b59a2ad6ac645cde4e91c1afc47eeb80dc9e1adf26ad1aef7a1c5`
   - MVP core.ruffle.8ee07edaf47829ab3e6f.js: `4cec3ffb0f5aa994e4bede3f182ba606edbc40611a3e1e563a1536a495cf5f61`

The historical observer did not capture input/getter categories, so undefined→null in that particular run is supported by standards/source/compiled ABI, not directly measured by its old event rows. The corrected rerun must capture those categories; the old failure is not retroactively declared a pass.

## Strict corrected contract

Record setterCategory and native getterCategory without retaining either value. Function attachments require getter identity to match the exact original function. Removal accepts only null or undefined input, and only a native getter exactly equal to null counts as detached. Any unsupported input, changed function, undefined getter or other non-null getter fails. Only actual exact-null state clears the attachment ledger; no callback is wrapped, rewritten or directly invoked.

Before installing hooks, an unstarted OfflineAudioContext-created AudioBufferSourceNode checks the same native descriptor with function, null, function, undefined, then exact-null cleanup. This preflight does not instantiate a live AudioContext, start a source, start offline rendering or retain context/node/function references in evidence. All cases and descriptor identity are required; mocks alone cannot establish the real browser's conversion.

The old waitUntil also retried thrown assertions until its timeout, explaining prolonged audio refill after a fatal observation. The corrected helper latches the first sync/async thrown value using a separate flag (including falsy throws), terminates polling and rethrows it. False readiness still polls with identical timeout/interval limits; trusted input is never retried. This is harness failure containment, not a runtime scheduler change.

The existing 22-case matrix, runtime inventories, renderer/feature-path checks, fresh Promise/refill/heartbeat checks, close settlement, expected baseline defect, candidate detachment and separately labeled synthetic-event gates remain intact. Existing candidate artifact12752805773 must be reused unchanged; no Rust source, SWF, engine binary or production runtime change is part of this observer repair. A complete actual rerun remains required before native comparison or any stability claim.

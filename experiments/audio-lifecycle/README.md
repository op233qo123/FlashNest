# Experimental WebAudio ownership repair (not promoted)

This experiment retains the exact existing queued-goto guard and changes only
`web/src/audio.rs` at Ruffle commit
`89a7049965f3090e706265670df309a5128233ac`. No render-density patch, game asset,
save data, production runtime pin or app version is changed.

## Proven source defect; limited causal scope

The pinned Buffer owns its onended Closure, while that Closure captures a strong
Rc back to the same Buffer. Dropping the backend's Vec cannot by itself release
that ownership cycle. The proposed repair captures Weak, temporarily upgrades for
a callback, detaches retired/current/failed-start node handlers, and releases the
buffers before requesting asynchronous AudioContext.close. Mixer/decoder logic,
adaptive buffer sizing, pause/resume, RAF and close Promise scheduling are unchanged.

This is a teardown/constructor-failure retention defect. It is **not an established
cause of WebKit SIGBUS**, a proof of physical-memory savings, or a fix for every
AVM2/media failure. Child Loader unload, orientation and background/resume within
the same surviving player do not drop this backend. Fresh-player failures cannot
be explained by accumulated teardown retention alone. The native unchanged-player
transition comparison remains a separate required symptom gate.

## Required gates

The manual-only standard Ubuntu workflow validates the exact upstream source,
existing guard and additive audio patch. It retains all source/test failure evidence.

1. Compile two standalone Rc ownership-pattern tests. These are a useful source
   model, explicitly **not enough** to establish WebAudio behavior.
2. Preserve the two original nested/control frame-order outputs and 31 adjacent
   upstream gates (29 strict reference outputs plus two known-failure preservation
   tests). No reference output is rewritten.
3. Build both WASM variants from the pinned dependency locks and compatible pinned
   tools; require all 59 unchanged core JS tests, none skipped.
4. Compare the exact existing guard-only runtime against the isolated candidate in
   real WebAudio: natural onended refills, pause/resume, eight same-page create/
   destroy cycles, injected first/second start failures, and a separately labeled
   retained-node synthetic ended event after removal. Do not directly invoke a
   dropped Rust closure or require nondeterministic JavaScript GC.
5. Missing actual close entry/refill/trace/readiness is a separate lifecycle failure,
   not the expected baseline ownership defect. Observe explicit handler detachment
   and bounded close settlement, without claiming all undetached JS nodes stayed
   alive. No forced GC or automatic retry/reopen can turn a failed case into a pass.

Real browser observations, native WKWebView comparison and user-relevant transition
coverage are still pending. Passing a Linux software-rendered test is not iOS or
Adobe equivalence. No production promotion is performed by this workflow.

## Build identity and source/license correspondence

Rust 1.99.1, Node 24.22.1, wasm-bindgen 0.2.127, Binaryen 129, pinned Temurin
21.0.13+9 and exact Cargo/npm lockfiles follow the already-validated build recipe.
Downloaded Java/Binaryen archives and both source patches have fixed SHA256 gates.
The baseline is the immutable checked-in queued-goto candidate ZIP, not an unmodified
official release. Its bytes, provenance and complete runtime inventory are verified.
Candidate provenance lists every modified source and packaged file hash, upstream
commit, build/run identity, dependency locks, tool versions and explicit experimental
version label. Independent clean-build byte identity is not claimed.

Artifacts retain modified source, patches, original fixture sources, MPL 2.0 and
MIT/Apache license texts, existing third-party notices and a modification notice.
No package is labeled official stable. This is source correspondence, not a legal
compliance certification. Publication or shipment requires separate review.

## First build result and narrow compiler correction

Run [40536964358](https://github.com/op233qo123/FlashNest/actions/runs/40536964358),
source `07365dba3a9d67427ed55ca79b4f406edd003f86`, passed the two ownership-model
tests, two original frame-order tests and all 31 adjacent gates. WASM compilation
then failed with E0308: the explicit failed-start cleanup branch returned
`ruffle_web_common::JsError`, while the function returns `wasm_bindgen::JsError`.
The original question-mark operator supplied this conversion implicitly. The
reviewed correction is exactly `return Err(error.into())`, preserving detachment
and the original conversion. No decoder, callback ordering or test predicate is
changed. No candidate web build, core-JS gate or real WebAudio observation
completed in that failed run. Its retained artifact `12749088918` has SHA256
`0d11560bf16fe0574b3c1efd947f43f9b7544f97c25a9cbefdcca41e2f4b2605`.
A full corrected build and actual browser gate remain required.

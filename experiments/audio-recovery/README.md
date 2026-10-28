# Experimental source-bound audio-device recovery

**Experimental and unpromoted.** This isolated experiment does not replace the shipped
runtime or alter the application, games, saves, renderer selection or media policy.
It contains original diagnostics only. A successful build is not proof that a
particular phone's audio hardware interruption or other crashes are repaired.

## Source finding

Pinned Ruffle `89a7049965f3090e706265670df309a5128233ac` discards the Promise from
[`AudioContext.resume()` in backend play](https://github.com/ruffle-rs/ruffle/blob/89a7049965f3090e706265670df309a5128233ac/web/src/audio.rs#L91-L100).
The frontend also resumes on
[visibility return](https://github.com/ruffle-rs/ruffle/blob/89a7049965f3090e706265670df309a5128233ac/web/packages/core/src/internal/player/inner.tsx#L470-L496)
and [unmute](https://github.com/ruffle-rs/ruffle/blob/89a7049965f3090e706265670df309a5128233ac/web/packages/core/src/internal/player/inner.tsx#L1863-L1872)
without rejection handling. Constructor failure is different:
[the builder falls back to NullAudioBackend](https://github.com/ruffle-rs/ruffle/blob/89a7049965f3090e706265670df309a5128233ac/web/src/builder.rs#L629-L638).

Historical WebKit revision `b498597741af207e69fc5510de87ab12193f7edc`
(2024-08-14) creates the exact InvalidStateError message
`Failed to start the audio device` when its destination start callback reports
false, in [initial start or resume](https://github.com/WebKit/WebKit/blob/b498597741af207e69fc5510de87ab12193f7edc/Source/WebCore/Modules/webaudio/DefaultAudioDestinationNode.cpp#L158-L184).
[AudioContext resume rejects its Promise with that exception](https://github.com/WebKit/WebKit/blob/b498597741af207e69fc5510de87ab12193f7edc/Source/WebCore/Modules/webaudio/AudioContext.cpp#L254-L273).
This identifies a source route, not the exact WebKit version or hardware cause
of any specific incident. InvalidStateError also covers an uninitialized
destination or a closed context; name-only recovery would be too broad.

## Narrow patch and event contract

Four paths change: one new internal audio-operation helper, its JS/WASM import,
backend play/pause delegation, and frontend binding/visibility/unmute/release.
The constructor, mixer, decoding, buffer sizing, scheduling, renderer and core
timeline are untouched. No global prototype hook or global string filter is used.

The actual context is bound immediately after instance creation, before autoplay.
The outer player element emits `ruffle-audio-status` with immutable primitive data:

```
schema: 1
contextId: positive safe integer
operationId, intentId: nonnegative safe integer
phase: bind | release | core-play | core-pause | visibility | unmute
operation: none | resume | suspend
status: bound | released | pending | fulfilled | rejected
state: actual bounded AudioContext state string
current, retryEligible: boolean
errorName?, errorMessage?: at most 128 / 512 characters
```

Every resume/suspend advances operation and intent. Release advances intent and
detaches the subscriber. Bound/released events have operation `none`; bound may
have zero operation/intent. Unknown state strings cannot establish recovery.

Retry eligibility requires **all** of: a rejection from the owned context's
resume Promise; current context/intent; context not closed; actual DOMException;
exact InvalidStateError name and exact known device-start message. The message
is only a supplemental whitelist, never a sufficient classification.

Unknown errors remain fatal with their original exception object through one
intentionally unhandled child Promise. This preserves the host's existing
`unhandledrejection` route; throwing via `window.error` is not substituted.
Synchronous native throws are not retry eligible. Known stale owned device-start
rejections are bounded diagnostics, not a new warning for a successor context.
Unknown stale failures and closed-context failures are not silently suppressed.

An application may offer one explicit trusted in-page retry without restarting
the game. Existing public `ruffle().resume()` invokes backend play even if already
playing. The UI must capture its new synchronous pending core-play operation,
then clear its warning only after that same context/operation/intent fulfills
with actual state `running`, while the application still intends active playback.
Pending, statechange, stale fulfillment and synchronous method return are not
success. This helper performs no retry, reload or settlement-triggered playback.

## Independent layers and reproducible gate

The manual workflow is `.github/workflows/experiment-audio-recovery.yml`.
`workflow-draft.yml` must be byte-identical to it. It uses a standard Ubuntu24.04
runner, contents-read permission and no production promotion step.

Ordered layers remain separately hashed:

1. Pinned official source `89a7049965f3090e706265670df309a5128233ac`.
2. Existing queued-goto patch `de0acabdf957fccbc11966b67defd0a7f577cdc5a147db949e0a4f0e56c6331f`.
3. Existing Weak/detachment ownership patch `89dfadc1b9d113adb01f08582237559c71a5c0e04fe712cb0e31d80f077b07b9`.
4. This additive recovery patch, exact SHA and per-source hashes in
   `patch-manifest.json` / `engine-build/build-inputs.json`.

`check_patch.py` reconstructs and reverses the Weak and recovery layers against
exact upstream file hashes. Build provenance independently reconstructs all
three patches, permits overlap only in `web/src/audio.rs`, rejects foreign source
changes and verifies complete resulting bytes before and after building.

The verified previous build recipe is reused: Rust1.99.1, Node24.22.1,
wasm-bindgen0.2.127, checksum-pinned Binaryen129 and Temurin21.0.13+9,
upstream Cargo.lock/package-lock.json, dual WASM and original59 core JS tests.
Early standalone TypeScript compilation and23 source-helper groups run before
expensive WASM compilation. Full core TypeScript needs generated declarations: the
build first generates genuine extensions bindings and typechecks all core sources
before the MVP compile, then retains the complete ordinary dual-WASM build, its
fresh-declaration typecheck and unchanged59 JS gate. No fabricated or borrowed ABI
declarations are used. Gates also retain ownership-model2, original
frame-order2, adjacent31 (including their two preexisting known-failure goldens),
and the real Chrome22 ownership cases on baseline versus candidate. Original
browser observers and golden expectations are not modified.

The helper23 are Node source-unit tests, not native execution. Full source
compilation, Chrome ownership22, actual WK trusted retry/fatal-routing tests and
independent native lifecycle acceptance remain required. The previous native
ownership experiment failed on diagnostic event-cap overflow before reaching its
candidate; this lane does not relabel that failure or claim it passed.

## Evidence, licensing and limits

Artifacts use the explicit `flashnest-audio-recovery-experimental` channel and
retain exact upstream commit, ordered patches, modified source, dependency locks,
build inputs, original fixtures/tests, runtime hashes, tool versions and existing
MIT/Apache and third-party notices. No official stable-release identity is claimed.
An independent clean-build byte-for-byte reproducibility result is not claimed.
Partial failure artifacts are retained and cannot be promoted by this workflow.

This change does not fix WebContent process termination, JSC/WASM faults, GPU
context loss, missing rendering features, input problems or memory pressure by
assertion. Those failure tracks require separate evidence and tests.

## Initial build evidence and nullable lookup repair

Run [40611265560](https://github.com/op233qo123/FlashNest/actions/runs/40611265560)
at experiment commit `8bcb79f65f165c23b57bb324008ec76431744781` passed the23
source-helper groups, ownership-model2 and original2/adjacent31 core gates. Both
WASM flavors compiled, but full core TypeScript then rejected the newly added
nullable instance lookup (TS2531). CoreJS59 and Chrome22 were not accepted;
artifact12783219780 is failure evidence, not a validated candidate.

The repair uses optional context lookup after the builder returns. A null
instance or absent audio context cannot be bound; the existing downstream
instance/error handling is unchanged. No non-null assertion, fake context,
recovery classification or retry predicate is added. The binding remains before
autoplay. The separately tested source helper and Weak ownership layer are
byte-identical. The full-core gate above now catches integration errors after
genuine extensions declarations exist and before the second expensive flavor.

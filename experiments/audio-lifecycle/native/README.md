# Isolated native Canvas / WebAudio lifecycle gate — preparation

**No native build or execution has been performed for this harness.** The workflow
is a draft in this directory only; publication and dispatch require separate
review/authorization. Do not run it concurrently with the existing Loader18.5
investigation. There are no App, default-test, production-runtime or release edits.

## What is pinned, and what already passed

- Immutable audio candidate: build `40540513351`, source
  `d3b402aec064f326a6b03c022253ccea559aa62f`, artifact `12752805773`.
- Candidate adds audio patch
  `89dfadc1b9d113adb01f08582237559c71a5c0e04fe712cb0e31d80f077b07b9`
  to the unchanged queued-goto guard. Baseline is the exact existing build17
  guard runtime, not an unmodified official Ruffle release.
- Original silent AVM2 fixture: **799 bytes**, SHA256
  `e25f5dba4162a25b9a07832be4e6f8f62242734f6f39e92983c53467a28e7fd2`.
  It has no sound tags, network loaders, SharedObjects or user-game content.
- Corrected **Chrome wgpu-webgl 22-case gate** passed in
  [run40548833402](https://github.com/op233qo123/FlashNest/actions/runs/40548833402),
  artifact `12753987072`. `browser-approval.json` pins its exact successful API
  identity, reviewed ZIP, results/provenance and immutable build/helper lock.
  The prior build's failed browser result is retained, not reclassified.

The current offline verifier has checked the accepted ZIP, all22 raw browser
attachments,95 candidate provenance-inventoried files and12 baseline runtime files.
Offline staging is not native execution. It also is not a signature or a second
independent engine rebuild.

## Deliberate renderer boundary

This native experiment requests **Canvas for both arms**. It requires the actual
runtime banner to identify `canvas`, a non-null native `getContext('2d')`, positive
actual backing dimensions, and actual WK DPR matching `UIScreen.main.scale`.
A WebGL/Metal fallback is a failure, not a substitute. The pinned builder supports
[`canvas` as a preferred backend](https://github.com/ruffle-rs/ruffle/blob/89a7049965f3090e706265670df309a5128233ac/web/src/builder.rs#L516-L529)
and [constructs a Canvas renderer](https://github.com/ruffle-rs/ruffle/blob/89a7049965f3090e706265670df309a5128233ac/web/src/builder.rs#L607-L623).

This isolates the silent audio-ownership question from separately observed
simulator `SimMetalHost` / `WebKit.GPU` crashes. It does **not** establish that
Canvas avoids every GPU interaction, repair those crashes, or establish normal
FlashNest/default-renderer lifecycle stability. The production/default-backend
lifecycle gate remains separately required before shipping.

Original Chrome helpers remain byte-unchanged. Staging generates auditable native
copies with exactly four page transformations (two capability-relative paths,
Canvas preference, real2D proof) and five contract transformations (two import
adapters, truthful expected-DPR parameter, Canvas banner, real2D backing proof).
The original/derived hashes and each exact single-occurrence replacement are
recorded. No GL fields are fabricated or normalized in raw evidence.

## Meaningful native actions and unchanged audio policy

A separate UIKit host compiles only the unchanged production `LoopbackServer`
and `HTTPProtocol` as transport support. It serves verified bundled files over
capability-prefixed `127.0.0.1`, with existing CSP, MIME, streaming and bounded
server drainage. It does not launch the FlashNest app or modify its player.

The host keeps `allowsInlineMediaPlayback=true` and
`mediaTypesRequiringUserActionForPlayback=[.audio,.video]`. Apple documents the
[user-action media policy](https://developer.apple.com/documentation/webkit/wkwebviewconfiguration/mediatypesrequiringuseractionforplayback).
XCTest uses real [`XCUIElement.tap()`](https://developer.apple.com/documentation/xcuiautomation/xcuielement/tap())
on the page's Resume/Pause/Remove buttons. Every observed DOM event must have
`isTrusted=true`. No `evaluateJavaScript` click/resume, autoplay exemption, fake
AudioContext, muted output policy, or forced timeline state can pass this gate.

The exact corrected observer is reused. Its native offline EventHandler
preflight requires function identity and actual null/undefined-to-null behavior.
Normal hooks return original promises and never wrap/invoke `onended` callbacks
or retain source nodes. The explicitly labeled synthetic-ended arm alone retains
one source to dispatch its synthetic event; this is not natural callback evidence.

Each arm runs8 normal create/refill/pause/resume/remove cycles plus first-start,
second-start and synthetic-ended fault cases: **22 cases total**. Normal cases
require fresh action-specific fulfilled resume/suspend promises, natural source
refills after both resumes, fresh AVM2 heartbeats, one actual close entry and one
fulfilled original close promise. Baseline must expose its expected attached
handler control; candidate must have no tracked attached handler at close entry.
Baseline/candidate must select the same WASM feature path across all22 cases.

## Attestation and bounded evidence

1. `prepare_browser_archive.py` checks reviewed successful run/job/artifact API
   metadata and exact ZIP size/hash **before** bounded safe extraction.
2. `stage_native.py` repeats immutable source/runtime/helper verification and the
   complete successful corrected-browser22 prerequisite. Missing, skipped,
   foreign or partial evidence refuses staging. It never downloads or runs code.
3. A fresh Web directory contains both exact runtimes and only the original
   fixture plus reviewed helpers. Its complete33-file inventory is pinned in
   `native-manifest.json`; a generated compiled Swift SHA binds that manifest.
   Copy-time drift, extra files, missing files and symlinks fail closed.
4. The host hashes every bundled file before creating a WKWebView. Every mode's
   output retains that exact manifest/identity, raw case JSON, final snapshots,
   native OS/DPR, and teardown outcomes. It never overwrites a prior suite.
5. One UI test has a600-second matrix deadline, with660-second XCTest allowance.
   Readiness/action waits are bounded and fail immediately on assertions,
   including falsy thrown values. Native JS callback operations each have a
   three-second deadline and ignore late callbacks safely. Finalization allows
   at most two such calls plus the existing five-second server drain.
6. Failure invokes native Abort to attempt snapshot/disposal/drain before app
   termination. If the host does not confirm it within15 seconds, evidence marks
   forced termination; this is not clean close/drain proof. A host/AX hang may
   leave partial evidence, which cannot pass the final gate.
7. `verify_xctest.py` requires exactly the one selected test, no failures/skips,
   and raw iOS Simulator18.5 configuration. `check_native_evidence.mjs` separately
   replays every raw case with the staged exact contracts, requires all8 modes,
   all22 unique cases, attestation/DPR/feature agreement and successful drain.
   New test-window WebKit/GPU/SimMetalHost crash reports or truncated collection
   fail the draft gate. Empty reports are not a proof of long-term stability.

Close-promise settlement and explicit handler clearing are **not** observations
of garbage collection, physical RAM release, actual speaker output, phone crash
causality, arbitrary-game behavior or Adobe equivalence.

## Preparation checks

```sh
python3 -m unittest discover -s experiments/audio-lifecycle/native -p 'test_*.py'
node experiments/audio-lifecycle/native/test_raw_replay.mjs
for f in experiments/audio-lifecycle/native/Web/*.mjs; do node --check "$f"; done
```

These include synthetic metadata/hash/unsafe-path/partial-matrix negatives,
exact reversible adapter checks, all shared browser contract mock groups adapted
truthfully to Canvas/DPR3, fail-fast polling, trusted-action/source invariants,
exact XCTest selection/OS rejection and complete synthetic raw22 replay with
corrupt-evidence rejection. They are not native or browser execution results.

The draft uses standard `macos-15`, Xcode16.4 and exact iOS18.5, no paid lane or
fallback SDK. It builds only this diagnostic app/UI-test target, never an IPA.
Successful fixture-focused native evidence still does not authorize runtime
promotion or replace the separate normal-app lifecycle gate.

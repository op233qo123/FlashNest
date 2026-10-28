# Isolated native Canvas / WebAudio lifecycle gate — preparation

**No native execution has succeeded for this harness.** The first build attempt
failed before execution as detailed below. The isolated manual workflow and its
matching source copy in this directory require reviewed changes before retries.
There are no App, default-test, production-runtime or release edits.

### First build attempt and path-only correction

Run [40552081930](https://github.com/op233qo123/FlashNest/actions/runs/40552081930),
source `4d54135a5c6d1597bca1fd48c455d245dce6c42f`, passed prerequisite and exact
bundle staging but failed before native execution: relocating the generated
project made its relative Info.plist/Web paths resolve outside the checkout.
No runtime cases executed; the failure is not an audio/engine result.

Staging now generates a JSON-compatible XcodeGen spec **inside the staged project
directory**, using verified absolute paths for the four checkout Swift sources
and simple local paths for identity, Web resources and Info.plist. XcodeGen runs
from that same directory with no project relocation. Before compilation, actual
`-showBuildSettings -json` output must resolve PROJECT_DIR/SRCROOT and Info.plist
to the expected staged directory. Local tests reject the original escaping path,
wrong project root and missing resources. Generated project.pbxproj, resolved
spec, build settings and path-verification evidence are retained on failure.
Runtime bytes, Swift/audio behavior, trusted-action predicates and deadlines are
unchanged. Native compilation/execution remain unverified after this correction.

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

## Native partial failure and independent evidence retention

Corrected-project run [40557858860](https://github.com/op233qo123/FlashNest/actions/runs/40557858860),
source `147f02cee999337d2b860c934c8ffe4ee986105a`, compiled the host/UI targets
and ran the real test. It failed after the third baseline-normal Remove action,
before the next cycle's Resume, with a generic page-contract failure. The
candidate arm was never reached. The one XCTest failed after83.182 seconds;
this was **not** a workflow or matrix timeout. No test-window WebKit/GPU/Metal-host
crash report was collected. Artifact `12760335362`, 99,711,484 bytes, SHA-256
`7be1a7a75668b1b8c78ae447e87094f74703e05439c39c7344deea11b04de999`,
is retained as a failure, not a native audio pass.

That artifact lacked all raw Documents evidence. Its selected simulator UUID
and actual xcresult UUID agreed, so a cloned-device mismatch is not established.
The former collector discarded `simctl` stderr and accepted an absent directory;
the exact page assertion could not be recovered. Action progress alone cannot
establish how many full contracts passed.

The evidence-only repair preserves all runtime bytes,22-case expectations,
600-second matrix and660-second XCTest limits. It resolves the single actual
18.5 Simulator ID from xcresult, records lookup exit/stderr, validates and copies
only this diagnostic app's bounded JSON files, and fails if evidence is absent.
The host also exposes the terminal JSON (at most128KiB) as a diagnostic
accessibility value for an independent XCTest attachment before termination.
Only its exact ephemeral loopback-capability URL prefix is redacted; filenames,
assertion reason, values and stack locations remain. Oversized/unserializable
terminal bodies produce an explicit unavailable marker, never truncated JSON.
This attachment is diagnostic only and cannot substitute for the complete raw22
inventory/replay gate. The host's visible failure includes the bounded actual
page error instead of only a generic phrase.

Compilation now has a separate10-minute `build-for-testing` step; the existing
12-minute `test-without-building` step uses the same scheme, destination and
DerivedData. Job30-minute and native per-test deadlines are unchanged. This
separation does not reinterpret the historical assertion failure as a timeout.


## Native action scheduling and post-test extraction repair

Run [40563016412](https://github.com/op233qo123/FlashNest/actions/runs/40563016412),
source `44a5eaadd43c43d585c2b3aa5b10e8fa7f71f1d4`, built successfully but failed
at the first baseline-normal Remove lookup. No candidate case ran and no
WebKit/GPU/Metal-host crash was collected. Artifact `12760869377` is77,409,244
bytes, SHA-256 `53cf433b5aa2542991e848824f2b417ef7f01d8a995416dd8c921c8c62f1d5ec`.
It remains a failed run, not native audio validation.

The video shows the requested Remove button visibly on-screen while the native
status is `ACTION baseline/normal/0/4/remove`. XCTest's existence-to-hittability
lookups alone took over10 seconds; no Remove tap was recorded. The later AX
snapshot shows the page had already failed and its WK view had been removed.
The stack points at the page polling deadline, but WebKit's stack-only string
omitted the exact predicate message. This supports an action-scheduling race,
not an audio-engine failure or an off-screen button geometry diagnosis.

Only the wait for one **trusted UI action** is now90 seconds, matching the
existing native action/status allowance and capped by the unchanged global
600-second matrix deadline. Audio Promise, refill, heartbeat and close waits
remain20 seconds; load waits remain80 seconds. Every action still requires
exactly one fresh trusted event, without retries, forced coordinates, synthetic
clicks or media-policy changes. Duplicate, untrusted and stale actions fail.

Failures retain explicit error message plus stack, the pending action token,
request/deadline timestamps and the actual control rectangles before disposal.
The accessibility mirror now contains a bounded, explicitly diagnostic-only
summary with full terminal-body SHA-256/byte count, rather than dropping the
entire mirror when a full observer snapshot exceeds128KiB. Exact raw terminal
and per-case evidence remain in Documents and are still independently required
by the unchanged22-case replay gate. Teardown attempts this compact attachment
even when an XCTest AX exception bypasses a Swift guard; secondary collection
cannot replace the original failure. The overall660-second XCTest cap remains
necessary because synchronous AX calls cannot be individually cancelled.

The stricter collector established the exact post-test extraction problem:
selected and actual simulator UUIDs matched, but `simctl get_app_container`
returned149 with `Unable to lookup in current state: Shutdown`. Only after
preserving test-window crash reports, recovery may boot **that same available
Shutdown simulator** once, with30-second boot and90-second bootstatus limits,
then repeat the exact diagnostic bundle lookup. It never launches, reinstalls,
erases or resets any app, and never scans another device's containers. Receipt
records original error/state, crash-collection hash, timestamps and all recovery
exit/stderr/timeout results. Unknown/unavailable/non-Shutdown states fail closed.
Reports produced by evidence-only boot are not relabeled as test-window crashes.
These changes are diagnostic harness repairs only; runtime bytes and production
App behavior are unchanged. Actual repaired native execution remains pending.

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

## Historical Weak-only prerequisite (not the next selected candidate)

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

The historical offline verifier checked that accepted ZIP, all22 raw browser
attachments,95 candidate provenance-inventoried files and12 baseline runtime files.
Offline staging is not native execution. It also is not a signature or a second
independent engine rebuild.

## Explicit recovery-candidate reattestation for the next22-case run

The manual workflow now selects the **new structured-audio-recovery candidate**,
not the historical Weak-only candidate above. `recovery-approval.json` binds:

- Successful build and Chrome22 run
  [40614335019](https://github.com/op233qo123/FlashNest/actions/runs/40614335019),
  source `5d2cdcc6757d65194bd55c4a0395b76b0176d224`, job `122573186188`.
- Artifact `12783974867`,22,076,102 bytes, SHA-256
  `3befcb048669c074a017e2bfb6d3ccc283028ef90d7960695bbf0964a2634e9a`.
- Ordered queued-goto, Weak-ownership and structured-recovery patches; the last
  patch is `631027394ab35c7ff5b8bd1da1402a649c38e913dd2b788d1a9ef514fc6aee60`.
  The exact source-bound helper is
  `32986bab21da5cc3417ce2b67dfd6a3f829fa2b5c5910805e4a833fb1843a2cb`.

`recovery_prerequisite.py` validates successful API run/job/all-step identity,
ZIP size/hash before bounded extraction, all145 candidate correspondence files,
all12 files in each runtime, both actual JS/WASM manifests, the exact original
nine browser helpers and complete Chrome22 row attachments. `stage_recovery.py`
then repeats those checks and generates the34-file native Web bundle. The
baseline remains the same existing queued-goto build17 bytes. No engine is
rebuilt or production runtime replaced by this lane.

The old `browser-approval.json`, Weak-only validators and all failed native run
records remain unchanged as historical evidence; the active workflow explicitly
calls the new prerequisite/stager and records the new source/build identity.
Local exact-artifact preparation and staging succeeded. These are offline
checks, not native22 execution. The separate three-arm injected-recovery native
experiment does not replace this ownership matrix or prove real hardware repair.

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
copies with six page transformations (two capability-relative paths, Canvas
preference, real2D proof, window export and deferred observer restoration),
three observer transformations (native-only event window), and five contract transformations (two import
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
   fixture plus reviewed helpers. Its complete34-file inventory is pinned in
   `native-manifest.json`; a generated compiled Swift SHA binds that manifest.
   Copy-time drift, extra files, missing files and symlinks fail closed.
4. The host hashes every bundled file before creating a WKWebView. Every mode's
   output retains that exact manifest/identity, raw case JSON, final snapshots,
   native OS/DPR, and teardown outcomes. It never overwrites a prior suite.
5. One UI test has a600-second matrix deadline, with660-second XCTest allowance.
   Readiness/action waits are bounded and fail immediately on assertions,
   including falsy thrown values. Native JS callback operations each have a
   three-second deadline and ignore late callbacks safely. Finalization allows
   at most three such calls plus the existing five-second server drain, after
   awaiting already-started case-receipt operations (each independently bounded).
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
node experiments/audio-lifecycle/native/test_observer_window.mjs
node experiments/audio-lifecycle/native/test_window_replay.mjs
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


## Bounded native event windows — unexecuted diagnostic repair

Run [40606502048](https://github.com/op233qo123/FlashNest/actions/runs/40606502048)
retained two completed baseline-normal cases, then failed during cycle2 with
`events=4096`, `nodes=1019`, `contexts=3`: the original cumulative observer event
cap was reached while native accessibility actions were comparatively slow.
The candidate arm was not reached. This is an observer-cap failure, not evidence
that the audio patch passed or that the engine leaked1019 live nodes. The
artifact is `12781751317`,83,481,754 bytes, SHA-256
`1afb6288eb62ea16eedbdb062a6bbb1d903afd9bf4fa1ba70170767bed9248ad`.

The native adapter now uses a monotonically numbered **4096-event window**.
Each case serializes its exact original evidence and interval. Only after the
host atomically writes those exact bytes, reads back at most2MiB+1 and verifies
byte equality, does it return a receipt binding the case, unique token, interval,
byte count and SHA-256. The page validates every receipt field before removing
that prefix. Events arriving during serialization, write, readback or delivery
remain in the tail. A failed write/readback, missing/late/wrong/duplicate receipt,
gap, overflow or mismatched hash cannot authorize a drain. Each acknowledgment
uses the existing20-second functional bound and global600-second deadline;
native JavaScript callbacks keep their three-second bound.

Global node/context metadata, original close-entry snapshots and their counters
are **never reset**, and the original4096-node cap remains fatal. Completed cases
in the failed run used267 and208 new sources;8 times their mean is about1900,
but the incomplete third case used544. Thus variable accessibility delay may
still reach the node cap or unchanged global deadline. This repair does not
inflate either cap, speed up engine callbacks, reset the page per normal cycle,
or guarantee that all8 cycles fit the budget.

The writer remains active through player disposal and a host-requested final
snapshot. Observed resume/suspend/close promises must settle; that is not proof
that no future callback can ever occur. The host marks a finite final boundary,
persists the extended tail, then reads status and restores the observer hooks
synchronously. Any recorded activity between boundary and final status fails.
Offline replay requires every case exactly once, contiguous global sequences,
unchanged old metadata/close snapshots and an extending final tail. For the
candidate only, new source/start/handler-attachment activity after close entry
fails, including activity on old contexts in later windows or the final tail.
The baseline's retained-handler negative control remains separate and intact.
The claim ends at this explicit observation cutoff, not at an assumed GC event.

The original Chrome observer, contracts and goldens remain byte-unchanged;
only auditable native copies are adapted. Preparation checks exercise the actual
transformed observer with fake native objects, missing/mismatched receipts,
post-acknowledgment late events, retained global node overflow, candidate-only
post-close rejection and synthetic full22 replay. The Swift write/readback
failure test currently inspects throwing control flow; it does **not** execute
FileManager failure injection or establish native compilation. Native execution
of this window repair is still pending, and the separate focused recovery gate
must not be labeled a successful22-case ownership matrix.

## Mid-case durable prefixes (protocol2; native execution pending)

Run [40621531623](https://github.com/op233qo123/FlashNest/actions/runs/40621531623)
at `38e0cb305ff736b676111e2d85f3be67c7ffdb6c` built successfully but failed
before completing baseline-normal cycle0 or reaching the candidate. Its compact
terminal records `Evidence overflow or unavailable` while waiting for Remove,
with approximately69 seconds left in that action deadline. This is a diagnostic
observer failure, not a successful native22 gate or a demonstrated audio-engine
crash. No test-window crash report was collected. The artifact is
`12787533054`,77,515,814 bytes, SHA-256
`6450282cf8e02ccc5913ce076b755c74dab633b35804569c1cae4f20cdee9dcd`.

The collector's same-device evidence-only boot succeeded, but its old filename
allowlist rejected the newly produced `host-final-window.json`; it also lacked
`case-receipt-N.json`. Thus the full terminal body was not uploaded. Its compact
hash/size survived, but **the exact event/node counts and which overflow flag
fired are unavailable**. Do not substitute a calculated count for measurement.
The collector now accepts only the exact new names/ranges, rejects unknown,
linked, nested or out-of-range files, and bounds each mode to93 files. Compact
failure diagnostics additionally retain separate page/observer/window flags,
event/node/context and warning/error/action/trace counts, the event interval and
receipt ordinal. When the compact terminal attachment is captured, these counters
no longer depend on successful Documents collection. WebContent termination or
attachment failure can still prevent that evidence.

Completed-case draining alone cannot protect a slow single case. Native-only
protocol2 therefore checks at each existing polling iteration for a highwater
of1024 events and persists the **whole captured snapshot**, still at most4096
events. Keeping its events and metadata at the same capture boundary avoids
misrepresenting close ordering. There is only one in-flight prefix, with at
most32 mid-case chunks plus8 case receipts per mode (40 monotonic ordinals).
A chunk does not advance the case; only the exact completed-case receipt does.
No audio, gesture, renderer, media-policy or runtime operation is added.

Every chunk undergoes the original observer checks before persistence and
independent replay after collection. The host atomically writes and reads back
the exact bytes before returning the sequence/token/count/size/SHA-256 receipt.
Events appended while writing remain in the next tail. No acknowledgment is
accepted after its20-second/global deadline or after terminal retirement.
Missing, wrong, duplicate, reordered or late acknowledgments fail without
clearing the pending prefix. Polling includes checkpoint I/O in the **original
phase deadline** and rechecks it before accepting even a true predicate; an
engine operation cannot gain extra time from logging. Native callbacks retain
their3-second bound. Case and terminal handling cannot race a pending checkpoint.

Bounds remain2MiB per file,16MiB per mode and128MiB per collected suite, with
4096 global node metadata entries per mode. Neither node/context metadata nor
close snapshots are reset. Overflow remains latched and fatal. The1024
highwater leaves3072 event slots of nominal headroom, not a guaranteed callback
rate or bridge-latency allowance. If a stalled bridge, node cap, storage cap or
the unchanged global600-second matrix budget is exceeded, the run must fail.
Slow native accessibility operations may still exhaust those limits.

Replay consumes every chunk and case exactly once in one contiguous global
sequence, validates original attach/detach evidence even in discarded prefixes,
and rejects candidate post-close source/handler activity across chunks, cases
and both terminal intervals. Baseline retained-handler controls are unchanged.
The final writer/cutoff protocol is unchanged and remains a finite observation,
not a claim that all future callbacks or garbage collection have completed.
Synthetic tests exercise the actual JS poll/receipt pipeline with over6500
records in one slow-action case, failed/missing/late mock readback, exact prefix
and late-tail continuity, deadlines and full22 replay with intermediate chunks.
They are not native WebAudio or Swift/FileManager failure-injection execution.

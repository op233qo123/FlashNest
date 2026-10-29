# FlashNest1.5.6build19: bounded native save/audio validation

**Prepared, not native-executed.** The frozen production App was not edited. This package adds one synthetic-only save test and rebinds the existing reviewed late-audio harness; it does not create a second recovery implementation, change save schemas/keys/paths, change the shipping bundle ID, build an IPA, or dispatch CI.

## Immediate results

- New `NativeSaveSettingsPreservationTests` closes the gap left by the existing no-SOL sampling/renderer session fixtures: real nonempty AVM1 SOL bytes and native `current.json` stay unchanged through all four saved sampling tiers, renderer preference changes, a corrupt preference, explicit pause, repeated native background/foreground methods, and close/reopen reading42. Fixture game files remain unchanged. The test honors the actual runtime validation gate; it does not turn the gate on.
- The audio host/probe/UI tests and semantic verifier are copied **byte-identically** from the reviewed late-audio package. Exactly two diagnostic-copy changes are rebound: passive shell trace/intent/SOL readers and the existing native one-shot synchronous injection method. No status event is fabricated. No document-start audio injector, audio constructor hook or private runtime handle is added.
- Local source/model checks: **31 Python contract/mutation tests**, bilingual copied-shell/save regressions using the exact audio-operation source, **7** warning groups, **21** bridge/adapter groups and **68** late-probe groups passed. These are not the existing31picker XCTest cases and are not native results. Source review found no immediate new Swift/save-test defect; Swift compilation remains unperformed.

## Exact non-overlapping native selections

`test-selection.json` lists every method selector and source-file SHA256. Select methods exactly, never the entire test target.

| Lane | Scheme | Required executed/pass count | Maximum per test |
|---|---|---:|---:|
| `save-models` | `FlashNest` | 48 | 180s |
| `save-webkit` | `FlashNest` | 19 | 180s |
| `save-ui` | `FlashNestUI` | 1 | 420s |
| `audio-candidate` | `LateAudioDiagnostic` | 2 | 360s |
| `audio-baseline` | `LateAudioDiagnostic` | 1 | 180s |

Total: **67 unit tests (66 existing +1 new),1 existing app UI test,3 existing audio diagnostic tests**. No skipped/expected-failure/duplicate/retried cases count as success. All require **Xcode16.2 / iOS Simulator18.2**, serial execution and separate result bundles. Do not silently select another runtime. Parent owns one consolidated workflow; none is added here.

The19WK cases are SharedObjectWebKit2, SharedObjectPersistence10, RawSOLWebKit1, LegacySavePreservationWebKit1, PlayerCallbackIdentity3, InputFocusRuntime1, and the new save/settings1. They cover real destroy/flush/capture, close/reopen, explicit/current checkpoints, RAM-only distinctions, import and isolation, confirmed import once, interrupted native capture, unconfirmed flush quarantine, process-termination archive preservation, and stale page/navigation callbacks. `PlayerSessionTests`, save policy, archive parsing/store/summary and localization cases are in the48model lane.

The existing `LifecyclePlayerUITests/testBackgroundDirectSaveCancelManagementAndRestartSameGame` supplies real Files import, actual Home return, live-child input, explicit menu pause, direct-save outcome, management-warning cancellation and explicit save/restart. It requires the existing separate `FlashNestFixtureSource` app, fresh disposable simulator data and English UI. English/Chinese resource regression is separately retained by exact source checks/localization tests; this does not claim a second Chinese UI walkthrough.

Picker original31 and ZIPSelection UI, all RenderSampling/Sampling/Renderer setting/status/session suites, Fullscreen and RendererCompatibility UI are explicitly excluded to avoid the package/sampling lanes being counted twice. Memory performance and unrelated archive-deletion suites are not selected in this bounded lane.

## Main App unit overlay

Copy only `Tests/NativeSaveSettingsPreservationTests.swift` into the final test-only `Tests/` directory before XcodeGen. The existing `project.yml` already includes `Tests/`; no production target/resource edit is needed. Do not copy `diagnostics/` or `overlay/` into the shipping App. The baseline file is absent (`null`) and the new hash is recorded in `file-manifest.json`.

## Rebound audio target

`diagnostics/` contains immutable reviewed helpers, host, tests, Info.plist, verifier and historical runtime identities. `overlay/` contains only the two transformed App text files for review, with baseline/new hashes in `evidence/audio-overlay-plan.json`. The staging script recomputes those transformations independently from pinned App inputs rather than trusting overlay bytes.

```sh
python3 scripts/stage_audio_target.py plan --source /path/to/frozen-composite-app
```

`plan` performs no App/runtime copy. Full source/runtime target staging is deferred until the final engine exists, using a **new disjoint CI directory**:

```sh
python3 scripts/stage_audio_target.py stage \
  --source /path/to/final-app \
  --runtime /path/to/approved-composite-runtime \
  --runtime-inventory /path/to/runtime-files.json \
  --runtime-inventory-sha256 EXACT_REVIEWED_INVENTORY_SHA256 \
  --role candidate-composite --output /path/to/new-audio-candidate
```

The runtime inventory must be the full exact `path -> {sha256, bytes}` map, not `runtime.browser-manifest`'s subset/string map. Stage rejects symlinks/traversal, changed/missing/extra runtime files, non-dual runtime shape, original baseline masquerading as candidate, and the retired1.5.5candidate runtime masquerading as the final composite. **These checks are identity/shape checks, not proof of source/commit eligibility. Parent must bind the inventory to the approved final composite provenance independently.** The test runner must retain that provenance and `source-manifest.json` with the xcresult.

The final package owner may supply `--final-metadata /path/to/map.json` for explicitly reviewed engine notice/runtime-identity changes only. Executable Swift/JS/CSS/index, save, localization, bundle and preference inputs remain pinned. In particular, switching `runtimeValidated` to true intentionally fails the current gate-off lock; it needs an explicit reviewed source repin. Never silently relax that pin.

The historical fatal control is **not** a final-candidate test. Stage another new target with `--role baseline-historical` and the exact original audio baseline from run40614335019/artifact12783974867, whose full map is in `diagnostics/baseline-runtime-identity.json`. Run only `testLateBaselineKnownRemainsProductionFatal` there. Use the same rebound App and same iOS18.2environment. Never execute baseline-known mode on final candidate bytes. Fresh simulator/app state per arm avoids contamination.

Candidate selectors:

- `LateAudioUITests/LateAudioUITests/testLateKnownRecoveryKeepsLiveChildAndRealSOL`
- `LateAudioUITests/LateAudioUITests/testLateUnknownRemainsProductionFatal`

Both require trusted actual Play, root/child/input traces and real nonempty progress420SOL before helper loading. Known recovery requires source-owned current rejection, one trusted actual Retry, same captured native context and matching fulfilled/running tuple, cleared real production warning, fresh child input and unchanged SOL **before** explicit reopen. Unknown failure must remain production fatal. Prototype/instance restoration and native close/drain are mandatory. Existing3sJS,5ssuspend,15spoll and180/360stest bounds remain unchanged.

## Result verification and evidence

After each invocation, retain the **complete bounded test log**, not a truncated excerpt, and export:

```sh
xcrun xcresulttool get test-results summary --path RESULT.xcresult > SUMMARY.json
python3 scripts/verify_results.py --lane save-webkit --summary SUMMARY.json --log TEST.log
```

The verifier requires exact scheme title, count, iOS18.2device/configuration, zero skips/failures/expected-failures and exactly one started/passed line for every declared selector. Audio lanes additionally require exactly their expected `AUDIO_LATE_FINAL` records and reuse the reviewed fail-closed semantic verifier. Model-declared execution, absent records, foreign tests, duplicates and zero-test greens fail. Passing record semantics does **not** authenticate CI identity; parent must correlate actual xcresult, exact source/runtime manifests, commit and environment. Upload only allowlisted synthetic screenshots/text/JSON with bounded sizes; no user files, container trees, save dumps from private games or video.

## Deliberate evidence limits

- Linux has no Xcode; no Swift compile, simulator run, trusted native tap or audio playback ran during this preparation.
- The lifecycle SWFs are original synthetic save/input fixtures, not a PCM/audible-output or animation rendering fixture. Native AudioContext state/status and real retry are **not audible-output proof**.
- The reviewed audio probe keeps `totalContextCount: null`; one captured resume receiver is **not** a census of active audio graphs.
- Existing stale async audio status/intent cases are model coverage; native callback identity cases cover real WK page boundaries, not every native AudioContext Promise interleaving.
- Actual speaker/listening or approved physical-device capture, device interruptions, the prior unexplained SIGILL/SIGBUS/OOM cause, private-game compatibility and unknown file-provider behavior are not claimed resolved.

The stopping point for this preparation is a reviewed frozen test recipe/selection and passing local contract checks. The parent-owned next step is final-runtime binding followed by exact iOS18.2CI; only the single final user IPA may follow accepted gates.

## v2 candidate gate binding

Candidate `stage` now requires `--candidate-gate-on`; historical negative forbids
it. Only the exact `runtimeValidated = false` to `true` line may differ from the
frozen executable source, verified by inverse transform against the original
hash and byte count. The composite runner first requires its App map to equal
the post-geometry gate-on final App, including final metadata. Baseline historical
App and audio controls are unchanged. Source-manifest schema2 records the gate
state. This does not establish active reduced sampling or audible output.

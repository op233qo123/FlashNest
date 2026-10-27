# Isolated experimental candidate: native attestation and contracts

This opt-in directory does **not** promote a runtime into the app. It leaves
the official `FrameOrderRuntimeTests.swift`, `App`, default `Tests`, default
fixtures, and `project.yml` unchanged. `workflow-draft.yml` is a manual-workflow
draft; publication and dispatch require separate authorization. The candidate
has an experimental name/channel, even though its upstream package base version
is `0.7.1`. It is not an official unmodified Ruffle binary or upstream approval.

The isolated native run has now passed all three measured scopes; see
[NATIVE_RESULTS.md](NATIVE_RESULTS.md). Production-candidate integration and
its complete application validation remain separate.

## Fail-closed artifact → native-bundle chain

1. A reviewed `candidate.lock.json` identifies one successful engine build:
   repository/workflow, experiment head, run/attempt, artifact ID/name, ZIP SHA,
   provenance SHA, and fixed upstream/patch/source hashes. There is no usable
   placeholder, "latest artifact" lookup, arbitrary URL, or official fallback.
2. The authorized workflow fetches run, job, and artifact metadata from GitHub's
   authenticated API plus that exact ZIP. The offline verifier checks identity,
   completed/successful status, and every required baseline/patched/web-build
   step. Skipped, incomplete, foreign-head, expired, or mismatched artifacts fail.
3. The verifier checks the ZIP size/digest before bounded safe extraction. It
   rejects traversal/noncanonical paths, duplicate entries, symlinks/special
   files, encrypted entries, unexpected roots, and oversized archives.
4. The locked provenance must match the fixed source commit, exact reviewed
   one-file patch, original/modified source hashes, experimental version seal,
   dual-WASM build flags, and the runtime's embedded experimental identity. All
   candidate files must match its full size/hash inventory, without extra files.
   Source correspondence, locks, recipes, and licenses are required and retained.
5. Both original-fixture trace/log gates and all 31 adjacent-case records/logs
   are checked for **both** phases: 29 strict reference tests plus preservation
   of 2 already-known failures. A known-failure-preservation pass is not Adobe
   equivalence. No golden is regenerated.
6. Staging copies the unchanged shell into a fresh `Web` directory **outside
   App**, replacing its runtime as a whole rather than merging stale official
   chunks. The separate test resource folder includes original fixtures, frozen
   contracts, provenance, source correspondence, and the reviewed lock.
7. A deterministic `candidate-pin.json` contains complete runtime, shell, and
   test-resource file inventories. Its SHA and the lock SHA are emitted into
   `FrameOrderCandidateIdentity.generated.swift`. The native test verifies that
   **compiled** pin SHA first; a bundled manifest cannot authorize itself.
8. Native validation checks every bundled file, fixed source/patch identities,
   source bytes, original fixture hashes, and frozen contract hashes before
   `PlayerSession` is started. Failed attestation refuses candidate execution.

This is workflow chain-of-custody and exact byte verification, **not** a digital
signature, a second independently reproduced clean build, proof about untested
engine behavior, or proof that the user's full game follows this reduced path.

## Verifier interface

The helper performs no network access and executes no downloaded programs:

```bash
python3 experiments/frame-order/candidate-native/verify_candidate.py \
  --artifact-zip candidate.zip \
  --lock experiments/frame-order/candidate-native/candidate.lock.json \
  --run-metadata run.json --jobs-metadata jobs.json \
  --artifact-metadata artifact.json \
  --stage candidate-native-stage --repo-root .
```

`--archive` is an alias for `--artifact-zip`. The stage path must not already
exist. Outputs are:

- `candidate-native-stage/Web/`: unchanged shell plus fully verified candidate.
- `candidate-native-stage/frame-order-candidate/`: fixtures, expectations,
  compiled-hash-bound pin, lock, and complete compact source correspondence.
- `candidate-native-stage/FrameOrderCandidateIdentity.generated.swift`.
- `candidate-native-stage/verification.json` and the safely extracted artifact.

The exact lock schema has no additional fields:

| Field | Required value/type |
|---|---|
| `schemaVersion` | integer `1` |
| `repository` | `op233qo123/FlashNest` |
| `workflowPath` | `.github/workflows/experiment-frame-order-engine.yml` |
| `runID`, `runAttempt`, `artifactID` | positive integers from reviewed run |
| `headSHA` | exact 40-character lowercase experiment commit |
| `artifactName` | `FlashNest-experimental-frame-order-engine` |
| `artifactArchiveSHA256`, `provenanceSHA256` | verified 64-character SHA256 values |
| `upstreamCommit` | `89a7049965f3090e706265670df309a5128233ac` |
| `patchSHA256` | `de0acabdf957fccbc11966b67defd0a7f577cdc5a147db949e0a4f0e56c6331f` |
| `originalSourceSHA256` | `fc229d96ab6fced20391cf810d9d89a2118803cb7f5ce48ddf6967e52e35700a` |
| `patchedSourceSHA256` | `af780dae48b842e0756b8cd23f50a539737d0bcbbbdca970feb90f27725e96b0` |

The lock may be created only after authenticating the actual successful build
and verifying its artifact. The supplied lock pins successful web build
`40491098384`, artifact `12729069965`; offline verification and staging have
passed against that actual ZIP and its API metadata. This establishes the
artifact chain above; the separately measured native result is recorded in
[NATIVE_RESULTS.md](NATIVE_RESULTS.md), not inferred from offline verification.

## Native test semantics

The standalone class is `FrameOrderCandidateRuntimeTests` with methods:

- `testCandidateControlContract`
- `testCandidateNestedRepairContract`

It retains the original bounded WebKit calls, visible window, full raw observer,
trace overflow/truncation detection, awaited server drainage, and startup-error
evidence. It asserts the aggregate capture-completeness condition explicitly,
so an incomplete observation cannot silently bypass semantic assertions.

Reports distinguish `captureComplete` from `experimentalContract`. Missing or
malformed rows, nonsequential row IDs, duplicate/missing completion, incomplete
ticks, or observer/runtime failure are capture failures, not ordering results.

The semantic contract is compared **without filtering or sorting**:

1. Exact ordered trace prefix through the sole `FO_DONE 12 P B`.
2. Immediately following `FO_B_LOOP 7` and `FO_B_OPENING 5`, which finish the
   already-queued child script in that same engine frame.
3. Any later snapshot tail must be explicitly reported complete repetitions of
   that loop/open pair. The full raw snapshot is always retained.

The resulting first-complete-tick-12 windows match the frozen 32-row nested
experimental repair target and 31-row unchanged control. **FO_DONE is emitted
inside ENTER_FRAME, not after a settled final state.** No in-observer pause or
state forcing is used to manufacture an ending, and no surprising pre-DONE row
is discarded. The headless exact full-frame gate remains separate evidence.

These contracts are experimental targets/recorded controls, **not Adobe golden
outputs**. No Adobe execution or user-game execution is performed here.

## Separate save/restart and UI lifecycle stability gates

The manual workflow's `both` variant runs the two original-fixture contracts
above, then separately exercises unchanged existing tests against the staged
candidate:

- `SharedObjectPersistenceTests/testExplicitSaveAndRestartUsesNewPageAndPreservesSaveAndGameFiles`
- `SharedObjectPersistenceTests/testDestroyFlushPersistsAndRestartReadsActualSharedObject`
- `LifecyclePlayerUITests/testBackgroundDirectSaveCancelManagementAndRestartSameGame`

The UI gate imports a separate source app. Frame-order, save/restart, and UI
lifecycle scopes have distinct result bundles and logs, with exact selected
test names/counts and iOS Simulator 18.2 checks. Attachments, screenshots, and
available crash evidence are retained separately. A single `control` or `nested`
variant is only a targeted original-fixture diagnostic; it does **not** run or
establish these additional stability gates.

Scheduling correctness and WebContent process stability are different claims.
The stock build's 18/18 native tests did not rule out the separately observed
intermittent WebContent crash during real UI save/restart. The queued-goto guard
is not an established fix for that crash. The passing candidate lifecycle
run establishes only that observed run, not absence of an intermittent failure.
Its actual raw evidence and limitations are recorded in [NATIVE_RESULTS.md](NATIVE_RESULTS.md).

## Checks and remaining boundary

```bash
python3 -m unittest discover \
  -s experiments/frame-order/candidate-native -p 'test_*.py'
```

Pure checks cover metadata/hash/source tampering, skipped/partial gates, unsafe
ZIPs, symlinks, deterministic staging with compiled pin binding, source isolation,
and missing/reordered/repeated/unexpected trace rejection. Full-staging unit
tests use explicitly synthetic artifacts and mock only the synthetic modified
source hash; they do not bless or execute a candidate. Exact embedded JavaScript
is checked in Node, while Swift source contracts are checked as text.

Native compile and candidate execution were verified by the separately authorized
standard `macos-14` / Xcode 16.2 / iOS Simulator 18.2 run linked above. Linux
helper checks, headless engine tests, and a successful web build alone must not be
reported as an iOS/WebKit pass. The draft retains traces, crash evidence, the
reviewed ZIP, and source/license correspondence; it never packages an IPA.

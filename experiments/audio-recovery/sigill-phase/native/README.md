# Exactly one phase-boundary observation — LOCAL preparation

Intended repository paths: these code/resources under `experiments/audio-recovery/sigill-phase/native/`; workflow `observe-sigill-phase-ios18_2.yml` under `.github/workflows/`. No remote action, build, launch or native observation was performed by this author.

This is separate from the late-audio draft and the old three-attempt controller. It stages immutable production source `5862f8dbd414d9835f11872d3ebabd1eed315ffc`, the exact original startup injector `d495f538242dd49915810a33478c17da9c1e7a831a721524a9136c4f2628176b`, and proposed fixed phase observer/Swift allowlists. It never substitutes the new late probe, changes shipping defaults, taps Play, or arms a fault. Context-state is unknown/not queried: original injector startup behavior is preserved, not upgraded to a census or state-query claim.

## Activation gate

`approval.json` is deliberately absent. Parent must create/review it only after the new distinct engine build completes and actual artifact bytes/provenance are independently verified. Required fields:

- `kind`: `sigill-phase-diagnostic-not-shipping`; `authorizedObservationCount`: 1.
- `observationLabel`: unique reviewed `[A-Za-z0-9_-]{1,64}` manual input; dispatch exactly once. `github.run_attempt == 1` blocks GitHub reruns, but a human must not create a second new dispatch with the same label.
- `repository`: `op233qo123/FlashNest`; `sourceCommit`: production base above.
- `runID`, `artifactID`, `buildCommit`, `archiveBytes`, `archiveSHA256`, `provenanceSHA256`: exact new build inputs, never old candidate identity.
- `runtimes.diagnostic`: `{directory:"runtime", files:{relativePath:sha256}}`, all files including nested resources/maps/licenses from the new runtime-manifest.
- `diagnosticFiles`: exact SHA256 inventory of published native files (at least every required stager/runner/verifier/exporter/module/project/resource/Host file). Stage checks hashes, copies only two explicitly pinned Host Swift files, and never recursively includes an unapproved Swift source.

Artifact ZIP root must directly contain `runtime/`, `runtime-manifest.json`, `provenance.json` and complete source-correspondence/build inventory. `verify_engine.py` checks archive, build, artifact name, provenance and every extracted file. No guessed prefixes, old runtime fallback, arbitrary workflow input artifact or shipping approval reuse.

## Single-attempt and deadlines

Standard free `macos-14`, exact Xcode16.2 and iOS18.2 SDK/device. After boot, actual host and simulator `uname -m` must both equal arm64 before install/launch; unavailable architecture is a prelaunch failure, not permission to select a paid/larger runner. One launch loop `(1,)`, no native retries. A timed-out install is only inspected for exact installed bytes, never reinstalled. Readiness deadline60s, postready observation30s (at most90s observation), bounded teardown command30s, immediate3s reporting interval and final60s report-spool grace preserve prior limits. No three-attempt completion gate or XCTest test run.

Workflow itself is bounded40min, build15min and one observer10min; no matrix, retry action or automatic trigger. Parent owns exactly-one dispatch. A failed preflight or observation is not permission to rerun native.

## Publication privacy and evidence limits

Only `phase-public/observation.json` and its SHA manifest upload. Public projection includes validated allowlisted fixed-phase journal records, enum/bounded-number fields, public runtime hashes, and crash SHA/bytes/process class/signal/type/numeric termination code. The signature additionally retains a validated fault-thread index, architecture enum, at most eight fault-thread frames with fixed image class (`JavaScriptCore`, `WebCore`, `WebKit`, `unknown`, `other-system`), numeric image size and contained relative image offset, plus resolved booleans and omitted-frame count. An unresolved frame’s offset may actually contain an absolute fault address, so that offset is explicitly null; a resolved image means a valid indexed image with positive size and offset strictly inside that size. No symbol, image path/name, image base address, register or thread-name payload is published. It preserves host-PID/time association versus **shared-process-time-only-not-proven-ownership**. A report in a shared simulator time window does not prove reproduction of the original SIGILL or WebContent ownership.

Raw command output, source stage, build output, install paths, simulator inventory, raw IPS and any private ephemeral diagnostic files stay in `$RUNNER_TEMP` and are not uploaded. No raw xcresult, original decoded logs, games or saves enter this workflow. No unified-log stream is collected. Raw private receipts vanish when the runner is destroyed; there is **no durable private raw-log/IPS archive**. Only the bounded numeric/class signature survives; absence of full stacks, symbols, registers and raw images limits later attribution. This can compare an unresolved first frame followed by JSC-relative frames, but cannot prove the same fault address or cause.

`singleObservationComplete` means only bounded no-crash-observed evidence completeness. Crash/no-crash or fixed phase receipt absence is not a crash fix, root cause, audio recovery acceptance or shipping promotion. Real Swift compilation/generated runtime/native bridge delivery remain unverified until the authorized build/one observation.

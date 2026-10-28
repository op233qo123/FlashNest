# Passive iOS 18.2 startup control — diagnostic only

The real pre-Play WebContent SIGILL from run 40635582367 remains unresolved.
The subsequent three-case run 40638547694 instead encountered an XCTest PID
identification failure and a pre-injection Enter/child trace timeout. Neither
result disproves the earlier crash or establishes an audio root cause.

This manual lane removes XCTest and input from the startup observation. It
builds the same reviewed diagnostic host, exact production source snapshot,
Session configuration, original lifecycle fixture, and approved runtime arm.
The only differences between arms are the approved baseline/candidate runtime
files and their resource inventory. It does not force a renderer or WASM flavor.

For each arm the runner installs the built app once and performs exactly three
fresh app-process launch attempts using simctl. There are no launch retries,
Play, key, focus, fault injection, resume or recovery actions. `startup-only` is
metadata only; the host still automatically calls its unchanged normal open.

- The exact installed simulator must be iOS 18.2, Xcode 16.2/SDK 18.2, macos-14.
  No simulator download or OS fallback is permitted.
- Readiness must be observed within 60 seconds of the launch attempt, including
  simctl launch time. It requires the matching native PID/UUID journal with
  native-opened, shell-load-return, loadeddata, instance-banner and a request for
  an approved WASM basename. Load return and loadeddata may occur in either order.
- After readiness there is a full 30-second passive observation window, maximum
  90 seconds per launch. Polling at most every two seconds uses native journal
  files and process existence; it never evaluates JavaScript. A late 58-second
  startup therefore gets 30 seconds, not two seconds, of post-ready observation.
- The simctl PID, native journal PID, selected UDID/runtime, executable hash,
  source manifest, runtime inventory, context-created coverage, executed banner
  flavor/backend, wall/monotonic timestamps and pre/post
  termination evidence are retained. A process PID is not a WebContent PID;
  shared WebContent, JIT and cache coldness remain unknown. Context creation is
  reported, not required or inferred: a ready renderer without a context record
  is not evidence that audio initialization succeeded.
- Each native reset writes a new UUID file and retains at most four journals.
  All journal values are bounded public enums/numbers/runtime basenames/hashes;
  no game paths, URLs, query tokens, save keys or values are recorded.
- Only diagnostic-host, WebContent/GPU and SimMetalHost IPS reports are retained,
  max 2 MiB each, ten reports/10 MiB total; omissions fail evidence completeness.
  Reports are collected before explicit termination and after a fixed three-second
  grace. A final bounded 60-second REPORT-ONLY grace after all attempts then
  rescans retained reports and reassociates every attempt, so a report arriving
  35 seconds after an early incident is not lost just because a later attempt is
  current. This never extends startup observation or relaunches the app. Raw
  report PID/coalition are retained; outside-window/unassigned reports remain in
  the artifact and prevent overall complete-evidence success. Embedded
  captureTime, not file arrival alone, classifies the observation
  window. Reports without parseable captureTime fail conservatively. Shared
  WebContent reports are temporal associations, not proven app ownership.
- A bounded finally block terminates the app even if observation/collection fails.
  Cleanup failures remain separate and cannot count as a complete observation.
  External commands have bounded execution time and retained stdout/stderr 64 KiB
  each, except the public simulator inventory stdout has a 512 KiB cap (temporary command spool files are time-bounded, not byte-capped).

Outcomes distinguish launch-unconfirmed, process-exit-or-unconfirmed,
startup-not-ready, native-failure, crash-observed, journal-identity-unconfirmed,
evidence-incomplete, incomplete observation window and cleanup-unconfirmed.
Three complete observations return success only as **no crash observed in these
windows**. They do not prove the previous SIGILL fixed, hardware audio recovered,
or the original trusted-retry acceptance completed. Instrumentation can perturb
timing. Existing three-case tests and all their deadlines are unchanged.

## Preflight and report retention correction
Run40641827448 compiled both Apps but failed before any launch at simulator
inventory preflight. Its generic checker did not retain exit/truncation evidence,
so the original cause is unknown. This revision persists command returncode,
timeout, actual byte counts, separate truncation flags and bounded stdout/stderr
before checking or parsing. A future large inventory may support the cap
hypothesis but cannot retroactively prove the earlier cause. Exact18.2/PID
requirements and all command timeouts remain unchanged. The startup-control
step envelope is15minutes (formerly10) solely to fit bounded simulator
boot/install/teardown and final report retention; readiness60+postready30 and
exactly3attempts remain unchanged. No absence claim extends beyond the final
report-collection cutoff, and an unassigned/malformed/omitted report cannot
produce overall complete-evidence success.

## Optional passive-only profile (startup control only)
The existing/default `instrumented` profile retains the unarmed diagnostic fault
injector; its constructor/resume/event/Retry hooks are an experimental confound.
The optional `passive-only` profile removes its entire WKUserScript guard/read/
registration and bundled resource before compilation, rather than disarming or
restoring wrappers after the engine has captured constructor references. It is
restricted to this no-gesture simctl lane. The host's unused Inject/Snapshot/Close
buttons still require the probe and are NOT valid acceptance paths in this mode.

Production Session configuration, conditional save-restore bootstrap and shell
load arguments remain unchanged. Passive fetch/console observations, shell
milestones and native journal remain timing perturbations. Staging retains a
profile diff, original instrumented receipt, updated Session/source hashes and
the SHA256 of the exact diagnostic startup-script string. After registering
that exact WKUserScript, the native journal hashes the supplied string and emits
`native-script-registered`. This attests registration/installation requested,
NOT execution; the separately received document-start/phase records supply
execution evidence. It is not a claim to inventory arbitrary production restore
payloads. The fault script is absent from both staged project and compiled app.

Without the fault injector there is no AudioContext or source-audio-event probe:
contextCreatedObserved is JSON null and audioStateCoverage is explicitly
unavailable, not zero contexts or failed/successful audio. Actual renderer/flavor
still requires the exact real banner; resource hashes mean requests only. No
backend override, extra focus, resume, input, retry or restoration behavior is
introduced. A clean passive-only run remains finite non-reproduction, not proof
that the prior SIGILL was caused by instrumentation or that recovery is fixed.

## Targeted missing-arm completion and installed-app postcondition
The manual arm choice is closed to both (default), baseline or candidate. Unknown
choices fail preflight; selecting baseline creates no candidate job. This allows
completing the missing passive baseline from40646521966 without repeating its
already observed candidate windows.

That baseline stopped before launch when simctl install reached60seconds after
successful simulator boot. The revised setup makes exactly ONE install call,
bounded180seconds. This is installation infrastructure only; no launch, readiness,
post-ready, report-grace or engine deadline changes and no automatic reinstall.
The CLI result (including timeout/failure) is retained before inspecting the
selected simulator's installed app container. A timeout does not prove the side
effect failed: if the complete installed bundle matches the exact built bundle,
observations may proceed under `installed-verified-after-command-failure`, with
the failed command still explicitly recorded. Missing/mismatched/unsafe/inconclusive
postconditions stop before every launch, even after a successful CLI response.

Verification binds the exact selected simulator data directory, UUID bundle
container and app name; rejects symlinks/nonregular members and case collisions;
checks bundle identifier/executable and SHA256+size of EVERY code/resource file,
including the entire runtime, against the built app. Bounds are5000files and
256MiB total, streaming1MiB chunks; byte/file caps fail closed. Passive mode also
rejects a fault-injector resource at any bundle-relative location. Both complete
inventories are retained before a mismatch is raised. This verifies installed
bytes at inspection time, not future immutability or successful engine execution.

Only workflow/runner/setup verification changes: the exact passive Session,
startup observer, fixture, renderer/media/save configuration and both immutable
runtime inventories are unchanged from candidate40646521966. The target is still
three baseline fresh-process60+30second windows and final60second report grace.
No successful window can erase the earlier realSIGILL or prove instrumentation
was its cause.

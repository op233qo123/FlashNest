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
  grace. Embedded captureTime, not file arrival alone, classifies the observation
  window. Reports without parseable captureTime fail conservatively. Shared
  WebContent reports are temporal associations, not proven app ownership.
- A bounded finally block terminates the app even if observation/collection fails.
  Cleanup failures remain separate and cannot count as a complete observation.
  External commands have bounded execution time and retained stdout/stderr 64 KiB
  each (temporary command spool files are time-bounded, not byte-capped).

Outcomes distinguish launch-unconfirmed, process-exit-or-unconfirmed,
startup-not-ready, native-failure, crash-observed, journal-identity-unconfirmed,
evidence-incomplete, incomplete observation window and cleanup-unconfirmed.
Three complete observations return success only as **no crash observed in these
windows**. They do not prove the previous SIGILL fixed, hardware audio recovered,
or the original trusted-retry acceptance completed. Instrumentation can perturb
timing. Existing three-case tests and all their deadlines are unchanged.

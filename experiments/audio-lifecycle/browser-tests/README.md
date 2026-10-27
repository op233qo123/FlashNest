# Isolated WebAudio lifecycle browser gate

Current corrected harness revision: mocks and original SWF structural checks only; its actual rerun is still pending. Historical run40540513351 built the candidate and completed the eleven baseline cases, then failed the old observer during candidate-normal0 before candidate teardown. See [OBSERVER_CORRECTION.md](OBSERVER_CORRECTION.md). [`SOURCE_PROOF.md`](SOURCE_PROOF.md) explains the bounded source-level self-`Rc` cycle and why it is not an established native crash cause.

## Inputs and invocation

Requires explicit installed Chrome/Chromedriver and WebdriverIO **9.32.0**. The helper checks its actual package Node export (`./build/node.js`), not the browser entry. It performs no browser/package download and binds only `127.0.0.1`.

Each runtime manifest is a JSON object mapping every relative `.js` / `.wasm` file to its lowercase SHA256; no missing/extra JS/WASM or symlinks are accepted. Both manifest digests are mandatory and must come from the separately validated immutable build provenance. The runner verifies bytes, not the origin/trustworthiness of an arbitrarily supplied digest. Build provenance verification remains the workflow's responsibility. Output must be fresh/empty and cannot alias an input or helper tree. Do not pass deployed application paths as output.

```sh
node run.mjs \
  --baseline /verified/baseline --candidate /verified/candidate \
  --baseline-manifest /verified/baseline-runtime.json \
  --candidate-manifest /verified/candidate-runtime.json \
  --baseline-manifest-sha256 BASELINE_MANIFEST_SHA256 \
  --candidate-manifest-sha256 CANDIDATE_MANIFEST_SHA256 \
  --webdriverio /installed/node_modules/webdriverio \
  --chrome /installed/chrome --driver /installed/chromedriver \
  --fixtures ../fixtures --output /isolated/audio-evidence
```

Only backend `wgpu-webgl`, quality low, DPR1 is selected. Require its actual live WebGL2 context and positive drawing-buffer dimensions as well as its renderer log. Baseline and candidate must select the same actual ON/OFF WASM extension path. Exactly **22 rows** are required: eight normal cycles plus first-start, second-start and synthetic-ended fault arms per runtime. Normal cycles share a page for each runtime; each fault arm uses a fresh page. No zero-case/partial success is possible. A global 10-minute deadline, per-wait bounds, bounded capture and cleanup surround the run; false readiness still polls, but fatal sync/async assertions (including falsy thrown values) are latched and rethrown after ending the underlying WebdriverIO wait, so they cannot cause repeated post-failure execution or false success; provenance, incremental case journal, active case, raw per-case JSON and final summary survive failures where the process can write them.

## Evidence contract

- Before installing any observer, a real OfflineAudioContext-created AudioBufferSourceNode preflight checks the same native onended descriptor: identical function round-trip, null→null and undefined→null, with exact-null cleanup. It does not start playback/rendering or create an extra live AudioContext. Missing/failed preflight fails.
- WebDriver's actual button click supplies trusted activation, never synthetic `.click()` or JS-generated input.
- Require original AVM2 ENTER_FRAME activity and natural audio source refill (>2 sources).
- Each resume/pause action requires a fresh native method call and that action's own fulfilled Promise ID, not an old startup Promise. After the second resume Promise settles, require a newly created source and a heartbeat newer than the trusted resume callback, while playing=true.
- Require zero close calls immediately before normal/synthetic removal, then actual close entry and fulfilled Promise; missing close/refill is a failure in both arms.
- Baseline is expected to retain explicit handlers at close entry; candidate must detach every recorded attachment. An unexpectedly clean baseline is a control mismatch, not a pass. This is setter evidence, not GC evidence.
- Constructor start-error faults require exactly one known NullAudioBackend fallback ERROR and the expected one/two sources. Other errors fail; recorded native source-factory throws also fail outside the single explicitly dispatched baseline synthetic event. Exact pinned styled ERROR/WARN logger signatures are captured without coercing logged objects.
- Synthetic-ended deliberately retains one latest node. Baseline must attempt source creation during the dispatched event; candidate must not. No direct call into a dropped Rust closure occurs. The arm is fault injection, not spontaneous post-destroy event or SIGBUS reproduction.
- Normal observation does not retain node/context references, wrap onended callbacks, force GC, or change native Promise return identity. Attaches require exact function identity; detaches require an actual null/undefined input and native getter exactly null. Unexpected setter categories, a changed callback, or a non-null getter fail. Native getter state—not merely the requested assignment—drives conservative attachment bookkeeping. Hooks preserve callback identity, `this`, arguments and native exceptions. Promise observers add ordinary JS reaction microtasks in both arms while returning the native Promise unchanged; this is instrumentation, not a no-overhead execution path. Plain metadata arrays contain no nodes/callbacks.
- AL_ACTIVE traces are coalesced into a counter to avoid trace flood; unexpected trace records and errors remain bounded, with overflow failing the gate.

Mock-only checks (no browser, audio device, network, WASM or SWF execution):

```sh
node test_observer.mjs
node test_console_observer.mjs
node test_contracts.mjs
node test_runner_guards.mjs
node test_preflight.mjs
node test_wait_until.mjs
for file in *.mjs; do node --check "$file"; done
```

The source patch/fixture/gate alone does not update the app. A passing browser gate would not establish native WKWebView stability, actual garbage collection, complete memory reclamation, audible quality or that any prior user-game crash is fixed.

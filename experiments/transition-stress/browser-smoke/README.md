# Original Loader transition — existing-runtime Chrome smoke

This narrow diagnostic tests the unchanged original SWF37 normal-unload fixture with the immutable existing queued-goto-guard runtime. It does not patch the engine or application. Preparation checks are mocks/syntax only; actual browser execution is recorded separately by a manual diagnostic workflow.

**Chrome `webgl` is intentionally selected, not iOS/WKWebView's renderer.** Success would show that this tiny original bytecode/Loader path reaches its milestones on that specific runtime/browser/backend. It would not establish native stability, a fix for WebContent termination, Adobe ordering, large-SWF/media stress, rotation/background survival, or fresh child activity after those native operations. No user-game assets or saves are used.

## Immutable inputs and invocation

Requires explicit installed Chrome/Chromedriver and WebdriverIO 9.32.0 with the actual package Node export `./build/node.js`. No dependency/browser downloads, external server exposure or production runtime edits are performed by the runner. HTTP is bound to `127.0.0.1` and serves only enumerated helper files, hash-verified runtime JS/WASM, and the two original SWFs.

```sh
node run.mjs \
  --runtime /verified/runtime \
  --runtime-manifest /verified/runtime.browser-manifest.json \
  --runtime-manifest-sha256 VERIFIED_MANIFEST_SHA256 \
  --webdriverio /installed/node_modules/webdriverio \
  --chrome /installed/chrome --driver /installed/chromedriver \
  --fixtures ../fixture --output /isolated/transition-browser-evidence
```

The runtime manifest maps every relative JS/WASM path to its SHA256. The runner requires the exact full inventory and its supplied digest; the separate workflow/extraction verifier must establish the immutable vendor archive provenance. The runner cannot establish provenance merely because a caller supplied a matching digest. Output must be a fresh/empty real directory and cannot alias an input/helper tree.

Fixture pins (unchanged):

- `main.swf`: `7671411b8be327cb9cc105a782d14c9e999e828dbd2125268f2c913d5ddae151`
- `sub/child.swf`: `7f5015789f368ac2221d47930d255b204828f9d33384c14f36e6ed947edf58c8`
- fixture `manifest.json`: `fdcd95be4ab55c0101544a3e6c7d4ecaec2b9dd31a578642abb52bcc25926c98`

The alternative unloadAndStop prototype is not served or selected. Existing fixture sources/binaries/manifest remain untouched.

## Milestones

The page waits for `api.load` and trace-observer installation, then an actual WebDriver click on the host Resume button calls `api.resume`. It requires the actual selected renderer log `webgl`, ON/OFF WASM path, live WebGL1/2 context, positive drawing buffer, DPR1 and original LT trace readiness.

Require READY generation 0, then exactly three actual W3C pointer actions (down/up) at the canvas viewport center, each only after the preceding READY. Require READY 1, 2 and 3, unchanged boot token, `pointerCount == generation`, `keyCount == 0`, `ready == 1`, actual child generation equal to root generation, `errors == 0`, and independently recorded `unloadCalls == unloadEvents == generation`.

All traces are parsed against the exact original 13-field common contract. READY/STATE have exactly 13 fields; other allowed event markers may have one detail field. Missing/duplicate/automatic READY, malformed traces, unknown markers, errors, untrusted/extra pointer events, overflow, load timeout or missing renderer context fail. Non-milestone unload event records may legitimately precede the unload-call counter increment; the diagnostic does not impose Adobe total event ordering.

Optional Enter STATE is deliberately omitted from this first narrow smoke to avoid keyboard-focus confounding before proving the load/transition path. Therefore it does not attest advancing active child heartbeat across observation intervals. Canvas input evidence records actual trusted pointerdown/up with passive capture listeners, not compatibility DOM click events that the runtime may prevent. The SWF pointerCount remains the exact scene-advance assertion. No silence-is-survival inference is made.

The runner uses a five-minute overall bound and per-command/readiness bounds. It writes incremental raw trace/error/HTTP events, active generation, live partial evidence, full evidence and bounded raw PNG screenshots at READY0–3, and a failure PNG where available. Screenshots are evidence for manual inspection, not a new pixel golden. Complete success requires exactly four milestones. Cleanup/session failures also fail the summary. A process killed outside normal exception handling may leave only partial artifacts, not a successful result.

## Local checks only

```sh
node test_contracts.mjs
node test_runner_guards.mjs
node test_console_observer.mjs
for file in *.mjs; do node --check "$file"; done
```

The console helper captures the exact pinned styled tracing-wasm ERROR/WARN signature, not INFO/ordinary logs, while preserving original logger receiver/arguments/return and avoiding object coercion. These unit checks do not execute a real SWF, browser, WASM or audio device.

`owned-manifest.json` inventories only the browser files owned by this diagnostic implementation. The separately owned `prepare_runtime.py` and `test_prepare_runtime.py` are intentionally excluded and are covered by workflow/source review separately.

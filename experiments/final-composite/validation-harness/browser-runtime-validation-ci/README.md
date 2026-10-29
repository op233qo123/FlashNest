# Final browser lane CI adapter

Authored only. No CI, browser, engine rebuild or IPA dispatch performed here.
Consumes the frozen source-bound53-file browser harness without modifying it.

Invocation from an already reviewed/pinned workflow:

    VENV/bin/python browser-runtime-validation-ci/run.py \
      --composite-root experiments/final-composite \
      --harness browser-runtime-validation

The composite root must already contain approved `validation-lock.json`, the exact
`staged-engine-archive.zip`, verified `staged-engine/`, `evidence/engine-staging.json`,
and complete `baseline-bundle/sampling/runtime/` (actual delivered155 recovery arm).
Historical audio is a different baseline-bundle role and is never used here.

## Required external binding

- `dispatchAllowed=true` only after final artifact/harness review.
- All existing engine fields pinned:archive SHA,run ID,commit,source set,provenance
  SHA,runtime inventory SHA and bothWASM hashes.
- `engine.wasmFlavorBySHA256` maps exactly those two hashes to `extensions` and `mvp`.
  Integrator must prove this from actual flavor outputs/source-map+asset correspondence,
  not size, filename order or guessed hashes. Missing/ambiguous map fails before browser.
- `lanes.browser.harnessManifestSHA256` is the corrected reviewed browser manifest
  `6e544655adacf631deb98a9bdf46811e6cf877aba2db98953c71a66123599bf4`.
- `lanes.browser.expectedRowsPerExecutedPath=290`; commands and all wrapper/harness
  files externally pinned by the existing `validate_binding.py` harnessFiles map.

## Explicit workflow prerequisites, not implicit installs

The adapter deliberately performs no installation. On standard ubuntu24.04:
1. Verify Python3 and create a fresh virtualenv via `python3 -m venv browser-venv`.
2. Install the frozen harness requirements through that environment's interpreter:
   `browser-venv/bin/python -m pip install --require-virtualenv -r browser-runtime-validation/requirements.txt`.
   Exact pins:Playwright1.64.1,Pillow12.1.0,pyee13.0.0,greenlet3.3.1,typing_extensions4.15.0.
3. Use this same interpreter for `run_bound_lane.py` and this adapter, so subprocess
   imports use the verified environment. Do not install/use an arbitrary browser.
4. Require the runner's existing official `/opt/google/chrome/chrome`,sandbox helper
   and `/etc/apparmor.d/chrome`; the frozen preflight hashes them, checks reviewed
   Chrome155.0.8059/156.0.8078 branches and Playwright bundled metadata, then launches
   with `chromium_sandbox=True`. Missing/incompatible setup fails, no sandbox disable.

Workflow installation steps must be explicit in the actual workflow and reviewed;
writing this README does not execute or claim them. No browser downgrade, security
setting change, paid resource or user-private data is needed.

## Sequence and output

Fresh staging only; uncertain previous evidence is never overwritten. Copy only
manifested harness files to an isolated test directory, prepare exact runtime
binding, run mandatory browser preflight, actual290-row matrix, independent result
verifier and evidence budget check. Source manifest checked before/after. Every
actual candidate row must load the same independently mapped core WASM hash.
One290-row invocation proves one real shipping-default path, not two flavors.
MVP gap is explicit unless the real default genuinely selected MVP.

Writes `evidence/browser-acceptance.json` with keys required by run_bound_lane.py:
passed/skipped,engineSHA256,selectedWasmSHA256,realLoaderPaths,rows,
shippingSelectionExecuted,mvpSelectionStatus. Also retains verifier and exact
matrix/preflight/binding hashes, complete synthetic screenshots/logs/JSON under
`evidence/browser/`. A failure emits browser-failure.json, preserves completed
bounded evidence and never emits an acceptance receipt.

Full command logs capped16MiB, aggregate browser evidence128MiB, matrix original
80MiB PNG/16MiB JSON limits remain; process group is stopped on timeout/budget.
The matrix has its own30minute deadline; wrapper allows35minutes for subprocess
startup/cleanup but cannot relax the matrix deadline. No native, device, audio,
memory or user-game crash-resolution claim follows from this desktop evidence.

## Current three-mode App policy overlay
Automatic production rows forward preferredRenderer=webgl for both arms. Baseline is exact delivered 1.5.5 runtime under CURRENT controlled App policy, NOT its historical Automatic behavior. Explicit wgpu-webgl, WebGL, Canvas and all pixel/input/MSAA/fallback/noncenter oracles remain unchanged. Enhanced omission is exact frozen App source + executed JS forwarding control only, not a healthy rendering claim. Old native Automatic context-loss negatives remain valid independently. Earlier browser run40796744945 does not certify this new policy. New browser execution pending.

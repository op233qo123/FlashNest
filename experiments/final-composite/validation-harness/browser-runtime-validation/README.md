# Final composite browser validation adapter

Prepared and locally contract-tested only. No final browser cases have run yet.
The old 160-row smoke evidence remains unchanged and is not final-runtime proof.

## Scope

- 290 rows on the unmodified shipping loader's actual selected WASM:160 original
  replay,50 production-quality/fallback,80 non-center alignment pairwise controls.
- 58 baseline configurations, each followed by candidate100/75/50/25%.
- 870 same-player initial/resize/restore phases and screenshots,4,350 trusted mouse
  clicks /8,700 DOM down+up events. Original and fallback require exact same-config
  baseline pixels; low tiers use the previously reviewed four-CSS-pixel vector
  bounds oracle. All candidate SWF pointer traces match corresponding baseline.
- Direct WebGL/Canvas fallback, actual GL buffers, and actual custom renderbuffer
  allocation samples observed transparently. `gl.SAMPLES` is not used. Auto WebGPU
  observes the actual returned current texture dimensions when selected.
- Quality null means omitted. The existing mobile `window.orientation` branch is
  recorded; Rust High alone is not taken as the effective launch quality. Explicit
  WebGL High/Medium controls require actual WebGL2 custom allocator samples>1;
  unavailable MSAA means an incomplete control and a failed run, not a false pass.
- Whole candidate and baseline runtime inventories verified before and after;
  actual fetched core WASM response bytes hash-match their respective inventory.
- Browser sandbox remains enabled. Only local synthetic fixtures/runtimes can load.
  Existing reviewed Chrome155.0.8059/156.0.8078 preflight,Playwright1.64.1 pinned.
-30minute matrix bound;128MiB total evidence /80MiB PNG /16MiB JSON caps. Caps fail
  incomplete, not silently trim cases. Diagnostics-only log prefix capped separately.

## Corrected browser baseline identity

Use the **actual delivered1.5.5/build18 audio-recovery candidate**, verified directly
from IPA SHA256 `b67e084a74537fd95c2e90a560210e73858071da860d7e62f637e55b974e7c42`.
The primary12-file receipt is `provenance/delivered-155-runtime.json`, SHA256
`4f6c0ce66c2287ecaf64246e92b9b72b4e5d354fdaafdbe2b4c48243eaf5d3b4`.
Its WASM files are4b85d6e32912d24cca47.wasm and90aa6311b211f13e3cb5.wasm.
Use the complete candidate runtime including all source maps/licenses, not the
partial old smoke payload directory even though that payload's executable bytes match.

Correction record: an earlier version of this adapter incorrectly selected the
historical1bab/8135 fatal-audio baseline by assuming a run/artifact had only one arm.
Root inspection of the delivered IPA disproved that assumption. Original engine
run40614335019/artifact12783974867 contains distinct baseline and recovery-candidate
arms. Browser visual/runtime comparison now pins the delivered recovery candidate.
The1bab/8135 historical control remains valid solely for the separate audio
failure/recovery differential; it must not replace the delivered browser baseline.
Receipt and runtime substitution regression checks reject that mistake.
No actual browser run used the incorrect draft binding.

## Integration interface

After the integrator validates the official final engine artifact run/commit/archive:

1. `scripts/prepare_contract.py --candidate-artifact ENGINE --baseline BASELINE_RUNTIME
   --baseline-identity provenance/delivered-155-runtime.json --expected-provenance-sha256 REVIEWED_SHA
   --expected-baseline-identity-sha256 REVIEWED_SHA --out runtime-binding.json`
2. Run `scripts/browser_preflight.py` and require its success; it is setup only.
3. `scripts/browser_matrix.py --candidate ENGINE/runtime --baseline BASELINE_RUNTIME
   --contract runtime-binding.json`
4. `scripts/verify_results.py evidence/result.json runtime-binding.json`
5. Run the evidence budget check before upload; include binding, runtime receipt,
   preflight and complete synthetic evidence. The workflow itself supplies reviewed
   expected provenance/identity hashes, never computes them from an untrusted artifact
   and then treats that calculation as independent authority.

No force-MVP entry point exists in the pinned shipping loader. This adapter does
not spoof feature probes or rewrite import tables. Actual loaded WASM hash is
reported; `mvpExecution=not-established`. The template's `regular` row list is used
only to generate one290-row configuration set and output rows say `shipping-default`.
A supported separate real-engine feature-disable route would require its own reviewed
binding/selection proof, not a fabricated second path result. No iOS/touch, physical
GPU, memory, audible audio or crash-resolution claims follow from desktop results.

## Authored checks

`PYTHONDONTWRITEBYTECODE=1 python scripts/test_contracts.py -v` checks matrix identity,
complete runtime bindings, null-quality semantics, MSAA evidence rejection, fallback,
physical mappings, stale status, pointer mutations and noncenter clipped visual oracle.
JavaScript observer tests run separately in Node and are mocked, not GPU evidence.

## Current three-mode App policy overlay
Automatic production rows forward preferredRenderer=webgl for both arms. Baseline is exact delivered 1.5.5 runtime under CURRENT controlled App policy, NOT its historical Automatic behavior. Explicit wgpu-webgl, WebGL, Canvas and all pixel/input/MSAA/fallback/noncenter oracles remain unchanged. Enhanced omission is exact frozen App source + executed JS forwarding control only, not a healthy rendering claim. Old native Automatic context-loss negatives remain valid independently. Earlier browser run40796744945 does not certify this new policy. New browser execution pending.

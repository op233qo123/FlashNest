# Locked-build WebAudio browser retry

This is a manual **browser-only experiment**, not a runtime rebuild or promotion.
It reuses the exact already-built audio lifecycle candidate and existing guard
baseline from run `40540513351`, source
`d3b402aec064f326a6b03c022253ccea559aa62f`:
https://github.com/op233qo123/FlashNest/actions/runs/40540513351

- Artifact: `12752805773` (`FlashNest-experimental-audio-lifecycle`)
- ZIP bytes: `21752547`
- ZIP SHA-256: `cd5c2f5eb9f907ffe165148d942e9fff58194511097a3fc75f0dafc4a5a91cb7`
- Upstream source: `89a7049965f3090e706265670df309a5128233ac`
- Runtime patches: unchanged queued-goto guard and the exact audio lifecycle
  patch recorded in `build-lock.json`; no render-density patch is included.

## Inherited evidence is not a previous browser pass

The locked run is terminal **failed**, specifically in its browser step. Its
build, dual-WASM production, 59 unchanged core JS tests, 2 ownership-model tests,
2 original frame-order tests and 31 adjacent checks succeeded. The 31 comprise
29 strict reference cases and preservation of 2 existing known failures.

Its old browser evidence contains 11 completed **baseline** rows out of 22 and
a candidate-normal-0 observer identity failure. All old failure records remain
under `audio-reused-build/audio-lifecycle-evidence/browser/`; they are never
rewritten, removed, or inherited as a passing browser gate. A corrected observer
runs the full existing 22-row gate again into a separate evidence directory.
The correction does not alter either runtime or its source/license files.

## Verification and execution

`verify_artifact.py` requires the exact ZIP bytes and live run/job/artifact API
identity, the completed failed run and browser step, and successful build/core
steps. It bounds and safely extracts the archive, verifies all **95 candidate
provenance-inventoried files**, both patches and modified sources, dual-WASM
inventories, raw original/model/upstream evidence, and corrected helper hashes.

The baseline includes only its 12 runtime files plus provenance, browser manifest
and identity metadata. Those included files are verified against the frozen
original provenance. The baseline's absent old build log/source correspondence
entries are **not** claimed to have been reverified.

The workflow uses standard `ubuntu-24.04`, Node 24.22.1, and the same upstream
npm lock for WebdriverIO 9.32.0 (`npm ci --ignore-scripts`). Source checkout is
only for these locked dependencies; there are no Cargo, wasm-bindgen, webpack,
patch-application or engine-build commands. Installed Chrome/ChromeDriver are
explicitly selected, with no alternate download. Existing browser caps remain:
22 rows, 8 normal cycles per arm plus three labeled fault modes, 10-minute
internal deadline, 12-minute browser CI step. The whole job is bounded to 40
minutes. Failed/partial evidence is retained, including prior failed evidence.

The final summary independently requires 22 unique complete rows, matching
runtime/helper hashes, and each row's evidence attachment hash. A partial retry
cannot pass. New observer commit and old runtime build commit are recorded
separately. No artifact from this workflow changes a production runtime pin.

## Local checks

```sh
python3 experiments/audio-lifecycle/browser-reuse/test_verifier.py \
  --verified-root /path/to/extracted-locked-build
```

Tests cover wrong API identity/status/step results, wrong ZIP/hash, traversal,
symlinks/special entries, duplicates/noncanonical names, archive count/root bounds,
partial extraction cleanup, missing/extra/changed inventory files and semantically
false inherited results. They do not execute an engine/browser.

Corrected browser results, if successful, concern observable handler teardown,
close-Promise settlement and explicitly labeled fault injection. They are not
proof of garbage collection, physical memory release, native WebKit crash/OOM
repair, actual speaker output, Adobe equivalence or arbitrary game behavior.
Source correspondence and license texts remain unchanged inside the reused
artifact; this experiment makes no legal-compliance certification.

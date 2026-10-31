# Synthetic JPEG3 WebGL comparison

This runner tests newly built baseline/candidate engines, not historical measurements. It does not publish game data or build an IPA.

## Inputs and prerequisites

- CI uses `scripts/prepare_browser.py` with exact same commit/run/source-pair differences and loader-derived selected WASM pins. It verifies compilation provenance before invoking this runner. The standalone `browser/prepare_contract.py` is only a manual byte-inventory helper, not the CI provenance gate.
- Explicit selected `.wasm` filename for each arm, source-set SHA256, and the new candidate patch. The runner rejects a different downloaded WASM or identical baseline/candidate selected hashes.
- Official Chrome, Playwright and Pillow (pinned in requirements.txt), an available default sandboxed WebGL context. Launch uses `channel='chrome', chromium_sandbox=True` and no security-reducing extra flags. Run a browser availability preflight before expensive builds; missing WebGL is a setup failure, not a decoder pixel failure.

## Synthetic inputs

`generate_fixtures.py` uses only mathematical RGB/alpha patterns and the committed neutral `NeutralSharedRoot.abc`. The ABC is hash-pinned and its original ActionScript remains in the lazy-Graphic fixture source. Cases: 64, 511, 512 and 1024 squared patterned alpha; 1024 squared opaque alpha. The whole bitmap maps to a 16×16 display rectangle, displayed twice through a shared bitmap-fill definition. The original controls show, hide/reveal, mask and hit-test the shapes.

The complete original-resolution RGBA texture-upload bytes are SHA256 compared, in addition to full 320×240 rendered screenshot equality. Thus downsampling cannot conceal decoder-byte differences. Nonblank, multicolor pattern and white/masked boundary assertions are independent of A/B equality. No raw image/game content is captured from private inputs.

## Scope and limits

- Five cases × two new browser contexts, five visual states each. Actual renderer and texture-upload counts must be observed; ready must have no target image upload and shown must upload it. Repeat/mask/hit must reuse the upload.
- Full-canvas pixel equality and full-source-resolution texture hash equality are required.
- Actual exported WebAssembly.Memory byteLength is observed after load and at each state. This measures retained linear memory capacity/high-water capacity, not live requested allocation, RSS, GPU memory, or iPhone behavior.
- `crypto.subtle.digest` can temporarily copy the texture bytes outside WASM and costs CPU. At most 32 complete uploads are hashed per page; excess hashes set overflow and fail the gate without suppressing the original GL call. Instrumented load/key-to-settled durations are descriptive, not pure decode timing or benchmark medians. Do not make speed-adoption decisions from them.
- Observation handlers do not call preventDefault or otherwise enable restoration on the app’s behalf. A controlled loss/restore is attempted only on the 1024 patterned case. A baseline-success/candidate-failure is a regression. If both cannot recover, visual/loading parity can pass but `contextRecoveryLimitation=true` and a separate classification explicitly records that restoration did not pass. Unexpected loss before the controlled step is a failure.
- Hide/reveal tests cache reuse. Explicit `cacheAsBitmap` reconstruction is **not run** and is recorded as such. Do not call this comprehensive cache lifecycle validation.
- No native WebKit, iOS memory, or IPA acceptance is implied.

## Run

Generate fixtures and validate sources:

```
python browser/generate_fixtures.py
python browser/test_static.py
node browser/test_page.cjs
```

CI must use the strict `scripts/prepare_browser.py` contract preparation. The following is a manual helper example only and does not satisfy the CI provenance gate:

```
python browser/prepare_contract.py --baseline baseline/runtime --candidate candidate/runtime --baseline-wasm BASELINE.wasm --candidate-wasm CANDIDATE.wasm --source-set-sha256 SOURCE_SHA --patch patches/image-memory.patch --fixtures fixtures --output contract.json
python browser/run.py --contract contract.json --baseline baseline/runtime --candidate candidate/runtime --fixtures fixtures --out webgl-evidence
```

Committed fixture bytes were generated with Pillow13.0.0 / JPEG codec6.2; CI consumes the committed bytes and checks their hashes. Regeneration under a different Pillow/codec is not assumed byte-identical. The pinned runtime Pillow12.1.0 is used only for screenshot checking.

The output directory must not exist. `result.json` is written on success and failure, alongside a bounded screenshot set. Existing evidence is never overwritten. Actual browser execution is pending CI; syntax/unit/static results are not browser results.

## Render-order correction

Run41160325754 exposed a measurement race: a shown trace occurred before the bitmap upload, while the later screenshot already contained the rendered pixels. The runner now waits, with the normal25-second timeout, for an actual target-size texture upload followed by a draw on the same WebGL context. It then captures the screenshot before awaiting the scalar/hash snapshot. Missing rendering still times out and independent nonblank/pixel gates remain unchanged. A late-upload unit case verifies that a rendered screenshot cannot be paired with an earlier observation. Previously downloaded evidence remains unchanged.

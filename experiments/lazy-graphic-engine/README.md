# Isolated candidate engine + focused WebGL experiment (default disabled)

Not an IPA, native regression or crash fix. The accepted baseline remains engine
40794075613, reconstructed from the exact original SHA-256-pinned archive's two
already-published mirror parts. Full provenance, source correspondence and runtime
checks are preserved. No credential, private game, saved data or private log input.

Candidate production source differs only in core/src/display_object/graphic.rs:
Graphic::from_swf_tag starts with Some(RefCell(None)) rather than eager renderer
registration. Existing render-time/shared/scaled cache code remains unchanged.
The accepted five-patch chain, dependency locks, toolchain, JPEG-XR, two WASM
flavors and wasm-opt requirements remain intact. CountingRenderer and local Rust
test hooks are NOT in this engine. Local tests are source/mechanism evidence, not
actual browser/native results. Independent source review enables neither dispatch
nor production acceptance; these are distinct flags and productionAccepted=false.

The manual 150-minute job retains the exact prior toolchain installation/build
commands (65-minute engine step) and adds a maximum15-minute focused Chromium
WebGL phase. There are only three tiny synthetic fixtures: eight unshown JPEG3
shapes then one display, the forward-reference edge, and shared-redraw/mask/hit-test
boundaries. Baseline/candidate each load in independent pages. Full runtime byte
maps, sourcemap+compiled-loader WASM flavor identity and actual fetched WASM hashes
are required. WebGL calls and PNG pixels are compared; not CPU decode counts,
physical GPU memory or iOS certification. No full198 run or IPA is requested.

NativeAcceptance, productionAccepted and originalCrashResolved remain false.
Pipeline/source/baseline dispatch defaults are false pending explicit authorization.
A new candidate runtime must be built and its actual receipt checked before the
browser contract can be enabled within that already-authorized job. No default
path invents or substitutes missing candidate WASM.

Engine artifact retention7days includes full before/after source maps, original
patches plus candidate patch, provenance, runtime source maps and complete license
notices. Focused browser evidence is separate and retained7days. Partial/missing
results cannot be reported as full acceptance.

## Focused-only recovery after engine40998892881 succeeded

The new 25-minute focused workflow reuses artifact12953027984, exact archive
SHA2562cb4022b1859156f2e28dcb5d499ebf01cbf13b386acb8467d34c147ed22d28d,
original run40998892881/head6d3e4322293972a28ab2cdf129ee6398f40f0f37. It does
not rebuild the engine or relabel that receipt as the retry run. The first browser
launch failed before any fixture because the downloaded headless shell had no
usable sandbox on that runner. Recovery uses the already successful official
Chrome channel and exact old preflight, with chromium_sandbox=True; no security
policy changes, sandbox disabling, browser downgrade or arbitrary substitute.
All six fixture pages and assertions remain unchanged.

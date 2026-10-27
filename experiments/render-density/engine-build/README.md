# Isolated render-density engine experiment

This manual recipe builds an **experimental, unpromoted** derivative of official
Ruffle source `89a7049965f3090e706265670df309a5128233ac`. It keeps the exact
queued-goto guard (`de0acabdf957fccbc11966b67defd0a7f577cdc5a147db949e0a4f0e56c6331f`)
and adds only the reviewed frontend/WebGL and WGPU density patches. It never
replaces the application runtime, production pins or source assets.

`workflow-draft.yml` is intended for separate publication as
`.github/workflows/experiment-render-density.yml`; it is not an active workflow
at this location. No dispatch is performed by these files.

## Required gates

1. Verify exact upstream checkout, stage the existing original SWF37 integration
   target and apply the unchanged queued-goto guard. Compile before case timeouts.
2. Guard-only baseline: the existing two original fixtures must match the prior
   repair/control expectations, and all 31 selected upstream checks must pass.
   Those are **29 strict reference cases plus preservation of two existing known
   failures**, not 31 Adobe-equivalence claims. No golden is regenerated.
3. Apply both hash-pinned density patches. Reconstruct their combined output from
   pinned Git source and verify all modified/new source bytes, exact tracked diff,
   and permitted untracked test files. Repeat the same original and upstream gates.
4. Build two WASM variants with the existing explicit toolchain and upstream
   locked Cargo/npm build paths. Core Mocha must report exactly **63 passing
   tests: the original 59 plus 4 new density config tests**, with no failures,
   skips or exclusive tests. Added config-test titles are checked separately.
5. Run the full independent browser matrices with the **unchanged existing
   vendored guard runtime** as control and the new density runtime as candidate.
   Each backend has a 60-minute internal budget and 65-minute CI bound for final
   failure capture; no partial matrix is a pass.
   Both backends are attempted after a successful build, even if WebGL fails.
   Installed runner Chrome and ChromeDriver paths are passed explicitly to avoid
   WebdriverIO downloading a different browser/driver.

The Rust expectation environment is `FRAME_ORDER_ENGINE_PHASE=patched` in both
phases because both contain the existing guard. Evidence directories `baseline/`
and `patched/` distinguish guard-only from guard-plus-density, respectively.
The old 31-case runner is reused unchanged, including process-group timeout
cleanup and complete-suite checks. The browser baseline is **not rebuilt**.

## Pins and outputs

- Standard `ubuntu-24.04`; job bound 240 minutes, no paid/larger runner.
- Rust 1.99.1 + `rust-src` + `wasm32-unknown-unknown`.
- Checksum-pinned Temurin JRE 21.0.13+9, Binaryen 129.
- Node 24.22.1, wasm-bindgen CLI 0.2.127, Ubuntu clang 18.
- Existing upstream npm lock, including WebdriverIO 9.32.0.
- Renderer backends: `webgl` and `wgpu-webgl`; actual renderer identity and results
  are the browser harness's responsibility, not inferred from configuration.

`build-inputs.json` pins the exact three patches and the original guard artifact.
The candidate version seal uses a distinct
`flashnest-render-density-experimental` channel and patch-set hash. Source date
metadata is deterministic; actual build time, tools and runner image are recorded
separately. This is an auditable recipe, not a claim of independently reproduced
byte-identical outputs.

Artifacts retain raw logs, exact original and upstream evidence, full density
fixtures/harness/recipes, all three patches, every modified source file, dependency
locks, tool versions, original license texts and JavaScript NOTICE materials.
`runtime.browser-manifest.json` inventories every `.js` and `.wasm` for the
browser harness; the full candidate inventory also retains source maps/licenses.
The final artifact also retains the unchanged guard control and its provenance.
No third-party game assets, private saves, or original-game execution are involved.

A passing matrix would establish only its measured browsers/backends/scenarios,
not native iOS compatibility, lower measured RAM, unchanged performance, an
intermittent WebKit crash fix, Adobe equivalence or every game working. Native
candidate and application gates remain separate; no production promotion is
implicit. Source correspondence is not a complete upstream/dependency source
archive or a legal-compliance certification.

## Primary build contracts

- [Pinned upstream web build documentation](https://github.com/ruffle-rs/ruffle/blob/89a7049965f3090e706265670df309a5128233ac/web/README.md)
- [Locked Cargo, dual-WASM and MVP flags](https://github.com/ruffle-rs/ruffle/blob/89a7049965f3090e706265670df309a5128233ac/web/packages/core/tools/build_wasm.ts)
- [Version seal](https://github.com/ruffle-rs/ruffle/blob/89a7049965f3090e706265670df309a5128233ac/web/packages/core/tools/set_version.ts)
- [Upstream release toolchain recipe](https://github.com/ruffle-rs/ruffle/blob/89a7049965f3090e706265670df309a5128233ac/.github/workflows/release.yml)
- [Original queued-goto candidate run](https://github.com/op233qo123/FlashNest/actions/runs/40491098384)

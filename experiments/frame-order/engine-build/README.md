# Isolated queued-goto engine experiment

This directory supplies a manual, test-first recipe for **modified** Ruffle
0.7.1 source at `89a7049965f3090e706265670df309a5128233ac`. It does not
replace any application runtime, package an IPA, or include third-party game
assets. `workflow-draft.yml` is a publication draft, not an active workflow in
this location. Its optional `build_web` input defaults to **false**.

## Gates and evidence

1. Check out the exact official source and stage the original SWF37 integration
   target from `../engine-patch/`; verify Cargo discovers that target.
2. Compile both headless test targets before starting per-case timeouts.
3. Run the two original fixtures against the unmodified engine and compare with
   their captured baseline traces. Run all **29 strict upstream golden cases**
   and **2 existing known-failure preservation cases** in `adjacent-tests.json`.
4. Apply only the supplied `queued-goto-guard.patch`, rebuild, then repeat the
   original fixtures and the same upstream cases. The patched original nested
   fixture is compared with an **experimental repair target**, not an Adobe
   reference run. The original control must remain unchanged.
5. Only when explicitly requested and all earlier gates pass, build a separate
   dual-WASM selfhosted candidate and retain its source correspondence.

The official runner uses checked-in SWFs (`--compile-mode=use-precompiled`).
Every selected upstream `test.toml`, `test.swf`, and reference output must match
its pinned Git bytes. A selected known failure must retain both its annotation
and `output.ruffle.txt`: its pass means **preservation of the existing known
failure**, not Adobe equivalence. Zero selected tests, skips, unexpected test
configuration, mismatches, and timeouts fail the gate. Each per-case timeout
kills the Cargo process group. Progressive summaries remain incomplete and
`allPassed: false` until all 31 cases have finished successfully.

The workflow retains raw compile/test logs, exact original traces, per-case
input hashes, applied source diff, runner image, run ID, experiment commit, and
recipe files even when a gate fails. No golden is regenerated or blessed.

## Pinned recipe and optional web build

- Standard `ubuntu-24.04` runner; Rust **1.99.1**.
- Checksum-pinned Temurin JRE **21.0.13+9** runs the upstream checked-in ASC jar
  needed by Ruffle's build. This is not a Flash Player executable.
- Optional web tooling: Node **24.22.1**, wasm-bindgen CLI **0.2.127** (matching
  Cargo.lock), checksum-pinned Binaryen **129**, Ubuntu clang **18**.
- Cargo commands use `--locked`; `npm ci` uses the upstream npm lock. The
  upstream `build_wasm.ts` also passes `--locked` to its Cargo invocation.
- The optional build uses upstream core/selfhosted workspace scripts,
  `BUILD_WASM_MVP=true`, `CARGO_FEATURES=jpegxr`, and version sealing.

This is a pinned, auditable **recipe**, not yet a claim that independent clean
builds produce byte-identical artifacts. The runner image and apt package
versions are recorded rather than assumed immutable. The explicit Rust/Node
pins are experimental build tools, not a claim to reproduce the tool versions
used for the original official release.

`candidate_provenance.py` rejects any tracked upstream source changes beyond
exactly applying the supplied one-file patch. It verifies this before and after
the build. A candidate has an explicitly experimental version name/channel,
not an unmodified official-binary identity. Its compact correspondence bundle
contains the exact patch and modified source, dependency locks, commands,
upstream commit URL, original/modified hashes, and upstream `LICENSE.md`,
`LICENSE_MIT`, and `LICENSE_APACHE`. Recipe files are copied **before** the final
file-hash inventory. Production runtime notices and manifests stay untouched.

Successful headless tests are not native WKWebView validation, proof of exact
Adobe behavior for the original fixture, or proof of any particular game's
root cause. A separate native candidate comparison and explicit promotion are
required before any application runtime change. Broader regression and license
review remain necessary before redistribution; the compact bundle is not
represented as a complete upstream source archive.

## Primary sources

All Ruffle references below are fixed to the source commit being tested:

- [Official web build documentation](https://github.com/ruffle-rs/ruffle/blob/89a7049965f3090e706265670df309a5128233ac/web/README.md)
- [WASM build script, flags, and locked Cargo command](https://github.com/ruffle-rs/ruffle/blob/89a7049965f3090e706265670df309a5128233ac/web/packages/core/tools/build_wasm.ts)
- [Version sealing](https://github.com/ruffle-rs/ruffle/blob/89a7049965f3090e706265670df309a5128233ac/web/packages/core/tools/set_version.ts)
- [Official release build configuration](https://github.com/ruffle-rs/ruffle/blob/89a7049965f3090e706265670df309a5128233ac/.github/workflows/release.yml)
- [Regression runner](https://github.com/ruffle-rs/ruffle/blob/89a7049965f3090e706265670df309a5128233ac/tests/tests/regression_tests.rs)
- [Trace and known-failure checks](https://github.com/ruffle-rs/ruffle/blob/89a7049965f3090e706265670df309a5128233ac/tests/framework/src/runner/trace.rs)
- [Upstream ASC Java invocation](https://github.com/ruffle-rs/ruffle/blob/89a7049965f3090e706265670df309a5128233ac/tools/asc/src/lib.rs)
- [Upstream license and dependency notices](https://github.com/ruffle-rs/ruffle/blob/89a7049965f3090e706265670df309a5128233ac/LICENSE.md)
- [Rust 1.99.1](https://github.com/rust-lang/rust/releases/tag/1.99.1),
  [Node 24.22.1](https://github.com/nodejs/node/releases/tag/v24.22.1),
  [Temurin 21.0.13+9](https://github.com/adoptium/temurin21-binaries/releases/tag/jdk-21.0.13%2B9),
  [Binaryen 129](https://github.com/WebAssembly/binaryen/releases/tag/version_129)

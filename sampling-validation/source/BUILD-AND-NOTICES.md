# Modified combined audio+density smoke runtime: source and redistribution notes

This is a modified FlashNest experimental Ruffle build, not an official upstream release. Original project code/fixtures retain the included FlashNest license. Ruffle retains MIT OR Apache-2.0; all dependency licenses remain their own. Preserve this document, licenses/, provenance/, ordered patches and source correspondence when redistributing these bytes.

## Exact source and changes
Upstream: https://github.com/ruffle-rs/ruffle/tree/89a7049965f3090e706265670df309a5128233ac
Source archive: https://github.com/ruffle-rs/ruffle/archive/89a7049965f3090e706265670df309a5128233ac.tar.gz
Expected archive SHA-256: `246d02cc1211e4f2cfae8b34e672f49679738eaffd5a72999f4828d925668d9a` (the original downloaded archive digest; reject a mismatching download, do not silently refresh).
Apply with `git apply` from the extracted source root, in this exact order:
1. `provenance/queued-goto-guard.patch`
2. `provenance/audio-lifecycle.patch`
3. `provenance/audio-recovery.patch`
4. `provenance/frontend-webgl-density.patch`
5. `provenance/wgpu-density.patch`

`provenance/original.json` pins each patch hash, upstream archive and tools. `source/patched/` supplies every changed source file plus exact Cargo/npm lockfiles; `provenance/patched-source-hashes.json` checks correspondence. The additional quality.rs reference explains low-quality support. Source maps are omitted from runtime distribution, not substituted for corresponding source.

## Build recipe
The verbatim actual local recipe is `original-build-smoke.sh`; its workspace-specific PATH/CARGO_HOME/CARGO_TARGET_DIR describe the original environment, not portable download locations. In a new authorized build workspace, provide verified Rust 1.99.1 with wasm32-unknown-unknown std, wasm-bindgen-cli 0.2.127, Node 24.22.1, npm and locked dependencies. `cargo fetch --locked` and `npm ci --ignore-scripts` (from web/) obtain dependencies from the included exact locks; they require network authorization. Do not change lockfiles or add JPEG-XR features. Then use the original recipe's exact RUSTFLAGS, cargo profile/package/target/default features, wasm-bindgen parameters and three npm build steps, substituting only local workspace paths. `CFG_RELEASE_CHANNEL=flashnest-low-sampling-local` is intentional.

This smoke build has **no MVP variant, no JPEG-XR feature, no wasm-opt**. Its WASM/JS hashes identify existing tested inputs, not a promise of independent byte-reproducibility. The browser workflow does not build source. Release-equivalent build/provenance and audio/native gates remain outstanding.

The unchanged baseline's exact source is separately identified by `provenance/baseline-runtime.lock.json` and public audio experiment https://github.com/op233qo123/FlashNest/tree/5d2cdcc6757d65194bd55c4a0395b76b0176d224/experiments/audio-recovery . Baseline is not the density derivative; do not apply five-patch instructions to label baseline bytes.

## License inventory retained without pruning
- Both runtimes retain verbatim LICENSE_MIT and LICENSE_APACHE.
- `licenses/Ruffle-THIRD-PARTY-LICENSES.md` is the entire unmodified pinned upstream LICENSE.md, including upstream component attributions and complete license texts; `Ruffle-web-LICENSE.md` is also retained.
- JS dependency texts and Fluent NOTICE files are verbatim from the already-verified app license correspondence: tsx-dom, Fluent bundle/langneg, wasm-feature-detect and webpack. Exact versions/integrity are in the npm lock. No runtime dependency was introduced by these patches and dependency sources were not modified.
- Upstream inventory identifies MPL and other permissive/public-domain licenses. Its sole textual mention of LGPL is in MPL's definition of Secondary License, **not evidence of a linked LGPL component**. No LGPL component is identified by the retained upstream inventory. This is a recorded inventory check, not a blanket legal certification or permission to discard a newly discovered obligation. If a dependency audit identifies LGPL-covered linked code, hold publication until its notices/corresponding-source/relink obligations are addressed; do not infer compliance from root MIT alone.
- For dependency corresponding source, exact Cargo/npm locks identify registries, git revisions and versions; use those plus the upstream inventory links. Preserved patches and changed source accompany this distribution even though browser source maps do not.

## Backend contract (do not count fallback as low-resolution success)
The matrix explicitly selects `quality: low`. `StageQuality::Low` yields one sample. Direct WebGL therefore exercises its supported non-custom-MSAA density path. It rejects custom WebGL2 MSAA (`msaa_sample_count > 1`) and invalid/backing-limit conditions. Canvas inherits the renderer trait's false result. On any refusal the frontend restores original native-DPR canvas/viewport and records applied scale 1, even though requested scale is low.

Every candidate low row strictly requires requested == applied tier, canvas == drawing buffer == reduced dimensions, unchanged logical native-DPR viewport and actual requested renderer. Original fallback at a low tier FAILS this matrix; it cannot be labeled supported-low success. WGPU-WebGL is independently selected and checked. Canvas/high-quality-custom-MSAA fallback behavior is **not runtime-validated by this low-quality smoke matrix** and remains a separate gate; no scope expansion or omission of any of the four promised tiers occurs.


## Browser validation setup revision (not an engine rebuild)

The setup-only failure in run 40707702077 produced zero matrix cases. Its job setup image label (20261012.334.1) and artifact ImageVersion (20261023.334.3) differ; preserve both observations.

Use runner-installed official Chrome channel on standard Ubuntu 24.04, with explicit Chromium sandbox enabled. No browser download, AppArmor/sysctl changes, sandbox relaxation or automatic alternative browser. Playwright is pinned to 1.64.1: official 1.64 release notes list testing against Chrome 155, and the tagged Python package accepts the unchanged pyee/greenlet pins. Preflight fails closed if Chrome major is not 155. The rolling runner browser is identity-recorded, not claimed binary-pinned.

A bounded preflight records binary/profile hashes, installed versions, sandbox launch and a synthetic 16x16 WebGL buffer before either matrix. Its output is setup evidence only (zero matrix cases). No preflight success may substitute for any of the 160 geometry rows or native gates. Existing source/runtime hashes, original fixtures, four density tiers, trusted input and initial/resize/restore assertions are unchanged.

Primary sources:
- https://playwright.dev/python/docs/release-notes#version-164
- https://pypi.org/project/playwright/1.64.1/
- https://raw.githubusercontent.com/microsoft/playwright-python/v1.64.1/pyproject.toml
- https://playwright.dev/python/docs/browsers
- https://chromium.googlesource.com/chromium/src/+/main/docs/security/apparmor-userns-restrictions.md
- https://github.com/actions/runner-images/blob/ubuntu24/20261012.334/images/ubuntu/Ubuntu2404-Readme.md
- https://github.com/actions/runner-images/blob/ubuntu24/20261023.334/images/ubuntu/Ubuntu2404-Readme.md

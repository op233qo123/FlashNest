# Vendored experimental Ruffle candidates

`ruffle-audio-recovery-40614335019.zip` is the exact original
[build 40614335019 artifact 12783974867](https://github.com/op233qo123/FlashNest/actions/runs/40614335019/artifacts/12783974867),
not a repacked or newly rebuilt runtime.

- Bytes: `22076102`
- SHA-256: `3befcb048669c074a017e2bfb6d3ccc283028ef90d7960695bbf0964a2634e9a`
- [Base source](https://github.com/ruffle-rs/ruffle/tree/89a7049965f3090e706265670df309a5128233ac)
- [Build source/recipe](https://github.com/op233qo123/FlashNest/tree/5d2cdcc6757d65194bd55c4a0395b76b0176d224/experiments/audio-recovery)

Identity: **FlashNest experimental Ruffle 0.7.1 audio-recovery 3eea9c1603f4**,
not an official stable fix. The artifact contains a baseline, candidate, original
test fixtures, evidence and source correspondence. Only the **twelve files** under
`audio-recovery-candidate/runtime/` are installed into App/Web. Never copy the
whole ZIP, baseline, evidence, source tree, test host or injection scripts into
the app. No user game, real save, screenshot or video belongs in this archive.

The source index and three reviewable patches are in
`ruffle-audio-recovery-source/`. The immutable ZIP preserves all five modified
source records, Cargo/npm locks, upstream licenses, tool versions and build
recipe. Fixed upstream links identify the original sources. This compact
correspondence is not a complete upstream/dependency source archive; no
independent clean-rebuild byte-identity claim is made.

Keep `App/Resources/Web/licenses/`, both third-party notices and
`Ruffle-MODIFICATIONS.md` with any runtime redistribution. The latter records
measured tests and remaining native/application validation limits. Original
build-time `experimental-unpromoted` metadata is not rewritten during integration.
This directory is not a legal-compliance certification.

The earlier `ruffle-frame-order-40491098384.zip` and its correspondence remain
historical, separately identified source material. The installer does not fall
back to them and they are not copied into the application bundle.

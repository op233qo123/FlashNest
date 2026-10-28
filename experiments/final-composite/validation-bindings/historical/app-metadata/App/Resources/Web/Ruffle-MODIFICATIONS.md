# Ruffle modification and source correspondence

## Identity

This build uses **FlashNest experimental Ruffle 0.7.1 frame-order guard
de0acabdf957**, channel `flashnest-frame-order-experimental`. It is modified
software, not an unmodified official Ruffle binary or an upstream stable fix.
The base version number 0.7.1 alone does not identify this candidate.

- Upstream commit: `89a7049965f3090e706265670df309a5128233ac`
- Experiment/build source commit: `f60ff6a99941937056eee5ad94ed4b4af9c72c99`
- Original candidate archive: `vendor/ruffle-frame-order-40491098384.zip`
- Archive SHA-256: `57d7eaed19edd006e2a33a9bfa816f22da8b1003becf3719dfca0c97cb38c4af`
- Provenance SHA-256: `73829617008e26ffe48bfc29e689c0a719641f6c9e93214b29f8ee3c6bfd22d5`
- Patch SHA-256: `de0acabdf957fccbc11966b67defd0a7f577cdc5a147db949e0a4f0e56c6331f`

The archive is retained unchanged from build run 40491098384. It is not a new
rebuild, and no independent clean-build byte-identity claim is made.

## Modification and source

The patch adds a reentrancy guard in
`core/src/display_object/movie_clip.rs`, before consuming a queued goto while
the same clip's frame script is executing. Original source SHA-256:
`fc229d96ab6fced20391cf810d9d89a2118803cb7f5ce48ddf6967e52e35700a`.
Modified source SHA-256:
`af780dae48b842e0756b8cd23f50a539737d0bcbbbdca970feb90f27725e96b0`.

- Base source: https://github.com/ruffle-rs/ruffle/tree/89a7049965f3090e706265670df309a5128233ac
- Original source file: https://github.com/ruffle-rs/ruffle/blob/89a7049965f3090e706265670df309a5128233ac/core/src/display_object/movie_clip.rs
- Patch and original tests: https://github.com/op233qo123/FlashNest/tree/f60ff6a99941937056eee5ad94ed4b4af9c72c99/experiments/frame-order/engine-patch
- Build recipe: https://github.com/op233qo123/FlashNest/tree/f60ff6a99941937056eee5ad94ed4b4af9c72c99/experiments/frame-order/engine-build

Within the retained ZIP, `frame-order-engine-candidate/source-correspondence/`
contains the exact patch, modified source file, Cargo/npm locks, upstream license
texts and build recipe. `frame-order-engine-candidate/provenance.json` records
source, patch, tool and file hashes. The adjacent
`vendor/ruffle-frame-order-source/source-correspondence.manifest.json` indexes
these archived materials; its standalone patch is byte-identical to the ZIP.
The source correspondence is compact, not a complete upstream/dependency source
archive. The fixed source links and lockfiles identify the remaining sources.

## Measured scope, not a compatibility guarantee

Build run https://github.com/op233qo123/FlashNest/actions/runs/40491098384 passed
59 JavaScript tests. Its unmodified and patched headless phases each passed two
original SWF37 fixtures and 31 selected upstream checks: 29 strict reference
checks and preservation of two existing known failures. The latter are not
claims of Adobe-equivalent output. The patched original fixture matches an
explicit experimental repair target; it has not been run in Adobe Flash.

One native candidate run,
https://github.com/op233qo123/FlashNest/actions/runs/40494446464, passed two
frame-order checks, two save/lifecycle checks and one UI lifecycle check on an
iPhone 16 iOS 18.2 simulator. A single successful run does not prove that
intermittent WebKit startup/process crashes are fixed. These results are not
proof of full Flash compatibility, every game working, or a particular game's
root cause. Application release validation remains separate.

## Attribution

Original Ruffle MIT/Apache texts, the full upstream third-party inventory,
JavaScript license texts, Fluent NOTICE attributions and source-map comments
are retained. See `THIRD_PARTY_NOTICES.md` and `licenses.manifest.json` in this
bundle. Third-party licenses are not replaced by FlashNest's project license.

Historical source documents and build-time `experimental-unpromoted` metadata
inside the original ZIP are preserved unchanged. They describe the build at
that time; they are not a claim that this modified binary is the official
unmodified runtime. This notice is not a legal-compliance certification.

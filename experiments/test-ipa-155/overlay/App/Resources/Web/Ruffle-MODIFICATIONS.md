# Ruffle modification and source correspondence

## Exact identity

**FlashNest experimental Ruffle 0.7.1 audio-recovery 3eea9c1603f4**, channel
`flashnest-audio-recovery-experimental`, is modified software, not an unmodified
official release or an upstream stable fix. Base version 0.7.1 alone does not
identify this candidate.

- Upstream commit: `89a7049965f3090e706265670df309a5128233ac`
- Build source commit: `5d2cdcc6757d65194bd55c4a0395b76b0176d224`
- Original archive: `vendor/ruffle-audio-recovery-40614335019.zip`
- Archive bytes: `22076102`
- Archive SHA-256: `3befcb048669c074a017e2bfb6d3ccc283028ef90d7960695bbf0964a2634e9a`
- Provenance SHA-256: `01838aff92eb05cde33babb8153c82de2d9c2889a2795c2f2f2c72a65e3eed59`
- Ordered patch-set SHA-256: `3eea9c1603f46966d4de835325484d5433d8999998e6fb9baadf98c56b9fab2e`

The archive is unchanged from [build 40614335019](https://github.com/op233qo123/FlashNest/actions/runs/40614335019).
It is not a repacked archive or a new rebuild. Independent clean-build byte
identity is not verified. Historical `experimental-unpromoted` metadata remains
unchanged; it describes the artifact at build time, not an upstream endorsement.

## Three ordered patches

1. Queued-goto reentrancy guard:
   `de0acabdf957fccbc11966b67defd0a7f577cdc5a147db949e0a4f0e56c6331f`.
2. Audio-context ownership/lifecycle cleanup:
   `89dfadc1b9d113adb01f08582237559c71a5c0e04fe712cb0e31d80f077b07b9`.
3. Source-bound WebAudio resume status/rejection handling:
   `631027394ab35c7ff5b8bd1da1402a649c38e913dd2b788d1a9ef514fc6aee60`.

The five modified/added upstream paths are:

- `core/src/display_object/movie_clip.rs`
- `web/src/audio.rs`
- `web/packages/core/src/ruffle-imports.ts`
- `web/packages/core/src/internal/player/inner.tsx`
- `web/packages/core/src/internal/audio-operation.ts` (new)

Every original/modified digest is preserved in the archive provenance and the
bundled runtime identity. A null original digest identifies the added file;
it does not claim that the file existed upstream. The patches preserve original
copyrights. No density change, renderer-default switch, new runtime dependency,
or dependency-source modification is part of this derivative.

- [Fixed upstream source](https://github.com/ruffle-rs/ruffle/tree/89a7049965f3090e706265670df309a5128233ac)
- [Queued-goto patch](https://github.com/op233qo123/FlashNest/tree/5d2cdcc6757d65194bd55c4a0395b76b0176d224/experiments/frame-order/engine-patch)
- [Audio lifecycle patch](https://github.com/op233qo123/FlashNest/tree/5d2cdcc6757d65194bd55c4a0395b76b0176d224/experiments/audio-lifecycle/engine-patch)
- [Audio recovery patch and build recipe](https://github.com/op233qo123/FlashNest/tree/5d2cdcc6757d65194bd55c4a0395b76b0176d224/experiments/audio-recovery)

Within the original ZIP, `audio-recovery-candidate/provenance.json` records all
145 candidate file hashes/sizes, source records, ordered patch digests, tools and
build identity. `audio-recovery-candidate/source-correspondence/` contains the
patches, modified files, dependency locks, recipe and upstream licenses. The
adjacent `vendor/ruffle-audio-recovery-source/source-correspondence.manifest.json`
indexes that original archive; its three standalone patches are byte-identical.
This is compact correspondence, not a complete upstream/dependency source archive.
The installer copies only the twelve candidate runtime assets into the app.

## Measured scope and limitations

Build 40614335019 compiled both WASM variants and passed the original 59 core
JavaScript checks (zero pending). This is not proof of every game working.
[Native recovery run 40621779877](https://github.com/op233qo123/FlashNest/actions/runs/40621779877)
passed three separate arms: the prior runtime's known-error fatal behavior, the
candidate's owned device-start rejection followed by one trusted Retry with the
same page/context/save and child input continuity, and an unknown rejection
remaining fatal. All used original synthetic fixtures, not user game/save data.

The separate [iOS 18.5 lifecycle run 40630893964](https://github.com/op233qo123/FlashNest/actions/runs/40630893964)
produced a passing XCTest and complete, independently verified raw evidence for
all 22 baseline/candidate cases (zero skips). Its outer workflow nevertheless
timed out, so it is not a green workflow. No case exercised the new high-water
mid-case evidence path. Earlier failed harness runs remain historical evidence.

These are iOS 18.5 simulator results. In [iOS 18.2 audio run 40635582367](https://github.com/op233qo123/FlashNest/actions/runs/40635582367),
the candidate known-error case suffered a real WebContent startup
`EXC_BAD_INSTRUCTION/SIGILL` before injection; it did not establish recovery.
The baseline fatal and candidate unknown-error controls passed. The separate
[18.2 readback/frame-order run 40635635667](https://github.com/op233qo123/FlashNest/actions/runs/40635635667)
passed all three tests in both arms. The historical readback SIGBUS was not
reproduced in that run; this is not proof of a causal fix. Production promotion
and formal IPA packaging remain paused while the startup crash is investigated.
These results do not establish
audible hardware output, every audio error being recoverable, or a fix for the
user's scene/memory/WebContent termination. No automatic renderer switch or
silent reload is a consequence of the audio warning.

## Attribution

Original Ruffle MIT/Apache texts, the full upstream third-party inventory,
JavaScript licenses, Fluent NOTICE attributions and source-map comments remain.
See `THIRD_PARTY_NOTICES.md` and `licenses.manifest.json` in this bundle. The
project MIT license does not replace third-party terms. This notice is not a
legal-compliance certification.

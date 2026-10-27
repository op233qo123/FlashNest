# Upstream ownership fix and experimental additions

Verified on 2026-10-27 against the primary GitHub commit, pull request and raw
source. This note does not change the frozen candidate or its build inputs.

## Upstream repair

Ruffle merged [PR #24919](https://github.com/ruffle-rs/ruffle/pull/24919) on
2026-10-16. Its resulting commit is
[`45366370ed7d1a59c89aa3cf7b765c7a274407cd`](https://github.com/ruffle-rs/ruffle/commit/45366370ed7d1a59c89aa3cf7b765c7a274407cd),
authored by Torrekie Gen. The commit changes only `web/src/audio.rs` (six added,
two removed lines): the buffer callback captures a `Weak` reference and upgrades
it for callback duration instead of retaining its own buffer through a strong
`Rc`. This is the same ownership repair independently identified in this
experiment, not a new FlashNest-only discovery.

The merged PR includes no browser regression. Its discussion explicitly notes
that the Rust code uses browser JS types and that a real lifecycle test requires
a browser. Upstream acceptance corroborates the ownership analysis; it is not
evidence that this experiment has passed, that every additional change below is
upstream-approved, or that a particular native crash is fixed.

## Exact source correspondence

Applying only that upstream callback change to the pinned Ruffle source
`89a7049965f3090e706265670df309a5128233ac` reconstructs the complete upstream
`audio.rs` at the fix commit, byte for byte. No other upstream engine changes
are needed for this source-file backport.

| Source file | SHA-256 |
| --- | --- |
| Pinned `audio.rs` | `0cca2bc14a593060a233ec68a2ae725efc381c9068626a92a82c67a3bc732b8b` |
| Minimal upstream repair applied | `1c38f1759cec2d04af6dc37627fe4f53f2f5d0d7be9c9fbfc3fe2507ed24760c` |
| Current experimental `audio.rs` | `363ef32a15617be3d1a52c306bd09478cf5dd4f1e9922316e2c56c7b079ff3ca` |

The current experimental patch SHA-256 remains
`89dfadc1b9d113adb01f08582237559c71a5c0e04fe712cb0e31d80f077b07b9`.
The already-running candidate is not silently replaced with the smaller patch.

## Local additions are separately gated

Besides equivalent callback ownership semantics (with different comments), the
experimental patch adds three behaviors absent from the upstream commit:

1. Clear backend buffer owners before requesting `AudioContext.close()`. This
   moves explicit current-handler detachment before close entry; upstream's
   ordinary field destruction occurs after its drop body.
2. Detach the previous source's handler when refilling a buffer, so completed
   historical nodes do not retain a callback whose Rust closure later dies.
3. If starting a newly created source fails, detach its handler before returning
   the converted error. That source has not yet been stored as the buffer's
   current node, so the ordinary buffer drop cannot find it.

These changes require their own natural-refill, pause/resume, repeated teardown,
constructor-start-failure and explicitly synthetic late-event measurements.
The browser gate compares the immutable deployed guarded runtime against this
exact candidate. It is not a three-arm comparison against an upstream-only
build, so a pass cannot attribute every observed difference to the Weak change
alone. A pure Rust ownership model is not a substitute for these browser tests.

## Promotion and attribution limits

If a runtime is later promoted, its source/license correspondence must cite the
upstream commit and distinguish these local additions, retain the Ruffle
licenses/notices, and identify the exact modified sources and patch hashes.
Do not label this local multi-change candidate as an unchanged upstream release.
If an extra cleanup behavior fails its gate, prefer investigating or removing
that behavior rather than weakening the expected observation.

This defect concerns backend teardown and constructor failure. Ordinary
same-player child loading, rotation, and background/foreground do not themselves
destroy the audio backend. Neither the upstream merge nor this experiment proves
the cause or resolution of WebContent SIGBUS, simulator GPU SIGABRT, media
decoding failures, or the user's transition crashes. No memory-footprint or
garbage-collection gain has been measured here.

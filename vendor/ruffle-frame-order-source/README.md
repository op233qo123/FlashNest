# Compact source correspondence

This directory adds a reviewable copy of the exact queued-goto patch and a
SHA-256/size/path index of the source correspondence already retained in
`../ruffle-frame-order-40491098384.zip`. It deliberately does not duplicate the
large lockfiles and modified source file outside that archive.

Base: https://github.com/ruffle-rs/ruffle/tree/89a7049965f3090e706265670df309a5128233ac

Experiment and original test sources:
https://github.com/op233qo123/FlashNest/tree/f60ff6a99941937056eee5ad94ed4b4af9c72c99/experiments/frame-order

The indexed archive entries include `core/src/display_object/movie_clip.rs`,
`queued-goto-guard.patch`, `Cargo.lock`, `web/package-lock.json`, license texts,
version seal and build recipes. The original source is available at the exact
base commit; apply the supplied patch to obtain the indexed modified bytes.
No upstream expected output or third-party game content is modified.

The archived build-time experimental/unpromoted metadata and historical source
documents remain unchanged. Current integration identity, attribution and test
limits are described in `../../App/Resources/Web/Ruffle-MODIFICATIONS.md`.
This is not a complete upstream/dependency source archive, a second clean rebuild
verification, or a legal-compliance certification.

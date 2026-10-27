# Third-party notices

FlashNest's MIT license covers original project code and generated fixtures only.
Third-party components retain their own copyrights and licenses. No Flash game
content is included. The following complete upstream texts are distributed in
`App/Resources/Web/`, which `project.yml` copies into the application bundle.

## Modified experimental Ruffle 0.7.1

Runtime identity: **FlashNest experimental Ruffle 0.7.1 frame-order guard
de0acabdf957**, channel `flashnest-frame-order-experimental`. This is a modified
FlashNest build, **not an unmodified official Ruffle release or an upstream
stable compatibility fix**. The upstream base version remains 0.7.1.

Base source: https://github.com/ruffle-rs/ruffle/tree/89a7049965f3090e706265670df309a5128233ac

The queued-goto guard modifies only `core/src/display_object/movie_clip.rs` in
the pinned upstream source. The exact patch, modified source, dependency locks,
build recipes and license inventory are retained inside
`vendor/ruffle-frame-order-40491098384.zip`; the archive is preserved byte-for-byte
from the successful candidate build, verified offline before runtime extraction.
`vendor/ruffle-frame-order-source/` provides the reviewable patch and a hash/size
index of that source correspondence. This compact bundle is not a complete
upstream or dependency source archive.

Public experiment source and build recipe:
https://github.com/op233qo123/FlashNest/tree/f60ff6a99941937056eee5ad94ed4b4af9c72c99/experiments/frame-order

`Ruffle-MODIFICATIONS.md` identifies the exact archive, patch and provenance
hashes, corresponding-source locations, measured tests and their limits. The
original `LICENSE_MIT` and `LICENSE_APACHE` remain verbatim (MIT OR Apache-2.0).
`Ruffle-THIRD-PARTY-LICENSES.md` is the complete, unmodified upstream `LICENSE.md`
from the pinned base, including third-party attributions and the complete 0BSD,
Apache-2.0, BSD-2-Clause, BSD-3-Clause, CC0-1.0, ISC, MIT, MPL-2.0, Unlicense and
Zlib texts. This inventory also covers components not used by the web build; it
is intentionally preserved without pruning.

For dependency source, use the pinned base's `Cargo.lock` and
`web/package-lock.json`, also retained in the source correspondence. They
identify exact versions and source repositories linked in the upstream
inventory. MPL-covered components remain under MPL-2.0; the project MIT license
does not replace third-party terms. This patch introduces no new runtime
dependency and does not modify dependency source.

### JavaScript dependencies included in the web runtime

The shipped JavaScript source maps identify the following third-party modules.
Versions below are from the pinned base's `web/package-lock.json`. Full texts are in
`licenses/`; generated webpack runtime code is covered conservatively as well.

| Component | Version | License file |
| --- | --- | --- |
| tsx-dom | 3.1.0 | `licenses/tsx-dom-LICENSE` (MIT) |
| tsx-dom-types | 2.1.0 | `licenses/tsx-dom-LICENSE` (MIT; same upstream project) |
| @fluent/bundle | 0.19.1 | `licenses/fluent-bundle-LICENSE` (Apache-2.0) |
| @fluent/langneg | 0.7.0 | `licenses/fluent-langneg-LICENSE` (Apache-2.0) |
| wasm-feature-detect | 1.9.0 | `licenses/wasm-feature-detect-LICENSE` (Apache-2.0) |
| webpack runtime | 5.111.1 | `licenses/webpack-LICENSE` (MIT) |

Fluent attribution is retained verbatim in `licenses/fluent-bundle-NOTICE`
and `licenses/fluent-langneg-NOTICE`.
The distributed source maps retain source-level copyright/license comments.

License provenance:

- tsx-dom / tsx-dom-types: https://github.com/Lusito/tsx-dom/blob/9d1061257227c7ca59d41ab68c45fb8db222ddab/LICENSE
- Fluent bundle: https://github.com/projectfluent/fluent.js/blob/88582193c29a689241a4f7b2ca7086c802840264/LICENSE
- Fluent langneg: https://github.com/projectfluent/fluent.js/blob/67e038ec83f7136fea29af09a2b080df94e074d3/LICENSE
- wasm-feature-detect / webpack: unmodified license files from the exact npm
  tarballs; tarball SHA-512 integrity checked against Ruffle's pinned lockfile.

## ZIPFoundation 0.9.20

Source: https://github.com/weichsel/ZIPFoundation/tree/0.9.20

MIT. Complete verbatim upstream text: `ZIPFoundation-LICENSE.txt`.
Copyright (c) 2017-2025 Thomas Zoechling (https://www.peakstep.com).

## Distribution and updates

Keep this notice, `Ruffle-MODIFICATIONS.md`, all linked license files, source
correspondence, and original runtime attribution
when redistributing source or an IPA. `FlashNest-LICENSE.txt` is the project MIT
license bundled alongside these notices. `licenses.manifest.json` records the
SHA-256 of the shipped license texts and modification notice. Updating any dependency requires refreshing
its notices, checking its source/license obligations, and updating that manifest;
retaining only the root project MIT license is not sufficient.

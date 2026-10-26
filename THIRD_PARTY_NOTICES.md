# Third-party notices

FlashNest's MIT license covers original project code and generated fixtures only.
Third-party components retain their own copyrights and licenses. No Flash game
content is included. The following complete upstream texts are distributed in
`App/Resources/Web/`, which `project.yml` copies into the application bundle.

## Ruffle 0.7.1

Source: https://github.com/ruffle-rs/ruffle/tree/v0.7.1

The unmodified official self-hosted release is fetched into `runtime/` at build
time (large runtime binaries/source maps are not tracked in Git). Its original
`LICENSE_MIT` and `LICENSE_APACHE` are retained verbatim (MIT OR Apache-2.0).
`Ruffle-THIRD-PARTY-LICENSES.md` is the complete, unmodified `LICENSE.md` from the
same upstream tag, including third-party attributions and the complete 0BSD,
Apache-2.0, BSD-2-Clause, BSD-3-Clause, CC0-1.0, ISC, MIT, MPL-2.0, Unlicense and
Zlib texts. This upstream inventory also covers components not used by the web
build; it is intentionally preserved without pruning.

For source of Ruffle and its dependencies, use the tag above and its `Cargo.lock`
and `web/package-lock.json`, which identify exact dependency versions and source
repositories. MPL-covered components remain under MPL-2.0; the project MIT
license does not replace their license. Their source is available from the
upstream repositories linked in the retained inventory, at the versions in that
lockfile. No bundled Ruffle binary or dependency source was modified.

### JavaScript dependencies included in the web runtime

The shipped JavaScript source maps identify the following third-party modules.
Versions below are from Ruffle v0.7.1's `web/package-lock.json`. Full texts are in
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

Keep this notice, all linked license files, and original runtime attribution
when redistributing source or an IPA. `FlashNest-LICENSE.txt` is the project MIT
license bundled alongside these notices. `licenses.manifest.json` records the
SHA-256 of the shipped license texts. Updating any dependency requires refreshing
its notices, checking its source/license obligations, and updating that manifest;
retaining only the root project MIT license is not sufficient.

# Dependencies

- Ruffle 0.7.1: official self-hosted runtime, bundled for offline use. Version,
  release URL and archive SHA-256 are pinned in `runtime.lock.json`; individual
  runtime files are checked against `runtime.files.json`. The checksum records
  reproducibility, not an independent publisher signature.
- ZIPFoundation 0.9.20: exact Swift Package Manager dependency and revision pinned
  in `project.yml` and `Package.resolved`.
- System frameworks: Apple SwiftUI, WebKit, Network, Foundation and related iOS
  SDK frameworks; supplied by Apple's SDK/OS, not vendored project code.

See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for complete license files,
attribution and upstream source locations. `App/Resources/Web` is copied as an
app resource folder, including the notices and license files.

`fixtures/multi-swf` and its ZIP are original generated test content, covered by
the project MIT license. No third-party games or artwork are bundled.

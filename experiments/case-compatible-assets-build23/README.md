# Unique-case game assets: build23 diagnostic-v2 experiment

This is an isolated source/validation experiment, not a release, IPA build, or claim of complete game compatibility. It starts from exact diagnostic-v2/import-warning commit `cc6c4bf285a201d9c1a827140662c54606027d10`, reconstructing its accepted 207-file build22 baseline and reviewed build23 overlays. The fixed 12-file runtime, import confirmation UX, diagnostic-v2 observer, and default-OFF diagnostics are unchanged.

Only two product sources change: `HTTPProtocol.swift` and the games-branch call in `LoopbackServer.swift`. Exact path resolution is attempted first. Only a missing component allows a unique normalized-case match within its current parent directory. Existing exact paths never backtrack, ambiguous matches fail, and path decoding/traversal, symlink, root containment, forbidden executable document and active-package restrictions remain. Web shell/runtime resources never opt in. No game files are renamed, edited, imported here, or published.

## Validation boundaries

- Native Swift resolver fixtures execute the actual candidate HTTPProtocol on a new macOS APFSX disk image. The fixture proves two differently cased files coexist with distinct contents; a case-insensitive filesystem fails rather than falsely passing. Cases cover exact precedence, unique/multiple-component matches, missing/ambiguous names, Unicode normalization without diacritic folding, symlinks, encoded traversal, nested entries and sibling data directories. This is native macOS Foundation evidence, not a physical iPhone test.
- Actual iOS18.2 selected tests compile the candidate App and run the original diagnostic/import regressions plus existing HTTP server tests and two separate import-confirmation UI tests. Their exact methods/counts and source identities are recorded; this is not the full suite. Simulator filesystem behavior is not used as proof of case-sensitive fallback.
- The neutral AS3 fixture is a generated 24fps SWF with ENTER_FRAME scalar traces only. Chromium executes the unchanged hash-bound runtime. Default/explicit24/explicit48 wall-clock controls are separate from injected60/120Hz RAF timestamps; the latter do not represent physical displays. Browser sandbox remains enabled. Any failure remains a failure, not an excuse to change the product frame rate.

The reported faster animation has **no established root cause**. No default frame-rate override was found in the actual App configuration. These tests characterize timing independently; they do not certify that a private game's loading or animation issue is fixed. Public fixtures and logs contain no private game names, assets, paths, saves or incident records.

CI has read-only repository permissions, no signing credentials, no publishing and no IPA step. Only the isolated experimental branch triggers this workflow. Main, tags and formal release recipes are untouched.

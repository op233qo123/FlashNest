# FlashNest 1.5.6 build23 long-run diagnostic test package

This is an unsigned, default-off diagnostic test IPA. It is not a formal Release,
a crash fix, a cache eviction policy, or a physical-device certification.
The accepted 1.5.6/build22 engine's twelve runtime files remain byte-identical.
No experimental alpha decoder, scale-1 shape reuse, or root-cache policy is added.

## Source and packaging identity

The root repository App is not the accepted build22 App. Staging reconstructs the
207-file build22 source from frozen source commit
`9bc000e37695696f2427b25fe08efe4993bf22e5`, its exact build20 diagnostic overlays,
the explicitly enabled sampling preference gate, and original candidate engine
archive `40998892881`. It verifies every source hash against the release recipe
at `985f25c44ead766b2c4f9bd77b82e7b92bf95cc0`, then applies only reviewed build23
overlay files. This does not inherit an old UI-test waiver as a new test result.

The source reconstruction needs the pinned historical vendor archive and pinned
candidate archive. An unavailable or mismatched artifact fails closed; no
substitute engine is silently accepted. The old composite archive is recovered
from exact committed mirror parts and checked by its original full digest.

## Diagnostic scope and privacy

The added observer is opt-in. It records only bounded scalar samples and fixed
native lifecycle/marker event types in anonymous local sessions. It does not
record game names, URLs, paths, save contents, pixel bytes, free-form traces, or
error text. There is no automatic upload. Export is an explicit user action.
It cannot universally detect Flash scene transitions. Heartbeat gaps can arise
from scheduling/background throttling and do not establish a crash cause.
Texture API counts and byte estimates are not physical GPU allocation; missing
WASM capacity coverage is reported as unsupported, not guessed.
Only WebGL is observed: at most four contexts and 16,384 lifetime tracked
textures. Overflow means incomplete coverage; unique deletion counts may be
lower bounds. Counts do not prove resources were physically freed.
The separate older load-phase observer keeps its original first-64-request /
first-256-event limit; only the new long-run recorder rolls indefinitely
within its last-120-events per session / two-session bound.

## Acceptance

The workflow uses Xcode 16.2 and iOS 18.2, runs reviewed JavaScript/source checks
and selected actual simulator XCTest methods, and then builds a Release arm64
unsigned IPA. Selected method identities/counts, no skips, tested source hashes,
and actual packaged runtime/Web bytes are verified. Passing these focused tests
is not complete application regression, long-term game validation, context-loss
recovery, or real iPhone acceptance. Prior observed UI/context limitations remain.

The workflow cannot change main, create a tag or Release, or publish an App Store
build. It uploads only the requested test artifact and synthetic test evidence.

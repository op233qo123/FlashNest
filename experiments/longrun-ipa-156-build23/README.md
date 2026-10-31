# FlashNest 1.5.6 build23 — diagnostic v2 / import-warning TEST IPA

This is a rebuild of the default-OFF long-run diagnostic test package, not a new formal release. It retains version 1.5.6/build23 and uses a distinct `FlashNest-1.5.6-build23-diagnostic-v2-import-warning-unsigned.ipa` filename and artifact names to distinguish it from the prior build23 diagnostic package.

## Reviewed scope

The import revision replaces the prior 256 MiB per-file and 1 GiB per-package hard byte rejection with a user warning and explicit continuation choice. Large imports are not automatically confirmed. Cancellation must leave library/source data unchanged. Confirmation permits the warned byte size; it does not waive ZIP path traversal, unsafe entry, symlink, entry-count, compression-ratio/bomb or other structural safety checks. The warning is not a promise that available storage or runtime memory is sufficient. Exact product policy and UX are source- and test-bound in the overlay, not implied by this document alone.

The engine remains the same 12 pinned accepted runtime files from build22. No new image-decoder, texture eviction, JPEG-drop, alpha or scale policy is bundled. Long-running diagnostics stay opt-in and default OFF, local bounded scalar records only; no automatic upload or game paths/names/URLs/save/image/raw-buffer payloads. WebGL counters are API observations, not physical GPU/CPU memory measurements. Internal Flash scene transitions are not universally observed. Existing resource limits and process termination do not by themselves prove OOM.

## Reproducible staging

`package.py` first validates the immutable build22 release recipe and its exact 207-file source/runtime closure, reconstructs that baseline from pinned source and original archive bytes, then applies the hash-bound reviewed build23 overlay. It rejects runtime overlays, unsafe paths, extra source entries and mismatched hashes. The source checkout remains frozen commit `9bc000e37695696f2427b25fe08efe4993bf22e5`; baseline release commit is `985f25c44ead766b2c4f9bd77b82e7b92bf95cc0`.

Recipe modifications must refresh `recipeFiles` and overlay hashes in `inputs.json`. Dispatch requires the separately authorized `dispatchAllowed` flag. This recipe does not modify main, tags, formal Releases, credentials or security settings.

## Evidence boundaries

CI uses Xcode16.2 / iOS18.2 SE3 simulator and unsigned arm64 device packaging. Selected native tests include the original 25 diagnostic methods plus explicitly enumerated import policy/flow regressions. A separate FlashNestUI lane on the same simulator verifies actual confirmation taps with actual Files cross-container synthetic fixtures from the separately built/installed FlashNestFixtureSource app and a DEBUG-only reduced warning threshold; this is not all-provider or real large-file end-to-end coverage. Both unit and UI receipts must pass before packaging. The Release executable must not contain the DEBUG harness launch argument. `testSourceFiles` maps class names to files; class-aware Swift method extraction prevents a second XCTestCase in the same file being wrongly attributed to the first. Each selected method must actually pass; missing, skipped, unexpected or failed cases fail the gate. No prior UI waiver is reused. Simulator cleanup and per-unit-test180-second and per-UI-test420-second limits remain enabled.

Static/Node/Python controls are separate from actual native execution. The final receipt binds the selected XCTest pass and IPA Web/runtime bytes to the staged source. `fullGatePassed`, `physicalDeviceCertified` and `originalCrashResolved` remain false; no prior or new focused test result establishes complete game compatibility or resolution of the long-run crash. Real-device import confirmation and long-running reproduction remain user validation steps.

## Diagnostic observer revision 2

This revision keeps import confirmation and the accepted 12-file engine unchanged. Diagnostics remain OFF by default. Ten additional scalar request counters distinguish `texImage2D` argument forms and framebuffer/renderbuffer API calls. Counters cover only successfully hooked APIs; a normal return does not imply GL success. Null/repeated create/delete requests are not live resource counts, memory ownership, resident GPU bytes or successful releases. No raw pixel buffers, game identifiers, source URLs, saves or private incident logs are included or uploaded.

New records carry native app version/build plus diagnostic schema2 and observer revision2; these are not accepted from JavaScript. Legacy schema1 checkpoints remain readable without relabeling them as new sessions. Actual bundled JS must be schema2, and native build-identity source is hash-bound to the tested application. The selected native inventory is70 methods (prior66 plus four explicit schema/build-identity tests), with the same two separate actual confirmation UI tests. Static/Node controls do not substitute for those CI gates. No full-suite, physical-device, OOM or crash-resolution certification is claimed.

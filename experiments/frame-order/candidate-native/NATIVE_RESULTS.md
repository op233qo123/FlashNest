# Measured experimental candidate on iOS Simulator 18.2

[Run 40494446464](https://github.com/op233qo123/FlashNest/actions/runs/40494446464)
passed on 2026-10-27 at diagnostic commit
`92ecbeb474b92ce6700b34c494f7d3e905a741a4`. The standard `macos-14` runner used
Xcode 16.2 and an arm64 iPhone 16 / iOS Simulator 18.2. This was an isolated
candidate overlay, not a physical-device test or a production IPA build.

The runtime was the exact modified dual-WASM artifact from build `40491098384`,
artifact `12729069965`, ZIP SHA-256
`57d7eaed19edd006e2a33a9bfa816f22da8b1003becf3719dfca0c97cb38c4af`.
Its source, patch, experimental identity and complete runtime inventory were
verified before execution. The workflow retained an empty production-source
diff; it did not modify the checked-in application or default tests.

## Separate measured gates

| Scope | Result |
| --- | --- |
| Original nested-goto repair contract | Passed; 32 raw rows exactly match the frozen repair target |
| Original control contract | Passed; exact 31-row canonical window, plus two explicitly reported later loop/open pairs |
| Existing actual SharedObject save/restart tests | 2/2 passed |
| Existing real background/direct-save/cancel/restart UI lifecycle test | 1/1 passed |

All three result bundles have their exact selected test names/counts and zero
failed, skipped or expected-failure tests. Both original captures are complete,
with no observer overflow, truncated lines, operational or snapshot errors;
server drainage was confirmed between tests.

The nested raw trace SHA-256 is
`57648847e013eb2aaa9e45a91eb0a55c66c97862defd8e3c1cd5b74ef4e3c2ae`.
Its parent script finishes on frame 1 before the queued target script executes;
the target then starts the child's opening loop. The control's canonical trace
SHA-256 remains
`cb1f8c5a8f0770d7ed9c92fd3219dc11294746258fa9a4ec8558c82eda9626c0`.
The complete 35-row control snapshot is retained, not silently truncated.
`FO_DONE` occurs during ENTER_FRAME: already-queued child scripts can run after
it. The canonical window includes the immediate loop/open pair, and later pairs
are reported separately.

The UI lifecycle test retained background/child input counters, direct-save and
cancel evidence, then required the restarted movie's `LIFECYCLE_ROOT_READY:420`
callback and an interactive game/menu. The final screenshot shows the original
fixture stage and menu rather than an error panel. The bounded crash collector
reported no matching crash reports and zero skipped reports for this run.

## Evidence and limits

Native artifact `12730103711`, `FlashNest-experimental-candidate-native-evidence`,
is 11,740,674 bytes; its downloaded ZIP matches SHA-256
`bef0ebd61418c57e1817d22696ebb8813c78f172388a96d520aa7bbbbe62c8ca`.
It contains complete raw captures, exact candidate provenance, summaries,
cleanup evidence, UI attachments and crash-collection results.

This verifies the **reduced-fixture repair in native WebKit/WASM**. It is not an
exact Adobe reference run, original-game execution, or proof of that game's root
cause. One lifecycle pass does not establish that the separately observed
intermittent WebContent startup/restart crash is fixed. A rebuilt candidate can
also differ from the official ZIP in toolchain/build details; such stability
differences must not be attributed solely to this source guard.

Integrating these same bytes into application version 1.5.4/build 17 is a
separate candidate change. Its complete application regression, UI checks and
device IPA validation must run separately before delivery.

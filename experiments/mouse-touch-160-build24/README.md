# Experimental FlashNest 1.6.0 / build 25

This recipe reconstructs the immutable delivered build23 unload-candidate stage from frozen commits, verifies it before applying the explicit mouse-touch/menu/version overlay, and binds the new source closure to a separate current-run receipt. It does not modify the runtime or claim the new app is byte-identical to build23.

Acceptance requires actual case-sensitive path tests, unchanged-runtime cadence controls, a four-arm real-Ruffle mouse browser matrix, expanded selected native tests including actual WKWebView/Ruffle mouse semantics and virtual-key focus, both inherited import-confirmation UI tests, and a new draggable-menu/rotation UI test. It is not a complete native/UI suite and not physical-device certification. All packaging gates fail closed; no skip or prior native evidence reuse is allowed.

The workflow is limited to the existing experimental branch; no tags, releases, or default-branch changes. The unsigned arm64 iPhoneOS IPA must have version 1.6.0/build25, preserve the exact 12-file runtime inventory, match all Web resources and source hashes, contain no DEBUG test harness/assets, and pass the unchanged offline archive consumer. Native menu drag geometry and simulator drag/tap/rotation are tested; physical-device gesture behavior still needs confirmation.

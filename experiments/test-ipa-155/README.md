# Experimental device IPA 1.5.5 / build 18

Manual device-only packaging of existing App source at `7f51087c662688bda6757df08d94c0aca7ae2e0e` plus the original reviewed recovery runtime built by run `40614335019` (`5d2cdcc6757d65194bd55c4a0395b76b0176d224`). This is not the phase-instrumented runtime. Shipping main runtime/version and normal release workflows are not changed: the overlay is applied only to a separate pinned checkout in the build workspace.

Includes existing external Open In, JSON/raw SOL import, explicit archived-save deletion, bounded save-summary/cache handling, per-game optional WebGL compatibility, and the experimental in-page audio recovery warning/Retry implementation. Multiple low-sampling tiers are not included. Automatic rendering remains the default. Bundle identifier and save paths remain unchanged (`com.flashnest.app`).

This build runs source/runtime/metadata checks and compiles an unsigned iPhoneOS App. It does not run or claim iOS 18.2 native functional acceptance, physical audio output validation, or resolution of the original intermittent WebContent SIGILL. No experimental diagnostic injector, phase probe, fixture, user game or save is an App resource. Exact JS/Wasm inventories and licenses are checked before and after packaging.

The IPA requires the user's existing signing/installation route. Back up/export important saves before upgrading; retain the same signing identity/bundle identifier and avoid uninstalling first. Compatibility of an arbitrary signing tool or preservation after a changed signing identity is not guaranteed. No public GitHub release is created by this workflow.

# Bounded Loader UNLOAD lifecycle candidate

This is an experimental one-source-file increment over the accepted six-patch
runtime source set, not an IPA build, reference-Flash certification, or a claim
that an application compatibility problem is solved.

## Bound source

- Upstream: `89a7049965f3090e706265670df309a5128233ac`
- Accepted build source: `6d3e4322293972a28ab2cdf129ee6398f40f0f37`
- Accepted source-lock SHA256: `7200650c24fe505844ea676c02c44a42dd2ee7bc484344e775e4458d84566494`
- Only changed product file: `core/src/avm2/object/loaderinfo_object.rs`.
- `source-lock.json` binds exact before/after bytes and the incremental patch.
- Accepted `core/src/loader.rs` was independently reconstructed and checked at
  SHA256 `a8a1faf8c1e3bcf471bc3d631ecca84e38775fd30b8af69b64204867c715d54c`.
  Its existing cancellation uses generational SlotMap handles, checks for
  cancellation after constructors and child insertion, and is not modified here.

## Lifecycle rules

1. The old content identity comes from `loaded_stream`, not Loader child index 0.
   Reparenting or removing a loaded root does not erase its LoaderInfo lifecycle.
2. UNLOAD eligibility requires an exposed root. A pending dummy, missing content,
   or unexposed failed load is not enough. Exposed content during ADDED before
   INIT remains eligible, preserving the previous attached-child behavior.
3. A stream generation changes whenever `set_loader_stream` replaces the stream,
   even for reloading the same URL. The current generation is marked consumed
   before dispatch. Recursive unload can clean up without emitting UNLOAD again.
4. UNLOAD listeners still observe the old stream/content until they themselves
   unload or replace it. After callbacks, reset occurs only if that generation
   remains current. A same-Loader load initiated by the callback first calls a
   nested unload, resets old flags, and then establishes its new generation;
   the outer unload does not overwrite the new stream or initialization flags.
5. Reset includes `expose_content=false`, preventing the next pending dummy from
   inheriting visibility from a previous successful load.
6. Cancellation stays before all callbacks. The outer call never cancels again
   after a callback creates a new load. Cleanup uses the captured old object,
   removes it only if it still belongs to this Loader, and releases only its old
   non-root movie render caches. No movie library/domain eviction is added.

## Expected focused regressions

- Attached, removed/reparented, and retained-other-parent roots.
- No-load, failed, and incomplete loads: no false UNLOAD.
- Repeat/recursive unload: one event per exposed lifecycle.
- UNLOAD callback replacing via a fresh Loader, the same Loader, or loadBytes.
- New content identity/parent/token and INIT/COMPLETE survive outer return.
- ADDED callback unload before INIT remains eligible; cancelled old completion
  must not resume and overwrite the new lifecycle.
- Attached baseline/candidate callback content observations should remain equal.

The patch applies locally with `patch --fuzz=0` and produces the exact candidate
hash. No Rust compiler is installed in the local workspace. Compilation and
actual baseline/candidate browser regression results remain pending CI.

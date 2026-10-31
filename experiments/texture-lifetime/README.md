# Texture lifetime request diagnostics

This is a diagnostic-only experiment against the exact accepted lazy-Graphic baseline runtime. It does not include the alpha two-pass, JPEG decoder lifetime, or shape reuse candidates. No application source, cache policy, release tag or IPA is changed.

The browser wraps WebGL texture creation, binding, upload/storage, and deletion calls and retains only scalar request metadata. Native texture objects are keys in a WeakMap, not owned by diagnostics. WASM memory is weakly observed. Upload pixels are not copied or hashed here, and no forced GC, `getError`, BitmapData disposal, or security-disabling browser arguments are used.

The reported texture bytes are dimension-based base-level RGBA8 request budgets. They exclude mipmaps, driver metadata, alignment and other GPU resources. A deletion call does not prove physical GPU memory was freed. WASM linear capacity is not live heap, process RSS or GPU residency and normally does not shrink.

A bounded synthetic run can establish whether API requests plateau or are repeated in these exact scenarios. It cannot prove the cause or resolution of a private game's long-duration failure, WebKit/iPhone behavior, or general context recovery. All fixtures are newly generated mathematical imagery and synthetic code, with no private inputs.

## Source and runtime binding

`engine-lock.json` pins the completed CI artifact ZIP, run/commit, baseline provenance and all12 runtime file sizes/hashes. `stage_engine.py` extracts only that baseline after all checks, not the other experimental engine. Actual downloaded WASM response bytes are checked again in the browser run. No engine recompilation is needed.

## Reproduction

Run `scripts/check_package.py`, `node browser/test_page.cjs`, then install the exact `browser/requirements.txt` versions. Use sandboxed official Chrome. The workflow obtains the pinned artifact using its read-only Actions token, stages the baseline, and runs `browser/run.py`. Setup and diagnostic outputs are bounded to64MiB. An unavailable artifact or changed hash stops instead of silently rebuilding/substituting another runtime.

The fixture manifest specifies actual execution coverage and exact trace/key phase boundaries. No result exists until the CI has actually run and its evidence is reviewed.

## Bounded coverage

Four AVM2 cases use actual Flash `MovieClip` and `Loader` APIs:16 distinct root images for4 traversals;64 distinct root images for2 traversals;6 child load/unload cycles without retained references; and6 cycles retaining3 child references, followed by reattachment and release. Images are512² and displayed64². The root is cleared but stays alive before final player removal. Loader reference release is followed by120 normal frames, then a bounded idle interval. No global leak-freedom or physical freeing assertion is inferred from this bounded observation.

The runner requires every expected per-resource/per-cycle trace, all Loader complete/unload markers, retained-object ping markers, trusted keyboard inputs, actual WebGL renderer selection, actual pinned WASM bytes, and nonblank visible phase screenshots. Lifecycle and capacity outcomes remain observations, not assertions that force a preferred plateau/deletion result.

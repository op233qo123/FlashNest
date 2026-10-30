# Controlled retained-prefix scene diagnostic (local preparation)

Not a product fix, native acceptance, OOM diagnosis, or assertion that the user's
private movie uses AVM2. No private files are inputs. External publication and
CI are not yet authorized. See PLAN.md for exact bounded resource scope.

## Two cases, one shared package
`retention/main-retain.swf` and `main-drop.swf` have identical bytes; the parent
checks its own URL to select the case. Native verification MUST observe the
actual branch phase/counts; filenames alone cannot prove the branch ran.
Both prefixes load concurrently with the default per-Loader context. The parent
waits for each prefix INIT, COMPLETE and first-frame in any relative order.
Both prefixes have one valid DefineBinaryData tag and no bound binary class,
no instantiated ByteArray, no texture/audio, and no external data. Their logical
content objects and Loaders remain in two arrays; loaded bytes share decoded SWF
storage through the engine's existing SwfSlice/Arc path. This is a controlled
ownership hypothesis, not a faithful simulation of a complex game.

Old/new bitmap SWFs are byte-identical to the preceding public bitmap diagnostic.
After old first-frame/INIT/COMPLETE, one Space is accepted. Retain keeps prefix
Loader/content references and display children. Drop removes eight listeners,
calls two normal unloads, removes two Loader children, nulls four array entries
and the temporary Loader local, then returns before old unload/new load. No GC
is forced. `prefixes.references-dropped` means only the fixture's explicit
references are gone; hidden class/domain/runtime references may still remain.
The counters do not show physical freeing, RSS, or GPU memory.

The parent starts immediately when stage exists; otherwise it waits for
ADDED_TO_STAGE and removes that listener before initialization. Both native
mains still execute identical startup code. The local null-core wrapper control
removes/re-adds its loader once to verify no duplicate parent initialization.

## Budgets
Prefixes: 48 + 44 MiB outer decoded CWS streams, 45 + 40 MiB deterministic
entropy and zero padding. Prefix compressed sum <=86 MiB. Complete package
compressed <=144 MiB, outer decoded streams <=154 MiB, generated local disk
budget <=512 MiB. Existing bitmap nested decode adds 8 MiB logical pixel bytes
outside the outer-stream budget. None of these is a process-memory bound.

## Evidence and limitations
`compile_abc.py` verifies pinned ASC/playerglobal hashes and byte-reproducible
ABC. `generate_fixtures.py` emits only six synthetic SWFs and enforces the frozen
manifest, old/new identities, tag structure and budgets. Tests mutate size,
checksum, branch, prefix completion and reference-count evidence.

`run_core_smoke.py` is LOCAL-ONLY control source. It reuses a pinned existing
null-renderer binary; it does not rebuild the engine. Small wrapper movies load
the actual parent filenames because the null harness otherwise replaces the
root URL with test.swf. Wrapper movies are NOT in the generated/native fixture
manifest or native bundle. Two earlier invalid control logs are retained locally
but excluded from the frozen/public candidate: normalized URL made both cases
drop; then wrapper child stage absence required the startup guard. Neither was
counted as success. Final `core-smoke.log` still has intentionally empty Flash
golden failures; `local-core-evidence.json` independently verifies both 25-phase
semantic paths. This is not Flash-golden, WebKit, pixel, or native success.

The body observer adds Promise reactions, with timing and unhandled-rejection
observation effects; no clone, extra body read, or buffer retention. Body receipt
does not observe WASM copy/decompression/parse or prove a failure cause. Native
runner must separately confirm one WK/epoch through each case, fixed runtime/
renderer, the real old/new palettes, exactly one Space, and all five complete
body operations. Prefix request/completion order may interleave.

Large generated SWFs, local wrapper binaries and prior invalid control logs are
excluded from the source freeze. `manifest.json` lists only bounded public
synthetic source/test/evidence candidates; approval is still required to publish.

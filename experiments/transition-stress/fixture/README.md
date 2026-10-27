# Original AVM2 Loader transition fixture — selected normal-unload diagnostic

**Not executed in Ruffle, WebKit or Adobe Flash.** No user files, saves, game
assets, compiler downloads or external network dependencies were used. These are
original SWF37 one-frame/24fps movies assembled from a deliberately small ABC
subset. Root and child retain ENTER_FRAME listeners after their timelines stop.

- Selected normal arm: `main.swf` and `sub/child.swf`.
- The selected directory contains no alternative playable root. The generator
  retains `root_abc("unloadAndStop")` for in-memory structural checks only; its
  separate prototype remains outside this selected bundle.
- Four loaded generations: 0 initially, then 1/2/3 only from click events after
  the current load reached COMPLETE. A new Loader is used each generation.
- No automatic scene advance, periodic trace, SharedObject, ExternalInterface,
  URL navigation, shader, or timer. Root and child heartbeat counters increment
  silently on ENTER_FRAME. The host/UI supplies actual trusted taps and Enter;
  the fixture itself does not attest browser/native input trust.
- Root redraws its full logical stage on RESIZE; child is a visible pink 96×96
  vector square at Loader position (36,48). Stage uses noScale/TL. Rotation or
  foregrounding must not itself invoke the click transition.

## Exact common trace contract

All trace calls emit a single string:

```
LT|KIND|bootToken|generation|rootHeartbeat|pointerCount|keyCount|ready|activeChildGeneration|childHeartbeat|errors|unloadCalls|unloadEvents
```

`STATE` and `READY` have **exactly 13 fields**, including `LT`. Other events may
append `|detail` (not a second trace argument). `bootToken` is
`String(Math.random())` once per root instance; it is not a secret, persistent ID,
or cryptographic uniqueness guarantee. Numeric fields use decimal string coercion.

| Field | Source / meaning |
|---|---|
| generation | 0 initially; incremented after an unload returns and old Loader is removed; bounded at 3 |
| rootHeartbeat | Actual root ENTER_FRAME count; never itself logs or advances a scene |
| pointerCount | Incremented for every stage click, including ignored clicks while not ready or at generation 3 |
| keyCount | Incremented only for keyCode 13; each such event immediately emits STATE |
| ready | 1 only in the current LoaderInfo COMPLETE callback; set 0 before unloading/loading |
| activeChildGeneration | Read from actual `currentLoader.content.childGeneration` when ready; otherwise -1 |
| childHeartbeat | Read from actual `currentLoader.content.childHeartbeat` when ready; otherwise 0 |
| errors | IO/security error callbacks and stale/duplicate COMPLETE observations; not a catch-all for AVM exceptions or process death |
| unloadCalls | Incremented only after the selected unload API invocation returns |
| unloadEvents | Incremented only by the LoaderInfo UNLOAD event callback |

The READY handler writes the generation label onto the actual loaded child.
It does **not** synthesize its heartbeat. Stale/duplicate COMPLETE is an explicit
ERROR and cannot mark another generation ready. Child ADDED/REMOVED callbacks
report through a captured root object using the same common prefix, with their
Loader's stable `scene-N` origin in detail. The common generation is root state at
callback time; detail identifies the child's origin. Do not equate those if a late
callback is observed. Child constructor registers its observers; it emits no
unattributable pre-attachment trace. The child deliberately does not remove its
ENTER_FRAME listener on normal unload, so this fixture does not hide unloading
semantics by stopping it manually. STATE reads only the current active child.

Markers: BOOT, LOAD_BEGIN, LOAD_RETURN, OPEN, PROGRESS, INIT, COMPLETE, READY,
POINTER, UNLOAD_BEGIN, UNLOAD_EVENT, UNLOAD_RETURN, CHILD_ADDED, CHILD_REMOVED,
RESIZE, STATE, ERROR. STATE/READY carry no detail. No fixed count of PROGRESS or
RESIZE events is assumed.

## Milestone gates (not Adobe total event ordering)

For the intended UI sequence:
1. Observe initial READY: generation 0, ready 1, active child generation 0,
   errors 0, unloadCalls/unloadEvents both 0.
2. Enter after an observation interval must yield a fresh STATE: same boot,
   generation and pointer count; keyCount exactly +1; actual child heartbeat
   greater than the prior snapshot. Require readiness and errors 0.
3. Rotate / background / foreground as real native interactions at each READY.
   Then request fresh STATE; no scene advancement or new boot is allowed.
4. One trusted center-stage tap after readiness increments pointerCount once and
   starts one transition. Require a new READY for the next generation, with
   errors 0, active child generation equal to root generation, and independently
   recorded unloadCalls == generation and unloadEvents == generation.
5. Stop after READY generation 3 and final fresh STATE. Any missing event, native
   process termination, unexpected reload, timeout, parser failure or uncaught
   console exception is evidence of failure—not something to normalize away.

UNLOAD_EVENT may occur *inside* the unload call before unloadCalls increments;
transient event records need not have counts equal to generation. The equality
checks above apply to completed READY/STATE milestones. These checks express the
original diagnostic's intended operation, not a claimed complete Flash event
ordering. No Adobe matching reference has been run. The unselected unloadAndStop
prototype remains outside this bundle and must not silently replace the normal
unload arm. Default generation writes only main.swf and sub/child.swf, and refuses
a folder already containing the alternative prototype payload.

There are at most four load invocations in the intended path and three completed
unload invocations. The fixture intentionally waits indefinitely between user
operations; the native test must impose bounded readiness/interaction timeouts
and preserve partial traces on failure. No fixture assertion treats silence as
proof of survival. Tiny children do not cover large-file preloading schedules,
large media memory pressure or all Loader cancellation/reuse cases.

## Rebuild and structural checks

```
python3 make_fixtures.py
python3 validate_fixtures.py
python3 -m unittest -v test_fixture_validation
```

`abc_subset.py` is copied **byte-for-byte** from the earlier original fixture
writer, SHA-256 `d8d7f30cc2edc06fda039f0d57fc8b8e38126b5f98d0b6b7b82e0de464de6701`.
Its binary format reference is pinned Ruffle
[`swf/src/avm2/write.rs`](https://github.com/ruffle-rs/ruffle/blob/89a7049965f3090e706265670df309a5128233ac/swf/src/avm2/write.rs)
and [`opcode.rs`](https://github.com/ruffle-rs/ruffle/blob/89a7049965f3090e706265670df309a5128233ac/swf/src/avm2/opcode.rs).
The independent byte-reader is adapted from the earlier structural validator; new
subset support is local2, pushnull, callproperty, convert_s, add and ifeq, plus
valid empty-string constant index 0. It checks pools/references/class scopes,
branch targets and stack/scope balance, plus explicit load/marker/counter paths.
It is not a substitute for AVM2 verification or a real runtime run.

Six unit tests cover deterministic binaries/helper identity, both selected binary
structures plus the alternative ABC in memory, exact field order and marker sites, separated unload arms, malformed
branches/stack underflow, and truncated ABC rejection. `ReferenceRoot.as` and
`ReferenceChild.as` are human-readable equivalents, not compiler inputs or Adobe
reference outputs. The root reference shows the selected normal arm; the in-memory alternative
changes the called API and BOOT detail only. Python cache files are not bundle
inputs; use PYTHONDONTWRITEBYTECODE=1 when validating this locked directory.

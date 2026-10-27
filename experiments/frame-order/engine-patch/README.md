# Experimental pinned-engine repair

**Not shipped; not yet a demonstrated compatibility fix.** This directory contains
an isolated candidate patch against Ruffle 0.7.1, source commit
`89a7049965f3090e706265670df309a5128233ac`. It does not modify the application's
bundled runtime, runtime locks, default tests, or any third-party game.

## Minimal behavior change

`queued-goto-guard.patch` adds a guard immediately before `queued_goto.take()`
in `MovieClip::run_local_frame_scripts`. A reentrant stage pass must not consume
that clip's queued goto while the same clip's frame script is still executing.
The original invocation clears the existing execution flag after its script
returns, then drains the preserved goto normally.

Child traversal remains in `run_frame_scripts`; same-frame gotos still trigger
nested lifecycle processing. The existing script-recursion guard, cleanup queue,
and SWF9 special cases are unchanged. The patch deliberately changes observable
parent playhead/construction/event timing, so regression gates are necessary.

This follows the source's existing deferred-goto invariant and the
[AS3 documented contract](https://airsdk.dev/reference/actionscript/3.0/flash/display/MovieClip.html#gotoAndPlay()).
It is preferable as a first small experiment to new deferred-script bookkeeping,
but the exact original fixture has **not** been executed in Adobe Flash. The
documentation and nearby reference tests do not eliminate that evidence gap.

## Original fixtures and expectations

The exact two existing original SWF37 binaries are reused without modification.
`stage_original_tests.py` checks the pinned source and fixture/expectation hashes,
then adds an isolated Rust integration test to a disposable upstream checkout.
It does not alter upstream `Cargo.toml`, official fixtures, or their goldens.

The expectation files are deliberately separate from official Flash goldens:

- `nested-baseline.txt`: measured pinned-Ruffle native simulator trace from
  [run 40473436551](https://github.com/op233qo123/FlashNest/actions/runs/40473436551).
- `control.txt`: measured pinned-Ruffle native simulator trace from
  [run 40474781959](https://github.com/op233qo123/FlashNest/actions/runs/40474781959),
  required to remain unchanged.
- `nested-repair-target.txt`: **experimental desired output**, derived from the
  control while retaining the nested variant's synchronous child reset. It is
  neither observed Adobe output nor a claim that the patch has already passed.

The Rust test runs at most 20 frames with bounded script execution and preload,
records raw output before assertions, requires all 12 observation ticks, and
stops after the complete engine frame containing `FO_DONE`. Consequently it
retains any already-queued child scripts after that ENTER_FRAME boundary.

```sh
python3 experiments/frame-order/engine-patch/check_patch_bundle.py \
  --source-file /path/to/pinned-ruffle/core/src/display_object/movie_clip.rs
python3 experiments/frame-order/engine-patch/stage_original_tests.py /path/to/pinned-ruffle
# From the disposable upstream checkout; use a fresh absolute trace directory:
FRAME_ORDER_ENGINE_PHASE=baseline FRAME_ORDER_TRACE_DIR=/path/to/evidence/baseline \
  cargo test --locked -p tests --test flashnest_frame_order --profile ci -- \
  --nocapture --test-threads=1
```

Only after baseline and unchanged official neighboring tests pass should the
patch be applied and the same gates rerun with `FRAME_ORDER_ENGINE_PHASE=patched`.
A failure is a blocker to candidate web-runtime production, not permission to
replace official expected output. Rust/core success is not a WebAssembly or
iOS/WebKit pass; a new candidate runtime must later receive independent native
capture with its own verified hashes.

## Provenance and redistribution boundary

`patch-manifest.json` records exact upstream/patched source and patch hashes.
Ruffle remains MIT OR Apache-2.0; its original copyright, complete license texts,
third-party inventory, Cargo/npm lockfiles, and dependency notices must be retained
with any candidate artifact. The candidate must identify this modification and
provide source correspondence (pinned source, exact patch, modified file, build
recipe and tool/dependency hashes), not claim to be the unmodified official release.

This experiment introduces no new runtime dependency. Existing MPL-covered and
other third-party components retain their respective terms and source references.
Promotion into an application requires reviewing the produced dependency inventory,
updating the application's runtime/license manifests and notices, and passing its
native/release gates separately. No such promotion is performed by this directory.

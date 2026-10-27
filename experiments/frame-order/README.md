# Original AVM2 nested-goto diagnostic (SWF37)

**Status: both original variants captured on pinned Ruffle 0.7.1 in iOS Simulator 18.2.** The nested variant reached the closed-stop path; the control executed the target/opening path. See [native measurements and limitations](NATIVE_RESULTS.md) and `runtime-status.json`. There has been **no exact Adobe Flash reference run or physical-device validation**. This isolated experiment is not part of the default release gate and does not establish a particular third-party game's cause. The earlier local Chromium launch failed before page/SWF execution and remains a separate unsuccessful attempt.

## Purpose and scope

Measure what the exact bundled Ruffle 0.7.1 runtime does when a parent frame script queues a goto to another parent frame, then calls a same-frame goto on its child. Separate **moving the playhead** from **running the target frame script**. Never infer that one implies the other.

Both SWFs are original, under 2 KiB, with no game code/assets, network, files, storage, audio, host bridge, or downloads. The public `trace()` API is their only reporting mechanism. The experiment does not change `App`, default `Tests`, default `fixtures`, or the release workflow. The manual-only `diagnose-frame-order.yml` workflow stages the harness and fixtures in its disposable checkout and uploads measurements, not an IPA.

## Two variants

- `fixtures/nested-child-goto.swf`: P.frame1 queues `gotoAndPlay("target")`, then executes `B.gotoAndPlay("reset")`, then returns.
- `fixtures/control-no-child-goto.swf`: identical semantics except it omits the child goto. The variant marker differs too.

P is the root MovieClip, with three frames (`init=1`, `target=2`, `after=3`). B is a persistent timeline child with seven frames (`reset=1`, `open=5`). P.frame2 reports entry, starts B at `open`, and stops P. P.frame3 reports that it was reached and stops P. B.frame4 reports/stops; B.frame5 reports opening; B.frame7 loops to `open`.

The small frame numbers replace real-game numbers deliberately. Labels are used for parent and child gotos. P-as-root is a reduction, not an assertion that the original nested-container context is irrelevant. Additional constructor/sibling/event interactions are excluded.

`source/*.as` are human-readable semantic counterparts, **not inputs to an ActionScript compiler**. `make_fixtures.py` is the authoritative, deliberately tiny ABC/SWF assembler. Its format was checked against official Ruffle [ABC writer](https://github.com/ruffle-rs/ruffle/blob/89a7049965f3090e706265670df309a5128233ac/swf/src/avm2/write.rs) and [opcodes](https://github.com/ruffle-rs/ruffle/blob/89a7049965f3090e706265670df309a5128233ac/swf/src/avm2/opcode.rs). No Adobe or external compiler binary was downloaded.

## Regenerate and structurally validate

From the repository root:

```sh
python3 experiments/frame-order/make_fixtures.py
python3 experiments/frame-order/validate_fixtures.py
```

`fixtures/manifest.json` records file SHA256s. The independent byte reader checks lengths, frame counts, labels, persistent placement, symbol bindings, all ABC pools/references/traits/methods, opcode boundaries, both branch paths, stack/scope balance, and exact EOF. `structural-validation.json` records the result. This does **not** replace a runtime verifier or establish Flash semantics.

## Trace contract

- `FO_VARIANT:<variant>` identifies the generated variant.
- `FO_P1_BEGIN <tick> <P-frame> <B-frame>` starts the frame1 observation.
- `FO_P1_AFTER_SELF_GOTO ...` observes after the parent goto returns.
- `FO_P1_END ...` observes after the optional child goto returns.
- `FO_P2_TARGET ...` proves the parent target frame script actually ran.
- `FO_P3_REACHED ...` proves parent frame3's script ran; do not label it a failure without reference evidence.
- `FO_B_RESET`, `FO_B_CLOSED_STOP`, `FO_B_OPENING`, `FO_B_LOOP` identify child script execution.
- `FO_STATE <tick> <P-frame> <B-frame>` observes each ENTER_FRAME callback.
- `FO_DONE 12 <P-frame> <B-frame>` finishes the measurement **during the twelfth observed ENTER_FRAME callback, before that tick's frame scripts**. It unregisters the observer and stops both clips after reporting.

Trace calls do not perform a goto or mutate timelines. The observer calls `stop()` on both clips only after `FO_DONE`; already-queued scripts can still run later in that tick and restart playback. Therefore `FO_DONE` is not a final settled-state report. Ignore `isPlaying` as an oracle: that getter has separate upstream compatibility issues. An incomplete trace, missing start marker, timeout, VerifyError, or buffer overflow is an **incomplete measurement**, never evidence that the target script was skipped.

## What source research establishes

At pinned commit `89a7049965f3090e706265670df309a5128233ac`:

1. A self-goto while the clip is executing a frame script queues its target and, when applicable, a cleanup entry ([movie_clip.rs 903–923](https://github.com/ruffle-rs/ruffle/blob/89a7049965f3090e706265670df309a5128233ac/core/src/display_object/movie_clip.rs#L903-L923)). Thus “target script always executes synchronously and then the outer tail overwrites B” is not justified.
2. A child no-op goto still starts a nested frame ([952–958](https://github.com/ruffle-rs/ruffle/blob/89a7049965f3090e706265670df309a5128233ac/core/src/display_object/movie_clip.rs#L952-L958)). SWF10+ nested frames clear the cleanup queue and process the stage ([frame_lifecycle.rs 129–157](https://github.com/ruffle-rs/ruffle/blob/89a7049965f3090e706265670df309a5128233ac/core/src/frame_lifecycle.rs#L129-L157)). SWF37 takes this path.
3. Recursive frame scripts on the same clip are blocked, but queued goto draining occurs outside that guard ([movie_clip.rs 2446–2500](https://github.com/ruffle-rs/ruffle/blob/89a7049965f3090e706265670df309a5128233ac/core/src/display_object/movie_clip.rs#L2446-L2500)). Therefore another clip's goto can move P's queued playhead early without executing P's target script then. Whether that script later runs depends on subsequent passes and must be measured.
4. Upstream [PR 7014](https://github.com/ruffle-rs/ruffle/pull/7014) documents Flash's same-stack recursion prohibition. Its [queueing expected trace](https://github.com/ruffle-rs/ruffle/blob/89a7049965f3090e706265670df309a5128233ac/tests/tests/swfs/avm2/movieclip_gotoandstop_queueing/output.txt) places parent frame5 after parent frame1 ends, despite intervening child gotos. The [nested-framescript expected trace](https://github.com/ruffle-rs/ruffle/blob/89a7049965f3090e706265670df309a5128233ac/tests/tests/swfs/avm2/goto_nested_framescript/output.txt) likewise finishes each self-goto caller before the target script.
5. The [contribution guide](https://github.com/ruffle-rs/ruffle/blob/89a7049965f3090e706265670df309a5128233ac/CONTRIBUTING.md#L167-L196) identifies such expected traces as Flash Player reference output. These upstream fixtures are **not the exact stripped fixture here**. No expected `output.txt` has been invented for this experiment.
6. [PR 24684](https://github.com/ruffle-rs/ruffle/pull/24684), already merged and represented in pinned code, expressly notes another case where nested processing runs a queued goto early. It does not prove this experiment or the user's game shares its final outcome. Current master inspected on 2026-10-27 retained the same relevant guard/drain structure; upgrading is not evidence of a fix.

## Measurements and next discriminator

The native captures and exact run/commit/runtime provenance are recorded in [NATIVE_RESULTS.md](NATIVE_RESULTS.md). Both variants have complete observations, obtained across two runs after one pre-load WebContent crash. The next discriminator is an exact Adobe-reference trace of these same original binaries; nearby upstream reference fixtures do not replace that comparison.

For a new independently authorized capture, use the standalone `FrameOrderRuntimeTests.swift` and `HARNESS.md` to stage an **opt-in diagnostic** in a disposable checkout. Capture raw trace and engine version/hash provenance for both variants; assert only that measurement completed reliably. Do not modify runtime behavior to force a presumed result. A Linux run would establish bundled-engine behavior, not iOS behavior. A native WKWebView run would establish iOS harness behavior, not Adobe reference behavior or a particular game's cause.

The exact Adobe comparison remains open. Reliable Ruffle traces alone do not select a compatibility fix: an engine experiment must preserve the observed Flash playhead and script ordering. No runtime change or claimed compatibility fix is included here.

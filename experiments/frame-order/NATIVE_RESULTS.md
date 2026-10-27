# Native simulator measurements — 2026-10-27

**Both original variants have complete captures. This is not an Adobe-equivalence test or a demonstrated cause of a third-party game's failure.** No third-party game code, assets, saves, or screenshots were used in these captures.

## Provenance

Both measurements used iPhone 16 **arm64 iOS Simulator 18.2**, Xcode 16.2, and the standard `macos-14` runner (reported host macOS 14.8.9). They used unchanged original SWFs, the same standalone harness, and the same pinned runtime. No physical iPhone or Adobe player was run.

| Capture | Workflow run | Repository commit | Outcome |
|---|---|---|---|
| Both variants | [40473436551](https://github.com/op233qo123/FlashNest/actions/runs/40473436551) | `a0ab1ffffee212903ea67e5d768aec4ad93f4b29` | Nested complete; control crashed before SWF request; workflow failed |
| Control only | [40474781959](https://github.com/op233qo123/FlashNest/actions/runs/40474781959) | `f086ac58cde9a085096b6402488456bc60c173c3` | Control complete; workflow passed |

The second commit adds only the manual workflow's `both`/`control`/`nested` selector. It does not change the app, runtime, fixtures, harness, or capture checks.

- Ruffle version: **0.7.1**; source commit: `89a7049965f3090e706265670df309a5128233ac`.
- Harness SHA256: `5beb4b3205cf5b7b8fe09a8b5cc0b946a235612501d2072a50ab255c7db92308`.
- Nested SWF SHA256: `ae3e561e8695a0be147e2192cd6d067eaa9462daedf92213bed86c9e4c4a4d8b`.
- Control SWF SHA256: `dd85e9f2b63b32199b7d04def4efbd80ccf68fb42da63cfe987e94358c49f030`.

Runtime SHA256s verified by both native captures:

| File | SHA256 |
|---|---|
| `ruffle.js` | `26036a94567088dfb3de88a759e8ed10a4cea07b29500af36f345eef42420098` |
| `172de42e6619eac8f371.wasm` | `1ed33b9b71a6b01b9aafafed660be343ffeb2d246c5d79e6425a32bf93e38207` |
| `878d548199cddef07035.wasm` | `af9b6a13a8f5e8d305bc3ce28a4edf3f6242df1183e8576ad4ca086e9f21eaea` |

Evidence artifacts (subject to GitHub's seven-day retention):

- First run: artifact `12719988411`, ZIP SHA256 `3aefee2c8a4855d9ab12151a9d2ef979232d63ed9e912fececa0b2f58750aa44`.
- Control run: artifact `12719534918`, ZIP SHA256 `347e9e7ab4a5cac9b11688ee88b6d3065011a7132ad3a972fbe3cd9092b4dc7d`.

## Measured trace contrast

Each state marker has `tick parentFrame childFrame` fields. These are **actual observations, not expected Flash output**.

Nested variant, selected lines from its complete 20-row trace:

```text
FO_P1_BEGIN 0 1 1
FO_P1_AFTER_SELF_GOTO 0 1 1
FO_B_RESET 1
FO_P1_END 0 2 1
FO_STATE 1 3 2
FO_P3_REACHED 1 3 2
FO_STATE 2 3 3
FO_STATE 3 3 4
FO_B_CLOSED_STOP 4
FO_STATE 12 3 4
FO_DONE 12 3 4
```

Control, selected lines from its complete 31-row trace:

```text
FO_P1_BEGIN 0 1 1
FO_P1_AFTER_SELF_GOTO 0 1 1
FO_P1_END 0 1 1
FO_P2_TARGET 0 2 1
FO_B_OPENING 5
FO_STATE 1 2 6
FO_STATE 2 2 7
FO_B_LOOP 7
FO_B_OPENING 5
FO_STATE 12 2 7
FO_DONE 12 2 7
FO_B_LOOP 7
FO_B_OPENING 5
```

In the nested variant, the child same-frame goto moves the parent's queued playhead to frame2 before frame1 returns. The target frame2 script does not take effect during the capture: no target/opening marker appears, parent frame3 executes instead, and child frame4 executes its closed-stop script. In the control, frame1 returns while the parent is still on frame1, then target frame2 executes and starts the child's opening loop.

Both successful captures have sequential rows, all observer ticks1–12, matching raw-text/JSON traces, and no overflow, truncation, operational error, snapshot error, or cleanup error. An independent artifact review agreed with this interpretation. Tests assert capture completeness only, **not** which ordering is correct.

**Observation boundary:** `FO_DONE` is emitted during ENTER_FRAME12, before that tick's scripts. It is not the final settled state. The control's already-queued child frame7 script runs afterward and restarts the opening loop, explaining its two post-DONE lines. The observer's `stop()` calls do not cancel every already-queued frame script.

The first control attempt crashed before its SWF request: WebContent `EXC_BAD_ACCESS`/`SIGSEGV` at address `0x40`, with JavaScriptCore WASM-call trampolines in the faulting stack. This is not a jetsam report, and its underlying defect is unknown. Its empty trace is not used as frame-order evidence. The unchanged isolated control subsequently succeeded, with no collected crash reports; no startup-reliability fix is claimed.

## Source correspondence and remaining gap

The pinned source [queues a self-goto](https://github.com/ruffle-rs/ruffle/blob/89a7049965f3090e706265670df309a5128233ac/core/src/display_object/movie_clip.rs#L903-L923), processes a [child same-frame goto as a nested frame](https://github.com/ruffle-rs/ruffle/blob/89a7049965f3090e706265670df309a5128233ac/core/src/display_object/movie_clip.rs#L952-L958), [clears the cleanup queue](https://github.com/ruffle-rs/ruffle/blob/89a7049965f3090e706265670df309a5128233ac/core/src/frame_lifecycle.rs#L129-L157), and drains queued gotos [outside the same-clip script-recursion guard](https://github.com/ruffle-rs/ruffle/blob/89a7049965f3090e706265670df309a5128233ac/core/src/display_object/movie_clip.rs#L2446-L2500). This provides a source-level explanation consistent with the measured contrast.

Nearby official Flash-reference tests are not exact substitutes. In particular, [movieclip_gotoandstop_queueing](https://github.com/ruffle-rs/ruffle/blob/89a7049965f3090e706265670df309a5128233ac/tests/tests/swfs/avm2/movieclip_gotoandstop_queueing/output.txt) re-queues the parent from the child; our nested fixture returns without that extra parent goto. Other inspected self-goto, same-frame, constructor, and cleanup tests have different control flow. No exact reference output was found in that scoped review.

Upstream [PR24684](https://github.com/ruffle-rs/ruffle/pull/24684) documents a related unresolved early queued-goto case; it is not proof of identical behavior. Current master inspected on 2026-10-27 (`fe6cfc545405b888ebb478ce1c211d63147ca49b`) retains the relevant guard/drain structure. No ready, validated fix for this exact fixture was identified. There was no previous-version bisect, so this is not a demonstrated historical regression.

**Next discriminator:** obtain traces of these exact two original binaries from a trusted existing Adobe debug-player environment, recording player version and SWF hashes. Until then, delaying the whole queued goto versus only its target script remains an unresolved compatibility choice. Do not substitute a speculative runtime patch, download an unknown legacy player, or infer a third-party game's execution path from this reduced fixture alone.

# Original-fixture headless repair experiment

## Verified run

[Run 40489965702](https://github.com/op233qo123/FlashNest/actions/runs/40489965702)
completed successfully on 2026-10-27 at experiment commit
`f60ff6a99941937056eee5ad94ed4b4af9c72c99` using a standard `ubuntu-24.04`
runner (image `20261023.334.3`). Rust was pinned to `1.99.1`; upstream Ruffle
source was exactly `89a7049965f3090e706265670df309a5128233ac`.

The only engine source change was the reviewed queued-goto guard patch, SHA-256
`de0acabdf957fccbc11966b67defd0a7f577cdc5a147db949e0a4f0e56c6331f`.
Both phases used the same original SWF37 binaries and unchanged test expectations.

| Gate | Unmodified baseline | Experimental guard |
| --- | --- | --- |
| Original control trace | Exact 31-line match | Same exact 31-line match |
| Original nested trace | Exact 20-line stalled baseline | Exact 32-line repair target |
| Adjacent strict upstream reference cases | 29/29 pass | 29/29 pass |
| Existing upstream known-failure preservation cases | 2/2 preserved | 2/2 preserved |

All 62 adjacent-case logs report exactly one passed test, zero failures and zero
ignored tests. The two known-failure cases retain their existing Ruffle outputs;
they are **not** additional Adobe-equivalence passes. No selected case was
skipped, and no upstream golden or comparison was changed or disabled.

## Observed change

In the baseline nested fixture, the parent's target frame script is not observed,
the parent advances to frame 3, and the child reaches its closed frame 4 stop.
With the guard, the parent remains on frame 1 until its current script returns;
then `FO_P2_TARGET` executes, the child emits `FO_B_OPENING 5`, and its opening
loop is observed throughout the 12-tick window. The control trace is unchanged.

The exact raw trace SHA-256 values are:

- Control, both phases: `cb1f8c5a8f0770d7ed9c92fd3219dc11294746258fa9a4ec8558c82eda9626c0`
- Nested baseline: `1ef37bcc059380e33b2140536dea771d9b647b8a20bdf01c015a5493269d04ef`
- Nested patched: `57648847e013eb2aaa9e45a91eb0a55c66c97862defd8e3c1cd5b74ef4e3c2ae`

The patched trace includes the already-queued child loop/opening pair after
`FO_DONE 12`. That marker is an ENTER_FRAME observation boundary, not a guarantee
that all scripts for the frame have finished or that the child remains stopped.

## Evidence and limits

Artifact `FlashNest-experimental-frame-order-engine`, ID `12729096589`, contains
the raw traces, all per-case logs, complete 31/31 phase summaries, applied source
diff and build provenance. Its downloaded ZIP was independently checked against
SHA-256 `9dceac854fe48f17aa50a03ec804c0f5104116ab30631110f443d8cba63235e3`.
Artifacts have seven-day retention; the committed expectations preserve the
reported original trace bytes, but are not a substitute for the raw run evidence.

This is measured **headless Ruffle-core** behavior, not a WebAssembly or
iOS/WebKit pass. The exact original fixture has not been run in Adobe Flash, so
the repaired trace remains an explicitly experimental target, not an Adobe
golden. The adjacent reference cases reduce regression risk but do not prove
global compatibility. This experiment contains no third-party game assets and
does not establish the cause of any particular game's behavior.

The run deliberately used `build_web=false`; it produced no candidate web
runtime and changed no bundled application runtime. Candidate construction and
native validation are separate gates before any promotion can be considered.

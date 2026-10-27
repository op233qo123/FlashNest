# Native save-memory A/B — manual, no IPA

`measure-save-memory.yml` is a separate **manual-only** workflow on the standard
`macos-14` runner, Xcode 16.2 and an installed iOS 18.2 iPhone simulator. There is
no dispatch in the implementation task and no automatic push/PR trigger.

Both worktrees start at `a09ccefc4513b617a88898a3d1e4dfb6eaea91f9`. The exact same
reviewed `SaveStoreMemoryTests.swift` is copied into each. Only the patched arm's
`App/Models/SaveStore.swift` differs. Staging fingerprints every tracked file and
rejects any other difference, including runtime/engine/version changes. Source
and test fingerprints are deliberately pinned in `benchmark.py`; future changes
require review and corresponding updates, not silently measuring new code.

Each arm builds Debug without coverage and executes the same two tests:

1. Eight distinct 1 MiB synthetic SOL-header objects roundtrip with independently
   computed checksums; a ninth object is rejected without changing current.json.
2. Five `XCTMemoryMetric` and `XCTClockMetric` iterations of the unchanged-current
   save path. Fixture preparation and initial current-save creation are outside
   measurement. These fixtures do not load or execute SWF/game code.

The helper sets `FLASHNEST_MEASURE_SAVE_MEMORY=1` in the **generated xctestrun
test target EnvironmentVariables**, not merely in the CI shell. The patched plan
is retained. Tests must be exactly the expected two, passed with **zero skips**;
the log must contain five finite values for both memory and clock measurements.
Unexpected result formats fail closed and retain raw results for diagnosis.

Both arms use the same simulator UDID, reset before each run. Baseline runs first,
patched second, sequentially with no parallel testing. Both arms are attempted
if setup succeeded even when the baseline test fails. A failure is not hidden by
the second arm. All raw `.xcresult` bundles, logs, per-test summary JSON, metric
values, xctestrun, source fingerprints, delta, toolchain and host metadata are
retained for seven days; download them before expiry. No IPA is created.

The comparison reports raw values and patched-minus-baseline median differences,
not a pass/fail threshold for memory improvement. Five samples on one hosted
simulator are noisy and order-biased; allocator state, process startup, physical
memory sampling and shared host load can overwhelm a small lifetime change.
[Apple documents XCTMemoryMetric](https://developer.apple.com/documentation/xcode/preventing-memory-use-regressions)
as measuring peak use and growth during the block. These are native app-process
measurements, **not WebContent/GPU or real-game measurements**, and provide no
causal evidence about the earlier Wasm SIGBUS or whether that crash was OOM.

Local harness checks (no simulator required):

```sh
python3 -m unittest discover -s experiments/save-memory -p 'test_*.py'
bash -n experiments/save-memory/run_variant.sh
```

Native A/B results are pending until an authorized manual workflow run finishes.

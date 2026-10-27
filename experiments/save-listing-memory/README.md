# Populated native save-listing memory A/B

**Implementation and harness only; native results are pending.** No workflow is
dispatched automatically. `measure-save-listing-memory.yml` is manual-only and
uses the standard hosted `macos-14` runner, pinned Xcode 16.2 and an installed
iOS 18.2 iPhone simulator. It creates no IPA and executes no SWF/game code.

## Controlled comparison

Both source trees start at `967a0a3f37ab842b8ebddffc0daa0d7237d8ad13`, which
already contains the earlier decoded-buffer checksum change. In the patched
tree, only production files `SaveStore.swift` and `SaveAreaView.swift` are
replaced. The new nine-case summary correctness test is patched-only. The exact
same `SaveListingMemoryTests.swift` is copied into both trees. All four reviewed
input hashes are pinned, and every tracked source file is compared before build;
runtime, version and unrelated application changes are rejected.

There is one intentional harness selection difference: the patched build adds
`-DSAVE_METADATA_LISTING`, selecting its new summary API; the baseline selects
the existing full-snapshot API. This is not claimed to be identical compiled
test code. Fixture data, measurement boundaries, simulator UDID, Debug build,
disabled coverage, five iterations and output lifetime are otherwise identical.

`generate_fixtures.py` produces six named archives plus current.json, with eight
distinct 1 MiB inert SOL-header objects per archive. Generation happens in the
host Python process **before build**, not in the measured app. Both generated
manifests and all seven archive hashes must match. Five named archives fit within
the unchanged 64 MiB listing read budget; a sixth exceeds it and must produce one
invalid-file count, not additional retained rows. The test holds five returned
rows and current-save data through measurement end, then releases them before
the next measured interval. No arbitrary sleep or allocator purge is used.

The baseline output contains **67,108,992 UTF-8 bytes of SOL base64 values**;
the metadata output contains zero SOL values. This logical-retention assertion
is **not** a physical-memory measurement. XCTest separately records physical
peak/growth and clock metrics. No fixed threshold is used to force an improvement.

## Safety and evidence gates

The patched arm first runs exactly nine native summary tests (identity,
ordering, current/backup metadata, corrupt neighbor recovery, stale/deleted/
replaced/symlink export refusal, bounded name metadata, archive and directory
limits). It then runs the listing measurement in a fresh test process after a
full reset of the same disposable simulator, preventing the safety tests' large
allocation history from contaminating the benchmark. The baseline measurement
also starts after a simulator reset. Baseline runs first, patched second; no
parallel testing. Baseline failure does not prevent the patched attempt, but any
failed step still fails the workflow. A failed patched safety test blocks its
dependent measurement rather than being hidden.

The helper edits the actual generated `.xctestrun` target's EnvironmentVariables
to opt in `FLASHNEST_MEASURE_SAVE_LISTING=1`, and sets exact test identifiers.
The measured arm must pass exactly one named test with zero skips and five finite
values for memory and clock metrics, plus the unique expected payload marker.
The safety run must pass exactly nine named tests with zero skips. Wrong device,
missing metrics, unknown formats, duplicate tests, skipped opt-in or wrong marker
fail closed. The same simulator identity is required for all three invocations.

Artifacts retain all three raw `.xcresult` bundles, logs, metrics/summary JSON,
xctestrun plans, source/fixture manifests and toolchain/host metadata for seven
days. Large generated input archives are reproducible from the included generator
and hashes; they are not uploaded. Compare raw values and medians cautiously:
single-run hosted-simulator results are affected by allocator state, sampling,
host load and baseline-first order. Native listing evidence says nothing about
WebContent/GPU/gameplay RAM or the earlier SIGBUS/OOM question.

Local validation:

```sh
python3 -m unittest discover -s experiments/save-listing-memory -p 'test_*.py'
bash -n experiments/save-listing-memory/run_variant.sh
```

# Synthetic restart ownership / representable identity controls

Three diagnostic XCTest methods only. `stage_controls.apply_overlay(app)` adds `Tests/RestartOwnershipDiagnosticTests.swift`; approved PlayerView source and exact copied conditional/representable blocks are pinned. All existing source (including App and stale-callback tests) stays unchanged, with an exact inverse file map. No package runtime is loaded by these tests.

1. Blank WK under container + explicit owner: both alive, clear explicit owner to establish container-only retention, restore explicit owner then detach, drop explicit owner, observe weak reference for ≤3 seconds. Weak timeout is inconclusive, not proof of a permanent leak; weak nil is wrapper release, not GPU/process memory reclamation.
2. Source-copied optional representable, old→nil→new in one MainActor turn, no await between assignments.
3. Same copy, first confirm nil branch has no WK and old is detached, then assign new.

The original conditional branch (including else ProgressView) and make/update are copied exactly. Synthetic model failure is nil and progress message constant; this is NOT actual PlayerView/PlayerSession. Identity controls deliberately strongly retain both WK objects for comparison, so they do NOT test weak release. Each records 40 samples at 50ms intervals, actual hierarchy identities as booleans, and final identityMatches. All methods have a 30s XCTest allowance. No .id intervention, navigation/JS/GPU recovery, product editing, or repeated restart.

`selection.json` has exact three selectors. JSON marker `FLASHNEST_OWNERSHIP_JSON ` and attachment name `ownership-{owners|same-turn|rendered-nil}` contain identical records, ≤32KiB each. Runner must verify exact external source/toolchain/selection binding and strict XCTest status separately, plus stdout/attachment equality. `verify_observations.verify_records(records)` validates three complete bounded observations, negative owner controls and typed results. It does not produce a healthy flag: same-turn identity mismatch can be the diagnostic finding; weak timeout is inconclusive. All reports preserve diagnosticOnly=true/nativeAcceptance=false/renderHealthCertified=false. Do not classify the user's gameplay scene-change crash as this synthetic boundary without separate evidence.

Local tests: `python native-restart-ownership-controls/tests/test_controls.py` (run from workspace root). Four Python methods cover source/inverse/drift, scope, result classification, malformed records. No Swift compilation/native result is claimed by these controls.

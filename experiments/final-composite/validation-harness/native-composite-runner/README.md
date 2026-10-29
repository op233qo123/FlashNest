# Consolidated native runner adapter

Authored only. No Xcode, simulator, dispatch or IPA ran here. This adapter consumes existing reviewed harnesses instead of creating new runtime behavior. Independent review and final source/artifact binding are mandatory before ready=true.

## Invocation

    DEVELOPER_DIR=/Applications/Xcode_16.2.app/Contents/Developer python3 native-composite-runner/run.py --app FINAL_MATERIALIZED_GATE_OFF_APP --candidate-engine VERIFIED_ENGINE_DIRECTORY --baseline BASELINE_BUNDLE --binding REVIEWED_BINDING_JSON --output NEW_EVIDENCE_DIRECTORY

All directories must be fresh/disjoint where copied. The candidate App already contains the exact candidate runtime; the adapter verifies that correspondence. Parent workflow installs XcodeGen2.42.0 from the checksum-pinned official archive and retains the exact archive. The adapter independently hashes that archive, reads its canonical xcodegen/bin/xcodegen member, compares the installed executable bytes and records a tool receipt; an optional independently pinned executable hash may also be supplied. No hash is invented. No package installation, credentials or network dispatch is performed by this adapter. xcodebuild resolves only the already locked ZIPFoundation package with automatic resolution disabled.

The baseline bundle has TWO non-interchangeable roles:

- sampling/runtime/ and sampling/runtime.files.json: exact delivered155candidate (4b85… and90aa… WASM), inventory SHA25d4453b0375349e55b9f63f609bd129d6a3549e1da792e811f0e5d121247e90.
- historical/runtime/ and historical/runtime-files.json: original late-audio fatal-control runtime (1bab… and8135… WASM), exact full map from native-save-audio-validation/diagnostics/baseline-runtime-identity.json.
- Each arm additionally has app-metadata/App/Resources/Web/{runtime-identity.json,Ruffle-MODIFICATIONS.md,Ruffle-THIRD-PARTY-LICENSES.md,THIRD_PARTY_NOTICES.md,licenses.manifest.json}. Every file is bound by external reviewed sha256+bytes maps. Baseline runtime bytes are never labeled with candidate identity. Candidate metadata is the actual final App metadata.

`binding-template.json` intentionally cannot execute. Populate appFiles with the complete frozen App tree path→sha map, engine provenance/inventory/artifact identities, exact helper-lock hash, tool identity, actual installed simulator names, per-arm metadata maps, and external per-arm sampling App manifests. The latter preserve all approved executable Swift/JS/CSS/resources and differ only in the five explicitly allowed metadata files. The sampler's source verifier rejects any executable change through this metadata mechanism. Parent must verify the actual installed devices/runtime and native observed DPR; model names alone never establish DPR.

## Exact sequence / counts

1. Gate-off main App:18 sampling/settings/session/status tests.
2. Sampling baseline4 and candidate7 methods on each observed DPR2/3:22 methods,52 matrix rows,156 phases. Expected identities are frozen from reviewed staging before any launch, not extracted from observed attachments. Actual native geometry, rendering, input and current status verifier must pass and establish one shipping policy supports all tiers before step3.
3. New gate-on main regression copy:18 same sampling methods +67 save/model/WK methods. Exactly one production constant false→true and one hardcoded XCTestFalse→True expectation change; every other test remains intact. Changes are recorded in gate-on-overlay.json. This does NOT modify the original input tree or publish/enable shipping.
4. Final candidate picker31 model tests plus1 real Files UI test. Separate picker-only source-app copy prevents its tiny fixture seed from replacing lifecycle fixture source. Original/private-copy byte verifier runs before simulator reset.
5. Existing lifecycle UI1 on the original lifecycle source app, fresh hosted simulator data.
6. Existing candidate late-audio2 and separate historical known-fatal1 using exact different runtimes; gate-off production source remains unchanged, audio diagnostic transforms are existing reviewed helpers.

Total161 native method executions, zero skips/failures/expected failures. Counts are distinct from52 sampling rows and are checked against exact source-backed method selectors, not whole-target selection. Picker baseline differential is not repeated; its earlier accepted result remains separate.

## Bounds and outputs

Serial xcodebuild, no automatic test repetition, no parallel simulators. Standard installed Xcode16.2/exactiOS18.2 only. Each command has a deadline (tests capped40minutes; per-method original bounds retained), a full16MiB log cap, and an aggregate128MiB evidence cap. Oversize/incomplete evidence fails, never truncates or passes by omission. Process groups are killed on deadline/budget failure. Full xcresult stays in the sibling staging directory; only complete summaries, full bounded logs and allowlisted PNG/JPEG/TXT/JSON attachments enter upload evidence. No videos, app-container trees, private games or saves are copied. Failed runs emit native-failure.json and retain completed results; never automatically retry an uncertain run.

Each suite invokes the strict save/audio summary-and-log verifier, including actual module/class/method names and iOS18.2. Audio uses its semantic record checker. Sampling has its separate external-identity/rendering/input verifier. Final native-acceptance.json supplies the agreed workflow receipt: actual selected candidate WASM hash, geometry requirement, exact shipping policies that achieved all reductions, a default=true claim only when automatic achieved them, simulator classification, results,161 methods, no physical-device/audible/private-provider/IPA claim.

Remaining unknowns are deliberate fail-closed inputs: final engine receipt/map and App metadata, installed runner model availability, compiled Swift/Xcode outcomes and actual native results. No local mock or source check can fill those unknowns.

## v2 semantic amendment

`nativeContract=flashnest-native-composite-v2` requires geometry contract
`flashnest-native-sampling-v2` with24 explicitly historical negative phases,
132 candidate current-input phases and936 trace-before-reset controls.
161 method selections remain, but the old contract is NOT claimed unchanged.
After geometry passes, candidate audio uses a fresh exact gate-on transform and
its entire production App inventory must equal the post-geometry gate-on main
App. The map and its SHA256 are emitted in the native acceptance receipt.
Historical fatal-audio negative still uses its unchanged gate-off App/runtime.
Audio staging permits only the inverse-verified exact runtimeValidated line;
metadata overrides cannot authorize executable changes. No low-tier activation
or audible output is inferred merely from this gate-on source binding.
New engine, browser and native execution are mandatory; prior receipts cannot
certify changed runtime/fixture/harness bytes.

After each successful exported sampling lane, early visibility rejection checks
12 baseline /66 candidate before-input screenshot hashes with the existing
verifier green-vector predicate. No thresholds/fallbacks are changed. Failure
uses normal artifact preservation; success is not acceptance and never bypasses
the complete52-row/156-phase final geometry/pixel gate.

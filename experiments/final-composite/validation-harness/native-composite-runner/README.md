# Current execution contract: v4 isolated DPR jobs

The active runner uses `selection-contract-v4.json`: 198 method executions (196 regression + 2 Enhanced boundary diagnostics), not the historical 166 described below. Two isolated macOS jobs each execute 2 baseline, 23 candidate and 1 Enhanced method; the dependent functional job verifies both immutable same-run/head/attempt leaf inventories and all 144 sampling phases before its 146 functional methods. Gate-off controls still precede gate-on tests. The original 48 rows, 720 taps, 144 drags, 864 resets and 150 capture sidecars remain required. Quarter/showAll lifecycle assertions remain in the same player after that tier's three orientations.

Each runner remains bounded by 7,800 seconds and each hosted job by 150 minutes. Splitting does not waive a failed, missing or timed-out method. Leaf success is never native acceptance. Per-arm builds, generated Info.plist, tool receipts and child results retain their own DPR job identity; compiled products need not be byte-identical across hosts. Only the exact independently pinned XcodeGen-generated App/Info.plist may be excluded from the audio source comparison. START/DONE/FAIL stage messages are flushed without private content.

The following sections preserve prior design/evidence history; v4 selection and actual new receipts govern current acceptance. No v4 native execution or IPA success is asserted by this source document.

# Native v3 — authoritative current contract

# Native v3 three-policy contract — authored, actual acceptance pending

Root-approved scope: candidate44rows132phases unchanged; historical DirectWebGL
4rows12phases as healthy reference. Matrix48rows144phases =36 shipping rows and12
explicit-quality diagnostics;720 real taps144 real drags864 post-UP RESETs.
Candidate132 phases require current touch coordinates/independent target deltas;
legacy12 phases preserve source-derived stale touch negative expectations.

## Exact native methods and role accounting

| lane/run | executions |
|---|---:|
| sampling-gate-off |18|
| sampling-gate-on |18|
| renderer-models |6|
| picker-models |31|
| save-models |48|
| save-webkit |19|
| picker-ui |1|
| renderer-ui |1|
| save-ui |1|
| audio-candidate |2|
| audio-baseline |1|
| sampling-baseline-dpr2 / dpr3 |2 each|
| sampling-candidate-dpr2 / dpr3 |7 each|
| enhanced-boundary-dpr2 / dpr3 |1 each|

166 total =164 regression executions (including explicit legacy negative
controls) +2 Enhanced configuration/error-boundary diagnostics. NOT166 rendering
health passes. No skipped/failed XCTest cases are accepted. Enhanced screenshot
health is reported separately and cannot enter the positive matrix.

## Real policy/source binding

Candidate Automatic and existing WebGL must pass the actual load argument
preferredRenderer='webgl', exact production query identity, and actual backend
webgl. No test forces this preference: it comes from the product shell. Passive
observeLoad forwards the identical config object/receiver/result/exception;
duplicates mark overflow, never suppress a call. Candidate Enhanced must forward
query enhanced and OMIT preferredRenderer/quality/reduction, preserving original
upstream renderer ordering. This is constructor preference, not recovery.

Candidate Automatic and WebGL Original/fallback exact pixels compare against
historical DirectWebGL sameDPR/mode/phase; reduced vector bounds/backing checks
unchanged. All input, quality/MSAA, lifecycle, real redirect/failure and native
status checks remain mandatory. Candidate original-tier input parity remains
per-policy; cross-arm tap coordinates/metadata remain checked independently of
known legacy target deltas.

Candidate63-App source authority is separately pinned; original baseline source
authority and exact5 metadata-only exceptions stay unchanged. The explicit
reviewed9-file product delta is inverted in FULL (App5 and4 tests/scripts) for
legacy sampling and historical fatal audio. Validate all candidate and inverse
hashes before modifying the disposable copy. Local test proves complete restored
tree equals accepted-before-app. No broad executable allowlist.

Candidate audio uses new candidate-input-lock.json plus the sole exact inverse
runtimeValidated gate line. Entire source App equals post-geometry gate-on main
App. Historical audio keeps original source lock/gate/runtime after9-file inverse.

## Enhanced boundaries and historical negative

Enhanced native method captures ready/5s/15s sameplayer automatic-order outcome
without gameplay input or rotation, then an existing real loopback navigation
failure. Actual production forwarding, sameepoch/CSS/times, one noScale READY,
noSWF pointer callbacks and real error/status visibility are asserted. Separate
Renderer UI test asserts visible limitation text, deferred Enhanced selection,
WebGL selection and explicit restart while preserving live synthetic state.

Enhanced observation reports bounded-visible, bounded-unhealthy or an unverified
backend. Always nativeAcceptance=false and platformRenderHealthCertified=false.
The explicit navigation-error check is NOT a claim that context loss itself
produces a user-facing error; that remains uncertified. No GPU/shader repair or
user-game compatibility investigation is included.

Historical baseline Automatic run40800398628 remains FAILED. Its exact snapshot,
zeroGL/context-loss, missing-vector crop, external identity and source provenance
are pinned in legacy-automatic-negative/. The old shell hash proves original
Automatic behavior was not rewritten. A verified known-negative report is not a
successful historical run and never substitutes candidate positive checks.

## Receipt/schema

nativeContract=flashnest-native-composite-v3; samplingContract=v3;
samplingRows48/samplingPhases144/nativeMethods166;
positiveRegressionMethods164/enhancedBoundaryDiagnosticMethods2;
enhancedRenderHealthCertified=false;
rendererPolicyContract=candidate-three-mode-v1;
legacyRendererPolicyPreserved=true;
legacyAutomaticKnownNegativeSHA256 hashes native output
legacy-automatic-known-negative.json (packet manifest is58371d6a…30ec7a).
Enhanced nested evidence is geometry.enhancedBoundaryDiagnostic: config/error
boundary verified, diagnosticOnly=true/nativeAcceptance=false, six independently
classified observed outcomes. Existing exact candidate-audio gate-on/source-map
fields remain mandatory.

Geometry contract=flashnest-native-sampling-v3;
historicalStaleDownNegativePhases12/candidateCurrentDownUpPhases132;
fixtureResetsAfterObservedUp864/shippingRows36/diagnosticRows12/phases144;
trustedTaps720/trustedDrags144.

Native binding must explicitly say nativeContract v3 and remain ready=false until
source/tool/runtime/candidate maps and helpers receive final review. Shipping
runtimeValidated remains false; nothing here builds an IPA or certifies a phone.
WASM bytes unchanged. Production browser policy must be rebound and all290 rows
rerun. Native must actually execute the new166 selection and complete matrix;
old161 or one-off healthy diagnostics are not substitutes.


---
## Superseded v1/v2 history (NOT the current selection or acceptance contract)

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

## Source-bound sampling build/run separation

Only sampling-baseline/candidate lanes are split. Each arm uses one fresh build-for-testing (600s command cap) from exact staged source/project/configuration. The source map excludes ONLY its dedicated build/ directory, explicitly recorded. The proof binds actual preflight Xcode/device/tool/binding receipt hashes, full Build/Products regular-file map, unique xctestrun SHA and resolved host/test/app paths. Symlinks, outside product references, unknown placeholders, ambiguous xctestrun files, source or product drift fail closed. Different arms never share products. Same-arm DPR reuse requires unchanged configuration/source/products and a destination from the preflight exact18.2 device inventory.

Each original selector runs once in XCTest lexical order via test-without-building and the exact pinned xctestrun/derivedData. Per-method900s remains; one-selector command cap1200s includes300s startup/finalization. Every child has its own completed xcresult/summary/log/export and original strict selector verifier (expected1, no fail/skip/duplicate). Source/product pins are checked before and after, even on failure. First failure stops: no automatic retry, no omitted selector accepted. Progress records preserve completed children and explicitly name failed/not-executed selectors. Immediate primary-error and separate extraction errors remain intact.

Only all2/7 children verified and pinned can create the original lane-level report. Children are nested evidence, not additional entries in native results; original166=164+2 roles remain unchanged. The four DPR/arm aggregate reports include buildProofSHA256 and children(selector,report,verificationSHA256). Two arm build proofs are named sampling-{arm}-build-for-testing-proof.json. Child attachments remain beneath the original lane attachment directory so existing recursive pixel/geometry checks still consume exact captures. No App/runtime/probe/input/pixel threshold or workflow changes.

The outer7800s process and150-minute workflow budgets are NOT increased. Theoretical sum of all per-method maxima cannot fit this aggregate cap; this change does not claim otherwise. Deadline exhaustion fails closed, preserving previously completed child evidence, and never manufactures acceptance. Remaining nonsampling commands retain their original caps. No native execution is claimed by local mocks; actual build-for-testing/xctestrun behavior must be verified by the next authorized run.

Enhanced boundary uses the already pinned candidate xctestrun too, without rebuilding or refreshing its proof; this prevents its intervening DPR2 diagnostic from mutating products reused at DPR3. It retains its original one selector,300s method/600s command and diagnostic-only role, pre/post pins and independent simulator reset. Missing prior candidate build fails; no extra compilation/recovery is attempted.

# Native sampling validation — authored, not executed

This isolated simulator harness is ready for source review and integration. Linux cannot compile Swift/Xcode or supply real WKWebView evidence. It does not enable the shipping gate or produce an IPA.

## Exact bounded scope

- Exact installed iOS 18.2, two simulator models whose *observed* UIScreen.scale and JavaScript devicePixelRatio are 2 and 3. Suggested models are iPhone SE (3rd generation) and iPhone 16 only if installed; no silent OS/model/DPR substitution.
- 40 shipping-default rows: two DPRs × automatic/WebGL-compatibility × showAll/noScale × (historical runtime Original + candidate four tiers).
- 12 explicitly diagnostic candidate rows: each DPR gets WebGL High all four tiers and WebGL Low Original/Quarter. The diagnostic-only load-quality hook is inactive in all 40 shipping rows. SWF `_quality` is never used as allocator-quality proof.
- Total 52 rows, 156 portrait/landscape/portrait-return phases, 780 trusted UIKit taps and 156 short drags. Exact synthetic SWF traces and actual canvas screenshots accompany each phase.
- Four candidate Quarter/showAll lifecycle records cover real WK message delivery barrier, background return, same-view reload invalidation and fresh save/restart. Two additional candidate records cover a real HTTP 302 initial navigation and a real empty-response WebKit failure. These are actual callbacks, not direct delegate invocations.
- Current UIKit-host overlay is a separate simulator target. Production App/shell/runtime bytes are never edited in place. Its three documented test hooks are: passive observation in PlayerSession, synthetic loopback redirect/failure, and diagnostic-only load quality. Candidate adds a separate one-line simulator gate activation. Native runtime resources remain exact reviewed release bytes.

## Default quality and physical evidence

The App shell omits quality. Existing runtime configureBuilder chooses Low if window.orientation is defined; Rust's High default only applies otherwise. The observer records the detected mobile branch and diagnostic launch quality separately. Legacy WebGL chooses its custom MSAA allocation at renderer construction and ignores later set_quality, so post-load SWF quality changes are not a valid control.

The observer reads real GL drawingBufferWidth/Height, canvas/client/CSS bounds, custom renderbuffer allocator call arguments, actual selected WASM resource name, trusted pointer events, actual backend console declaration and production status attributes. Allocator arguments alone are not proof of successful allocations: backing, screenshot/vector, input and baseline parity checks remain mandatory. `gl.SAMPLES` is deliberately not used to infer the custom framebuffer.

If a High diagnostic has no actual >1-sample WebGL2 allocation, the verifier emits an explicit unsupported control and exits nonzero. No High/MSAA pass is claimed. At least one *shipping* renderer policy must actually apply all three reduced tiers on both DPRs and modes; diagnostic Low success alone cannot enable shipping modes. WebGPU/Canvas observation is deliberately unsupported by this GL-specific native probe rather than fabricated as a pass.

## Staging and immutable identity

Read `scripts/prepare_overlay.py` before staging. It requires a disposable copy with NATIVE_VALIDATION_COPY.json containing `{ "disposable": true, "sdk": "iphonesimulator" }`. It verifies the full approved gate-off App map, exact runtime inventory and both release WASM files before edits. The historical baseline is the delivered 1.5.5 audio runtime but uses the same reviewed App shell with its sampling gate off.

Baseline command:

    python scripts/prepare_overlay.py --app DISPOSABLE_COPY --arm baseline --runtime-inventory-sha256 25d4453b0375349e55b9f63f609bd129d6a3549e1da792e811f0e5d121247e90

Candidate additionally requires `--candidate-freeze REVIEWED_FINAL_FREEZE.json`. That externally reviewed file must bind frozen=true, releaseEquivalent=true, runtimeInventorySHA256 and approvedAppManifestSHA256. The old audio-only runtime is rejected as a candidate. If final production App metadata/notices change, update/review the pinned App map explicitly; never bypass the source check.

Each staged copy produces NativeSamplingValidation/staging-provenance.json and SamplingIdentity.json. Before simulator launch, the workflow must preserve/hash both and freeze an external expected-identities.json object with keys `baseline` and `candidate`, each containing its exact SamplingIdentity.json. The result verifier compares every phase/lifecycle/navigation identity to this external map, including observer, approved App and staging provenance hashes, rather than trusting self-reported labels. Preserve source hashes, project overlay and test selector list with the run evidence.

## Native selectors and counts

Scheme: FlashNestSamplingUI. Target: FlashNestSamplingUITests. Class: NativeSamplingUITests.

Baseline on each DPR runs ONLY these four methods (no intentionally skipped candidate methods):

- testShippingAutomaticShowAll
- testShippingAutomaticNoScale
- testShippingWebGLShowAll
- testShippingWebGLNoScale

Candidate on each DPR runs all seven methods: the four above plus:

- testDiagnosticLaunchLowWebGLShowAll
- testDiagnosticLaunchHighWebGLShowAll
- testActualInitialRedirectAndNavigationFailure

Total expected XCTest methods: 8 baseline + 14 candidate = 22, zero skips/failures. Matrix row/phase count is separately checked; 22 tests is not 52 independent XCTest methods. Preserve xcresult exit status and strict selector/count validation. UI labels are asserted by actual XCUITest and screenshots; do not waive test failure because the attachment verifier passes.

## Result verification

Export actual xcresult attachments from all four device/arm runs into a bounded folder, preserving their bytes. Pass:

    python scripts/verify_results.py --attachments EXPORTED_ATTACHMENTS --candidate-inventory-sha256 FINAL_HASH --baseline-inventory-sha256 25d4453b0375349e55b9f63f609bd129d6a3549e1da792e811f0e5d121247e90 --expected-identities expected-identities.json --output result.json

The 128 MiB total evidence cap fails closed; do not truncate missing rows. All three phase records, screenshots, trusted pointer sequences, actual SWF geometry/hit/drag results, Original/fallback pixel parity, current status, lifecycle and navigation records are mandatory. Exit 2 means measurements were consistent but no shipping policy covered all reductions; exit 1 means failed/incomplete or unsupported diagnostic controls. No result changes runtimeValidated automatically.

## Validation performed locally

- Python verifier/source-anchor contract tests and transparent JS observer mock tests, recorded under evidence/. These are not native or rendered evidence.
- Disposable baseline staging succeeded and repeat application was rejected. Original full source inventory (206 files at this checkpoint) was unchanged; the pinned approved App manifest is separately authoritative.
- Fixture bytes are original synthetic AVM1 assembler output; no private games, archives, saves or videos.

Remaining mandatory work: independent final freeze review, final release artifact/App repin if needed, Xcode compilation, exact native execution and strict result review. Simulator results cannot certify physical-device GPU, RAM, audible output or universal scene-crash resolution. Only the naturally selected WASM branch is claimed executed. Other scale modes, non-center alignments, filter/cache/mask/context-loss matrices remain outside this bounded native scope.

### Per-arm metadata repin amendment

Staging additionally accepts --approved-app-manifest FILE and --approved-app-manifest-sha256 HASH. These must be independently reviewed before launch. The original manifest remains the executable/source authority: only runtime-identity.json, Ruffle-MODIFICATIONS.md, Ruffle-THIRD-PARTY-LICENSES.md, THIRD_PARTY_NOTICES.md and licenses.manifest.json may differ; all other App paths and the full file set remain identical. Baseline and candidate use distinct truthful metadata maps where their actual engine differs. Observed SamplingIdentity binds the effective per-arm manifest hash. This is not permission to alter code or bypass final review.

Actual WebGPU backend is named webgpu. It is recognized but fails the explicit GL-only probe boundary; the harness never forces another backend to hide missing WebGPU evidence.

## v2 input contract amendment (authored; new actual execution required)

This is **not** the unchanged old 161-method contract. Method selections remain
22 sampling / 161 total, while input semantics and fixture bytes are revised.
The old delivered baseline is an explicitly observed negative, not Flash reference
compatibility: DOWN reports the previous stored stage point; UP reports the last
MOVE (or DOWN when no MOVE), before storing release coordinates. Candidate DOWN
and UP must independently report the current event point.

- `independent_mouse_mapping.py` models f32 matrices and Twips/physical-pixel
  quantization for the known zero-origin 320×240, centered fixture. It is derived
  from source, never fitted/calibrated from DOWN or UP responses. Its five-point
  self-test reproduces the actual old diagnostic UP values; that check is not
  native execution or a Flash golden. Existing .15 numeric tolerance is retained.
- Passive canvas-target input observation captures offsetX/Y, client coordinates,
  rect, pointer identity and only the last MOVE of each contact (bounded storage).
  Offset versus client-minus-rect is checked independently. Resize keeps stored
  stage Twips; previous physical inputs use their old rect before re-reporting
  through the new viewport. No baseline defect is imposed on candidate output.
- Five real taps plus one real short drag per phase remain. Drag target comes
  only from fixture geometry and viewport, never callback-derived calibration.
- Each UP first stops drag and traces actual position/target, then traces actual
  onMouseMove count, **then** resets target to (100,70) and emits RESET. Six exact
  resets/order and actual positive drag movement are required. This original
  synthetic-fixture change makes subsequent-phase cross-arm pixels comparable;
  it cannot erase the recorded pre-reset drag failure. No host target mutation.
- Candidate tier DOWN/UP parity remains against candidate Original. The five
  valid tap-UP coordinates and Stage metadata also retain cross-arm parity.
  ALL six target values are independently checked using raw stage-Twips delta: a
  stale baseline DOWN that hits can move the target during a post-resize tap, even
  without a MOVE; a negative target before RESET is an explicit known negative. Legacy drag-UP is independently
  checked against its observed last MOVE rather than silently waived.
- Original/fallback full pixel equality, green-vector bounds, backing/GL ratios,
  trusted UIKit event counts, all lifecycle/navigation checks remain mandatory.
  Auto white/black screenshots still fail; READY never substitutes visibility.
- 24 baseline negative phases + 132 candidate current-input phases =156;
  780 taps +156 drags =936 pointer pairs and936 post-UP resets. These are
  semantic controls, not extra XCTest methods or executed evidence.

The passive before-input visibility snapshot is merged without extra rendering
work. All hashes must be newly reviewed and actual engine/browser/native runs
must use the revised runtime and this v2 contract before any package gate opens.

### Early visibility rejection (not acceptance)

After each exported lane, check_early_visibility.py requires12 baseline or66
candidate before-input snapshot/hash pairs and uses the exact unchanged
`green_bounds` predicate to reject blank/missing vectors before the next lane.
A successful early check does not prove full pixel parity, geometry, input or
runtime eligibility; the complete final verifier remains mandatory.

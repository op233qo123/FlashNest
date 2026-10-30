# FlashNest 1.5.6 build22 — accepted automated UI-validation limitation

Independent build-only release decision explicitly accepted by the user. This
recipe does not modify, substitute or mark the original selected16 gate passed.
Application XCTest methods executed in this packaging job:0. The pinned earlier
run passed15 App methods and failed1 UI method; the separately pinned final UI
run also failed. These results are not combined into a passing gate.

Reuse the frozen release recipe only for exact207 App staging and existing
artifact/source validation. No cleanup or diagnostic overlay is applied. Reuse
the same12 runtime assets and complete32-file Web payload, same bundle/save format,
version1.5.6/build22, diagnostics defaultOFF and existing sampling risk notice.
No engine rebuild, new optimization, product change, new fixture or full198 run.

The separate verifier preserves original generated Info/version, exact207source,
completeWeb/runtime, source-correspondence/licenses, outerpayload, unsignedarm64,
and test-probe exclusion checks. packageVerified=true means only those package
checks passed. selectedReleaseGatePassed/productionAccepted/native/full/physical/
crash-resolution acceptance remainfalse. Historical artifacts are pinned by full
ZIP size/hash, run/head and complete inventory, plus exact method/source evidence.

Public release wording: “稳定性优化。已知限制：模拟器 UI 自动化验证尚未稳定通过。”
No user content, conversation text or device-testing records are included.
An unsigned IPA still requires signing for device installation. Original failed
runs remain recorded; acceptedByUser identifies the release decision, not proof
of crash resolution. Dispatch defaults disabled until exact-scope review.

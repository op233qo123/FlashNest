# Bounded native ZIP-selection differential (manual only)

This experiment does not change shipping paths. It stages exact test-IPA155 App source from base commit `7f51087c662688bda6757df08d94c0aca7ae2e0e` with the previously reviewed `experiments/test-ipa-155` overlay, checks a SHA256 freeze of Swift sources/native tests/project/locked dependency/helper, then replaces only the picker Swift in the disposable checkout. Baseline and candidate have identical bounded callback diagnostics; only files-copy preference differs. Folder mode remains open-in-place. No UTI widening, broad file access or delegate guard relaxation.

## Native plan and budget

One explicit workflow dispatch, 2 serial standard `macos-14` jobs, hard 30 minutes each, maximum 60 runner-minutes. Public repository standard runners only; parent must verify repository visibility/free eligibility before dispatch. No larger/self-hosted runners, purchase, subscriptions or paid capacity. Exact installed Xcode16.2/iOS18.2 required; missing environment fails before builds. No runtime download or OS substitute. Simulator boot readiness is bounded to120seconds. Native summaries must show exactly31 passed tests and UI summary exactly1, no skipped/failed/expected failures, on one iOS18.2 simulator configuration; missing summaries/copy proof fail. Existing exact original engine artifact is retrieved/hash-verified, not rebuilt. Pinned XcodeGen2.42.0/checksum and ZIPFoundation lock are reused. No IPA/archive/package step.

Existing success precedent: `diagnose-picker-ios18.yml` and `FolderPickerUITests`; local `flashnest-diagnostics/ui15-pass/picker-test.log` has actual XCTest success (3 tests). The new ZIP journey is AUTHORED, NOT yet compiled/executed.

Each arm:
- Native existing PackageImporterTests, ImportFlowTests, ImportAliasTests, LocalImportInboxTests and ExternalImportInboxTests.
- Real system Files picker cross-container: Cancel before selection → ZIP tap/Open → Cancel preserving imported game → SWF tap/Open → repeated ZIP selection → whole-folder selection with nested asset. Require post-callback entry selector and exact visible library count.
- Source app writes only its own Documents. Test-owned original 132-byte ZIP and 18-byte SWF, plus a generated nested asset; no private game/save/video. Distinct synthetic filenames avoid ambiguity when Files hides extensions. No test calls importer/delegate or seeds FlashNest Documents.
- Post-journey host verifies only allowlisted synthetic source bytes, four private package contents and manifests, distinct containers, no symlink escape/no staging leftovers. Host checks are read-only; data reaches destination ONLY by actual system selection.
- Evidence: xcresult summaries, screenshots/AX attachments and test logs from fresh disposable simulator, code identities, fixed shape/boolean/hash copy report. No app-container export, user's device/account/files, credential output or raw user content. 1-day retention; maximum about 24 MiB evidence per arm (48 MiB total plus tiny inventories). Full head/tail build/setup/test failure logs are retained up to 2 MiB each; omissions/truncation are explicit in evidence inventory.

## Interpretation and limits

Local Files/AppDocuments simulator success is not affected-provider reproduction, iCloud/third-party account testing or physical-device proof. If both arms pass, report compatibility candidate regression safety, not observed bug fixed. User manually cancelled after tapping ZIP failed to import; cancellation is NOT evidence of automatic dismissal/race. Do not add a broad file-selection fallback without runtime/type evidence. Copy mode may require provider download/temp disk before callback; importer limits do not bound this preceding copy.

Existing 9 model/source checks are not native controller tests. This bounded workflow does not newly prove stale/duplicate/empty delegate callback handling, detached presenter recovery, every corruption/ratio-limit case, original deletion independence, large-archive disk pressure or unknown-provider behavior. These remain explicit coverage limits, not skipped tests relabeled passes. Tests execute unchanged importer guards; no safety limits lowered.

Publication/dispatch requires parent's review and confirmation. Stop/report exact environment or authorization blockers. Do not replace exact18.2 with another OS or rerun blindly. One final IPA is parent's separate responsibility.

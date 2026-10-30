# FlashNest 1.5.6 build22 release package

Release-channel packaging of the exact previously verified runtime. General stability improvements. Same bundle identifier com.flashnest.app, save format and business code; loading-phase diagnostics default OFF. The existing low-resolution experimental feature and its risk notice remain unchanged. No automatic upload.

Release channel describes distribution, not a promotion of the engine source or completion of full native regression. Original engine archive, provenance, source status, version seal and all 12 runtime assets remain byte-identical to engine run40998892881. Original productionAccepted=false and all full/native/physical/crash-resolution acceptance fields remain unchanged. The prior six-page desktop WebGL evidence is pinned, not described as native testing.

The unsigned arm64 IPA uses version1.5.6/build22. The existing nine loading-phase methods plus two runtime import methods, four save persistence methods and one lifecycle UI method form a selected 16-method gate. The gate must actually pass with no skipped cases before packaging. It is not the full198 suite. No engine rebuild, new fixture, identity patch or extra optimization is included.

Only version metadata and the build-specific license heading differ from build21 App source. Reconstruct the exact frozen build20 App and apply the same verified runtime/metadata operation; preserve complete source, archive, license, full Web, unsigned-device and source-correspondence checks. Dispatch defaults disabled until exact publication/build scope approval.

Proposed distribution: tag v1.5.6, title FlashNest 1.5.6; assets FlashNest-1.5.6-build22-unsigned.ipa and its SHA256 file. Signing is still required for device installation. Public release notes: “稳定性优化。” No user content or testing records are included in public materials.

## Reviewed test-only fixture isolation retry

The same 16 selected methods run once. Only Tests/RuffleRuntimeTests.swift receives
a reversible helper cleanup change: await the existing closeWithoutSaving API,
then detach the fixture window and release its ownership. Original body assertions
and 120/420-second method allowances are unchanged. This strengthens normal-path
fixture cleanup; it does not prove that every earlier failed-start server was
drained, that process memory was reclaimed, or that the crash cause is established.
No SharedObject test or production source is changed. The test receipt explicitly
binds original and actually executed test-source hashes; it never claims the
unmodified test file executed. Strict inverse restores all original207 files
before a passing receipt or Release build is allowed. Cleanup failure remains a
test failure; restoration failure blocks packaging.

On a failed lane, reuse the exact bounded sanitized crash collector with the
lane's PID/time window, waiting no more than15 seconds. Raw test logs/xcresult/IPS
remain runner-local; public test evidence is structured receipts and allowlisted
crash JSON only. A missing report cannot erase a test failure. When all16 methods
pass, no crash report is expected or claimed and notfound is not an extra gate.

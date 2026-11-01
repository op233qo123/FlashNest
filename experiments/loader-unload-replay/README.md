# Loader unload browser replay (no IPA)

The first run (`41318527222`, commit `3b0ab52a334336e6e6474e840e9c487e3f666f1d`) built the candidate engine and passed three bounded core regressions. Both browser arms executed all twelve neutral cases, but the browser job failed because the validator rejected expected cancellation and missing-resource diagnostics. The original failed receipts remain unchanged.

This workflow reuses only that exact engine artifact (`13089357368`, SHA-256 `dac0c326e29d2cfd354eb418000ac049fa7bdcfaa56b7693132f5799661d52c2`, 15,260,480 bytes) and its original core-test evidence. It verifies all six build files, all three engine source/patch/design files, complete source manifests, runtime closure and the original artifact checker. Engine/core producer identity remains the original run; browser consumer identity is recorded separately. No engine or core tests are represented as newly executed.

Only diagnostic classification, its tests and explanatory documentation change. The browser runner, page, fixture generators and baseline runtime lock remain byte-identical to the first execution. All fourteen generated SWF hashes are pinned and compared for both arms. The updated validator has twenty-two unit tests. This workflow executes both browser arms again; it does not reuse their earlier outcomes or claim additional fixture coverage.

These are bounded neutral regressions, not Flash-reference certification, private-game or physical-iPhone acceptance, measured GPU-memory reclamation, an application-wide fix, an IPA, or a formal release. Browser sandbox/security settings are unchanged. The workflow triggers only for this new replay recipe and its own workflow mirror, avoiding a redundant engine rebuild.

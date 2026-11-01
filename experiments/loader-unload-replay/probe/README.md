# Neutral UNLOAD engine regression probe

Original generated SWF/AS3 inputs only. No private game names, code or assets.
This test does not build an IPA or claim a reference Flash run, physical GPU
memory measurement, or complete application compatibility.

```sh
python run.py --runtime-root runtime/ --runtime-lock runtime-lock.json \
  --expect baseline --output evidence/baseline.json
# Repeat with candidate runtime/lock and --expect candidate.
```

Requires Playwright 1.51, system Google Chrome, Pillow 11.1.0. Chrome's normal
headless/GPU configuration and sandbox are preserved. Both unsafe SwiftShader
and devtools-self-XSS opt-outs are excluded from defaults; effective flags are
recorded and checked. All page network requests are confined to temporary
loopback. The actual player canvas must use WebGL.

The complete runtime file inventory and actual selected WASM response are checked
against the supplied lock. Same generated fixture hashes must be required across
baseline and candidate receipts. Each arm has an isolated page, recorded SWF
requests/status/body hashes, trace evidence, errors and a screenshot. Observation
continues 5.5 seconds after the outer unload call returns.

## Twelve arms

* attached-content / fresh next Loader (strict baseline control)
* moved-and-removed content / fresh next Loader
* moved-but-kept content / fresh next Loader
* attached content / SAME Loader replacement in the UNLOAD callback
* moved-and-removed content / SAME Loader replacement
* recursively unload once inside UNLOAD (fixture has a recursion guard)
* repeated unload after return
* unload with no previous load
* incomplete load cancellation (server delays bytes for 3 seconds)
* failed 404 load followed by unload
* retained script reference and static bitmap reattachment after unload
* ADDED callback unload before INIT, preserving the pre-INIT exposed-content case

Initial content/parent/loaderInfo identities must hold. Candidate continuations
require the complete callback/request/INIT/COMPLETE sequence, new content token,
Loader.content matching contentLoaderInfo.content, exactly one child, and old
content not still parented to the Loader. Recursive/repeated unload require a
single notification. No-load/incomplete/failed cases must not invent UNLOAD.
UNLOAD-time content visibility is observed separately for comparison; no new
Flash-reference expectation is invented for it.

Baseline known moved-content omissions and the attached/fresh control remain
strict. The previously unmeasured attached/same reentrant edge is a bounded
**observation**, not an oracle: after valid initial prerequisites and replacement
attempt it can record incomplete, errored, clobbered or complete final state.
Such a row has `engineCorrectnessPassed:false`; it never relaxes candidate gates.
Baseline recursive count 1 or 2 is reported explicitly, not called correct merely
because it was observed. `validationPassed` indicates a valid measurement
contract; `applicationPass` stays false.

## Static bitmap/cache-retention coverage

Each child contains an original 16x16 DefineBitsLossless2 ARGB bitmap, a
DefineShape3 bitmap-filled rectangle, and a placed static graphic. First bitmap
is red (230,30,90); next is blue (30,60,230). Dynamic background rectangles are
separate. The moved-kept holder is offset to x=128, outside the next child's
120-pixel-wide dynamic rectangle, so (136,8) samples the retained old bitmap
while (8,8) samples the new one. Retained-script reattachment also checks the old
red pixel. These are real screenshot pixel assertions (RGBA tolerance 2), with
DPR=1 and an exact 160x120 player screenshot. A COMPLETE trace alone is not a
rendered-frame proof. This exercises visible retained static bitmap rebuilding;
it does not measure texture deletion or prove a GPU-memory reduction.

`test_validate.py` uses synthetic receipts to test the evidence classifier; these
unit tests are not Ruffle execution. Generated fixture binaries are not required
in source control. Python/JS syntax and generation checks passed locally; actual
baseline/candidate runtime execution belongs to CI, not the blocked local browser.

## Expected cancellation diagnostics

The incomplete-load, failed-load and ADDED-before-INIT arms deliberately cancel
load work. Their receipts may contain at most one exact pinned
`web/src/navigator.rs:477` cancellation diagnostic; it is not ignored in any
other arm. Failed-load additionally requires exactly one pinned
`core/src/loader.rs:868` HTTP 404 diagnostic for the loopback
`/fixtures/missing.swf` resource. Message substrings, other resources/hosts,
duplicate diagnostics and unexpected runtime errors are rejected. Acceptance is
conditional on all of the arm's request, event, identity and observation-window
checks; the raw diagnostics remain in the receipt. This fixes classification of
an expected test operation, not engine behavior.

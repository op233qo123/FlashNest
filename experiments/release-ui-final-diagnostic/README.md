# Final one-method UI failure-location diagnostic

One existing Lifecycle UI method only, original assertions and waits unchanged
(including Play60s and method420s), in a new SE3/iOS18.2 simulator with the required
synthetic FixtureSource. No 15/16 rerun, no identity probe, engine change, product
change, Release build or IPA. This is the final localization run in this scope,
not an automatic retry-until-green loop.

Only the UITest source receives fixed checkpoint markers and XCTest failure
recording. The failure marker is emitted before super.record preserves the
original issue. Its source line is mapped back to the original frozen test.
All207 original source hashes and exact runtime identity are checked; the sole
executed UITest delta is explicit, then strictly inverted even on failure.

Public artifacts contain only safe enums, allowed source basenames/original line
numbers, integer counts and hashes, source-restoration summary, fixed control-ID
boolean AX observations, and at most one explicitly named synthetic App PNG.
No raw stdout, summary, xcresult, arbitrary attachment/export log, URLs, hierarchy
text, labels, paths, save contents or IPS are uploaded. The collector first reads
safe stdout markers so missing attachments cannot discard an available failure
location. The fixed testIdentifier and attachment names are required. Old Home,
import, arbitrary captures and other test attachments are always excluded.

Failure AX/PNG are best-effort: XCTest may abort at super.record. Screenshots are
excluded for import and background/Home phases. Missing evidence is explicit,
not success or proof a phase did not occur. Evidence collection adds no pass gate
and cannot erase an original failure. Total payload6MiB, one PNG at most3MiB,
three failure/scalar observations; only this public-evidence directory is uploaded.
The job ceiling is30minutes; all original assertion/method timeouts remain fixed.
Dispatch defaults disabled pending exact-scope review.

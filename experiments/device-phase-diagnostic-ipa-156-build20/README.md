# Default-off loading-phase diagnostic IPA — NOT a crash fix

User explicitly opted into a dedicated local diagnostic package. Version1.5.6 /
build20 keeps com.flashnest.app and the existing save format. Do not uninstall
the existing App or remove saves. Unsigned thin-arm64 iPhoneOS package requires
user signing. Xcode16.2 / SDK18.2 / minimum17.0 remain fixed.

This recipe reconstructs exact source9bc000e37695696f2427b25fe08efe4993bf22e5,
verifies all204 baseline App files, applies only the existing two-file experimental
low-sampling override, then applies a separately enumerated text overlay. The
final full source map, all Web bytes, runtime bytes, schema4 source correspondence,
licenses and unsigned device executable are independently checked. Engine run
40794075613/artifact12862634818 is unchanged. No game/save/private screenshot or
raw script traces belong in this package or its repository.

Loading-stage diagnostics are default OFF and apply on the next game opening.
When enabled they store only bounded local scalar metadata and anonymous session /
request identifiers; no automatic upload. Promise observers can change scheduling
and unhandled-rejection reporting: observation is not zero-interference. Server
completion means the local network stack accepted bytes, not client consumption;
client arrayBuffer fulfillment does not establish subsequent WASM copy, decompression,
parse, rendering or save completion. No measurement of WebContent memory or proof
of OOM / termination reason is provided. A missing phase may reflect interrupted
message delivery. Reproduction on the actual user's phone remains necessary.

The focused simulator tests validate the diagnostic subsystem and local loopback
contract; they do not replace full198 regression or certify physical devices.
NativeAccepted/fullGatePassed/physicalDeviceCertified/originalCrashResolved stay
FALSE. Enhanced renderer context loss and original scene-transition crash remain
unresolved. Full functional regression remains incomplete.

Only new reviewed experiment files under
experiments/device-phase-diagnostic-ipa-156-build20 and its distinct manual workflow
may be published after approval. Existing recipes, acceptance gates and runtime
source are not modified. No automatic dispatch or retry is part of this recipe.

Local tests: PYTHONDONTWRITEBYTECODE=1 python3 test_experiment.py

Existing baseline static suite contains obsolete schema3 expectations against the
unchanged schema4 runtime: baseline and candidate have the same10 failures/2 errors.
They are not reported as passing or repaired here. New package, focused diagnostic
JS/source controls and actual selected XCTest receipts are separate evidence.

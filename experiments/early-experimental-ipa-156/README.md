# Early experimental device-test IPA — NOT full native acceptance

Explicit user request: deliver an experimental package for physical-device testing
while the complete regression continues separately. This recipe is independent
of the disabled formal full gate. It neither waits for nor fabricates198 passes.

Frozen source9bc000e37695696f2427b25fe08efe4993bf22e5, accepted engine40794075613 /
artifact12862634818, same com.flashnest.app/save format, version1.5.6/build19.
Only the reviewed two-file sampling gate/test override changes the frozen204-file
App. Internal runtimeValidated=true is an **experimental override**, not a claim
that native validation succeeded. Low-sampling controls are intentionally enabled
for the user's test. No experimental warning code is injected into product source;
artifact name, provenance and delivery explanation carry the explicit limitations.

nativeAccepted=false; fullGatePassed=false; physicalDeviceCertified=false.
Full198 regression and functional146 remain incomplete. Enhanced/upstream renderer
has observed context loss; renderer health is not certified. Intermittent restart
behavior and original user crashes are not proven fixed. Prior peak RSS around
516MiB did not improve. Browser success is not physical-device acceptance.

Use macOS14/Xcode16.2/SDK18.2, one unsigned thin-arm64 iPhoneOS Release build,
minimum17.0. Requires user signing before installation. Preserve bundle/data;
never ask the user to delete their existing app or saves. Do not upload private
games, save files or user traces. Full source/runtime/Web/license/source-map byte
checks, schema4 correspondence and strict bundle payload checks remain mandatory.

Only publish the reviewed files under experiments/early-experimental-ipa-156 and
its separate manual workflow. Artifact name is distinct and explicitly
EXPERIMENTAL-UNVERIFIED. Formal full gate is unchanged and remains disabled.

Local test command: PYTHONDONTWRITEBYTECODE=1 python3 test_experiment.py.
Local mutation tests are not Xcode/device execution or full acceptance.

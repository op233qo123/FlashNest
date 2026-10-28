# Original AVM2 frame-order regressions

These two small SWF version 37 fixtures and frozen traces are exact copies of
the original experiment inputs in `experiments/frame-order`. They contain no
user-game assets or code. The generator/source description remains there.

`nested-child-goto.swf` models a parent frame script that queues its own target,
then calls a persistent child's reset frame label. `control-no-child-goto.swf`
omits that child reset. The frozen traces are the experimental repaired nested
contract (32 rows) and unchanged recorded control (31 rows), **not Adobe goldens**.

`Tests/FrameOrderRuntimeTests.swift` is a default regression for the exact shipped
FlashNest-modified runtime. It authenticates the compiled SHA256 of the bundled
`Web/runtime-identity.json`, its explicit experimental identity, and the complete
runtime file inventory before starting the player. Fixture and trace hashes are
also fixed in the test. The standalone candidate test retains its separate full
artifact/provenance/source attestation; that payload is not duplicated here.

The default test intentionally repeats only the bounded capture mechanics rather
than refactoring the already-measured historical harnesses. Its observer and
snapshot JavaScript are byte-identical to the standalone candidate harness.
Capture completeness is asserted independently from semantic agreement, with
raw traces, JSON reports, and awaited server-cleanup evidence retained.

`FO_DONE` is emitted during ENTER_FRAME tick 12, before already-queued child
scripts. The comparison preserves the exact prefix through that marker plus
the immediately following `FO_B_LOOP 7` / `FO_B_OPENING 5` pair. Any later raw
snapshot tail must consist solely of complete loop/open pairs and is explicitly
recorded. No unexpected early row is filtered and no settled final state is
inferred from `FO_DONE`.

The native candidate diagnostic measured those contracts successfully on iOS
Simulator 18.2; the default integration itself requires a new native build/run.
Neither result proves the user's full game follows this reduced path, nor that
the frame-order guard fixes an intermittent WebContent lifecycle crash.

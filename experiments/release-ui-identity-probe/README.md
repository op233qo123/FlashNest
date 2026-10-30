# Synthetic restart identity observation (local diagnostic overlay)

This is not a product fix or a release acceptance gate. It observes the existing
representable without replacing its UIView, adding `.id`, or changing restart,
save, rendering, input, pause, or timeout behavior. Run only the public synthetic
Lifecycle fixture in Debug with `--flashnest-identity-probe`.

`overlay.apply(app, state, source_map=inputs['candidateAppFiles'])` verifies the
frozen source map, transforms three Swift files, and adds IdentityProbe.swift.
Apply before regenerating the Xcode project. `overlay.restore(app, state)` first
rejects changed overlay hashes, restores exact original bytes, removes the new
file, and verifies every original source hash. The runner separately verifies
all 207 source paths and absence of extra product files. The generated diagnostic
Xcode project is not restored or used for a Release build; this is explicitly
recorded as generatedProjectRestored=false. The runner never treats UI results as a
formal release pass. State belongs outside the App directory.

Probe coordinator holds only weak references to session, represented WK, label,
and up to eight WK epoch entries. make/update observe the actual UIKit argument.
A one-second UIKit-only timer reads current model and window attachment; it does
not send SwiftUI changes or execute JavaScript. No raw pointers, URLs, trace
strings, or save contents are recorded. At most 420 samples report anonymous
identity epochs and scalar state. Epoch -1 means the eight-object cap was hit,
not a trustworthy equality result. `same` uses actual object identity separately.
Attachment means a nonnil window, not that a view is unobscured or its pixels
are current. Sampling/AX/logging can affect timing; this is not zero-interference
or a memory measurement. Sampling may miss transient states between ticks; a
false termination flag is not proof that no earlier termination occurred. A
sheet may hide the AX label; retained App console may supplement it, but console
absence must not be treated as a negative event oracle.

The existing Play wait remains 60 seconds and its success assertion remains.
A baseline requires observable schema 1, matching identity, and an attached
represented WK before proceeding; otherwise diagnosis fails explicitly.
At baseline, restart-before, restart-tap-after, Play timeout, and final exit the test keeps
at most 64 KiB AX text, 4 KiB scalar JSON, and one screenshot per checkpoint.
The initial Play failure could add one additional timeout checkpoint. Synthetic
AX can contain synthetic source paths; never run/upload this against user data.
The runner must export these bounded attachments from xcresult, with logs and
source maps; attachment absence is explicit missing evidence, not a pass.

Local validation: `python test_overlay.py`. These Python checks do not compile
Swift or demonstrate the defect. Actual Xcode compilation and simulator evidence
remain pending separately authorized execution.

Evidence retention is capped at 24 MiB payload, 3 MiB per attachment, 2 MiB per log. Oversized images are omitted with explicit size/reason, never truncated. Only bounded synthetic attachments and whitelisted log/receipt files are uploaded; overlay state, source backups and simulator containers are excluded.

## Current execution scope

Only the existing lifecycle UI method and its required FixtureSource app run. The App unit suite is not rerun: receipt unitNotRun=true. The earlier selected-unit run41011238103 remains failed, not promoted or erased. This targeted observation cannot satisfy the unchanged formal 16-method release gate. All original UI assertions, the 60-second Play wait, source/runtime checks, opt-in probe, and inverse-source verification remain unchanged.

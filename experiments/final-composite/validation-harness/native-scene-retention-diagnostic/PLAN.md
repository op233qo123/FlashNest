# Local-only retained-prefix diagnostic fixture plan

Two fresh WK cases: retained/released. Shared directory `retention/` contains
byte-identical `main-retain.swf` / `main-drop.swf` (branch by parent filename),
`prefix-a.swf`, `prefix-b.swf`, and unchanged prior bitmap `old.swf`/`new.swf`.
Prefixes load concurrently and both must emit INIT, COMPLETE, and first-frame
before normal old scene begins. Exactly one Space selects the old→new boundary.
Retained keeps both prefix Loader/content references. Released unsubscribes all
four listeners per Loader, calls normal unload, removes Loader, and nulls all
four Loader/content references. No forced GC. Reference counts mean logical
reachability in this fixture, NOT measured physical memory release.

Prefix decoded sizes exactly 48 MiB + 44 MiB = 92 MiB (including SWF headers),
using known DefineBinaryData ID 1 and deterministic entropy 45/40 MiB.
Prefix compressed total ≤86 MiB; complete generated package compressed ≤144 MiB,
SWF outer decoded streams total ≤154 MiB. Existing two 1024² bitmaps add
8 MiB logical nested decoded pixels, unchanged from the prior bitmap case;
these are not included in the outer-stream budget. No GPU/RSS/physical-memory
bound follows from these file and pixel sizes. Maximum generated local disk ≤512 MiB;
large generated SWFs are excluded from publication. Existing bitmap old/new
SWFs must match prior manifest SHA256 and sizes exactly.

Controlled AVM2 fixture, not a claim about private game's VM or resource mix.
DefineBinaryData shares decoded SWF storage; no ByteArray instantiated. Prefixes
have no textures/audio or private input. They do not reproduce arbitrary assets,
GPU memory, decode peaks, or game logic. No engine/policy/sampling changes.
No external publication, CI, or product changes authorized by this local plan.

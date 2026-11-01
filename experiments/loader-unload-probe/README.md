# Focused neutral Loader UNLOAD observation

This standalone recipe consumes exactly the accepted 12-file runtime inventory
and selected extensions WASM from `runtime-lock.json`. It does not rebuild or
modify the engine, app, IPA or private games. Original fixtures are generated
from a small local ABC writer, copied from the existing neutral FPS fixture.

Run:

```sh
python run.py --runtime-root /path/to/exact/runtime --output evidence/result.json
```

Dependencies: Python 3, Playwright (CI pins 1.51), installed system Google Chrome.
Use the ordinary GPU configuration and `chromium_sandbox=True`. The runner
explicitly excludes Playwright's unsafe SwiftShader and devtools-self-XSS
opt-outs, checks effective command-line flags, blocks all browser requests
outside its temporary loopback origin, and fails unless the actual player canvas
uses WebGL. No renderer fallback is silently accepted. Local browser execution
was blocked by the executor; generation/syntax checks alone are not runtime proof.

Two arms both create a FRESH Loader for the next scene in their UNLOAD handler:

* **attached-control:** first COMPLETE retains content inside Loader, transitions
  on the next ENTER_FRAME, removes Loader from root and calls unloadAndStop.
* **moved-removed:** first COMPLETE reparents content into a neutral Sprite;
  next ENTER_FRAME stops/removes content from that container, removes original
  Loader from root and calls the original Loader's unloadAndStop.

Parent identities and loaderInfo identities are traced and required true. INIT,
COMPLETE and UNLOAD count/order, newly constructed child, and exact next resource
responses are checked. Both arms are observed for at least 5 seconds after
UNLOAD_CALL_RETURNED; baseline must reach next completion. Absence of moved-arm
UNLOAD is classified as a reproduced neutral event omission only after those
prerequisites, the observation window and absence of errors are established.
If both arms deliver UNLOAD and finish, classification is not reproduced. No other
partial result is a pass. `validationPassed` means the observation contract ran
successfully, NOT application correctness: `applicationPass` is always false.

Receipts include source/fixture/runtime hashes, actual selected WASM hash, actual
neutral SWF response bytes/statuses, bounded traces/errors, effective browser
flags and screenshots of blue first/green next neutral content. Screenshots are
observational attachments; a COMPLETE trace is not a rendered-frame assertion.
No reference Flash player run or iOS/private-game root-cause claim is made.

# Additive DEBUG-only WKWebView smoke tests

`generate_native_probe.py` generates exactly `Tests/UnloadWKSmokeTests.swift`;
it never writes App resources or runtime files. Run before xcodegen:

```sh
python generate_native_probe.py --probe-root <validated-unload-probe> \
  --runtime-lock <candidate-runtime-lock.json> \
  --output-swift <staged-app>/Tests/UnloadWKSmokeTests.swift \
  --receipt <stage-output>/wk-smoke-source.json
```

Append these exact two methods to the native runner's selected-method contract:

* UnloadWKSmokeTests/testAttachedLoaderUnloadsAndContinuesInWKWebView
* UnloadWKSmokeTests/testMovedRemovedLoaderUnloadsAndContinuesInWKWebView

The existing test target includes `Tests` sources. No project product target or
production resource changes are needed. Embedded base64 SWFs reside only in the
DEBUG test source, not in the app bundle. The generated source receipt binds all
four SWF hashes, generator/template source, and the candidate 12-file runtime
inventory. Fixture bytes were checked locally to match those used in actual
candidate Chrome CI, not re-created from a private game.

Tests import the neutral folder through the actual PackageImporter, start the
actual PlayerSession/loopback server/bundled shell, attach its WKWebView to a
visible UIWindow, wait for the real instance and root SWF, then install a bounded
**test-only** trace observer before clicking Start. The observer avoids the
production 20-traces/second diagnostic throttle; it does not replace Ruffle,
mock events, change the shell, or change its network restrictions.

The native test verifies SHA256 of every bundled runtime file, records actual
WK WASM resource names, requires a real WebGL context on the player's canvas,
checks child responses, parent/loaderInfo identity, one UNLOAD and next completion
with final content token/child-count checks, and observes another 5.5 seconds.
The simulator may choose a different compiled WASM flavor than Chrome; both
flavors are hash-bound in the exact candidate runtime, and the actual loaded
resource name is recorded rather than claiming an unobserved flavor.

A kept JSON XCTest attachment and a `FLASHNEST_UNLOAD_WK_EVIDENCE` log line carry
the neutral observation, runtime/fixture identities and scope. No private file
paths/capability URLs are included. Synthetic clicking is execution smoke, not a
trusted audio gesture test. No screenshot pixel assertion or physical-device
claim is made here; the browser suite separately covers retained bitmap pixels.

**Status:** Python generator checks passed locally. This Linux workspace has no
Swift/Xcode/WKWebView, so the new Swift source is not locally compiled or run.
Only an actual simulator/device XCTest run with exactly these two methods and
zero failures/skips can establish native success. The original 76 native + 2 UI
regressions remain separate; do not promote them to this WK smoke result.

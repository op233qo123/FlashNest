# Build and verification

## Verified test artifact

- **1.5.2 / build 11:** [unsigned test IPA](https://github.com/op233qo123/FlashNest/actions/runs/40435351644/artifacts/12704167540), [successful build and 105 core tests](https://github.com/op233qo123/FlashNest/actions/runs/40435351644), [built source `d8bd574`](https://github.com/op233qo123/FlashNest/commit/d8bd5746fb8be08640abe6224bec2884a51d2f9e).
- IPA: **15,416,631 bytes**. SHA-256: `23f42906ea9f5a2434f152cccfb34679ff0c35c87522637fbad35b0974e469d0`.
- Direct save copies validated, nonempty game-written SOL data without destroying the live player; it distinguishes unchanged data. It cannot flush arbitrary pending Flash RAM or create an instant savestate. Save-and-restart performs final capture, closes the old page/listener, clears only transient cache types, then opens the same package. It preserves game files, localStorage and native archives; failure does not launch a replacement page. Public WebKit APIs do not guarantee immediate reclamation of every OS-managed allocation.
- Ordinary backgrounding pauses and retains the current page, with a best-effort written-save checkpoint. OS process termination may still lose unsaved scene state.

## Validation limits

- The core suite includes real Ruffle/WKWebView tests for written-save checkpoints, unchanged/empty/failure protection, checkpoint/close ordering, same-game restart, background RAM-marker continuity, imports and archive isolation.
- [An iOS 18.2 full run](https://github.com/op233qo123/FlashNest/actions/runs/40442002386) passed all 18 selected native tests and the three pre-existing Files/fullscreen UI tests. The new lifecycle UI journey did not pass that run's stale app-state assertion; its recording showed actual Home navigation.
- [Focused lifecycle evidence](https://github.com/op233qo123/FlashNest/actions/runs/40446652615) completed real Files import, trusted child input, Home/return continuity, paused-menu preservation, direct save, cancelled backup management and save/restart reading progress 420. The final assertion incorrectly treated a covered, noninteractive Library accessibility node as an exit; the recording showed the foreground game and preserved hidden controls. This is useful interaction evidence, **not a green automated test**.
- The corrected [follow-up run](https://github.com/op233qo123/FlashNest/actions/runs/40448243245) stalled in an XCTest interaction and exceeded its allowance. It did not pass. These later commits changed tests/workflow only; the shipped App sources are unchanged from the built source.
- Other iOS 18.2 runs intermittently crashed WebContent in Wasm execution; no causal fix or universal game compatibility is claimed. Native termination diagnostics provide no reason code. Simulator GPU evidence also contained SimMetalHost failures, which are not proof of device OOM.
- The unverified half-resolution experiment is excluded from App targets/resources and retained separately under `experiments/half-resolution`. Lower memory use remains future work, not a claim of this release.
- UI workflow default scope is `all`; explicit `lifecycle` runs only that focused journey and cannot stand in for full-suite acceptance.

## Build

Use macOS, Xcode 16.4 and XcodeGen 2.42.0 from this repository root:

```sh
python3 scripts/fetch_runtime.py
python3 scripts/test_static.py
python3 scripts/test_localization.py
python3 scripts/test_licenses.py
node scripts/test_shell.js
node scripts/test_shell.js zh-Hans
xcodegen generate
xcodebuild -project FlashNest.xcodeproj -scheme FlashNest -configuration Release -sdk iphoneos -destination 'generic/platform=iOS' -derivedDataPath build CODE_SIGNING_ALLOWED=NO CODE_SIGNING_REQUIRED=NO build
bash scripts/package_unsigned.sh build/Build/Products/Release-iphoneos/FlashNest.app artifacts/FlashNest-unsigned.ipa
```

The manual `build-unsigned.yml` workflow runs the full simulator XCTest scheme before building the device IPA. Failed tests block packaging; it does not substitute a different simulator when the matching installed runtime is absent. Review runner usage before dispatching. No signing credentials are needed; the resulting IPA requires external signing before installation.

Runtime JS/WASM/source maps are restored from the official SHA-256-pinned Ruffle archive, not committed to Git. Complete license files remain tracked. Packaging rejects simulator executables, missing runtime and unexpectedly signed applications.

Static checks and `test_shell.js` are not iOS runtime tests. `fixtures/` contains original synthetic SWFs for reproducible testing, not user games. The separate `diagnose-picker-ios18.yml` workflow runs the real Files picker and full-screen UI on an installed iOS 18.2 simulator.

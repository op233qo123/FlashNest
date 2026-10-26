# Build and verification

## Verified artifact

- **1.5.1 / build 8:** [unsigned IPA](https://github.com/op233qo123/FlashNest/actions/runs/40367909141/artifacts/12670429950), [successful build and 95 tests](https://github.com/op233qo123/FlashNest/actions/runs/40367909141), [source `c1fd6e8`](https://github.com/op233qo123/FlashNest/commit/c1fd6e81f2154f4223c3b40dd0a17c106023a89d).
- IPA: **15,372,095 bytes**. SHA-256: `bfafe9cba82ba6037232390f588c4879546459e6736d970bf369f44c74c20d1d`.
- [iOS 18.2 validation on the same source](https://github.com/op233qo123/FlashNest/actions/runs/40368031828): 10 targeted input/save/incident tests plus 3 real Files/full-screen UI tests passed.
- The real Ruffle/WKWebView input regression verifies child-movie loading and pointer callback, old unfocused-canvas key failure, then repaired host-focus key delivery. The termination test invokes the delegate signal and verifies archive preservation/reopen; it is **not** a reproduction of memory pressure or the user's game crash.
- Bounded last-session diagnostics persist fixed event/time/state metadata, not raw game output, paths, credentials or save payloads. They can be cleared from Diagnostics. SWF trace forwarding is rate-limited; rendering defaults are unchanged.
- User-reported scene-transition process termination remains unresolved without actual-device evidence. No test promises every Flash game's compatibility or preservation of unsaved progress after process termination.

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

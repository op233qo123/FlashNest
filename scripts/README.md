# Build and verification

## Verified artifact

- **1.5 / build 6:** [unsigned IPA](https://github.com/op233qo123/FlashNest/actions/runs/40346370319/artifacts/12663010141), [successful build and 89 tests](https://github.com/op233qo123/FlashNest/actions/runs/40346370319), [source `432a139`](https://github.com/op233qo123/FlashNest/commit/432a139610dcf462b1ea34133369f8abb704fa60).
- IPA: **15,345,590 bytes**. SHA-256: `4745322f9758225e5f1944b923746895ac7d64005cf9761d9043d91f3bfd4987`.
- XCTest covers real bundled Ruffle in WKWebView, multi-SWF assets, offline denial, 44 MiB Unicode-path transport, SharedObject save/restore, selected-game import, isolation, deletion safeguards and input models.
- Three iOS 18.2 UI tests passed on the earlier `0d3c` revision, including cross-app folder import and full-screen controls. UI code was unchanged afterward, but storage lifecycle code changed; those results are not a fresh UI run of `432a139`.
- Actual-device game playback was confirmed before this update. Version 1.5 save/control behavior on the user's device still requires confirmation. Tests do not promise compatibility with every Flash game or preservation of unsaved progress after force termination.

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

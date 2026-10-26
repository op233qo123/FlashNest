# Build and verification

The `.github/workflows/build-unsigned.yml` workflow is manual-only. Review GitHub account runner-minute costs before running; macOS builds can
consume billed minutes. No signing keys are needed.
The repository root for this workflow must be this `FlashNest` directory.

On a Mac with Xcode and XcodeGen 2.42.0:

```sh
python3 scripts/fetch_runtime.py
python3 scripts/test_static.py
python3 scripts/test_licenses.py
node scripts/test_shell.js
xcodegen generate
xcodebuild -project FlashNest.xcodeproj -scheme FlashNest -configuration Release -sdk iphoneos -destination 'generic/platform=iOS' -derivedDataPath build CODE_SIGNING_ALLOWED=NO CODE_SIGNING_REQUIRED=NO build
bash scripts/package_unsigned.sh build/Build/Products/Release-iphoneos/FlashNest.app artifacts/FlashNest-unsigned.ipa
```

The IPA contains a real device Mach-O executable, not source renamed as an IPA.
Unsigned artifacts require an appropriate external signing/install workflow;
they cannot be installed directly. Packaging rejects simulator builds, missing
executables, missing runtime, or unexpectedly signed apps.

`fetch_runtime.py` re-fetches the official pinned Ruffle archive, checks the
SHA256 before extracting, rejects unsafe archive entries, and includes upstream
licenses. No package manager or third-party install script is executed.

## Tests and exact limits

* `test_static.py`: bundled file hashes, WASM signatures, safety configuration,
  fixture SWF header lengths, and ZIP membership. Passed in Linux.
* `test_shell.js`: **mock** unit test for shell URL encoding, relative base,
  config and pause/resume method calls. Not Ruffle compatibility evidence.
* `make_fixtures.py`: reproducibly generates original AVM1 main + child SWFs and
  sibling text. Import `fixtures/multi-swf.zip` or its extracted directory.
* `serve_fixture.py`: loopback-only local fixture server on port 8766.
* `test_runtime_browser.py`: **actual Ruffle**, checks real bundled WASM request,
  child SWF trace, sibling text request, and pause/resume. Uses preinstalled
  Python Playwright and Chromium. Run the server first, then this script. This
  test requires a working local browser. Actual iOS playback remains unverified.

No successful Xcode build or iOS device test is currently recorded.
Touch-key delivery, WebKit audio gestures, SharedObject persistence, import flow,
and WKWebView WASM behavior require actual simulator/device acceptance tests.
The script keeps runtime integration testing distinct from mock/static tests.

## Manual workflow simulator gate

Before the device build, CI selects Xcode 16.4 explicitly, discovers an available
iPhone by UDID whose installed runtime matches its iOS Simulator SDK, and runs
the complete FlashNest XCTest scheme. It fails closed if that compatible runtime
is absent. The test step is limited to 15 minutes (overall job: 30 minutes);
individual tests have 60-second default / 120-second maximum allowances. Failed
tests block IPA packaging. Failure artifacts include test logs and xcresult.
The checkout and upload-artifact actions are pinned to commits verified against
their official v4 refs on 2026-10-26. This workflow has not been run here.

Runtime JavaScript, WebAssembly and source maps are intentionally excluded from Git. The manual workflow restores the exact SHA-256-pinned official archive before validation and bundles it into the iOS app. License/notice files remain tracked and are checked before build.

#!/bin/bash
set -euo pipefail
case "${TRANSITION_ARM:-}" in baseline|guarded) ;; *) exit 2;; esac
: "${TRANSITION_DEVICE:?}"
tree="$RUNNER_TEMP/transition-trees/$TRANSITION_ARM"
evidence="$GITHUB_WORKSPACE/transition-evidence/$TRANSITION_ARM"
mkdir -p "$evidence"
cd "$tree"
python3 scripts/fetch_runtime.py | tee "$evidence/runtime.log"
"$RUNNER_TEMP/xcodegen-pinned/xcodegen/bin/xcodegen" generate
mkdir -p FlashNest.xcodeproj/project.xcworkspace/xcshareddata/swiftpm
cp Package.resolved FlashNest.xcodeproj/project.xcworkspace/xcshareddata/swiftpm/
xcrun simctl shutdown "$TRANSITION_DEVICE" 2>/dev/null || true
xcrun simctl erase "$TRANSITION_DEVICE"
xcrun simctl boot "$TRANSITION_DEVICE"
xcrun simctl bootstatus "$TRANSITION_DEVICE" -b
xcodebuild -resolvePackageDependencies -project FlashNest.xcodeproj -scheme FlashNestUI -disableAutomaticPackageResolution > "$evidence/dependencies.log" 2>&1
xcodebuild build -project FlashNest.xcodeproj -scheme FlashNestFixtureSource -configuration Debug -sdk iphonesimulator -destination "platform=iOS Simulator,id=$TRANSITION_DEVICE" -derivedDataPath build-transition -disableAutomaticPackageResolution CODE_SIGNING_ALLOWED=NO CODE_SIGNING_REQUIRED=NO 2>&1 | tee "$evidence/source-build.log"
xcrun simctl install "$TRANSITION_DEVICE" build-transition/Build/Products/Debug-iphonesimulator/FlashNestFixtureSource.app
touch "$evidence/start.marker"
set +e
xcodebuild test -project FlashNest.xcodeproj -scheme FlashNestUI -configuration Debug -sdk iphonesimulator -destination "platform=iOS Simulator,id=$TRANSITION_DEVICE" -destination-timeout 120 -derivedDataPath build-transition -resultBundlePath "$evidence/Results.xcresult" -disableAutomaticPackageResolution -parallel-testing-enabled NO -maximum-concurrent-test-simulator-destinations 1 -test-timeouts-enabled YES -default-test-execution-time-allowance 120 -maximum-test-execution-time-allowance 480 -only-testing:FlashNestUITests/TransitionStressUITests/testThreeSceneLoadsWithRotationAndBackgroundPreserveLiveState CODE_SIGNING_ALLOWED=NO CODE_SIGNING_REQUIRED=NO 2>&1 | tee "$evidence/test.log"
status=${PIPESTATUS[0]}
set -e
printf '%s\n' "$status" > "$evidence/xcodebuild-exit-status.txt"
python3 scripts/collect_test_webkit_crashes.py "$evidence/start.marker" "$evidence/webkit-crashes"
xcrun xcresulttool get test-results summary --path "$evidence/Results.xcresult" > "$evidence/summary.json"
xcrun xcresulttool export attachments --path "$evidence/Results.xcresult" --output-path "$evidence/attachments"
python3 "$GITHUB_WORKSPACE/experiments/transition-stress/harness.py" verify "$evidence/summary.json" "$evidence/test.log" "$GITHUB_WORKSPACE" > "$evidence/verified.json"
test "$status" -eq 0

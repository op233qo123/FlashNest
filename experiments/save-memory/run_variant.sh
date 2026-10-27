#!/bin/bash
set -euo pipefail
case "${MEMORY_VARIANT:-}" in baseline|patched) ;; *) echo 'Invalid A/B variant' >&2; exit 2;; esac
: "${MEMORY_DEVICE_ID:?Require verified simulator UDID}"
helper="$GITHUB_WORKSPACE/experiments/save-memory/benchmark.py"
tree="$RUNNER_TEMP/save-memory-$MEMORY_VARIANT"
evidence="$GITHUB_WORKSPACE/save-memory-evidence/$MEMORY_VARIANT"
mkdir -p "$evidence"
cd "$tree"
python3 scripts/fetch_runtime.py | tee "$evidence/runtime.txt"
"$RUNNER_TEMP/xcodegen-pinned/xcodegen/bin/xcodegen" generate
mkdir -p FlashNest.xcodeproj/project.xcworkspace/xcshareddata/swiftpm
cp Package.resolved FlashNest.xcodeproj/project.xcworkspace/xcshareddata/swiftpm/
xcodebuild -resolvePackageDependencies -project FlashNest.xcodeproj -scheme FlashNest -disableAutomaticPackageResolution > "$evidence/dependencies.log" 2>&1
xcodebuild build-for-testing -project FlashNest.xcodeproj -scheme FlashNest -configuration Debug -sdk iphonesimulator \
  -destination "platform=iOS Simulator,id=$MEMORY_DEVICE_ID" -destination-timeout 120 -derivedDataPath "$tree/build-memory" \
  -disableAutomaticPackageResolution -enableCodeCoverage NO CODE_SIGNING_ALLOWED=NO CODE_SIGNING_REQUIRED=NO \
  2>&1 | tee "$evidence/build.log"
shopt -s nullglob
plans=("$tree"/build-memory/Build/Products/*.xctestrun)
test "${#plans[@]}" -eq 1
python3 "$helper" opt-in "${plans[0]}" "$evidence/opted-in.xctestrun"
# Disposable hosted-runner simulator, not a connected user's device. Both
# variants receive identical clean simulator state; no game is launched.
xcrun simctl shutdown "$MEMORY_DEVICE_ID" 2>/dev/null || true
xcrun simctl erase "$MEMORY_DEVICE_ID"
xcrun simctl boot "$MEMORY_DEVICE_ID"
xcrun simctl bootstatus "$MEMORY_DEVICE_ID" -b
set +e
xcodebuild test-without-building -xctestrun "${plans[0]}" \
  -destination "platform=iOS Simulator,id=$MEMORY_DEVICE_ID" -destination-timeout 120 \
  -resultBundlePath "$evidence/Results.xcresult" -parallel-testing-enabled NO \
  -maximum-concurrent-test-simulator-destinations 1 -test-timeouts-enabled YES \
  -default-test-execution-time-allowance 120 -maximum-test-execution-time-allowance 180 \
  -only-testing:FlashNestTests/SaveStoreMemoryTests 2>&1 | tee "$evidence/test.log"
test_status=${PIPESTATUS[0]}
set -e
printf '%s\n' "$test_status" > "$evidence/xcodebuild-exit-status.txt"
xcrun xcresulttool get test-results summary --path "$evidence/Results.xcresult" > "$evidence/summary.json"
python3 "$helper" verify "$evidence/summary.json" "$evidence/test.log" "$evidence/metrics.json"
test "$test_status" -eq 0

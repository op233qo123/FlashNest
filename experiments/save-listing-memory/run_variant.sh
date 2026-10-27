#!/bin/bash
set -euo pipefail
case "${LISTING_VARIANT:-}" in baseline|patched) ;; *) echo 'Invalid listing variant' >&2; exit 2;; esac
: "${LISTING_DEVICE_ID:?Require verified simulator UDID}"
helper="$GITHUB_WORKSPACE/experiments/save-listing-memory/listing_harness.py"
tree="$RUNNER_TEMP/save-listing-$LISTING_VARIANT"
evidence="$GITHUB_WORKSPACE/save-listing-evidence/$LISTING_VARIANT"
mkdir -p "$evidence"
cd "$tree"
python3 scripts/fetch_runtime.py | tee "$evidence/runtime.txt"
"$RUNNER_TEMP/xcodegen-pinned/xcodegen/bin/xcodegen" generate
mkdir -p FlashNest.xcodeproj/project.xcworkspace/xcshareddata/swiftpm
cp Package.resolved FlashNest.xcodeproj/project.xcworkspace/xcshareddata/swiftpm/
xcodebuild -resolvePackageDependencies -project FlashNest.xcodeproj -scheme FlashNest -disableAutomaticPackageResolution > "$evidence/dependencies.log" 2>&1
flags=('OTHER_SWIFT_FLAGS=$(inherited)')
if [ "$LISTING_VARIANT" = patched ]; then flags=('OTHER_SWIFT_FLAGS=$(inherited) -DSAVE_METADATA_LISTING'); fi
printf '%s\n' "variant=$LISTING_VARIANT" "configuration=Debug" "coverage=NO" "selector=${flags[*]:-none}" > "$evidence/build-contract.txt"
xcodebuild build-for-testing -project FlashNest.xcodeproj -scheme FlashNest -configuration Debug -sdk iphonesimulator \
  -destination "platform=iOS Simulator,id=$LISTING_DEVICE_ID" -destination-timeout 120 -derivedDataPath "$tree/build-listing" \
  -disableAutomaticPackageResolution -enableCodeCoverage NO "${flags[@]}" CODE_SIGNING_ALLOWED=NO CODE_SIGNING_REQUIRED=NO \
  2>&1 | tee "$evidence/build.log"
shopt -s nullglob
plans=("$tree"/build-listing/Build/Products/*.xctestrun)
test "${#plans[@]}" -eq 1

run_scope() {
  local scope="$1" class_name="$2" folder="$3"
  mkdir -p "$folder"
  python3 "$helper" opt-in --scope "$scope" "${plans[0]}" "$folder/opted-in.xctestrun"
  # Disposable hosted-runner simulator only. Safety and measurement launch in
  # separate processes with a full reset, avoiding safety-test allocation state.
  xcrun simctl shutdown "$LISTING_DEVICE_ID" 2>/dev/null || true
  xcrun simctl erase "$LISTING_DEVICE_ID"
  xcrun simctl boot "$LISTING_DEVICE_ID"
  xcrun simctl bootstatus "$LISTING_DEVICE_ID" -b
  set +e
  xcodebuild test-without-building -xctestrun "${plans[0]}" \
    -destination "platform=iOS Simulator,id=$LISTING_DEVICE_ID" -destination-timeout 120 \
    -resultBundlePath "$folder/Results.xcresult" -parallel-testing-enabled NO \
    -maximum-concurrent-test-simulator-destinations 1 -test-timeouts-enabled YES \
    -default-test-execution-time-allowance 120 -maximum-test-execution-time-allowance 180 \
    "-only-testing:FlashNestTests/$class_name" 2>&1 | tee "$folder/test.log"
  local status=${PIPESTATUS[0]}
  set -e
  printf '%s\n' "$status" > "$folder/xcodebuild-exit-status.txt"
  xcrun xcresulttool get test-results summary --path "$folder/Results.xcresult" > "$folder/summary.json"
  python3 "$helper" verify --scope "$scope" "$folder/summary.json" "$folder/test.log" "$folder/metrics.json"
  test "$status" -eq 0
}

if [ "$LISTING_VARIANT" = patched ]; then
  run_scope safety SaveStoreSummaryTests "$evidence/safety"
fi
run_scope "$LISTING_VARIANT" SaveListingMemoryTests "$evidence/memory"

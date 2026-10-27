#!/bin/bash
set -euo pipefail
# Input must be an iphoneos Release .app, never a Simulator bundle.
app="${1:?usage: package_unsigned.sh /path/FlashNest.app [output.ipa]}"
out="${2:-FlashNest-unsigned.ipa}"
[[ -d "$app" && -f "$app/Info.plist" ]] || { echo 'Missing app bundle' >&2; exit 1; }
exe=$(/usr/libexec/PlistBuddy -c 'Print CFBundleExecutable' "$app/Info.plist")
[[ "$exe" != */* && -x "$app/$exe" ]] || { echo 'Missing executable or permissions' >&2; exit 1; }
file "$app/$exe" | grep -q 'Mach-O' || { echo 'Not Mach-O' >&2; exit 1; }
xcrun lipo -archs "$app/$exe" | grep -qw arm64 || { echo 'Not arm64' >&2; exit 1; }
platform=$(/usr/libexec/PlistBuddy -c 'Print DTPlatformName' "$app/Info.plist")
[[ "$platform" == iphoneos ]] || { echo 'Not an iPhoneOS device build' >&2; exit 1; }
python3 "$(dirname "$0")/verify_bundled_runtime.py" "$app/Web"
python3 - "$app/Info.plist" "$(dirname "$0")/../App/Info-Debug.plist" <<'PY_VERSION'
import plistlib, sys
with open(sys.argv[1], "rb") as f: actual = plistlib.load(f)
with open(sys.argv[2], "rb") as f: expected = plistlib.load(f)
for key in ("CFBundleShortVersionString", "CFBundleVersion"):
    assert actual[key] == expected[key], f"Packaged version mismatch: {key}"
PY_VERSION
[[ -z "$(find "$app" -name embedded.mobileprovision -print -quit)" ]] || { echo 'Unexpected provisioning profile' >&2; exit 1; }
if codesign -dv "$app" 2>/dev/null; then echo 'Expected unsigned app, found signature' >&2; exit 1; fi
out=$(python3 -c 'import os,sys; print(os.path.abspath(sys.argv[1]))' "$out")
mkdir -p "$(dirname "$out")"
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
mkdir "$tmp/Payload"
ditto "$app" "$tmp/Payload/$(basename "$app")"
# zip updates existing archives; always create a fresh one so reruns cannot
# retain deleted resources or signatures from an older output IPA.
(cd "$tmp" && /usr/bin/zip -qry package.ipa Payload)
unzip -t "$tmp/package.ipa"
mv -f "$tmp/package.ipa" "$out"
shasum -a 256 "$out" > "$out.sha256"
echo "Unsigned archive created: $out (requires signing before installation)"

#!/bin/bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
# Optional arguments permit compiling the staged exact candidate product source.
SOURCE="${1:-$HERE/HTTPProtocol.swift}"
OUTPUT="${2:-$HERE/native-result.json}"
WORK="$(mktemp -d)"
MOUNT=""
cleanup() {
  if [ -n "$MOUNT" ]; then hdiutil detach "$MOUNT" >/dev/null; fi
  rm -rf "$WORK"
}
trap cleanup EXIT
if [ "$(uname -s)" = Darwin ]; then
  # macOS CI's normal APFS volume is frequently case insensitive. An APFSX
  # disk image, plus the Swift two-distinct-files assertion, prevents falsepass.
  hdiutil create -size 64m -type SPARSE -fs APFSX -volname FlashNestCaseTests "$WORK/case.sparseimage" >/dev/null
  mkdir "$WORK/mount"
  hdiutil attach -nobrowse -mountpoint "$WORK/mount" "$WORK/case.sparseimage" >/dev/null
  MOUNT="$WORK/mount"
  FIXTURE="$MOUNT/fixture"
else
  FIXTURE="$WORK/fixture"
fi
swiftc "$SOURCE" "$HERE/CaseCompatibilityFixture.swift" "$HERE/main.swift" -o "$WORK/path-tests"
"$WORK/path-tests" "$FIXTURE" > "$OUTPUT"
python3 - "$OUTPUT" <<'PY'
import json,sys
r=json.load(open(sys.argv[1]))
assert r['passed'] is True and r['caseSensitiveFilesystemVerified'] is True
assert r['count'] == len(r['tests']) and r['count'] >= 16
print('Verified native resolver tests:',r['count'])
PY

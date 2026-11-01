#!/bin/bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
# Optional arguments permit compiling the staged exact candidate product source.
SOURCE="${1:-$HERE/HTTPProtocol.swift}"
OUTPUT="${2:-$HERE/native-result.json}"
EVIDENCE="$(dirname "$OUTPUT")"
mkdir -p "$EVIDENCE"
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
  # 64 MiB can be below the selected APFS/container-layout minimum. Sparse
  # virtual capacity is bounded at 1 GiB; actual allocation grows with writes.
  # Keep APFSX and the independent case-sensitivity assertion, never downgrade.
  hdiutil create -help > "$EVIDENCE/hdiutil-create-help.txt" 2>&1 || true
  if ! hdiutil create -size 1g -type SPARSE -fs APFSX -volname FlashNestCaseTests "$WORK/case.sparseimage" > "$EVIDENCE/hdiutil-create.log" 2>&1; then
    cat "$EVIDENCE/hdiutil-create.log" >&2
    exit 1
  fi
  mkdir "$WORK/mount"
  hdiutil attach -nobrowse -mountpoint "$WORK/mount" "$WORK/case.sparseimage" >/dev/null
  MOUNT="$WORK/mount"
  diskutil info -plist "$MOUNT" > "$EVIDENCE/native-volume.plist"
  df -k "$MOUNT" > "$EVIDENCE/native-volume-df.txt"
  du -k "$WORK/case.sparseimage" > "$EVIDENCE/native-image-allocation.txt"
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
assert r['count'] == len(r['tests']) == len(set(r['tests'])) == 18
print('Verified native resolver tests:',r['count'])
PY

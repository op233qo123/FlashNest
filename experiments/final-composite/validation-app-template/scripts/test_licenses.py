#!/usr/bin/env python3
"""Verify shipped notices and their app-resource inclusion without network access."""
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
web = root / 'App/Resources/Web'
manifest = json.loads((web / 'licenses.manifest.json').read_text())
for name, expected in manifest.items():
    assert hashlib.sha256((web / name).read_bytes()).hexdigest() == expected, name
assert (root / 'LICENSE').read_bytes() == (web / 'FlashNest-LICENSE.txt').read_bytes()
assert (root / 'THIRD_PARTY_NOTICES.md').read_bytes() == (web / 'THIRD_PARTY_NOTICES.md').read_bytes()
assert 'path: App/Resources/Web\n        type: folder\n        buildPhase: resources' in (root / 'project.yml').read_text()
assert '## MPL-2.0' in (web / 'Ruffle-THIRD-PARTY-LICENSES.md').read_text()
assert len(manifest) >= 12
print(f'License checks passed: {len(manifest)} complete text files; app resources configured.')

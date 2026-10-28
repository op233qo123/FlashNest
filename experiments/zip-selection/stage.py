#!/usr/bin/env python3
"""Fail-closed source freeze and test-only overlay; invoked after reviewed 155 staging."""
import hashlib, json, shutil, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent

def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def stage(root, arm):
    assert arm in ('baseline', 'candidate')
    root = root.resolve()
    freeze = json.loads((HERE / 'source-freeze.json').read_text())
    for name, expected in freeze.items():
        p = root / name
        assert p.is_file() and not p.is_symlink() and digest(p) == expected, 'Source drift: ' + name
    picker = (HERE / 'overlay/PackageDocumentPicker.swift').read_text()
    if arm == 'baseline':
        assert picker.count('var importsCopy: Bool { self == .files }') == 1
        picker = picker.replace('var importsCopy: Bool { self == .files }', 'var importsCopy: Bool { false }')
    (root / 'App/Import/PackageDocumentPicker.swift').write_text(picker)
    for name, target in [('FixtureSourceApp.swift', 'UITestSupport/FixtureSource/FixtureSourceApp.swift'),
                         ('ZIPSelectionUITests.swift', 'UITests/ZIPSelectionUITests.swift')]:
        shutil.copyfile(HERE / 'overlay' / name, root / target)
    report = {'arm': arm, 'sourceFreeze': digest(HERE / 'source-freeze.json'),
              'picker': digest(root / 'App/Import/PackageDocumentPicker.swift'),
              'importsCopyFiles': arm == 'candidate', 'importsCopyFolder': False,
              'providerScope': 'simulator local Files / separate source app Documents only'}
    (root / 'source-identity.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))
if __name__ == '__main__': stage(Path(sys.argv[1]), sys.argv[2])

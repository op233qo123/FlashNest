#!/usr/bin/env python3
"""Apply an exact reviewed overlay to a clean pinned checkout; never promote main."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
INPUTS = json.loads((HERE / 'inputs.json').read_text())

def sha(data):
    return hashlib.sha256(data).hexdigest()

def stage(root):
    root = root.resolve()
    assert subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip() == INPUTS['baseCommit']
    assert not subprocess.check_output(['git', '-C', str(root), 'status', '--porcelain', '--untracked-files=all'], text=True).strip(), 'Checkout must be clean'
    expected = {item['path'] for item in INPUTS['overlay']}
    actual = {p.relative_to(HERE / 'overlay').as_posix() for p in (HERE / 'overlay').rglob('*') if p.is_file()}
    assert actual == expected, 'Overlay inventory differs'
    for entry in INPUTS['overlay']:
        relative = Path(entry['path'])
        assert not relative.is_absolute() and '..' not in relative.parts
        source = HERE / 'overlay' / relative
        data = source.read_bytes()
        assert not source.is_symlink() and len(data) == entry['bytes'] and sha(data) == entry['sha256'], entry['path']
        destination = root / relative
        assert not destination.is_symlink()
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
    print('Exact experimental overlay staged; shipping checkout/reference not modified')

if __name__ == '__main__':
    stage(Path(sys.argv[1]))

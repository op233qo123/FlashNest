#!/usr/bin/env python3
"""Read-only checks of allowlisted synthetic files. Never uploads app containers."""
import hashlib, json, subprocess, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent

def container(device, bundle):
    return Path(subprocess.check_output(['xcrun', 'simctl', 'get_app_container', device, bundle, 'data'], text=True).strip()).resolve(strict=True)
def regular(path, root):
    assert path.is_file() and not path.is_symlink()
    assert path.resolve().is_relative_to(root)
    return path.read_bytes()
def main(device, output):
    source = container(device, 'com.flashnest.fixture-source')
    target = container(device, 'com.flashnest.app')
    assert source != target
    swf = (HERE / 'fixtures/tiny-valid.swf').read_bytes()
    zip_data = (HERE / 'fixtures/tiny-valid.zip').read_bytes()
    folder = {'main.swf': swf, 'sub/child.swf': swf, 'sub/config.txt': b'original synthetic nested asset\n'}
    expected = {'Synthetic ZIP Input.zip': zip_data, 'Synthetic SWF Input.swf': swf,
                **{'FlashNest Cross-App Fixture/' + name: data for name, data in folder.items()}}
    for name, data in expected.items(): assert regular(source / 'Documents' / name, source) == data, 'Original changed'
    packages = target / 'Library/Application Support/Packages'
    entries = list(packages.iterdir())
    assert len(entries) == 4 and all(p.is_dir() and not p.is_symlink() for p in entries), 'Expected exactly four committed packages, no staging leftovers'
    shapes = []
    for package in entries:
        manifest = json.loads(regular(package / 'manifest.json', target))
        assert manifest['id'].lower() == package.name.lower()
        content = package / 'content'
        names = sorted(p.relative_to(content).as_posix() for p in content.rglob('*') if p.is_file())
        assert all(not p.is_symlink() for p in content.rglob('*'))
        if names == ['main.swf']: shape, wanted = 'zip', {'main.swf': swf}
        elif names == ['Synthetic SWF Input.swf']: shape, wanted = 'swf', {'Synthetic SWF Input.swf': swf}
        else: shape, wanted = 'folder', folder
        assert names == sorted(wanted)
        for name, data in wanted.items(): assert regular(content / name, target) == data
        shapes.append(shape)
    assert sorted(shapes) == ['folder', 'swf', 'zip', 'zip']
    result = {'originalsByteIdentical': True, 'privateCopiesByteIdentical': True,
              'differentAppSandboxes': True, 'committedPackages': 4, 'shapes': sorted(shapes),
              'sourceZIPsha256': hashlib.sha256(zip_data).hexdigest(),
              'sourceSWFsha256': hashlib.sha256(swf).hexdigest(),
              'scope': 'local simulator Files provider only; not unknown user provider'}
    Path(output).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))
if __name__ == '__main__': main(*sys.argv[1:])

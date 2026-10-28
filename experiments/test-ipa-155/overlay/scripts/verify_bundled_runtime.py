#!/usr/bin/env python3
"""Verify actual app Web resources before packaging; no fetch or replacement."""
import argparse
from pathlib import Path
from fetch_runtime import ROOT, digest, parse_json, require, safe_path, verified_identity

FORBIDDEN_PARTS = {'fixtures', 'experiments', 'source-correspondence',
                   'audio-recovery-baseline', 'audio-recovery-candidate',
                   'audio-recovery-injection.js', 'renderer-observer.js'}


def verify_web(web, root=ROOT):
    web, root = Path(web), Path(root)
    require(web.is_dir() and not web.is_symlink() and not web.parent.is_symlink(),
            'Bundled Web and its app directory must be real directories, not links')
    # Canonicalize harmless outer OS aliases (macOS /var -> /private/var)
    # only AFTER rejecting links at the actual app/Web resource boundary.
    web = web.resolve()
    for resource in web.rglob('*'):
        require(not resource.is_symlink() and (resource.is_file() or resource.is_dir()),
                'Linked/nonregular bundled Web resource: ' + str(resource.relative_to(web)))
        relative = resource.relative_to(web)
        require(not FORBIDDEN_PARTS.intersection(relative.parts) and resource.suffix.lower() not in {'.swf', '.sol', '.flashnestsave'},
                'Test/source/save data must not be bundled in Web: ' + str(relative))
    lock = parse_json((root / 'runtime.lock.json').read_bytes())
    identity_bytes = (web / 'runtime-identity.json').read_bytes()
    manifest = parse_json((root / 'runtime.files.json').read_bytes())
    identity = verified_identity(lock, manifest, identity_bytes)
    expected = identity['runtimeFiles']
    runtime = web / 'runtime'
    require(runtime.is_dir() and not runtime.is_symlink(), 'Missing/linked bundled runtime')
    actual = {p.name for p in runtime.iterdir()}
    require(actual == set(expected), 'Bundled runtime contains missing or stale/unmanaged files')
    for name, entry in expected.items():
        require(len(safe_path(name).parts) == 1, 'Unsafe runtime identity path')
        path = runtime / name
        require(path.is_file() and not path.is_symlink(), 'Nonregular bundled runtime asset')
        require(path.stat().st_size == entry['bytes'], 'Bundled runtime asset size mismatch: ' + name)
        data = path.read_bytes()
        require(len(data) == entry['bytes'] and digest(data) == entry['sha256'], 'Bundled runtime asset mismatch: ' + name)
    source_web = root / 'App/Resources/Web'
    require((web / 'licenses.manifest.json').read_bytes() == (source_web / 'licenses.manifest.json').read_bytes(),
            'Packaged license manifest differs from reviewed source')
    for name, expected_hash in parse_json((web / 'licenses.manifest.json').read_bytes()).items():
        path = web.joinpath(*safe_path(name).parts)
        require(path.is_file() and not path.is_symlink() and digest(path.read_bytes()) == expected_hash,
                'Bundled license/modification notice mismatch: ' + name)
    require((web / 'THIRD_PARTY_NOTICES.md').read_bytes() == (root / 'THIRD_PARTY_NOTICES.md').read_bytes(),
            'Packaged notices differ from reviewed source')
    print('Verified actual bundled modified runtime, exact inventory, provenance identity and notices')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('web', type=Path)
    verify_web(parser.parse_args().web)

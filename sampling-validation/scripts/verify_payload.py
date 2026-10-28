#!/usr/bin/env python3
"""Fail closed on missing, changed or unexpected immutable payload inputs."""
import hashlib,json,pathlib,shutil
ROOT=pathlib.Path(__file__).resolve().parents[1]
def verify(root=ROOT):
    m=json.loads((root/'manifest.json').read_text())
    assert m['runtimeGate'] is False and m['releaseEquivalent'] is False
    expected=set(m['files'])|{'manifest.json'}
    actual=set()
    for p in root.rglob('*'):
        rel=p.relative_to(root).as_posix()
        assert not p.is_symlink(), 'symlink forbidden: '+rel
        if p.is_file() and not rel.startswith('evidence/') and '__pycache__' not in p.parts:
            actual.add(rel)
    assert actual==expected, (sorted(expected-actual),sorted(actual-expected))
    for rel,info in m['files'].items():
        p=root/rel
        assert p.is_relative_to(root) and '..' not in pathlib.PurePosixPath(rel).parts
        data=p.read_bytes()
        assert len(data)==info['bytes'] and hashlib.sha256(data).hexdigest()==info['sha256'],rel
    original=json.loads((root/'provenance/original.json').read_text())
    for rel,sha in original['builtRuntime'].items():
        p=root/'runtimes/candidate'/rel
        if p.exists():assert hashlib.sha256(p.read_bytes()).hexdigest()==sha,rel
    baseline=json.loads((root/'provenance/baseline-runtime.files.json').read_text())
    for rel,sha in baseline.items():
        p=root/'runtimes/baseline'/rel
        if p.exists():assert hashlib.sha256(p.read_bytes()).hexdigest()==sha,rel
    source=json.loads((root/'provenance/patched-source-hashes.json').read_text())
    for rel,sha in {**source['files'],**source.get('referenceFiles',{})}.items():
        assert hashlib.sha256((root/'source/patched'/rel).read_bytes()).hexdigest()==sha,rel
    fixtures=json.loads((root/'history/fixtures/manifest.json').read_text())
    for rel,info in fixtures['files'].items():
        assert hashlib.sha256((root/'history/fixtures'/rel).read_bytes()).hexdigest()==info['sha256']
    return m
if __name__=='__main__':
    m=verify();(ROOT/'evidence').mkdir(exist_ok=True)
    shutil.copyfile(ROOT/'manifest.json',ROOT/'evidence/input-manifest.json')
    print(f"PASS: {len(m['files'])} exact immutable files; runtime gate false; not release equivalent")

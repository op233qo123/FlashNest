#!/usr/bin/env python3
"""Reconstruct/reverse the isolated patch over exact pinned + Weak source bytes."""
import argparse, hashlib, json, subprocess, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PIN = '89a7049965f3090e706265670df309a5128233ac'
WEAK_SHA = '89dfadc1b9d113adb01f08582237559c71a5c0e04fe712cb0e31d80f077b07b9'
PATHS = {'web/src/audio.rs', 'web/packages/core/src/ruffle-imports.ts',
         'web/packages/core/src/internal/player/inner.tsx',
         'web/packages/core/src/internal/audio-operation.ts'}
def sha(data): return hashlib.sha256(data).hexdigest()
def inputs():
    if not __debug__: raise RuntimeError('Validation requires Python assertions')
    info = json.loads((HERE/'patch-manifest.json').read_text())
    patch = HERE/'audio-recovery.patch'
    weak = ROOT/'experiments/audio-lifecycle/engine-patch/audio-lifecycle.patch'
    assert info['schemaVersion'] == 1 and info['upstreamCommit'] == PIN
    assert info['prerequisiteWeakPatchSHA256'] == WEAK_SHA == sha(weak.read_bytes())
    assert info['patchSHA256'] == sha(patch.read_bytes())
    assert len(info['files']) == 4 and {x['path'] for x in info['files']} == PATHS
    seen = set(); old = None
    for line in patch.read_text().splitlines():
        if line.startswith('--- '): old = line[4:]
        if line.startswith('+++ '):
            new = line[4:]; assert new.startswith('b/')
            path = new[2:]; assert path in PATHS and path not in seen
            assert old in ('a/'+path, '/dev/null')
            assert (old == '/dev/null') == (path.endswith('/audio-operation.ts'))
            seen.add(path); old = None
    assert seen == PATHS
    return info, patch, weak
def apply(directory, patch, reverse=False):
    args=['git','apply'] + (['--reverse'] if reverse else [])
    subprocess.run(args+['--check',str(patch)],cwd=directory,check=True,capture_output=True)
    subprocess.run(args+[str(patch)],cwd=directory,check=True,capture_output=True)
def verify(source):
    info,patch,weak=inputs()
    with tempfile.TemporaryDirectory(prefix='audio-recovery-source-') as d:
        temporary=Path(d)
        for row in info['files']:
            original=source/row['path']
            if row['originalSHA256'] is None:
                assert not original.exists(), 'Unexpected pre-existing helper'
                continue
            data=original.read_bytes();assert sha(data)==row['originalSHA256'],row['path']
            target=temporary/row['path'];target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
        apply(temporary,weak)
        for row in info['files']:
            if row['beforeRecoverySHA256'] is not None:
                assert sha((temporary/row['path']).read_bytes())==row['beforeRecoverySHA256']
        apply(temporary,patch)
        for row in info['files']:
            data=(temporary/row['path']).read_bytes()
            assert len(data)==row['bytes'] and sha(data)==row['modifiedSHA256'],row['path']
        apply(temporary,patch,True)
        for row in info['files']:
            path=temporary/row['path']
            if row['beforeRecoverySHA256'] is None: assert not path.exists()
            else: assert sha(path.read_bytes())==row['beforeRecoverySHA256']
        apply(temporary,weak,True)
        for row in info['files']:
            if row['originalSHA256'] is not None:
                assert sha((temporary/row['path']).read_bytes())==row['originalSHA256']
    return {'upstreamCommit':PIN,'recoveryPatchSHA256':info['patchSHA256'],
            'preservedWeakPatchSHA256':WEAK_SHA,'exactForwardAndReverse':True}
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--source-root',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(verify(args.source_root.resolve()),indent=2))

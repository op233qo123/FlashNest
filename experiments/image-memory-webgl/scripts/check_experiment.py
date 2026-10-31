#!/usr/bin/env python3
"""Fail closed on exact experiment source and fixture inventory before any build."""
from pathlib import Path
import hashlib,json,subprocess,sys
P=Path(__file__).resolve().parents[1];repo=P.parents[1]
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
m=json.loads((P/'experiment-manifest.json').read_text())
assert m['nativeAcceptance'] is False and m['IPARequested'] is False
for rel,row in m['files'].items():
 p=repo/rel;assert p.is_file() and not p.is_symlink(),rel
 assert p.stat().st_size==row['bytes'] and digest(p)==row['sha256'],rel
actual={p.relative_to(repo).as_posix() for p in P.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
expected={p for p in m['files'] if p.startswith('experiments/image-memory-webgl/')}
assert actual==expected|{'experiments/image-memory-webgl/experiment-manifest.json'},actual^expected
sys.path.insert(0,str(P.parent/'lazy-graphic-engine/scripts'))
from check_contract import check
check(P.parent/'lazy-graphic-engine','engine')
binding=json.loads((P/'source-binding.json').read_text())
assert digest(P/'product.patch')==binding['patchSHA256']
assert binding['baselineCommit']=='985f25c44ead766b2c4f9bd77b82e7b92bf95cc0'
assert binding['upstreamCommit']=='89a7049965f3090e706265670df309a5128233ac'
assert binding['reconstructedCandidate'] is True
print('PASS exact source/fixture/workflow experiment closure; not native acceptance')

#!/usr/bin/env python3
"""Whole reviewed recipe closure; no implicit candidate build or browser authority."""
import hashlib,json
from pathlib import Path,PurePosixPath
ROOT=Path(__file__).resolve().parents[1]
def check(root=ROOT):
 lock=json.loads((root/'pipeline-lock.json').read_text())
 if lock.get('dispatchAllowed') is not True:raise ValueError('Candidate engine/browser pipeline dispatch disabled')
 for p,row in lock['files'].items():
  rel=PurePosixPath(p)
  if rel.is_absolute() or '..' in rel.parts or '\\' in p:raise ValueError('Unsafe pipeline path')
  f=root/p
  if f.is_symlink() or not f.is_file() or f.stat().st_size!=row['bytes'] or hashlib.sha256(f.read_bytes()).hexdigest()!=row['sha256']:raise ValueError('Pipeline file changed: '+p)
 for directory in ('scripts','patches','reviews','app','browser','browser-fixtures','fixture-sources'):
  actual={f.relative_to(root).as_posix() for f in (root/directory).rglob('*') if f.is_file()}
  expected={p for p in lock['files'] if p.startswith(directory+'/')}
  if actual!=expected:raise ValueError('Unexpected source closure files: '+directory)
 if lock.get('nativeAcceptance') is not False or lock.get('originalCrashResolved') is not False:raise ValueError('Overclaimed acceptance')
 return lock
if __name__=='__main__':check();print('PASS exact candidate engine/browser recipe; not native acceptance')

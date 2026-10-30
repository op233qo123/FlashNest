#!/usr/bin/env python3
"""Bound complete engine upload and sole intended hidden source file; no credentials."""
from pathlib import Path
import hashlib,json,sys
root=Path(sys.argv[1]);tools=Path(sys.argv[2])
def require(ok,msg):
 if not ok:raise ValueError(msg)
def check_tree(directory):
 require(directory.is_dir() and not directory.is_symlink(),'Regular upload directory required')
 for f in directory.rglob('*'):require(not f.is_symlink() and (f.is_file() or f.is_dir()),'Nonregular upload member')
def check_map(directory,rows):
 actual={p.relative_to(directory).as_posix() for p in directory.rglob('*') if p.is_file()};require(actual==set(rows),'Upload inventory incomplete or extra')
 for rel,row in rows.items():
  raw=(directory/rel).read_bytes();require(len(raw)==row['bytes'] and hashlib.sha256(raw).hexdigest()==row['sha256'],'Upload bytes differ')
check_tree(root);check_tree(tools)
receipt=json.loads((root/'provenance.json').read_text());check_map(root/'runtime',json.loads((root/'runtime-files.json').read_text()));check_map(root/'source-correspondence',receipt['correspondence'])
hidden={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and any(x.startswith('.') for x in p.relative_to(root).parts)}
require(hidden=={'source-correspondence/source/.cargo/config.toml'},'Unexpected hidden upload file; do not expose credentials')
require(set(p.name for p in root.iterdir())=={'runtime','source-correspondence','runtime-files.json','provenance.json','full-source-before.json','full-source-after.json','core-js.log','core-types-preflight.log','build.log'},'Unexpected top-level engine output')
require({p.relative_to(tools).as_posix() for p in tools.rglob('*') if p.is_file()}=={'system-packages.txt','image.txt'},'Unexpected tool evidence')
require((root/'full-source-before.json').read_bytes()==(root/'full-source-after.json').read_bytes(),'Source changed')
print('PASS complete declared upload; only hidden file is reviewed source/.cargo/config.toml')

#!/usr/bin/env python3
from pathlib import Path
import argparse,os
p=argparse.ArgumentParser();p.add_argument('directory',type=Path);p.add_argument('--max-bytes',type=int,default=134217728);a=p.parse_args();files=[];ok=a.directory.is_dir()
if ok:
 for f in a.directory.rglob('*'):
  if f.is_symlink():ok=False
  elif f.is_file():files.append(f)
size=sum(f.stat().st_size for f in files);ok=ok and bool(files) and len(files)<=10000 and size<=a.max_bytes
print('evidence_files='+str(len(files))+' bytes='+str(size)+' allowed='+str(ok).lower())
if os.environ.get('GITHUB_OUTPUT'):
 with open(os.environ['GITHUB_OUTPUT'],'a') as f:f.write('allowed='+str(ok).lower()+'\n')
if not ok:raise SystemExit('Missing, symlinked or oversized evidence; upload withheld')

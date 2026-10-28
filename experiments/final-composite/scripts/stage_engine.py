#!/usr/bin/env python3
"""Apply exact reviewed patch chain to CLEAN pinned Git checkout. LOCAL DRAFT."""
from pathlib import Path
import argparse,subprocess,json,hashlib
from check_contract import check,ROOT,digest
p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('--engine-gate',action='store_true');a=p.parse_args();s=a.source.resolve();lock=check(ROOT,'engine' if a.engine_gate else 'source')
def git(*args):return subprocess.check_output(['git','-C',str(s),*args],text=True).strip()
if git('rev-parse','HEAD')!=lock['upstreamCommit'] or git('status','--porcelain'):raise SystemExit('Require clean exact upstream checkout')
for row in lock['patches']:
 patch=(ROOT/row['path']).resolve();subprocess.run(['git','-C',str(s),'apply','--check',str(patch)],check=True);subprocess.run(['git','-C',str(s),'apply',str(patch)],check=True)
changed=set(git('diff','--name-only').splitlines())|set(git('ls-files','--others','--exclude-standard').splitlines())
if changed!=set(lock['modifiedSourceFiles']):raise SystemExit('Unexpected modified source paths')
for rel,row in lock['modifiedSourceFiles'].items():
 f=s/rel
 if digest(f)!=row['sha256'] or f.stat().st_size!=row['bytes']:raise SystemExit('Source mismatch: '+rel)
for rel,h in lock['locks'].items():
 if digest(s/rel)!=h:raise SystemExit('Dependency lock mismatch: '+rel)
print('PASS exact reconstructed source; no build performed')

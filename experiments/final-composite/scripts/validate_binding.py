#!/usr/bin/env python3
"""Do not execute evolving or incomplete validation harnesses."""
from pathlib import Path
import json,sys,hashlib,argparse
from check_contract import ROOT,safe
p=argparse.ArgumentParser();p.add_argument('lane',choices=['browser','native']);p.add_argument('--root',type=Path,default=ROOT);a=p.parse_args();lock=json.loads((a.root/'validation-lock.json').read_text())
if lock.get('dispatchAllowed') is not True:raise SystemExit('Validation dispatch blocked: '+lock['reason'])
for key in ['engine','historicalBaseline','appSourceManifest']:
 if not isinstance(lock.get(key),dict):raise SystemExit('Missing identity binding: '+key)
for rel,row in lock['harnessFiles'].items():
 f=a.root/safe(rel)
 if f.is_symlink() or hashlib.sha256(f.read_bytes()).hexdigest()!=row['sha256']:raise SystemExit('Harness changed: '+rel)
lane=lock['lanes'][a.lane]
if not lane['commands'] or not lane['verifier']:raise SystemExit('Missing explicit reviewed commands/verifier')
for command in lane['commands']+[lane['verifier']]:
 if not isinstance(command,list) or not command or not all(isinstance(arg,str) and arg for arg in command):raise SystemExit('Command must be nonempty argv array')
print('PASS exact lane binding',a.lane)

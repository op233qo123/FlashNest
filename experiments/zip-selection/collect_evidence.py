#!/usr/bin/env python3
"""Bound synthetic-only evidence to 24 MiB per arm; retain readable failure logs."""
import json, subprocess, sys
from pathlib import Path
root=Path(sys.argv[1]);out=root/'evidence';out.mkdir(parents=True,exist_ok=True)
budget=24*1024*1024
inventory=[]
def retain(name,data,limit):
 global budget
 original=len(data);limit=min(limit,budget)
 if original>limit:
  marker=b'\n[DIAGNOSTIC EVIDENCE TRUNCATED; HEAD AND TAIL RETAINED]\n'
  half=max(0,(limit-len(marker))//2);data=data[:half]+marker+data[-half:] if half else b''
 if not data:return
 p=out/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data);budget-=len(data)
 inventory.append({'path':name,'originalBytes':original,'retainedBytes':len(data)})
for name in ['environment.log','stage.log','runtime-fetch.log','project-build.log','source-build.log','native-test.log','picker-test.log','copy-verification.log','source-identity.json','copy-verification.json']:
 p=(root.parent/name) if name in ['environment.log','stage.log'] else root/name
 if p.is_file() and not p.is_symlink():retain(name,p.read_bytes(),2*1024*1024)
for name in ['NativeTests','PickerTests']:
 result=root/(name+'.xcresult')
 if result.is_dir():
  summary=subprocess.run(['xcrun','xcresulttool','get','test-results','summary','--path',str(result)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
  retain(name+'-summary.json' if summary.returncode==0 else name+'-summary-error.txt',summary.stdout,512*1024)
  attachments=root/(name+'-exported-attachments')
  export=subprocess.run(['xcrun','xcresulttool','export','attachments','--path',str(result),'--output-path',str(attachments)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
  retain(name+'-export.log',export.stdout,128*1024)
  for p in sorted(attachments.rglob('*')):
   if not p.is_file() or p.is_symlink():continue
   if p.suffix.lower() not in ['.png','.jpg','.jpeg','.txt','.json']:continue
   size=p.stat().st_size
   # Never truncate images or upload media movies/container trees.
   if size>min(budget,3*1024*1024):
    inventory.append({'path':p.name,'omittedBytes':size,'reason':'bounded evidence budget'});continue
   retain(name+'-attachments/'+p.relative_to(attachments).as_posix(),p.read_bytes(),3*1024*1024)
(out/'evidence-inventory.json').write_text(json.dumps({'budgetBytes':24*1024*1024,'files':inventory},indent=2)+'\n')
print('Bounded synthetic-only evidence prepared; details in evidence-inventory.json')

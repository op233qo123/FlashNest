#!/usr/bin/env python3
"""Bound only synthetic UI diagnostics; never upload app/container trees or saves."""
import hashlib,json,subprocess,sys
from pathlib import Path
TOTAL=24*1024*1024
ROOT_FILES=('unit.log','ui.log','fixture-source-build.log','probe-project.log','unit-summary.json','ui-summary.json','unit-verification.json','ui-verification.json','diagnostic-receipt.json')
def collect(root):
 root=Path(root);out=root/'evidence';out.mkdir(parents=True,exist_ok=False);remaining=TOTAL;rows=[]
 def keep(name,data,limit,truncate=True):
  nonlocal remaining
  size=len(data);cap=min(limit,remaining)
  if size>cap:
   if not truncate:rows.append({'path':name,'omittedBytes':size,'reason':'evidence budget'});return
   marker=b'\n[BOUNDED DIAGNOSTIC: HEAD/TAIL TRUNCATED]\n';half=max(0,(cap-len(marker))//2);data=data[:half]+marker+data[-half:] if half else b''
  if not data:return
  dest=out/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data);remaining-=len(data);rows.append({'path':name,'originalBytes':size,'retainedBytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
 for name in ROOT_FILES:
  p=root/name
  if p.is_file() and not p.is_symlink():keep(name,p.read_bytes(),2*1024*1024,not name.endswith('.json'))
 result=root/'ui.xcresult'
 if result.is_dir() and not result.is_symlink():
  exported=root/'exported-ui-attachments'
  try:
   r=subprocess.run(['xcrun','xcresulttool','export','attachments','--path',str(result),'--output-path',str(exported)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=180)
   keep('attachment-export.log',r.stdout,128*1024)
   for p in sorted(exported.rglob('*')):
    if p.is_file() and not p.is_symlink() and p.suffix.lower() in ('.png','.jpg','.jpeg','.txt','.json'):
     if p.stat().st_size>3*1024*1024:rows.append({'path':p.name,'omittedBytes':p.stat().st_size,'reason':'per-file cap'});continue
     keep('attachments/'+p.relative_to(exported).as_posix(),p.read_bytes(),3*1024*1024,False)
  except (subprocess.TimeoutExpired,OSError) as error:keep('attachment-export-error.txt',type(error).__name__.encode(),1024)
 (out/'inventory.json').write_text(json.dumps({'diagnosticOnly':True,'selectedReleaseGatePassed':False,'maxPayloadBytes':TOTAL,'retainedPayloadBytes':TOTAL-remaining,'files':rows},indent=2)+'\n')
if __name__=='__main__':collect(Path(sys.argv[1]))

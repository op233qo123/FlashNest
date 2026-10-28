"""Bounded synthetic diagnostic-app evidence only; no arbitrary app containers/logs."""
import hashlib,json,re,shutil
from pathlib import Path
UUID=re.compile(r'^[0-9A-Fa-f]{8}(?:-[0-9A-Fa-f]{4}){3}-[0-9A-Fa-f]{12}\.json$')
PHASES={'native-open','native-opened','native-controller','native-failure','stale-controller-rejected','journal-truncated','document-start','shell-load-call','shell-load-return','loadeddata','context-created','context-state','audio-status','resource-request','resource-complete','instance-banner','disposed'}
KEYS={'phase','caseMode','processID','nativeSequence','receiptAgeMs','controllerGeneration','page','jsSequence','contexts','contextId','operationId','intentId','state','audioPhase','status','current','resource','sha256','resourceEvidence','requestedFlavor','flavor','backend','omittedAtLeast'}
def validate_journal(data,resources):
 if len(data)>65536:raise ValueError('Journal exceeds64KiB')
 rows=json.loads(data)
 if not isinstance(rows,list) or not 1<=len(rows)<=100:raise ValueError('Journal row bound')
 for i,x in enumerate(rows):
  if not isinstance(x,dict) or set(x)-KEYS or x.get('phase') not in PHASES or x.get('nativeSequence')!=i+1:raise ValueError('Unknown journal fields/sequence')
  for k,v in x.items():
   if k in {'nativeSequence','receiptAgeMs','controllerGeneration','page','jsSequence','contexts','contextId','operationId','intentId','processID','omittedAtLeast'} and (type(v)is not int or not 0<=v<=1000000000):raise ValueError('Invalid bounded number')
  enums={'caseMode':{'candidate-known','candidate-unknown','baseline-known','startup-only','unknown'},'state':{'suspended','running','closed','interrupted'},'audioPhase':{'bind','release','core-play','core-pause','visibility','unmute'},'status':{'bound','released','pending','fulfilled','rejected'},'requestedFlavor':{'extensions','mvp'},'flavor':{'extensions','mvp'},'backend':{'webgpu','wgpu-webgl','webgl','canvas'},'resourceEvidence':{'requested-or-completed-not-executed'}}
  if any(k in x and x[k] not in allowed for k,allowed in enums.items()):raise ValueError('Unknown enum')
  if 'current'in x and type(x['current'])is not bool:raise ValueError('Invalid bool')
  if 'resource'in x and (x['resource'] not in resources or x.get('sha256')!=resources[x['resource']]):raise ValueError('Unapproved public runtime resource')
  if 'sha256'in x and 'resource'not in x:raise ValueError('Unbound hash')
 return rows

def journals(container,output,resources,since):
 container=Path(container);output=Path(output);directory=container/'Documents/StartupDiagnostics'
 if container.is_symlink() or any(p.is_symlink() for p in [container/'Documents',directory]):raise ValueError('Symlink diagnostic directory')
 output.mkdir(parents=True,exist_ok=True);records=[]
 if not directory.exists():return records
 for p in sorted(directory.iterdir(),key=lambda p:p.name):
  if not UUID.fullmatch(p.name) or p.is_symlink() or not p.is_file() or p.stat().st_mtime<since:continue
  if len(records)>=4:raise ValueError('Unexpected journal file count')
  if p.stat().st_size>65536:raise ValueError('Oversize journal')
  data=p.read_bytes();rows=validate_journal(data,resources);(output/p.name).write_bytes(data)
  records.append({'file':p.name,'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'rows':rows})
 return records

def crashes(reports,output,since):
 """Shared10report/10MiB cap across all pre/post snapshots; no broad OS logs."""
 reports=Path(reports);output=Path(output);output.mkdir(parents=True,exist_ok=True)
 existing=[p for p in output.iterdir() if p.is_file() and p.suffix=='.ips'];total=sum(p.stat().st_size for p in existing);seen={hashlib.sha256(p.read_bytes()).hexdigest() for p in existing};records=[];omitted=0
 if not reports.is_dir():return {'records':records,'omitted':omitted}
 for p in sorted(reports.rglob('*.ips')):
  allowed=(p.name.startswith('AudioRecoveryDiagnostic-') or (p.name.startswith('com.apple.WebKit.') and ('WebContent' in p.name or 'GPU' in p.name)) or p.name.startswith('SimMetalHost-'))
  if not allowed or p.is_symlink() or not p.is_file():continue
  st=p.stat()
  if st.st_mtime<since:continue
  if st.st_size>2*1024*1024:omitted+=1;continue
  data=p.read_bytes();digest=hashlib.sha256(data).hexdigest()
  if digest not in seen:
   if len(seen)>=10 or total+len(data)>10*1024*1024:omitted+=1;continue
   (output/(digest+'.ips')).write_bytes(data);seen.add(digest);total+=len(data)
  records.append({'sha256':digest,'bytes':len(data),'reportName':p.name})
 return {'records':records,'omitted':omitted}

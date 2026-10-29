"""Staged-only two-file observation overlay; never product/native acceptance."""
import hashlib,json,re,math
from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parent
MARKER='FLASHNEST_RESTART_OBSERVATION_JSON '
LABELS=('before','after-reload','after-restart-wait-raw','after-restart-wait-refreshed')
TARGETS={'SamplingHost.swift':'Host/SamplingHost.swift','NativeSamplingUITests.swift':'UITests/NativeSamplingUITests.swift'}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def require(ok,why):
 if not ok:raise ValueError(why)
def inventory(root):
 result={}
 for p in sorted(Path(root).rglob('*')):
  require(not p.is_symlink(),'Linked staged file forbidden')
  if p.is_file():result[p.relative_to(root).as_posix()]=sha(p)
 return result
def apply_overlay(app,approved_sampling_root):
 app=Path(app);approved_sampling_root=Path(approved_sampling_root);pins=json.loads((ROOT/'source-pins.json').read_text());before=inventory(app);changes={}
 for name,rel in TARGETS.items():
  source=approved_sampling_root/rel;target=app/'NativeSamplingValidation'/rel
  require(sha(source)==sha(ROOT/'base'/name)==pins[name]['before'],'Approved original sampling source differs: '+name)
  require(sha(target)==pins[name]['before'],'Staged source not exact approved original: '+name)
  require(sha(ROOT/'overlay'/name)==pins[name]['after'],'Diagnostic overlay bytes differ: '+name)
 for name,rel in TARGETS.items():(app/'NativeSamplingValidation'/rel).write_bytes((ROOT/'overlay'/name).read_bytes())
 after=inventory(app);expected={**before}
 for name,rel in TARGETS.items():
  target='NativeSamplingValidation/'+rel;expected[target]=pins[name]['after'];changes[target]=pins[name]
 require(after==expected,'Unexpected staged delta')
 inverse={**after}
 for target,pin in changes.items():inverse[target]=pin['before']
 require(inverse==before,'Exact inverse failed')
 require({p:h for p,h in before.items() if p.startswith('App/')}=={p:h for p,h in after.items() if p.startswith('App/')},'Product App changed')
 return {'diagnosticOnly':True,'nativeAcceptance':False,'exactInverseVerified':True,'productAppUnchanged':True,'changedFiles':changes,'sourcePinsSHA256':sha(ROOT/'source-pins.json'),'beforeFiles':before,'afterFiles':after,'inverseFiles':inverse}
apply=apply_overlay

def verify_evidence(out,expected_identity):
 out=Path(out);errors=[];records=[]
 def check(ok,why):
  if not ok:errors.append(why)
 log=out/'restart-candidate.log'
 if not log.exists():errors.append('Original XCTest log missing');text=''
 else:
  check(log.stat().st_size<=16*1024*1024,'Log exceeds original bound');text=log.read_text(errors='replace') if log.stat().st_size<=16*1024*1024 else ''
 lines=re.findall(re.escape(MARKER)+r'([^\r\n]+)',text)
 check(len(lines)<=4,'Excess/duplicate marker records')
 for line in lines[:4]:
  check(len(line.encode())<=65536,'Record exceeds64KiB')
  try:records.append(json.loads(line))
  except ValueError:errors.append('Invalid marker JSON')
 folder=out/'attachments'/'restart-candidate';files=[p for p in folder.rglob('*') if p.is_file()] if folder.exists() else []
 check(not any(p.is_symlink() for p in files),'Linked diagnostic attachment')
 check(sum(p.stat().st_size for p in files)<=128*1024*1024,'Diagnostic attachments exceed original bound')
 pngs={sha(p):p for p in files if p.suffix.lower()=='.png' and not p.is_symlink()};attached={}
 for p in files:
  if p.suffix.lower()!='.json' or p.stat().st_size>65536:continue
  try:r=json.loads(p.read_text())
  except (ValueError,UnicodeError):continue
  if isinstance(r,dict) and r.get('schema')=='flashnest-restart-observation-v1':
   label=r.get('label');check(label not in attached,'Duplicate observation attachment');attached[label]=r
 by_label={}
 for r in records:
  if not isinstance(r,dict):check(False,'Record not an object');continue
  label=r.get('label');check(label in LABELS and label not in by_label,'Unexpected/duplicate observation label');by_label[label]=r
  check(r.get('schema')=='flashnest-restart-observation-v1' and r.get('diagnosticOnly') is True and r.get('nativeAcceptance') is False,'Observation schema/role differs')
  check(r.get('identity')==expected_identity,'External source identity differs')
  check(r.get('row')=='candidate-dpr2-webgl-showAll-quarter-shipping-default-quality','Wrong diagnostic row')
  if label in attached:check(attached[label]==r,'Attachment/stdout observation differs')
  # Missing JSON attachment is explicit but stdout remains preserved as fallback.
  if label not in attached:check(False,'Observation attachment missing: '+str(label))
 check(tuple(r.get('label') for r in records if isinstance(r,dict))==LABELS,'Four ordered bounded observations required')
 times=[r.get('observedUptimeSeconds') for r in records if isinstance(r,dict)]
 check(len(times)==4 and all(type(t) in (int,float) and math.isfinite(t) for t in times) and all(a<b for a,b in zip(times,times[1:])),'Observation monotonic ordering differs')
 before=by_label.get('before',{}).get('snapshot',{});after_reload=by_label.get('after-reload',{}).get('snapshot',{})
 check(isinstance(before,dict) and isinstance(after_reload,dict) and type(before.get('epoch')) is int and before.get('epoch')==after_reload.get('epoch'),'Original same-view reload epoch differs')
 snapshots=[]
 for label in ('before','after-reload','after-restart-wait-refreshed'):
  r=by_label.get(label,{})
  if 'snapshot' in r:snapshots.append((label,r['snapshot']))
  elif r:check(False,'Snapshot unavailable: '+label)
 raw=by_label.get('after-restart-wait-raw',{});available=raw.get('restartPlayAvailable')
 check(type(available) is bool,'Original90s result missing')
 original_png=raw.get('originalPNGSHA256')
 check(isinstance(original_png,str) and original_png in pngs,'Original restart screenshot PNG missing')
 image_size=None
 if isinstance(original_png,str) and original_png in pngs:
  try:
   with Image.open(pngs[raw['originalPNGSHA256']]) as image:
    image_size=list(image.size);check(image.format=='PNG','Original screenshot is not PNG');check(image.width>0 and image.height>0 and image.width*image.height<=16000000,'Unexpected screenshot size');image.verify()
  except (OSError,ValueError):check(False,'Original screenshot PNG invalid')
 cached=None
 try:cached=json.loads(raw.get('cachedAXValue',''))
 except (TypeError,ValueError):check(False,'Cached AX snapshot missing/unparseable')
 check(isinstance(cached,dict),'Cached AX is not a snapshot object')
 if isinstance(cached,dict):snapshots.append(('cached-after-restart',cached))
 check(raw.get('cachedAXSanitized') is True and raw.get('cachedAXParseFailed') is False,'Cached AX evidence unavailable/unsafe')
 refreshed=by_label.get('after-restart-wait-refreshed',{})
 check(refreshed.get('restartPlayAvailable')==available,'Original wait result changed during capture')
 if isinstance(cached,dict) and isinstance(refreshed.get('snapshot'),dict):
  request=refreshed['snapshot'].get('request');old=cached.get('request')
  check(type(request) is int and type(old) is int and request>old,'Refreshed snapshot did not advance')
 for label,s in snapshots:
  check(isinstance(s,dict) and s.get('identity')==expected_identity,'Snapshot source identity differs: '+label)
  if not isinstance(s,dict):continue
  check(s.get('screenScale')==2 and s.get('os')=='18.2','Wrong diagnostic OS/DPR')
  state=s.get('restartObservation',{})
  if not isinstance(state,dict):check(False,'Restart state is not an object');continue
  check('processTerminated' in state and 'preservationStage' in state and state.get('processTerminated') is None and state.get('preservationStage') is None and state.get('privateFieldAvailability')=='not-exposed-by-product','Private fields guessed/read')
  check(all(type(state.get(k)) is bool for k in ('saveReady','restartRequired','hasWebView')),'Public state fields missing')
  check(all(isinstance(state.get(k),str) for k in ('saveFailure','restartFailure')) and isinstance(s.get('failure'),str),'Public error fields malformed')
  check(state.get('restartPhase') in ('idle','requested','before-saveAndRestart','returned-true','returned-false','attached'),'Host restart phase missing')
  def safe_errors(value):
   if isinstance(value,dict):
    for k,x in value.items():
     if k=='identity':continue
     if k in ('failure','saveFailure','restartFailure','probeError','observationError','message') and isinstance(x,str):
      check(not re.search(r'(?i)\b(?:https?|file|wss?|flashnest)://|\b[A-Za-z0-9_-]{32,}={0,2}\b',x),'Unsafe diagnostic error text')
     else:safe_errors(x)
   elif isinstance(value,list):
    for x in value:safe_errors(x)
  safe_errors(s)
 has_failure=available is False or any(s.get('failure') or s.get('restartObservation',{}).get('saveFailure') or s.get('restartObservation',{}).get('restartFailure') for _,s in snapshots if isinstance(s,dict))
 return {'diagnosticOnly':True,'nativeAcceptance':False,'renderHealthCertified':False,'evidenceValid':not errors,'observationComplete':not errors,'restartPlayAvailable':available,'hasFailure':bool(has_failure),'diagnosticHealthy':not errors and not has_failure,'errors':errors,'records':records,'observedStates':snapshots,'jsonAttachmentCount':len(attached),'originalScreenshotSHA256':raw.get('originalPNGSHA256'),'originalScreenshotPixels':image_size,'limitations':['Observation occurs before original restart assertion and Play activation, not render health','Private product fields are explicitly unavailable','Original XCTest failure remains primary; observation never authorizes recovery']}

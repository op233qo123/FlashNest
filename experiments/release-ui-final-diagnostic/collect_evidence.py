#!/usr/bin/env python3
"""Public evidence contains only fixed enums/scalars and whitelisted synthetic PNG."""
import hashlib,json,re,subprocess,sys
from pathlib import Path
STEPS=('import','firstPlay','childInput','backgroundRunning','backgroundPaused','directSave','managementCancel','restartOptions','restartTap','restartPlay','restoredTrace','postRestartAssertions','complete')
IDS=('player-menu','player-resume','player-saves','save-entry-direct','save-entry-restart','save-management-cancel')
SOURCES=('LifecyclePlayerUITests.swift','LibraryNavigation.swift','unknown')
TEST='LifecyclePlayerUITests/testBackgroundDirectSaveCancelManagementAndRestartSameGame()'
METHOD='testBackgroundDirectSaveCancelManagementAndRestartSameGame'
LIMIT=6*1024*1024
PNG_LIMIT=3*1024*1024
def sha(data):return hashlib.sha256(data).hexdigest()
def failure(value):
 if not isinstance(value,dict) or type(value.get('schema')) is not int or value['schema']!=1 or value.get('step') not in STEPS or value.get('source') not in SOURCES or value.get('kind') not in ('assertion','other'):return None
 line=value.get('line')
 if type(line) is not int or not 0<=line<=1000 or (value['source']=='unknown' and line!=0):return None
 return {k:value[k] for k in ('schema','step','source','line','kind')}
def safe_ax(value):
 if not isinstance(value,dict) or type(value.get('schema')) is not int or value['schema']!=1 or value.get('step') not in STEPS or type(value.get('webViewPresent')) is not bool:return None
 rows=value.get('controls')
 if not isinstance(rows,list) or len(rows)!=len(IDS):return None
 controls=[]
 for row in rows:
  if not isinstance(row,dict) or row.get('id') not in IDS or type(row.get('exists')) is not bool or type(row.get('enabled')) is not bool:return None
  controls.append({k:row[k] for k in ('id','exists','enabled')})
 if {r['id'] for r in controls}!=set(IDS):return None
 return {'schema':1,'step':value['step'],'controls':controls,'webViewPresent':value['webViewPresent']}
def parse_markers(text):
 result={'steps':[],'failures':[],'safeAX':[],'invalidMarkers':0}
 def add(kind,value):
  if value is None:result['invalidMarkers']+=1
  elif value not in result[kind] and len(result[kind])<(len(STEPS) if kind=='steps' else 3):result[kind].append(value)
 for line in text.splitlines():
  match=re.search(r'\bFINAL_UI_(STEP|FAILURE|AX) (.{1,8192})$',line)
  if not match:continue
  kind,raw=match.groups()
  if kind=='STEP':add('steps',raw if raw in STEPS else None);continue
  try:value=json.loads(raw)
  except ValueError:result['invalidMarkers']+=1;continue
  add('failures' if kind=='FAILURE' else 'safeAX',failure(value) if kind=='FAILURE' else safe_ax(value))
 return result

def collect(private,public):
 private=Path(private);public=Path(public);public.mkdir(parents=True,exist_ok=False)
 result={'diagnosticOnly':True,'selectedReleaseGatePassed':False,'rawEvidenceUploaded':False,'files':[],'omitted':[],'maxPayloadBytes':LIMIT}
 retained=0
 def save(name,data):
  nonlocal retained
  if retained+len(data)>LIMIT:result['omitted'].append({'kind':'budget','bytes':len(data)});return
  (public/name).write_bytes(data);retained+=len(data);result['files'].append({'path':name,'bytes':len(data),'sha256':sha(data)})
 log=private/'ui.log';raw=log.read_bytes() if log.is_file() and not log.is_symlink() and log.stat().st_size<=32*1024*1024 else b''
 observed=parse_markers(raw.decode('utf-8',errors='replace'));observed['rawLogSHA256']=sha(raw) if raw else None
 summary=private/'ui-summary.json'
 if summary.is_file() and not summary.is_symlink() and summary.stat().st_size<=1024*1024:
  data=summary.read_bytes();observed['rawSummarySHA256']=sha(data)
  try:
   obj=json.loads(data);observed['counts']={k:obj[k] for k in ('totalTestCount','passedTests','failedTests','skippedTests','expectedFailures') if type(obj.get(k)) is int and 0<=obj[k]<=10000}
  except (ValueError,TypeError):observed['summaryUnsupported']=True
 receipt=private/'diagnostic-receipt.json'
 if receipt.is_file() and not receipt.is_symlink() and receipt.stat().st_size<=256*1024:
  try:
   obj=json.loads(receipt.read_bytes());safe={'diagnosticOnly':True,'selectedReleaseGatePassed':False,'unitNotRun':True}
   for k in ('runID','priorSelectedRun'):
    if type(obj.get(k)) is int and obj[k]>0:safe[k]=obj[k]
   if isinstance(obj.get('head'),str) and re.fullmatch('[0-9a-f]{40}',obj['head']):safe['head']=obj['head']
   for k in ('restoredOriginalSource','originalRuntimeUnchanged','generatedProjectRestored','observedUIAssertionsPassed','uiAttempted'):
    if type(obj.get(k)) is bool:safe[k]=obj[k]
   for key in ('baselineSourceFiles','restoredSourceFiles'):
    rows=obj.get(key)
    if isinstance(rows,dict) and len(rows)==207 and all(isinstance(v,str) and re.fullmatch('[0-9a-f]{64}',v) for v in rows.values()):safe[key+'MapSHA256']=sha(json.dumps(rows,sort_keys=True,separators=(',',':')).encode())
   delta=obj.get('executedTestOnlyOverlay',{})
   if delta.get('path')=='UITests/LifecyclePlayerUITests.swift' and all(isinstance(delta.get(k),str) and re.fullmatch('[0-9a-f]{64}',delta[k]) for k in ('beforeSHA256','afterSHA256')):safe['executedTestOnlyOverlay']={k:delta[k] for k in ('path','beforeSHA256','afterSHA256')}
   save('source-receipt.json',(json.dumps(safe,indent=2)+'\n').encode())
  except (ValueError,TypeError,AttributeError):observed['sourceReceiptUnsupported']=True
 exported=private/'exported-final-ui';xcresult=private/'ui.xcresult'
 if xcresult.is_dir() and not xcresult.is_symlink():
  try:
   command=subprocess.run(['xcrun','xcresulttool','export','attachments','--path',str(xcresult),'--output-path',str(exported)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=120);observed['attachmentExportSucceeded']=command.returncode==0
  except (OSError,subprocess.TimeoutExpired):observed['attachmentExportSucceeded']=False
 manifest=exported/'manifest.json';png_saved=False
 if manifest.is_file() and not manifest.is_symlink() and manifest.stat().st_size<=1024*1024:
  try:
   groups=json.loads(manifest.read_bytes())
   if not isinstance(groups,list) or len(groups)>32:raise ValueError('manifest')
   for group in groups:
    if not isinstance(group,dict) or group.get('testIdentifier')!=TEST:continue
    rows=group.get('attachments',[])
    if not isinstance(rows,list) or len(rows)>256:raise ValueError('attachments')
    for row in rows:
     if not isinstance(row,dict):continue
     name=row.get('suggestedHumanReadableName','');filename=row.get('exportedFileName','')
     match=re.fullmatch(r'(final-ui-failure|final-ui-safe-ax|final-ui-synthetic-app)_[0-9]+_[0-9A-Fa-f-]{36}\.(txt|png)',name)
     if not match or not re.fullmatch(r'[0-9A-Fa-f-]{36}\.(txt|png)',filename):continue
     kind,ext=match.groups();file=exported/filename
     if not file.is_file() or file.is_symlink():continue
     if kind=='final-ui-synthetic-app':
      if ext!='png' or png_saved:continue
      if file.stat().st_size>PNG_LIMIT:result['omitted'].append({'kind':'synthetic-png','bytes':file.stat().st_size});continue
      data=file.read_bytes()
      if not data.startswith(b'\x89PNG\r\n\x1a\n'):continue
      save('synthetic-app.png',data);png_saved=True
     elif ext=='txt' and file.stat().st_size<=8192:
      try:value=json.loads(file.read_bytes())
      except ValueError:continue
      key='failures' if kind=='final-ui-failure' else 'safeAX';value=failure(value) if key=='failures' else safe_ax(value)
      if value is not None and value not in observed[key] and len(observed[key])<3:observed[key].append(value)
  except (ValueError,TypeError,AttributeError):observed['attachmentManifestUnsupported']=True
 observed['failureMarkerAvailable']=bool(observed['failures']);observed['failureLocationAvailable']=any(row['source'] in SOURCES[:2] and row['line']>0 for row in observed['failures']);observed['syntheticScreenshotAvailable']=png_saved
 save('safe-ui-observation.json',(json.dumps(observed,indent=2)+'\n').encode());result['retainedPayloadBytes']=retained
 (public/'inventory.json').write_text(json.dumps(result,indent=2)+'\n')
if __name__=='__main__':collect(*map(Path,sys.argv[1:]))

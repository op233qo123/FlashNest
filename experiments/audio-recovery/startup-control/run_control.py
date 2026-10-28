"""Three fixed no-gesture startup observations; no retries and no recovery claim."""
import argparse,datetime,hashlib,json,os,plistlib,re,subprocess,time,tempfile
from pathlib import Path
from collect import journals,crashes
BUNDLE='com.flashnest.audio-recovery.diagnostic'
RUNTIME='com.apple.CoreSimulator.SimRuntime.iOS-18-2'
def command(args,timeout=30,env=None):
 with tempfile.TemporaryFile() as out,tempfile.TemporaryFile() as err:
  timed_out=False
  try: result=subprocess.run(args,stdout=out,stderr=err,timeout=timeout,env=env);code=result.returncode
  except subprocess.TimeoutExpired:code=-1;timed_out=True
  out.seek(0);err.seek(0);stdout=out.read(65537);stderr=err.read(65537)
  return {'returncode':code,'stdout':stdout[:65536].decode(errors='replace'),'stderr':stderr[:65536].decode(errors='replace'),'timedOut':timed_out,'truncated':len(stdout)>65536 or len(stderr)>65536}
def checked(args,timeout=30,env=None):
 r=command(args,timeout,env)
 if r['returncode'] or r.get('truncated'):raise RuntimeError('Required command failed: '+args[1])
 return r['stdout'].strip()
def device(json_text,udid):
 data=json.loads(json_text);matches=[(rt,x) for rt,rows in data['devices'].items() for x in rows if x['udid']==udid]
 if len(matches)!=1 or matches[0][0]!=RUNTIME or not matches[0][1].get('isAvailable'):raise ValueError('Not exact available18.2 UDID')
 return matches[0][1]
def launched_pid(result):
 m=re.fullmatch(re.escape(BUNDLE)+r': ([1-9][0-9]*)\s*',result['stdout'])
 return int(m[1]) if result['returncode']==0 and not result.get('truncated') and m else None

def capture_epoch(path):
 try:
  text=Path(path).read_text();d=json.loads(text[text.index('\n')+1:]);stamp=d['captureTime']
  return datetime.datetime.strptime(stamp,'%Y-%m-%d %H:%M:%S.%f %z').timestamp()
 except (ValueError,KeyError,OSError,TypeError):return None

def matching_journal(records,pid):
 matched=[j for j in records if any(x.get('phase')=='native-open' and x.get('processID')==pid and x.get('caseMode')=='startup-only' for x in j['rows'])]
 return matched[0] if len(matched)==1 else None

def ready(journal):
 if not journal:return False
 rows=journal['rows'];phases={x['phase'] for x in rows}
 return {'native-opened','shell-load-return','loadeddata','instance-banner'}<=phases and any(x['phase']=='resource-request' and x.get('resource','').endswith('.wasm') for x in rows)

def outcome(entry):
 if entry.get('crashesCapturedDuringObservation'):return 'crash-observed'
 if not entry.get('freshPID'):return 'launch-unconfirmed'
 if not all(x['pidAliveAsExpectedApp'] for x in entry['samples']):return 'process-exit-or-unconfirmed'
 if entry.get('journalValidationError') or entry.get('collectionIncomplete') or entry.get('observationError'):return 'evidence-incomplete'
 journal=matching_journal(entry.get('journalsBeforeTermination',[]),entry['pid'])
 if entry.get('reusedJournalIdentity'):return 'journal-identity-unconfirmed'
 if not journal or journal['file']!=entry.get('readyJournalFile',journal['file']):return 'journal-identity-unconfirmed'
 if any(x['phase']=='native-failure' for x in journal['rows']):return 'native-failure'
 if any(x['phase']=='journal-truncated' for x in journal['rows']):return 'evidence-incomplete'
 if entry.get('readyAtSeconds') is None or not ready(journal):return 'startup-not-ready'
 if entry['readyAtSeconds']>60 or entry['observedPostReadySeconds']<30:return 'observation-window-incomplete'
 if entry.get('explicitTermination',{}).get('returncode')!=0:return 'cleanup-unconfirmed'
 return 'complete-no-crash-observed'

def observe(udid,app,output,arm,approval,source_manifest):
 output=Path(output)
 if output.exists():raise ValueError('New evidence directory required')
 output.mkdir(parents=True)
 approved=json.loads(Path(approval).read_text());source=json.loads(Path(source_manifest).read_text())
 if arm not in ('baseline','candidate') or source['sourceCommit']!=approved['sourceCommit'] or source['runtime']!=approved['runtimes'][arm]:raise ValueError('Source/runtime arm drift')
 resources=approved['runtimes'][arm]['files'];app=Path(app)
 info=plistlib.loads((app/'Info.plist').read_bytes())
 if info['CFBundleIdentifier']!=BUNDLE:raise ValueError('Wrong diagnostic app')
 actual={str(p.relative_to(app/'Web/runtime')):hashlib.sha256(p.read_bytes()).hexdigest() for p in (app/'Web/runtime').rglob('*') if p.is_file()}
 if actual!=resources or any(p.is_symlink() for p in (app/'Web/runtime').rglob('*')):raise ValueError('Built runtime inventory mismatch')
 for name in ['shell.js']:
  if hashlib.sha256((app/'Web'/name).read_bytes()).hexdigest()!=source['files']['staged/App/Resources/Web/'+name]:raise ValueError('Built shell differs from staged source')
 for name in ['startup-journal.js','audio-recovery-injection.js','startup-resources.json']:
  if hashlib.sha256((app/name).read_bytes()).hexdigest()!=source['files']['staged/'+name]:raise ValueError('Built diagnostic asset drift')
 inventory=checked(['xcrun','simctl','list','devices','available','--json']);selected=device(inventory,udid)
 (output/'simulator-inventory.json').write_text(inventory)
 receipt={'schema':1,'arm':arm,'actualOS':'18.2','udid':udid,'deviceName':selected['name'],'sourceCommit':source['sourceCommit'],'runtime':source['runtime'],'appExecutableSHA256':hashlib.sha256((app/info['CFBundleExecutable']).read_bytes()).hexdigest(),'startupReadinessDeadlineSeconds':60,'postReadyObservationSeconds':30,'maximumWindowSeconds':90,'attempts':[],'cacheColdness':'unknown; fresh app PID does not imply fresh WebContent/JIT/cache','claim':'startup observation only, not recovery acceptance or crash fix'}
 def persist(): (output/'control-results.json').write_text(json.dumps(receipt,indent=2)+'\n')
 persist()
 if selected['state']!='Booted':checked(['xcrun','simctl','boot',udid])
 checked(['xcrun','simctl','bootstatus',udid,'-b'],120)
 checked(['xcrun','simctl','install',udid,str(app)],60)
 container=Path(checked(['xcrun','simctl','get_app_container',udid,BUNDLE,'data']))
 if not container.is_absolute() or not container.is_dir():raise ValueError('Invalid simulator app container')
 reports=Path.home()/'Library/Logs/DiagnosticReports'
 all_since=time.time();prior_pids=set();prior_journals=set()
 for attempt in range(1,4):
  folder=output/f'attempt-{attempt}';folder.mkdir();entry={'attempt':attempt,'preLaunchTermination':command(['xcrun','simctl','terminate',udid,BUNDLE]),'wallStart':time.time(),'monotonicStart':time.monotonic(),'samples':[]};receipt['attempts'].append(entry);persist()
  try:
   env=dict(os.environ);env['SIMCTL_CHILD_AUDIO_RECOVERY_MODE']='startup-only'
   try:entry['launch']=command(['xcrun','simctl','launch',udid,BUNDLE,'-FlashNest.language','en','-AppleLanguages','(en)'],30,env)
   except subprocess.TimeoutExpired:entry['launch']={'returncode':-1,'stdout':'','stderr':'simctl launch command deadline30s'}
   pid=launched_pid(entry['launch']);entry['pid']=pid;entry['freshPID']=pid is not None and pid not in prior_pids
   if pid:prior_pids.add(pid)
   started=entry['monotonicStart'];readiness_deadline=started+60;ready_at=None
   while True:
    deadline=readiness_deadline if ready_at is None else ready_at+30
    remaining=deadline-time.monotonic()
    if remaining<=0:break
    alive=False
    if pid:
     p=command(['ps','-p',str(pid),'-o','comm='],min(5,remaining));alive=p['returncode']==0 and not p['truncated'] and Path(p['stdout'].strip()).name==info['CFBundleExecutable']
    entry['samples'].append({'elapsedSeconds':time.monotonic()-started,'pidAliveAsExpectedApp':alive})
    try:
     current=journals(container,folder/'journal-snapshots',resources,entry['wallStart'])
     matched=matching_journal(current,pid)
     now=time.monotonic()
     if ready_at is None and now<=readiness_deadline and ready(matched):ready_at=now;entry['readyJournalFile']=matched['file']
    except (ValueError,OSError) as error:entry['journalValidationError']=type(error).__name__
    entry['readyAtSeconds']=None if ready_at is None else ready_at-started
    persist()
    deadline=readiness_deadline if ready_at is None else ready_at+30
    remaining=deadline-time.monotonic()
    if remaining<=0:break
    time.sleep(min(2,remaining))
   entry['observedPostReadySeconds']=0 if ready_at is None else time.monotonic()-ready_at
   entry['observationElapsedSeconds']=time.monotonic()-started
   entry['wallBeforeTermination']=time.time();entry['monotonicBeforeTermination']=time.monotonic()
   try:entry['journalsBeforeTermination']=journals(container,folder/'journals',resources,entry['wallStart'])
   except ValueError as error:entry['journalValidationError']=str(error);entry['journalsBeforeTermination']=[]
   entry['crashesBeforeTermination']=crashes(reports,output/'crashes',all_since)
   persist() # Evidence survives before explicit process teardown.
  except Exception as error:
   entry['observationError']=type(error).__name__
   entry.setdefault('wallBeforeTermination',time.time())
  finally:
   # Never let evidence collection errors bypass bounded teardown; no restart/retry.
   try:entry['explicitTermination']=command(['xcrun','simctl','terminate',udid,BUNDLE])
   except Exception as error:entry['explicitTermination']={'returncode':-1,'errorType':type(error).__name__}
   entry['wallAfterTermination']=time.time()
  time.sleep(3) # Fixed bounded reporting grace, not an engine retry or startup extension.
  try:entry['crashesAfterTermination']=crashes(reports,output/'crashes',all_since)
  except Exception as error:entry['crashesAfterTermination']={'records':[],'omitted':1};entry['postTerminationCollectionError']=type(error).__name__
  relevant=[]
  entry['collectionIncomplete']=bool(entry.get('crashesBeforeTermination',{'omitted':1})['omitted'] or entry['crashesAfterTermination']['omitted'])
  for c in entry['crashesAfterTermination']['records']:
   stamp=capture_epoch(output/'crashes'/(c['sha256']+'.ips'))
   if stamp is None or entry['wallStart']<=stamp<=entry['wallBeforeTermination']:relevant.append(c['sha256'])
  entry['crashesCapturedDuringObservation']=relevant
  final_journal=matching_journal(entry.get('journalsBeforeTermination',[]),entry.get('pid'))
  entry['reusedJournalIdentity']=final_journal is not None and final_journal['file'] in prior_journals
  if final_journal:prior_journals.add(final_journal['file'])
  final_rows=final_journal['rows'] if final_journal else []
  entry['contextCreatedObserved']=any(x['phase']=='context-created' for x in final_rows)
  entry['executedBanners']=[{'flavor':x.get('flavor'),'backend':x.get('backend')} for x in final_rows if x['phase']=='instance-banner']
  entry['outcome']=outcome(entry)
  entry['completeObservation']=entry['outcome']=='complete-no-crash-observed'
  persist()
 receipt['allThreeComplete']=len(receipt['attempts'])==3 and all(x['completeObservation'] for x in receipt['attempts']);persist()
 return receipt['allThreeComplete']
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--udid',required=True);p.add_argument('--app',required=True);p.add_argument('--output',required=True);p.add_argument('--arm',choices=['baseline','candidate'],required=True);p.add_argument('--approval',required=True);p.add_argument('--source-manifest',required=True)
 a=p.parse_args();raise SystemExit(0 if observe(a.udid,a.app,a.output,a.arm,a.approval,a.source_manifest) else 1)

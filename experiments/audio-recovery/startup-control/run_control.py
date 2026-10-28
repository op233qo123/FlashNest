"""Three fixed no-gesture startup observations; no retries and no recovery claim."""
import argparse,datetime,hashlib,json,os,plistlib,re,subprocess,time,tempfile
from pathlib import Path
from collect import journals,crashes
BUNDLE='com.flashnest.audio-recovery.diagnostic'
RUNTIME='com.apple.CoreSimulator.SimRuntime.iOS-18-2'
def command(args,timeout=30,env=None,stdout_limit=65536):
 if stdout_limit not in (65536,524288):raise ValueError("Unapproved command output bound")
 with tempfile.TemporaryFile() as out,tempfile.TemporaryFile() as err:
  timed_out=False
  try: result=subprocess.run(args,stdout=out,stderr=err,timeout=timeout,env=env);code=result.returncode
  except subprocess.TimeoutExpired:code=-1;timed_out=True
  out.seek(0,2);stdout_bytes=out.tell();err.seek(0,2);stderr_bytes=err.tell()
  out.seek(0);err.seek(0);stdout=out.read(stdout_limit+1);stderr=err.read(65537)
  return {'returncode':code,'stdout':stdout[:stdout_limit].decode(errors='replace'),'stderr':stderr[:65536].decode(errors='replace'),'timedOut':timed_out,'truncated':len(stdout)>stdout_limit or len(stderr)>65536,'stdoutLimit':stdout_limit,'stdoutBytes':stdout_bytes,'stderrBytes':stderr_bytes,'stdoutTruncated':len(stdout)>stdout_limit,'stderrTruncated':len(stderr)>65536}
def checked(args,timeout=30,env=None,receipt_path=None,inventory=False):
 r=command(args,timeout,env,stdout_limit=524288) if inventory else command(args,timeout,env)
 if receipt_path:Path(receipt_path).write_text(json.dumps(r,indent=2)+"\n")
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

def report_metadata(path):
 try:
  text=Path(path).read_text();body=json.loads(text[text.index('\n')+1:])
  return {'captureEpoch':capture_epoch(path),
          'pid':body.get('pid') if type(body.get('pid')) is int else None,
          'coalitionID':body.get('coalitionID') if type(body.get('coalitionID')) is int else None,
          'diagnosticHost':body.get('procName')=='AudioRecoveryDiagnostic'}
 except (ValueError,KeyError,OSError,TypeError):return {'captureEpoch':None,'pid':None,'coalitionID':None,'diagnosticHost':False}

def reconcile_reports(attempts,collection,directory):
 records=[dict(c,**report_metadata(Path(directory)/(c['sha256']+'.ips'))) for c in collection['records']]
 for entry in attempts:
  associated=[];uncertain=[]
  for record in records:
   stamp=record['captureEpoch']
   if stamp is None:uncertain.append(record['sha256']);continue
   if entry['wallStart']<=stamp<=entry['wallBeforeTermination']:
    if record['diagnosticHost'] and record['pid']!=entry.get('pid'):
     uncertain.append(record['sha256']);continue
    associated.append(dict(record,association='native-host-PID-and-time' if record['diagnosticHost'] else 'shared-process-time-only-not-proven-ownership'))
  entry['associatedCrashRecords']=associated
  entry['unattributedReportDigests']=uncertain
  entry['crashesCapturedDuringObservation']=[r['sha256'] for r in associated]
  entry['collectionIncomplete']=bool(entry.get('collectionIncomplete') or collection['omitted'] or uncertain)
  entry['outcome']=outcome(entry);entry['completeObservation']=entry['outcome']=='complete-no-crash-observed'
 for record in records:
  record['associatedAttempts']=[e['attempt'] for e in attempts if any(r['sha256']==record['sha256'] for r in e['associatedCrashRecords'])]
  record['classification']='observation-window-association' if record['associatedAttempts'] else 'unassigned-or-outside-observation-windows'
 return records

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
 if entry.get('instrumentationProfile')=='passive-only':
  hashes=[x.get('scriptSHA256') for x in journal['rows'] if x['phase']=='native-script-registered']
  if hashes!=[entry.get('expectedRegisteredScriptSHA256')]:return 'registered-script-unconfirmed'
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
 profile=source.get('instrumentationProfile','instrumented')
 if profile not in ('instrumented','passive-only'):raise ValueError('Unknown instrumentation profile')
 if profile=='passive-only' and (app/'audio-recovery-injection.js').exists():raise ValueError('Passive profile bundles fault injector')
 assets=['startup-journal.js','startup-resources.json']+(['audio-recovery-injection.js'] if profile=='instrumented' else [])
 for name in assets:
  if hashlib.sha256((app/name).read_bytes()).hexdigest()!=source['files']['staged/'+name]:raise ValueError('Built diagnostic asset drift')
 inventory=checked(['xcrun','simctl','list','devices','available','--json'],receipt_path=output/'inventory-command.json',inventory=True);selected=device(inventory,udid)
 (output/'simulator-inventory.json').write_text(inventory)
 receipt={'schema':1,'arm':arm,'instrumentationProfile':profile,'registeredStartupScriptSHA256':source.get('registeredStartupScriptSHA256'),'audioStateCoverage':source.get('audioStateCoverage','existing-injector-context-observer'),'actualOS':'18.2','udid':udid,'deviceName':selected['name'],'sourceCommit':source['sourceCommit'],'runtime':source['runtime'],'appExecutableSHA256':hashlib.sha256((app/info['CFBundleExecutable']).read_bytes()).hexdigest(),'startupReadinessDeadlineSeconds':60,'postReadyObservationSeconds':30,'maximumWindowSeconds':90,'attempts':[],'cacheColdness':'unknown; fresh app PID does not imply fresh WebContent/JIT/cache','claim':'startup observation only, not recovery acceptance or crash fix'}
 def persist(): (output/'control-results.json').write_text(json.dumps(receipt,indent=2)+'\n')
 persist()
 if selected['state']!='Booted':checked(['xcrun','simctl','boot',udid],receipt_path=output/'boot-command.json')
 checked(['xcrun','simctl','bootstatus',udid,'-b'],120,receipt_path=output/'bootstatus-command.json')
 checked(['xcrun','simctl','install',udid,str(app)],60,receipt_path=output/'install-command.json')
 container=Path(checked(['xcrun','simctl','get_app_container',udid,BUNDLE,'data'],receipt_path=output/'container-command.json'))
 if not container.is_absolute() or not container.is_dir():raise ValueError('Invalid simulator app container')
 reports=Path.home()/'Library/Logs/DiagnosticReports'
 all_since=time.time();prior_pids=set();prior_journals=set()
 for attempt in range(1,4):
  folder=output/f'attempt-{attempt}';folder.mkdir();entry={'attempt':attempt,'instrumentationProfile':profile,'expectedRegisteredScriptSHA256':source.get('registeredStartupScriptSHA256'),'preLaunchTermination':command(['xcrun','simctl','terminate',udid,BUNDLE]),'wallStart':time.time(),'monotonicStart':time.monotonic(),'samples':[]};receipt['attempts'].append(entry);persist()
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
  entry['contextCreatedObserved']=None if profile=='passive-only' else any(x['phase']=='context-created' for x in final_rows)
  entry['executedBanners']=[{'flavor':x.get('flavor'),'backend':x.get('backend')} for x in final_rows if x['phase']=='instance-banner']
  entry['outcome']=outcome(entry)
  entry['completeObservation']=entry['outcome']=='complete-no-crash-observed'
  persist()
 receipt['finalReportingGraceStarted']=time.time();persist()
 time.sleep(60) # Report-spool grace only: all app observations have ended and apps are terminated.
 try:final_reports=crashes(reports,output/'crashes',all_since)
 except Exception as error:final_reports={'records':[],'omitted':1};receipt['finalCollectionError']=type(error).__name__
 # Include earlier retained reports even if the OS rotates the original spool file.
 retained={r['sha256']:r for entry in receipt['attempts'] for key in ['crashesBeforeTermination','crashesAfterTermination'] for r in entry.get(key,{'records':[]})['records']}
 retained.update({r['sha256']:r for r in final_reports['records']});final_reports['records']=list(retained.values())
 receipt['finalReportingGraceEnded']=time.time()
 receipt['finalCrashReports']=reconcile_reports(receipt['attempts'],final_reports,output/'crashes')
 receipt['finalReportOmissions']=final_reports['omitted']
 receipt['unassignedReportDigests']=[r['sha256'] for r in receipt['finalCrashReports'] if not r['associatedAttempts']]
 receipt['allThreeComplete']=not receipt['unassignedReportDigests'] and not receipt['finalReportOmissions'] and len(receipt['attempts'])==3 and all(x['completeObservation'] for x in receipt['attempts']);persist()
 return receipt['allThreeComplete']
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--udid',required=True);p.add_argument('--app',required=True);p.add_argument('--output',required=True);p.add_argument('--arm',choices=['baseline','candidate'],required=True);p.add_argument('--approval',required=True);p.add_argument('--source-manifest',required=True)
 a=p.parse_args();raise SystemExit(0 if observe(a.udid,a.app,a.output,a.arm,a.approval,a.source_manifest) else 1)

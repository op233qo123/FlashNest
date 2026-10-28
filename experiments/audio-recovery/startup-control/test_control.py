import copy,json,tempfile,unittest,uuid
from pathlib import Path
from unittest.mock import patch
from collect import journals,validate_journal,crashes
from run_control import BUNDLE,RUNTIME,device,launched_pid,ready,outcome,matching_journal,command
RESOURCES={'fixture.wasm':'a'*64}
def journal(pid=42):
 phases=['native-open','native-opened','shell-load-return','loadeddata','instance-banner','resource-request']
 rows=[{'nativeSequence':i+1,'phase':p} for i,p in enumerate(phases)]
 rows[0].update(processID=pid,caseMode='startup-only')
 rows[-1].update(resource='fixture.wasm',sha256='a'*64)
 return {'file':str(uuid.uuid4())+'.json','rows':rows}
def entry():
 return dict(attempt=1,explicitTermination={'returncode':0},freshPID=True,pid=42,samples=[{'pidAliveAsExpectedApp':True}],journalsBeforeTermination=[journal()],readyAtSeconds=58,observedPostReadySeconds=30,crashesCapturedDuringObservation=[])
class ControlTests(unittest.TestCase):
 def test_exact_os_and_unique_device(self):
  d={'devices':{RUNTIME:[{'udid':'u','isAvailable':True}]}}
  self.assertEqual(device(json.dumps(d),'u')['udid'],'u')
  for wrong in ['com.apple.CoreSimulator.SimRuntime.iOS-18-5','unknown']:
   with self.assertRaises(ValueError):device(json.dumps({'devices':{wrong:d['devices'][RUNTIME]}}),'u')
 def test_launch_pid_requires_exact_success(self):
  self.assertEqual(launched_pid({'returncode':0,'stdout':BUNDLE+': 42\n'}),42)
  for r in [{'returncode':1,'stdout':BUNDLE+': 42'}, {'returncode':0,'stdout':'other: 42'},{'returncode':0,'stdout':BUNDLE+': 42','truncated':True}]:self.assertIsNone(launched_pid(r))
 def test_both_load_orders_ready_without_candidate_audio(self):
  j=journal();self.assertTrue(ready(j));j['rows'][2:4]=reversed(j['rows'][2:4]);self.assertTrue(ready(j))
  for phase in ['native-opened','shell-load-return','loadeddata','instance-banner','resource-request']:
   x=journal();x['rows']=[r for r in x['rows'] if r['phase']!=phase];self.assertFalse(ready(x))
 def test_current_pid_and_unique_journal(self):
  j=journal();self.assertIsNone(matching_journal([j],43));self.assertIsNone(matching_journal([j,j],42));self.assertEqual(matching_journal([j],42),j)
 def test_full_postready_window_not_fixed_total(self):
  e=entry();self.assertEqual(outcome(e),'complete-no-crash-observed')
  e['observedPostReadySeconds']=2;self.assertEqual(outcome(e),'observation-window-incomplete')
  e['readyAtSeconds']=61;e['observedPostReadySeconds']=30;self.assertEqual(outcome(e),'observation-window-incomplete')
 def test_passive_requires_exact_native_registration_receipt(self):
  e=entry();e.update(instrumentationProfile='passive-only',expectedRegisteredScriptSHA256='a'*64)
  self.assertEqual(outcome(e),'registered-script-unconfirmed')
  e['journalsBeforeTermination'][0]['rows'].append({'phase':'native-script-registered','scriptSHA256':'a'*64})
  self.assertEqual(outcome(e),'complete-no-crash-observed')
  e['journalsBeforeTermination'][0]['rows'][-1]['scriptSHA256']='b'*64
  self.assertEqual(outcome(e),'registered-script-unconfirmed')
 def test_distinct_failure_outcomes(self):
  cases=[('freshPID',False,'launch-unconfirmed'),('readyAtSeconds',None,'startup-not-ready'),('collectionIncomplete',True,'evidence-incomplete'),('crashesCapturedDuringObservation',['x'],'crash-observed'),('samples',[{'pidAliveAsExpectedApp':False}],'process-exit-or-unconfirmed'),('journalsBeforeTermination',[],'journal-identity-unconfirmed')]
  for key,value,want in cases:
   e=entry();e[key]=value;self.assertEqual(outcome(e),want)
  for phase,want in [('native-failure','native-failure'),('journal-truncated','evidence-incomplete')]:
   e=entry();e['journalsBeforeTermination'][0]['rows'].append({'phase':phase});self.assertEqual(outcome(e),want)
 def test_bounded_whitelisted_journal(self):
  data=json.dumps(journal()['rows']).encode();self.assertEqual(len(validate_journal(data,RESOURCES)),6)
  for mutate in [lambda r:r[0].update(url='private'),lambda r:r[-1].update(sha256='b'*64),lambda r:r[0].update(nativeSequence=2)]:
   rows=json.loads(data);mutate(rows)
   with self.assertRaises(ValueError):validate_journal(json.dumps(rows).encode(),RESOURCES)
 def test_journal_copy_rejects_symlink_and_stale(self):
  with tempfile.TemporaryDirectory() as t:
   t=Path(t);d=t/'app/Documents/StartupDiagnostics';d.mkdir(parents=True);j=journal();p=d/j['file'];p.write_text(json.dumps(j['rows']))
   self.assertEqual(len(journals(t/'app',t/'out',RESOURCES,0)),1)
   self.assertEqual(journals(t/'app',t/'out',RESOURCES,10**12),[])
   p.unlink();d.rmdir();d.symlink_to(t/'out')
   with self.assertRaises(ValueError):journals(t/'app',t/'out',RESOURCES,0)
 def test_crash_allowlist_dedupe_and_explicit_omissions(self):
  with tempfile.TemporaryDirectory() as t:
   t=Path(t);r=t/'reports';r.mkdir();(r/'private.ips').write_text('private');(r/'AudioRecoveryDiagnostic-one.ips').write_text('diagnostic')
   (r/'com.apple.WebKit.WebContent-large.ips').write_bytes(b'x'*(2*1024*1024+1))
   got=crashes(r,t/'out',0);self.assertEqual(len(got['records']),1);self.assertEqual(got['omitted'],1)
   self.assertEqual(crashes(r,t/'out',0),got);self.assertEqual(len(list((t/'out').iterdir())),1)
 def test_crash_global_count_and_byte_caps_are_fail_closed(self):
  with tempfile.TemporaryDirectory() as t:
   t=Path(t);r=t/'reports';r.mkdir()
   for i in range(11):(r/f'AudioRecoveryDiagnostic-{i}.ips').write_text(str(i))
   got=crashes(r,t/'out',0);self.assertEqual(len(got['records']),10);self.assertEqual(got['omitted'],1)
  with tempfile.TemporaryDirectory() as t:
   t=Path(t);r=t/'reports';r.mkdir()
   for i in range(6):(r/f'AudioRecoveryDiagnostic-{i}.ips').write_bytes(bytes([i])*(2*1024*1024))
   got=crashes(r,t/'out',0);self.assertEqual(len(got['records']),5);self.assertEqual(got['omitted'],1);self.assertEqual(sum(p.stat().st_size for p in (t/'out').iterdir()),10*1024*1024)
 def test_command_deadline_is_evidence_not_retry(self):
  import subprocess
  with patch('run_control.subprocess.run',side_effect=subprocess.TimeoutExpired(['fake'],1)) as run:
   result=command(['fake'],1);self.assertTrue(result['timedOut']);self.assertEqual(run.call_count,1)
 def test_inventory_bound_and_preflight_failure_receipt(self):
  from run_control import checked
  def write_output(args,stdout,stderr,timeout,env):
   stdout.write(b'x'*70000)
   class Result:returncode=0
   return Result()
  with patch('run_control.subprocess.run',side_effect=write_output):
   self.assertTrue(command(['synthetic'])['truncated'])
   self.assertFalse(command(['synthetic'],stdout_limit=524288)['truncated'])
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'receipt.json'
   with patch('run_control.command',return_value={'returncode':1,'stdout':'','stderr':'actual preflight error','timedOut':False,'truncated':False}):
    with self.assertRaises(RuntimeError):checked(['xcrun','simctl'],receipt_path=p)
   self.assertEqual(json.loads(p.read_text())['stderr'],'actual preflight error')
   with patch('run_control.command',return_value={'returncode':0,'stdout':'prefix','stderr':'','timedOut':False,'truncated':True}):
    with self.assertRaises(RuntimeError):checked(['xcrun','simctl'],receipt_path=p,inventory=True)
   self.assertTrue(json.loads(p.read_text())['truncated'])
 def test_preflight_preserves_timeout_stderr_and_malformed_inventory(self):
  from run_control import checked
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'receipt.json'
   for result in [{'returncode':-1,'stdout':'','stderr':'','timedOut':True,'truncated':False},{'returncode':0,'stdout':'{}','stderr':'x'*65536,'timedOut':False,'truncated':True}]:
    with patch('run_control.command',return_value=result):
     with self.assertRaises(RuntimeError):checked(['xcrun','simctl'],receipt_path=p,inventory=True)
    self.assertEqual(json.loads(p.read_text()),result)
   with patch('run_control.command',return_value={'returncode':0,'stdout':'malformed','stderr':'','timedOut':False,'truncated':False}):
    text=checked(['xcrun','simctl'],receipt_path=p,inventory=True)
    with self.assertRaises(ValueError):device(text,'u')
   self.assertEqual(json.loads(p.read_text())['stdout'],'malformed')
 def test_delayed_report_reassigned_to_original_observation(self):
  from run_control import reconcile_reports
  with tempfile.TemporaryDirectory() as t:
   t=Path(t);digest='a'*64
   body={'captureTime':'1970-01-01 00:16:45.0000 +0000','pid':77,'coalitionID':12,'procName':'com.apple.WebKit.WebContent'}
   (t/(digest+'.ips')).write_text('{}\n'+json.dumps(body))
   first=entry();first.update(wallStart=1000,wallBeforeTermination=1030)
   second=entry();second.update(attempt=2,wallStart=1040,wallBeforeTermination=1070)
   records=reconcile_reports([first,second],{'records':[{'sha256':digest}],'omitted':0},t)
   self.assertEqual(first['outcome'],'crash-observed');self.assertEqual(second['outcome'],'complete-no-crash-observed')
   self.assertEqual(records[0]['coalitionID'],12);self.assertIn('not-proven-ownership',first['associatedCrashRecords'][0]['association'])
   body['procName']='AudioRecoveryDiagnostic';body['pid']=999;(t/(digest+'.ips')).write_text('{}\n'+json.dumps(body))
   first=entry();first.update(wallStart=1000,wallBeforeTermination=1030)
   reconcile_reports([first],{'records':[{'sha256':digest}],'omitted':0},t)
   self.assertEqual(first['outcome'],'evidence-incomplete')
 def test_report_boundaries_and_outside_window_remain_retained(self):
  from run_control import reconcile_reports
  with tempfile.TemporaryDirectory() as t:
   t=Path(t)
   for seconds,associated in [('40',True),('50',True),('55',False)]:
    digest='b'*64;body={'captureTime':'1970-01-01 00:16:'+seconds+'.0000 +0000','pid':77,'procName':'com.apple.WebKit.WebContent'}
    (t/(digest+'.ips')).write_text('{}\n'+json.dumps(body));e=entry();e.update(wallStart=1000,wallBeforeTermination=1010)
    records=reconcile_reports([e],{'records':[{'sha256':digest}],'omitted':0},t)
    self.assertEqual(bool(records[0]['associatedAttempts']),associated);self.assertEqual(len(records),1)
 def test_unparseable_or_omitted_final_reports_fail_closed(self):
  from run_control import reconcile_reports
  with tempfile.TemporaryDirectory() as t:
   t=Path(t);digest='a'*64;(t/(digest+'.ips')).write_text('malformed')
   for collection in [{'records':[{'sha256':digest}],'omitted':0},{'records':[],'omitted':1}]:
    e=entry();e.update(wallStart=1000,wallBeforeTermination=1030);reconcile_reports([e],collection,t);self.assertEqual(e['outcome'],'evidence-incomplete')
 def test_three_launches_finally_cleanup_and_window(self):
  import hashlib,plistlib
  from run_control import observe
  with tempfile.TemporaryDirectory() as t:
   t=Path(t);app=t/'app';runtime=app/'Web/runtime';runtime.mkdir(parents=True);(runtime/'fixture.wasm').write_bytes(b'wasm')
   (app/'Info.plist').write_bytes(plistlib.dumps({'CFBundleIdentifier':BUNDLE,'CFBundleExecutable':'AudioRecoveryDiagnostic'}));(app/'AudioRecoveryDiagnostic').write_bytes(b'bin')
   files={}
   for name in ['shell.js','startup-journal.js','audio-recovery-injection.js','startup-resources.json']:
    path=app/'Web'/name if name=='shell.js' else app/name;path.write_bytes(b'x');files['staged/App/Resources/Web/'+name if name=='shell.js' else 'staged/'+name]=hashlib.sha256(b'x').hexdigest()
   inventory={'fixture.wasm':hashlib.sha256(b'wasm').hexdigest()};arm={'files':inventory};a=t/'approval.json';a.write_text(json.dumps({'sourceCommit':'pinned','runtimes':{'candidate':arm}}));sm=t/'source.json';sm.write_text(json.dumps({'sourceCommit':'pinned','runtime':arm,'files':files}));container=t/'container';container.mkdir()
   clock=[0.];launches=[];terminations=[]
   def cmd(args,timeout=30,env=None,stdout_limit=65536):
    text='';code=0
    if args[:4]==['xcrun','simctl','list','devices']:text=json.dumps({'devices':{RUNTIME:[{'udid':'u','isAvailable':True,'state':'Booted','name':'iPhone'}]}})
    elif 'get_app_container'in args:text=str(container)
    elif 'launch'in args:launches.append(40+len(launches));text=BUNDLE+': '+str(launches[-1]);self.assertEqual(env['SIMCTL_CHILD_AUDIO_RECOVERY_MODE'],'startup-only')
    elif 'terminate'in args:terminations.append(True)
    elif args[0]=='ps':text='AudioRecoveryDiagnostic'
    return {'returncode':code,'stdout':text,'stderr':'','truncated':False}
   def js(*args):
    j=journal(launches[-1]);j['file']=f'journal-{launches[-1]}.json';j['rows'][-1]['sha256']=inventory['fixture.wasm'];return [j]
   with patch('run_control.command',side_effect=cmd),patch('run_control.time.monotonic',side_effect=lambda:clock[0]),patch('run_control.time.time',side_effect=lambda:1000+clock[0]),patch('run_control.time.sleep',side_effect=lambda n:clock.__setitem__(0,clock[0]+n)),patch('run_control.journals',side_effect=js),patch('run_control.crashes',return_value={'records':[],'omitted':0}):
    self.assertTrue(observe('u',app,t/'out','candidate',a,sm))
   result=json.loads((t/'out/control-results.json').read_text());self.assertEqual(len(launches),3);self.assertEqual(len(terminations),6);self.assertTrue(all(x['observedPostReadySeconds']==30 for x in result['attempts']))
   # Final collection errors must still terminate each launched app, retaining failure.
   launches.clear();terminations.clear();clock[0]=0
   with patch('run_control.command',side_effect=cmd),patch('run_control.time.monotonic',side_effect=lambda:clock[0]),patch('run_control.time.time',side_effect=lambda:1000+clock[0]),patch('run_control.time.sleep',side_effect=lambda n:clock.__setitem__(0,clock[0]+n)),patch('run_control.journals',side_effect=OSError('test')),patch('run_control.crashes',return_value={'records':[],'omitted':0}):
    self.assertFalse(observe('u',app,t/'out2','candidate',a,sm))
   self.assertEqual(len(launches),3);self.assertEqual(len(terminations),6)
if __name__=='__main__':unittest.main()

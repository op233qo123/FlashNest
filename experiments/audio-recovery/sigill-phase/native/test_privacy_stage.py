import hashlib,json,pathlib,tempfile,unittest
from export_public import export
from stage_one import ORIGINAL_INJECTOR
HERE=pathlib.Path(__file__).resolve().parent
class PrivacyStageTests(unittest.TestCase):
 def approval(self):return dict(kind='sigill-phase-diagnostic-not-shipping',authorizedObservationCount=1,buildCommit='a'*40,runID=1,artifactID=2,archiveSHA256='b'*64,runtimes={'diagnostic':{'files':{}}})
 def test_export_never_copies_raw_command_paths_or_crash_stacks(self):
  with tempfile.TemporaryDirectory()as t:
   t=pathlib.Path(t);private=t/'private';private.mkdir();a=t/'approval.json';a.write_text(json.dumps(self.approval()))
   e={'attempt':1,'outcome':'crash-observed','freshPID':True,'explicitTermination':{'returncode':0,'stderr':'PRIVATE_GAME'},'journalsBeforeTermination':[{'rows':[{'nativeSequence':1,'phase':'engine-second-start-call'}]}],'launch':{'stdout':'PRIVATE_GAME'},'wallStart':1,'pid':99,'associatedCrashRecords':[{'sha256':'a'*64,'association':'shared-process-time-only-not-proven-ownership','private':'PRIVATE_GAME'}]}
   (private/'control-results.json').write_text(json.dumps({'attempts':[e],'deviceName':'PRIVATE_GAME','singleObservationComplete':False}))
   reports=private/'crashes';reports.mkdir();raw=b'{}\n'+json.dumps({'procName':'com.apple.WebKit.WebContent','exception':{'signal':'SIGILL','type':'EXC_BAD_INSTRUCTION'},'cpuType':'ARM-64','faultingThread':0,'threads':[{'private':'PRIVATE_GAME','frames':[{'imageIndex':0,'imageOffset':999999,'symbol':'PRIVATE_GAME'},{'imageIndex':1,'imageOffset':128,'symbol':'PRIVATE_GAME'}]}],'usedImages':[{'name':'???','size':0,'base':999999},{'name':'JavaScriptCore','size':4096,'path':'PRIVATE_GAME','base':999999}],'path':'PRIVATE_GAME'}).encode();sha=hashlib.sha256(raw).hexdigest();(reports/(sha+'.ips')).write_bytes(raw)
   out=t/'public';result=export(private,out,a)
   self.assertEqual(set(p.name for p in out.iterdir()),{'observation.json','publication-manifest.json'})
   self.assertNotIn('PRIVATE_GAME',(out/'observation.json').read_text());self.assertEqual(result['crashes'][0]['signal'],'SIGILL')
   self.assertEqual(result['crashes'][0]['sha256'],sha)
   self.assertFalse(result['crashes'][0]['faultImageResolved']);self.assertEqual(result['crashes'][0]['faultThreadFrames'][1]['imageClass'],'JavaScriptCore')
   self.assertNotIn('999999',(out/'observation.json').read_text())
   self.assertEqual(result['attempts'][0]['crashAssociations'],[{'sha256':'a'*64,'association':'shared-process-time-only-not-proven-ownership'}])
 def test_missing_receipt_never_claims_actual_os(self):
  with tempfile.TemporaryDirectory()as t:
   t=pathlib.Path(t);a=t/'approval.json';a.write_text(json.dumps(self.approval()))
   result=export(t/'missing-private',t/'public',a)
   self.assertEqual(result['expectedOS'],'18.2');self.assertIsNone(result['actualOS'])
   self.assertEqual(result['attempts'],[]);self.assertFalse(result['singleObservationComplete'])
 def test_publication_rejects_second_attempt_and_unapproved_payload(self):
  for invalid in ['second','payload']:
   with tempfile.TemporaryDirectory()as t:
    t=pathlib.Path(t);private=t/'raw';private.mkdir();a=t/'approval.json';a.write_text(json.dumps(self.approval()))
    row={'nativeSequence':1,'phase':'document-start'}
    if invalid=='payload':row['url']='PRIVATE_GAME'
    e={'attempt':1,'journalsBeforeTermination':[{'rows':[row]}]}
    (private/'control-results.json').write_text(json.dumps({'attempts':[e,e]if invalid=='second'else[e]}))
    with self.assertRaises(ValueError):export(private,t/'public',a)
    self.assertFalse((t/'public').exists())
 def test_original_injector_and_proposal_phase_allowlists(self):
  self.assertEqual(hashlib.sha256((HERE/'audio-recovery-injection.js').read_bytes()).hexdigest(),ORIGINAL_INJECTOR)
  for path in ['collect.py','startup-journal.js','Host/StartupJournal.swift']:
   text=(HERE/path).read_text()
   for phase in ['engine-second-start-call','engine-second-start-return','engine-audio-constructor-return','engine-audio-constructor-error','engine-core-build-return','engine-initial-tick-call','engine-initial-tick-return']:self.assertIn(phase,text)
 def test_single_workflow_and_explicit_upload_boundary(self):
  s=(HERE/'observe-sigill-phase-ios18_2.yml').read_text();r=(HERE/'run_one.py').read_text()
  self.assertIn('github.run_attempt == 1',s);self.assertIn('runs-on: macos-14',s);self.assertNotIn('matrix:',s)
  self.assertEqual(s.count('"$NATIVE/run_one.py"'),1);self.assertNotIn('allThreeComplete',r);self.assertIn('for attempt in (1,):',r)
  self.assertIn('time.sleep(60)',r);self.assertIn('readiness_deadline=started+60',r);self.assertIn('ready_at+30',r)
  upload=s.split('uses: actions/upload-artifact')[1]
  self.assertNotIn('phase-private',upload);self.assertNotIn('build.log',upload);self.assertNotIn('xcresult',upload)
  self.assertIn('phase-public/observation.json',upload);self.assertIn('phase-public/publication-manifest.json',upload)
 def test_stage_never_changes_production_or_installs_late_probe(self):
  s=(HERE/'stage_one.py').read_text();self.assertIn('git',s);self.assertIn('archive',s);self.assertIn("'App','fixtures/lifecycle','Package.resolved'",s)
  self.assertNotIn('FlashNestLateAudioProbe',s);self.assertIn('registeredScript(source: injection)',s)
  self.assertNotIn('AudioRecoveryUITests:',(HERE/'project.yml').read_text())
if __name__=='__main__':unittest.main()

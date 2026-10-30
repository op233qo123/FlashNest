#!/usr/bin/env python3
import copy,json,tempfile,unittest,zipfile,struct
from pathlib import Path
from unittest.mock import patch
import package as n
class PackageTests(unittest.TestCase):
 def fixture(self):return n.c.load(n.ROOT/'inputs.json')
 def test_exact_scope(self):n.inputs(False)
 def test_disabled_never_dispatches(self):
  x=self.fixture();x['dispatchAllowed']=False
  with patch.object(n.c,'load',return_value=x),self.assertRaises(ValueError):n.inputs(False,True)
 def test_no_native_acceptance_or_default_on(self):
  for k in ('nativeAccepted','fullGatePassed','physicalDeviceCertified','originalCrashResolved','diagnosticOptInDefault'):
   x=self.fixture();x[k]=True
   with self.subTest(k=k),patch.object(n.c,'load',return_value=x),self.assertRaises(ValueError):n.inputs(False)
 def test_business_code_changes_reject(self):
  x=self.fixture();x['candidateAppFiles']['App/Player/PlayerSession.swift']='0'*64
  with patch.object(n.c,'load',return_value=x),self.assertRaises(ValueError):n.inputs(False)
 def test_other_runtime_rejects(self):
  x=self.fixture();x['candidateEngine']['runID']=0
  with patch.object(n.c,'load',return_value=x),self.assertRaises(ValueError):n.inputs(False)
  x=self.fixture();x['candidateRuntimeFiles']['ruffle.js']='0'*64
  with patch.object(n.c,'load',return_value=x),self.assertRaises(ValueError):n.inputs(False)
 def test_browser_identity_and_bytes_reject(self):
  x=self.fixture();x['browserEvidence']['cases']=5
  with patch.object(n.c,'load',return_value=x),self.assertRaises(ValueError):n.inputs(False)
  with self.assertRaises(ValueError):n.verify_browser(b'wrong',self.fixture(),{})
 def test_stage_requires_exact_build20_source(self):
  with tempfile.TemporaryDirectory() as t,self.assertRaises(ValueError):n.rebind(Path(t),b'',self.fixture())
 def test_same_device_package_safety(self):
  raw=struct.pack('<8I',0xfeedfacf,0x100000c,0,2,1,24,0,0)+struct.pack('<6I',0x32,24,2,0x110000,0x120200,0)
  self.assertTrue(n.c.device_macho(raw)['unsigned'])
  for p in ('Payload/FlashNest.app/game.swf','Payload/FlashNest.app/save.sol'):
   with self.assertRaises(ValueError):n.c.safe_ipa_members([zipfile.ZipInfo(p)])
 def test_no_engine_build_or_matrix_expansion(self):
  s=(n.ROOT/'workflow.yml').read_text();self.assertNotIn('build_engine.sh',s);self.assertNotIn('cargo ',s);self.assertIn('release-ipa-156-build22/run_selected_tests.py',s);self.assertEqual(s.count('-configuration Release -sdk iphoneos'),1)
 def test_selected_gate_rechecks_both_lanes_and_rejects_skip(self):
  import run_selected_tests as runner
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);r={'schema':'flashnest-selected-native-regression-v1','selectedNativeRegressionPassed':True,'selectedReleaseGatePassed':True,'runID':123,'head':'a'*40,'totalTestCount':16,'passedTests':16,'failedTests':0,'skippedTests':0,'expectedFailures':0,'sourceInventory':{},'fixtureSourceInstalled':{'bundleID':runner.FIXTURE_BUNDLE,'executableSHA256':'a'*64},'fullGatePassed':False,'physicalDeviceCertified':False,'nativePixelAcceptance':False,'samplingBackingPixelAcceptance':False}
   for lane,bundle,expected in [('unit','FlashNestTests',runner.UNIT),('ui','FlashNestUITests',runner.UI)]:
    counts={'passedTests':len(expected),'failedTests':0,'skippedTests':0,'expectedFailures':0};summary={'result':'Passed','totalTestCount':len(expected),**counts,'devicesAndConfigurations':[{'device':{'deviceId':'synthetic-device','osVersion':'18.2','platform':'iOS Simulator','architecture':'arm64'},**counts}]}
    raw=json.dumps(summary).encode();log='\n'.join("Test Case '-["+bundle+'.'+cls+' '+method+"]' passed" for cls,method in expected)
    (root/(lane+'-summary.json')).write_bytes(raw);(root/(lane+'.log')).write_text(log);v=runner.verify(summary,log,expected,bundle,'synthetic-device');v.update(summarySHA256=n.c.digest(raw),resultBundle=lane+'.xcresult');r[lane]=v;(root/(lane+'-verification.json')).write_text(json.dumps(v))
   r['expected']=r['unit']['expected']+r['ui']['expected'];r['actual']=r['unit']['actual']+r['ui']['actual']
   (root/'verification.json').write_text(json.dumps(r))
   with patch.dict(n.os.environ,{'GITHUB_RUN_ID':'123','GITHUB_SHA':'a'*40}),patch.object(runner,'source_inventory',return_value={}):
    gate=n.selected_gate(root,root);self.assertEqual(len(gate['selectedNativeMethods']),16)
    r['skippedTests']=1;(root/'verification.json').write_text(json.dumps(r))
    with self.assertRaises(ValueError):n.selected_gate(root,root)
    r['skippedTests']=0;(root/'verification.json').write_text(json.dumps(r));(root/'ui.log').write_text('')
    with self.assertRaises(ValueError):n.selected_gate(root,root)
import copy,json,pathlib,sys,unittest
ROOT=pathlib.Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT));import run_selected_tests as r
DEVICE='01234567-89AB-CDEF-0123-456789ABCDEF'
def evidence(bundle,expected):
 count=len(expected);counts=dict(passedTests=count,failedTests=0,skippedTests=0,expectedFailures=0)
 summary=dict(result='Passed',totalTestCount=count,**counts,devicesAndConfigurations=[dict(**counts,device=dict(deviceId=DEVICE,osVersion='18.2',platform='iOS Simulator',architecture='arm64'))])
 log='\n'.join("Test Case '-["+bundle+'.'+cls+' '+method+"]' passed (0.01 seconds)." for cls,method in expected)
 return summary,log
class SelectedRunner(unittest.TestCase):
 def test_exact_unit_and_ui_sets(self):
  for bundle,expected in [('FlashNestTests',r.UNIT),('FlashNestUITests',r.UI)]:
   summary,log=evidence(bundle,expected);proof=r.verify(summary,log,expected,bundle,DEVICE)
   self.assertEqual(set(proof['expected']),set(proof['actual']));self.assertEqual(len(proof['actual']),len(expected))
 def test_aggregate_pass_cannot_hide_missing_duplicate_foreign_method(self):
  summary,log=evidence('FlashNestTests',r.UNIT)
  for changed in ['\n'.join(log.splitlines()[1:]),log+'\n'+log.splitlines()[0],log.replace(r.UNIT[0][1],'testUnexpected'),log+"\nTest Case '-[OtherTests.Other testUnexpected]' passed (0.1 seconds)."]:
   with self.assertRaises(ValueError):r.verify(summary,changed,r.UNIT,'FlashNestTests',DEVICE)
 def test_skip_failure_wrong_device_and_bundle_rejected(self):
  summary,log=evidence('FlashNestTests',r.UNIT)
  for key,value in [('skippedTests',1),('failedTests',1),('expectedFailures',1),('totalTestCount',14),('passedTests',True)]:
   mutated=copy.deepcopy(summary);mutated[key]=value
   with self.assertRaises(ValueError):r.verify(mutated,log,r.UNIT,'FlashNestTests',DEVICE)
  for key,value in [('osVersion','18.1'),('architecture','x86_64'),('platform','iOS'),('deviceId','other')]:
   mutated=copy.deepcopy(summary);mutated['devicesAndConfigurations'][0]['device'][key]=value
   with self.assertRaises(ValueError):r.verify(mutated,log,r.UNIT,'FlashNestTests',DEVICE)
  with self.assertRaises(ValueError):r.verify(summary,log,r.UNIT,'FlashNestUITests',DEVICE)
 def test_existing_inventory_and_explicit_method_selectors(self):
  self.assertEqual(len(r.selectors('FlashNestTests',r.UNIT)),15);self.assertEqual(len(r.UI),1)
  self.assertEqual(r.BUDGETS['unitMethodSeconds'],120);self.assertEqual(r.BUDGETS['uiMethodSeconds'],420)

if __name__=='__main__':unittest.main()

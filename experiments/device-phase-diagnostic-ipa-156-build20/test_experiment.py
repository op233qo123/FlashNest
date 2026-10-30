#!/usr/bin/env python3
import copy,json,struct,tempfile,unittest,zipfile,plistlib,re
from pathlib import Path
from unittest.mock import patch
import experiment as e
import package_checks as c

class Tests(unittest.TestCase):
 def fixture(self):return c.load(e.ROOT/'inputs.json')
 def test_explicit_scope(self):e.inputs(False)
 def test_acceptance_overclaims_reject(self):
  for k in ('nativeAccepted','fullGatePassed','physicalDeviceCertified'):
   x=self.fixture();x[k]=True
   with self.subTest(k=k),patch.object(c,'load',return_value=x),self.assertRaises(ValueError):e.inputs(False)
 def test_missing_experimental_override_rejects(self):
  x=self.fixture();x['experimentalGateOverride']=False
  with patch.object(c,'load',return_value=x),self.assertRaises(ValueError):e.inputs(False)
 def test_extra_product_source_delta_rejects(self):
  x=self.fixture();x['appGateOnFiles']['App/FlashNestApp.swift']='0'*64
  with patch.object(c,'load',return_value=x),self.assertRaises(ValueError):e.inputs(False)
 def test_wrong_version_or_commit_rejects(self):
  for k,v in [('build','18'),('bundleID','other'),('sourceCommit','0'*40),('xcode','16.4')]:
   x=self.fixture();x[k]=v
   with self.subTest(k=k),patch.object(c,'load',return_value=x),self.assertRaises(ValueError):e.inputs(False)
 def test_actual_gate_overlay_hashes_and_only_two_changes(self):
  x=self.fixture();self.assertEqual(len(x['appGateOffFiles']),204)
  for p,row in x['gateOverlay'].items():
   self.assertEqual(row['before'],x['appGateOffFiles'][p]);self.assertEqual(row['after'],x['appGateOnFiles'][p]);self.assertNotEqual(row['before'],row['after'])
 def test_overlay_rejects_wrong_input_before_write(self):
  with tempfile.TemporaryDirectory() as t,self.assertRaises(ValueError):e.overlay(Path(t),self.fixture())
 def test_two_file_overlay_applies_exact_bytes(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);x=self.fixture();before={};after={}
   for p,row in x['gateOverlay'].items():
    f=root/p;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(row['old']);before[p]=c.digest(f.read_bytes());after[p]=c.digest(row['new'].encode());row['before']=before[p];row['after']=after[p]
   x['appGateOffFiles']=before;x['appGateOnFiles']=after;e.overlay(root,x);self.assertEqual(c.file_map(root),after)
 def test_recipe_drift_rejects(self):
  x=self.fixture();x['recipeFiles']['experiment.py']='0'*64
  with patch.object(c,'load',return_value=x),self.assertRaises(ValueError):e.inputs()
 def assert_version_alignment(self,x,project,debug):
  expected={'CFBundleShortVersionString':x['version'],'CFBundleVersion':x['build']}
  for key,value in expected.items():
   self.assertEqual(debug[key],value)
   self.assertEqual(re.findall(r"^\s*"+key+r": '([^']+)'$",project,re.M),[value])
  self.assertEqual(re.findall(r"^\s*MARKETING_VERSION: '([^']+)'$",project,re.M),[x['version']])
  self.assertEqual(re.findall(r"^\s*CURRENT_PROJECT_VERSION: '([^']+)'$",project,re.M),[x['build']])
 def test_all_package_version_sources_align(self):
  x=self.fixture();project=(e.ROOT/'overlay/project.yml').read_text();debug=plistlib.loads((e.ROOT/'overlay/App/Info-Debug.plist').read_bytes())
  self.assert_version_alignment(x,project,debug)
  for key in ('CFBundleVersion','CFBundleShortVersionString'):
   bad=dict(debug);bad[key]='19'
   with self.subTest(key=key),self.assertRaises(AssertionError):self.assert_version_alignment(x,project,bad)
  with self.assertRaises(AssertionError):self.assert_version_alignment(x,project.replace("CURRENT_PROJECT_VERSION: '20'","CURRENT_PROJECT_VERSION: '19'"),debug)
 def test_diagnostic_default_on_rejected(self):
  x=self.fixture();x['diagnosticOptInDefault']=True
  with patch.object(c,'load',return_value=x),self.assertRaises(ValueError):e.inputs(False)
 def test_runtime_overlay_rejected(self):
  x=self.fixture();p='App/Resources/Web/runtime/ruffle.js';x['diagnosticAppFiles'][p]='0'*64;x['diagnosticOverlay'][p]={'before':x['appGateOnFiles'].get(p),'after':'0'*64}
  with patch.object(c,'load',return_value=x),self.assertRaises(ValueError):e.inputs(False)
 def test_missing_overlay_entry_rejected(self):
  x=self.fixture();x['diagnosticOverlay'].pop(next(iter(x['diagnosticOverlay'])))
  with patch.object(c,'load',return_value=x),self.assertRaises(ValueError):e.inputs(False)
 def test_diagnostic_overlay_wrong_before_does_not_write(self):
  with tempfile.TemporaryDirectory() as t,self.assertRaises(ValueError):e.diagnostic_overlay(Path(t),self.fixture())
 def test_focused_receipt_rejects_skip_duplicate_missing(self):
  import run_focused_tests as r
  expected=[('LoadingPhaseDiagnosticsTests','testA')]
  summary={'result':'Passed','totalTestCount':1,'passedTests':1,'failedTests':0,'skippedTests':0,'expectedFailures':0,'devicesAndConfigurations':[{'device':{'osVersion':'18.2'}}]}
  log="Test Case '-[FlashNestTests.LoadingPhaseDiagnosticsTests testA]' passed"
  r.verify(summary,log,expected)
  for bad in ('',log+'\n'+log):
   with self.assertRaises(ValueError):r.verify(summary,bad,expected)
  summary['skippedTests']=1
  with self.assertRaises(ValueError):r.verify(summary,log,expected)
 def macho(self,platform=2,sdk=0x120200):return struct.pack('<8I',0xfeedfacf,0x100000c,0,2,1,24,0,0)+struct.pack('<6I',0x32,24,platform,0x110000,sdk,0)
 def test_actual_device_contract(self):self.assertEqual(c.device_macho(self.macho())['sdk'],'18.2')
 def test_simulator_or_sdk_substitution_reject(self):
  for b in (self.macho(platform=7),self.macho(sdk=0x120500)):
   with self.assertRaises(ValueError):c.device_macho(b)
 def test_private_and_harness_payload_reject(self):
  for p in ('Payload/FlashNest.app/game.swf','Payload/FlashNest.app/saves.sol','Payload/FlashNest.app/Tests/a','Payload/FlashNest.app/_CodeSignature/a'):
   with self.subTest(p=p),self.assertRaises(ValueError):c.safe_ipa_members([zipfile.ZipInfo(p)])
 def test_unknown_outer_document_reject(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);(p/'private.pdf').write_text('x')
   with self.assertRaises(ValueError):c.verify_outer_payload(p)
 def test_source_mutation_reject(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);(p/'App').mkdir();(p/'App/a').write_text('bad')
   with self.assertRaises(ValueError):c.verify_sources(p,{'App/a':'0'*64})
 def test_workflow_one_device_build_not_full_workflow(self):
  s=(e.ROOT/'build-device-phase-diagnostic-ipa.yml').read_text();self.assertEqual(s.count('-configuration Release -sdk iphoneos'),1);self.assertIn('macos-14',s);self.assertIn('EXPERIMENTAL-UNVERIFIED',s);self.assertNotIn('cancel-in-progress: true',s);self.assertNotIn('test-ipa-156-restored',s);self.assertNotIn('workflow_dispatches',s)

if __name__=='__main__':unittest.main()

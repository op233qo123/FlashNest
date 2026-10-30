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
  s=(n.ROOT/'workflow.yml').read_text();self.assertNotIn('build_engine.sh',s);self.assertNotIn('cargo ',s);self.assertIn('device-phase-diagnostic-ipa-156-build20/run_focused_tests.py',s);self.assertEqual(s.count('-configuration Release -sdk iphoneos'),1)
if __name__=='__main__':unittest.main()

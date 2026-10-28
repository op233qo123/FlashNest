#!/usr/bin/env python3
"""Actual schema4 App integration checks; legacy schema3 suite remains separate."""
import argparse,copy,hashlib,importlib,io,json,subprocess,sys,unittest
from pathlib import Path
sys.dont_write_bytecode=True
p=argparse.ArgumentParser();p.add_argument('--app',required=True,type=Path);a=p.parse_args();app=a.app.resolve();sys.path.insert(0,str(app/'scripts'))
r=importlib.import_module('fetch_runtime');c=importlib.import_module('composite_runtime')
lock=json.loads((app/'runtime.lock.json').read_text());manifest=json.loads((app/'runtime.files.json').read_text());identity=(app/'App/Resources/Web/runtime-identity.json').read_bytes();archive=(app/lock['archivePath']).read_bytes()
class ActualCompositeTests(unittest.TestCase):
 def test_actual_schema_and_full_archive(self):
  self.assertEqual(lock['schemaVersion'],4);self.assertEqual(json.loads(identity)['schemaVersion'],3)
  actual=r.verified_runtime(archive,lock,manifest,identity)
  self.assertEqual(set(actual),set(manifest))
  for name,data in actual.items():self.assertEqual(data,(app/'App/Resources/Web/runtime'/name).read_bytes())
 def test_identity_mutation(self):
  with self.assertRaises(ValueError):r.verified_identity(lock,manifest,identity+b' ')
 def test_manifest_mutation(self):
  changed={**manifest,'ruffle.js':'0'*64}
  with self.assertRaises(ValueError):r.verified_identity(lock,changed,identity)
 def test_invalid_schema_types(self):
  for bad in (True,'4',2,5):
   with self.subTest(schema=bad),self.assertRaises(ValueError):r.verified_identity({**lock,'schemaVersion':bad},manifest,identity)
 def test_legacy_not_relabelled(self):
  with self.assertRaises(ValueError):r.verified_identity({**lock,'schemaVersion':3},manifest,identity)
 def test_archive_hash_mutation(self):
  with self.assertRaises(ValueError):r.verified_runtime(archive,{**lock,'sha256':'0'*64},manifest,identity)
 def test_archive_length_mutation(self):
  with self.assertRaises(ValueError):r.verified_runtime(archive,{**lock,'archiveBytes':len(archive)+1},manifest,identity)
 def test_no_gate_activation(self):self.assertIn('static let runtimeValidated = false',(app/'App/Player/RenderSamplingSettings.swift').read_text())
 def test_exact_frame_test_pin(self):self.assertIn('private static let identitySHA256 = "'+hashlib.sha256(identity).hexdigest()+'"',(app/'Tests/FrameOrderRuntimeTests.swift').read_text())
 def test_packaged_resource_verifier(self):importlib.import_module('verify_bundled_runtime').verify_web(app/'App/Resources/Web',app)
suite=unittest.TestSuite();loader=unittest.TestLoader();suite.addTests(loader.loadTestsFromTestCase(ActualCompositeTests))
# Select the original source-only class explicitly, not its imported schema3 class.
suite.addTests(loader.loadTestsFromTestCase(importlib.import_module('test_static').StaticTests))
for module in ('test_package_metadata','test_licenses','test_localization'):
 suite.addTests(loader.loadTestsFromModule(importlib.import_module(module)))
result=unittest.TextTestRunner(verbosity=2).run(suite)
if not result.wasSuccessful() or result.skipped:raise SystemExit('Actual final App checks failed/skipped')
for argv in [['node','--check','App/Resources/Web/shell.js'],['node','scripts/test_audio_warning.js'],['node','scripts/test_shell.js'],['node','scripts/test_shell.js','zh-Hans']]:subprocess.run(argv,cwd=app,check=True,timeout=120)
print(json.dumps({'actualCompositeAppPassed':True,'pythonTests':result.testsRun,'skipped':0,'engineSHA256':lock['sha256'],'nativeAccepted':False,'ipaBuilt':False}))

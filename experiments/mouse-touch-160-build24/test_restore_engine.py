#!/usr/bin/env python3
"""Descriptor negatives and real archive restoration (set FLASHNEST_ENGINE_ARCHIVE)."""
import copy, importlib.util, json, os, pathlib, shutil, tempfile, unittest
HERE=pathlib.Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('restore_engine',HERE/'restore_engine.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class DescriptorTests(unittest.TestCase):
 def test_exact_descriptor(self):m.validate_descriptor(m.descriptor_for_backup())
 def test_each_identity_pin_cannot_change(self):
  for key in m.PIN:
   with self.subTest(key=key):
    d=m.descriptor_for_backup();d['originalArtifact'][key]='wrong'
    with self.assertRaises(ValueError):m.validate_descriptor(d)
 def test_expiry_cannot_be_falsified(self):
  d=m.descriptor_for_backup();d['originalArtifactAvailability']='available'
  with self.assertRaises(ValueError):m.validate_descriptor(d)
 def test_no_new_execution_claims(self):
  for key in ['engineBuildExecutedThisRun','coreTestsExecutedThisRun']:
   d=m.descriptor_for_backup();d[key]=True
   with self.assertRaises(ValueError):m.validate_descriptor(d)
 def test_wrong_types_rejected(self):
  d=m.descriptor_for_backup();d['engineBuildExecutedThisRun']=0
  with self.assertRaises(ValueError):m.validate_descriptor(d)
 def test_extra_keys_rejected(self):
  d=m.descriptor_for_backup();d['unavailable']=False
  with self.assertRaises(ValueError):m.validate_descriptor(d)
 def test_missing_provenance_rejected(self):
  d=m.descriptor_for_backup();del d['backupProvenance']
  with self.assertRaises(ValueError):m.validate_descriptor(d)
 def test_other_transport_rejected(self):
  d=m.descriptor_for_backup();d['transport']='live-api-download'
  with self.assertRaises(ValueError):m.validate_descriptor(d)

@unittest.skipUnless(os.environ.get('FLASHNEST_ENGINE_ARCHIVE'),'Set FLASHNEST_ENGINE_ARCHIVE for real ZIP integration')
class RealArchiveTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.tmp.name)
  self.archive=pathlib.Path(os.environ['FLASHNEST_ENGINE_ARCHIVE']).resolve()
  self.original=HERE.parent/'loader-unload-fix'
  self.descriptor=self.root/'descriptor.json';self.descriptor.write_text(json.dumps(m.descriptor_for_backup()))
  self.out=self.root/'runtime';self.lock=self.root/'lock.json';self.receipt=self.root/'reuse.json'
 def tearDown(self):self.tmp.cleanup()
 def restore(self):return m.reuse(self.archive,self.descriptor,self.original,self.out,self.lock,self.receipt,'a'*40,'123')
 def test_real_backup_preserves_12_runtime_and_original_core_receipt(self):
  result=self.restore()
  self.assertEqual(len(result['runtimeFiles']),12)
  self.assertEqual(result['sourceCommit'],m.PIN['head'])
  self.assertEqual(result['runID'],str(m.PIN['runID']))
  self.assertEqual(result['consumerHead'],'a'*40)
  self.assertEqual(result['consumerRunID'],'123')
  self.assertFalse(result['engineBuildExecutedThisRun'])
  self.assertFalse(result['coreTestsExecutedThisRun'])
  self.assertFalse(result['applicationPass'])
  proof=pathlib.Path(str(self.receipt)+'.restoration.json')
  self.assertEqual(result['archivalRestoration']['receiptSHA256'],m.sha(proof.read_bytes()))
  r=json.loads(proof.read_text());self.assertFalse(r['liveArtifactDownloadPerformed'])
  self.assertEqual(r['descriptor']['originalArtifactAvailability'],'unavailable')
  self.assertEqual({p.name:m.sha(p.read_bytes()) for p in self.out.iterdir()},result['runtimeFiles'])
  self.assertEqual(json.loads(self.lock.read_text())['runtimeFiles'],result['runtimeFiles'])
 def test_modified_zip_rejected(self):
  p=self.root/'changed.zip';data=bytearray(self.archive.read_bytes());data[50]^=1;p.write_bytes(data);self.archive=p
  with self.assertRaisesRegex(ValueError,'bytes/hash'):self.restore()
  self.assertFalse(self.out.exists())
 def test_truncated_zip_rejected(self):
  p=self.root/'changed.zip';p.write_bytes(self.archive.read_bytes()[:-1]);self.archive=p
  with self.assertRaisesRegex(ValueError,'bytes/hash'):self.restore()
 def test_archive_symlink_rejected(self):
  p=self.root/'link.zip';p.symlink_to(self.archive);self.archive=p
  with self.assertRaisesRegex(ValueError,'Regular archive'):self.restore()
 def test_descriptor_symlink_rejected(self):
  p=self.root/'link.json';p.symlink_to(self.descriptor);self.descriptor=p
  with self.assertRaisesRegex(ValueError,'Regular descriptor'):self.restore()
 def test_changed_validator_rejected(self):
  p=self.root/'original';shutil.copytree(self.original,p);self.original=p
  (p/'integration/stage_candidate.py').write_text('# changed')
  with self.assertRaisesRegex(ValueError,'Original validator changed'):self.restore()
 def test_changed_build_source_rejected(self):
  p=self.root/'original';shutil.copytree(self.original,p);self.original=p
  (p/'build/build.sh').write_text('# changed')
  with self.assertRaisesRegex(ValueError,'Current source differs'):self.restore()
 def test_preexisting_outputs_rejected(self):
  self.receipt.write_text('do not overwrite')
  with self.assertRaisesRegex(ValueError,'outputs must be fresh'):self.restore()
  self.assertEqual(self.receipt.read_text(),'do not overwrite')
 def test_preexisting_restore_proof_rejected(self):
  pathlib.Path(str(self.receipt)+'.restoration.json').write_text('do not overwrite')
  with self.assertRaisesRegex(ValueError,'Restoration receipt must be fresh'):self.restore()
 def test_invalid_consumer_rejected(self):
  with self.assertRaisesRegex(ValueError,'Consumer CI identity'):
   m.reuse(self.archive,self.descriptor,self.original,self.out,self.lock,self.receipt,'invalid','123')

if __name__=='__main__':unittest.main()

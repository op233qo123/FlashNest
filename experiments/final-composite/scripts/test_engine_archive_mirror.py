#!/usr/bin/env python3
"""Transport controls: no fallback, same whole archive; no engine rebuild."""
import copy,json,shutil,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import stage_validation_runtime as s
ROOT=Path(__file__).resolve().parents[1]
class MirrorTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
  self.e={'bytes':6,'sha256':s.sha(b'abcdef')};self.t={'kind':'repository-exact-archive-parts','repository':'op233qo123/FlashNest','parts':[{'path':'engine-mirrors/ruffle-composite-40794075613.zip.part1','bytes':3,'sha256':s.sha(b'abc')},{'path':'engine-mirrors/ruffle-composite-40794075613.zip.part2','bytes':3,'sha256':s.sha(b'def')}],**self.e}
  self.file=self.root/self.t['parts'][0]['path'];self.file.parent.mkdir();self.file.write_bytes(b'abc');(self.root/self.t['parts'][1]['path']).write_bytes(b'def')
 def test_mirror_never_calls_network(self):
  with patch.object(s,'ROOT',self.root),patch.object(s,'fetch',side_effect=AssertionError('network')):self.assertEqual(s.fetch_engine(self.e,self.t),b'abcdef')
 def test_baseline_and_unspecified_engine_transport_keep_original_fetch(self):
  with patch.object(s,'fetch',return_value=b'original') as fetch:self.assertEqual(s.fetch_engine(self.e,None),b'original');fetch.assert_called_once_with(self.e)
 def test_invalid_identity_or_path_rejects_without_fallback(self):
  for key,value in [('kind','other'),('repository','other/repo'),('bytes',4),('sha256','0'*64)]:
   t=dict(self.t);t[key]=value
   with self.subTest(key=key),patch.object(s,'ROOT',self.root),patch.object(s,'fetch',side_effect=AssertionError('fallback')),self.assertRaises(ValueError):s.fetch_engine(self.e,t)
 def test_bad_size_and_same_size_content_reject(self):
  for raw in (b'abcd',b'bad'):
   self.file.write_bytes(raw)
   with patch.object(s,'ROOT',self.root),patch.object(s,'fetch',side_effect=AssertionError('fallback')),self.assertRaises(ValueError):s.fetch_engine(self.e,self.t)
 def test_missing_or_symlink_file_and_parent_reject(self):
  self.file.unlink()
  with patch.object(s,'ROOT',self.root),self.assertRaises(ValueError):s.fetch_engine(self.e,self.t)
  target=self.root/'target';target.write_bytes(b'abc');self.file.symlink_to(target)
  with patch.object(s,'ROOT',self.root),self.assertRaises(ValueError):s.fetch_engine(self.e,self.t)
  self.file.unlink();(self.root/self.t['parts'][1]['path']).unlink();self.file.parent.rmdir();self.file.parent.symlink_to(self.root)
  with patch.object(s,'ROOT',self.root),self.assertRaises(ValueError):s.fetch_engine(self.e,self.t)
 def test_part_order_path_hash_and_bounds_reject(self):
  variants=[]
  t=copy.deepcopy(self.t);t['parts'].reverse();variants.append(t)
  t=copy.deepcopy(self.t);t['parts'][0]['path']='../private';variants.append(t)
  t=copy.deepcopy(self.t);t['parts'][0]['sha256']='0'*64;variants.append(t)
  t=copy.deepcopy(self.t);t['parts'][0]['bytes']=8*1024*1024;variants.append(t)
  t=copy.deepcopy(self.t);t['parts'][0]['bytes']=True;variants.append(t)
  t=copy.deepcopy(self.t);t['parts'].pop();variants.append(t)
  for t in variants:
   with patch.object(s,'ROOT',self.root),patch.object(s,'fetch',side_effect=AssertionError('fallback')),self.assertRaises(ValueError):s.fetch_engine(self.e,t)
 def test_concat_hash_rejects_even_if_parts_each_match(self):
  t=copy.deepcopy(self.t);self.file.write_bytes(b'xyz');t['parts'][0]['sha256']=s.sha(b'xyz')
  with patch.object(s,'ROOT',self.root),self.assertRaises(ValueError):s.fetch_engine(self.e,t)
 def test_exact_real_archive_full_provenance_and_correspondence(self):
  lock=json.loads((ROOT/'validation-lock.json').read_text());original_engine=copy.deepcopy(lock['engine']);lock['dispatchAllowed']=True
  for part in lock['engineArchiveTransport']['parts']:shutil.copyfile(ROOT/part['path'],self.root/part['path'])
  (self.root/'validation-lock.json').write_text(json.dumps(lock))
  with patch.object(s,'ROOT',self.root),patch.object(s,'fetch',side_effect=AssertionError('network')):s.main()
  evidence=json.loads((self.root/'evidence/engine-staging.json').read_text());self.assertEqual(evidence['engine'],original_engine);self.assertEqual(evidence['archiveTransport'],lock['engineArchiveTransport']);self.assertEqual(s.sha((self.root/'staged-engine-archive.zip').read_bytes()),original_engine['sha256'])
if __name__=='__main__':unittest.main()

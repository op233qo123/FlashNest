#!/usr/bin/env python3
"""Read-only source/byte checks; real AVM2 behavior is gated by RawSOLWebKitTests."""
import hashlib,importlib.util,json,struct,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('rawfixture',Path(__file__).with_name('make_raw_sol_fixtures.py'))
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
class RawFixtureTests(unittest.TestCase):
 def test_original_swf_determinism_headers_manifest_and_api_markers(self):
  manifest=json.loads((ROOT/'fixtures/raw-sol/manifest.json').read_text())
  for name,writer in [('writer.swf',True),('reader.swf',False)]:
   b=(ROOT/'fixtures/raw-sol'/name).read_bytes();self.assertEqual(b,f.make(writer));self.assertEqual(b[:4],b'FWS\x25');self.assertEqual(struct.unpack_from('<I',b,4)[0],len(b))
   self.assertEqual(hashlib.sha256(b).hexdigest(),manifest['files'][name]['sha256'])
   for marker in [b'SharedObject',b'getLocal',b'FlashNestFixture',b'RAW_SOL_BEFORE',b'RAW_SOL_READY']:self.assertIn(marker,b)
   self.assertEqual(b'flush' in b,writer)
 def test_original_sol_exact_structure_and_independent_value(self):
  b=(ROOT/'fixtures/raw-sol/original-progress-7.sol').read_bytes();self.assertEqual(len(b),50)
  self.assertEqual(b[:2],b'\x00\xbf');self.assertEqual(struct.unpack_from('>I',b,2)[0],len(b)-6)
  self.assertEqual(b[6:16],b'TCSO\x00\x04\x00\x00\x00\x00');n=struct.unpack_from('>H',b,16)[0]
  self.assertEqual(b[18:18+n],b'FlashNestFixture');self.assertEqual(b[18+n:22+n],b'\0\0\0\3')
  self.assertEqual(b[22+n:],b'\x11progress\x04\x07\0')
 def test_fixture_files_are_small_and_original_inventory_exact(self):
  expected={'README.txt','manifest.json','reader.swf','writer.swf','original-progress-7.sol'}
  files=list((ROOT/'fixtures/raw-sol').iterdir());self.assertEqual({p.name for p in files},expected)
  self.assertTrue(all(p.is_file() and not p.is_symlink() and p.stat().st_size<4096 for p in files))
if __name__=='__main__':unittest.main()

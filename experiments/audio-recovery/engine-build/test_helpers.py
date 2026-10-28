import importlib.util,json,os,tempfile,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent
def module(name,path):
 spec=importlib.util.spec_from_file_location(name,path);value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value
p=module('recovery_provenance',HERE/'candidate_provenance.py')
c=module('recovery_patch',HERE.parent/'check_patch.py')
class Helpers(unittest.TestCase):
 def test_exact_layer_inputs(self):
  data=p.inputs();self.assertEqual(len(data['patches']),3)
  self.assertEqual(data['patches'][1]['sha256'],c.WEAK_SHA)
  self.assertEqual(data['patches'][2]['sha256'],c.inputs()[0]['patchSHA256'])
  self.assertEqual(data['expectedOriginalCoreJSTests'],59)
  self.assertEqual(data['expectedAudioOperationTests'],23)
 def test_patch_scope_and_only_intentional_overlap(self):
  paths=[x for row in p.inputs()['patches'] for x,_ in p.patch_paths(p.ROOT/row['path'])]
  self.assertEqual(paths.count('web/src/audio.rs'),2)
  self.assertEqual(set(paths),c.PATHS|{'core/src/display_object/movie_clip.rs'})
 def test_reject_unsafe_patch_paths(self):
  with tempfile.TemporaryDirectory() as d:
   file=Path(d)/'bad.patch'
   for old,new in [('a/../x','b/../x'),('a/x','b//tmp/x'),('a/old','b/new')]:
    file.write_text('--- '+old+'\n+++ '+new+'\n')
    with self.assertRaises(AssertionError):list(p.patch_paths(file))
 def test_exact_source_forward_and_reverse(self):
  source=Path(os.environ['RUFFLE_SOURCE_DIR']);self.assertTrue(c.verify(source)['exactForwardAndReverse'])
 def test_source_drift_rejected(self):
  source=Path(os.environ['RUFFLE_SOURCE_DIR'])
  with tempfile.TemporaryDirectory() as d:
   out=Path(d)
   for row in c.inputs()[0]['files']:
    if row['originalSHA256']:
     target=out/row['path'];target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((source/row['path']).read_bytes())
   path=out/'web/src/audio.rs';path.write_bytes(path.read_bytes()+b'\n')
   with self.assertRaises(AssertionError):c.verify(out)
 def test_existing_new_helper_rejected(self):
  source=Path(os.environ['RUFFLE_SOURCE_DIR'])
  with tempfile.TemporaryDirectory() as d:
   out=Path(d)
   for row in c.inputs()[0]['files']:
    target=out/row['path'];target.parent.mkdir(parents=True,exist_ok=True)
    target.write_bytes((source/row['path']).read_bytes() if row['originalSHA256'] else b'foreign')
   with self.assertRaises(AssertionError):c.verify(out)
if __name__=='__main__':unittest.main()

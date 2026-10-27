import importlib.util,json,tempfile,unittest,subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('audio_provenance',HERE/'candidate_provenance.py');p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
class Helpers(unittest.TestCase):
 def test_exact_inputs_and_patch_scope(self):
  c=p.inputs();self.assertEqual(len(c['patches']),2);self.assertEqual(c['expectedOriginalCoreJSTests'],59)
  paths=[x for row in c['patches'] for x,_ in p.patch_paths(p.ROOT/row['path'])]
  self.assertEqual(paths,['core/src/display_object/movie_clip.rs','web/src/audio.rs'])
 def test_reject_unsafe_patch_paths(self):
  with tempfile.TemporaryDirectory() as d:
   f=Path(d)/'x.patch'
   for old,new in [('a/../x','b/../x'),('a/x','b//tmp/x'),('a/old','b/new')]:
    f.write_text('--- '+old+'\n+++ '+new+'\n')
    with self.assertRaises(AssertionError):list(p.patch_paths(f))
 def test_exact_js_count_and_negative_reports(self):
  with tempfile.TemporaryDirectory() as d:
   d=Path(d);log=d/'log';summary=d/'summary'
   tests=[{'fullTitle':f'original {i}'}for i in range(59)]
   report={'stats':{'tests':59,'passes':59,'pending':0,'failures':0},'tests':tests,'passes':tests,'pending':[],'failures':[]}
   log.write_text(json.dumps(report));r=subprocess.run(['python3',str(HERE/'check_js_results.py'),str(log),str(summary)],capture_output=True);self.assertEqual(r.returncode,0,r.stderr);self.assertTrue(json.loads(summary.read_text())['allPassed'])
   for bad in ({**report,'stats':{**report['stats'],'pending':1}},{**report,'passes':tests[:-1]}):
    log.write_text(json.dumps(bad));r=subprocess.run(['python3',str(HERE/'check_js_results.py'),str(log),str(summary)],capture_output=True);self.assertNotEqual(r.returncode,0);self.assertFalse(json.loads(summary.read_text())['allPassed'])
if __name__=='__main__':unittest.main()

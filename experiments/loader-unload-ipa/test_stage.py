import importlib.util,json,pathlib,tempfile,unittest
ROOT=pathlib.Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('candidate_stage',ROOT/'stage.py');e=importlib.util.module_from_spec(spec);spec.loader.exec_module(e)
class StageTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.tmp.name);self.old=e.ROOT;e.ROOT=self.root
  runtime={f'{i}.wasm' if i<2 else f'{i}.js':str(i)*64 for i in range(12)}
  (self.root/'candidate-runtime-reference.json').write_text(json.dumps({'runtimeFiles':runtime}))
  self.overlay={'App/Resources/Web/Ruffle-MODIFICATIONS.md':{'before':'old','after':'new'}}
  (self.root/'resource-overlay.json').write_text(json.dumps(self.overlay));self.cfg={'additionalFiles':{'Tests/Probe.swift':'test'}};self.save()
  self.case={'App/Main.swift':'product','App/Resources/Web/Ruffle-MODIFICATIONS.md':'old','App/Resources/Web/runtime/old.wasm':'oldruntime','Tests/Existing.swift':'existing'}
 def save(self):(self.root/'inputs.json').write_text(json.dumps(self.cfg))
 def tearDown(self):e.ROOT=self.old;self.tmp.cleanup()
 def test_exact_product_scope(self):
  result,runtime=e.effective_inventory(self.case)
  self.assertEqual(result['App/Main.swift'],'product');self.assertEqual(result['Tests/Existing.swift'],'existing');self.assertEqual(result['Tests/Probe.swift'],'test');self.assertNotIn('App/Resources/Web/runtime/old.wasm',result);self.assertEqual(len(runtime),12);self.assertEqual(len(result),16)
 def test_notice_preimage_rejected(self):
  self.case['App/Resources/Web/Ruffle-MODIFICATIONS.md']='bad'
  with self.assertRaises(ValueError):e.effective_inventory(self.case)
 def test_additional_app_rejected(self):
  self.cfg['additionalFiles']={'App/Probe.swift':'bad'};self.save()
  with self.assertRaises(ValueError):e.effective_inventory(self.case)
 def test_existing_test_override_rejected(self):
  self.cfg['additionalFiles']={'Tests/Existing.swift':'bad'};self.save()
  with self.assertRaises(ValueError):e.effective_inventory(self.case)
 def test_runtime_missing_rejected(self):
  (self.root/'candidate-runtime-reference.json').write_text(json.dumps({'runtimeFiles':{}}))
  with self.assertRaises(ValueError):e.effective_inventory(self.case)
 def test_source_symlink_rejected(self):
  (self.root/'link').symlink_to(self.root/'inputs.json')
  with self.assertRaises(ValueError):e.inventory(self.root)
if __name__=='__main__':unittest.main()

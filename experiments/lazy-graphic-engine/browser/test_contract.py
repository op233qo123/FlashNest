import importlib.util,json,pathlib,tempfile,unittest
spec=importlib.util.spec_from_file_location('harness',pathlib.Path(__file__).with_name('run.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class ContractTests(unittest.TestCase):
 def test_disabled_never_runs(self):
  with self.assertRaises(AssertionError):m.validate(json.loads(pathlib.Path(__file__).with_name('contract.template.json').read_text()),{})
 def test_runtime_pin_and_candidate_difference(self):
  with tempfile.TemporaryDirectory() as t:
   root=pathlib.Path(t);(root/'ruffle.js').write_bytes(b'runtime');roots={'baseline':root,'candidate':root}
   c={'dispatchAllowed':True,'runtimes':{arm:{'files':m.inventory(root),'selectedWasmSHA256':arm} for arm in roots}}
   m.validate(c,roots);c['runtimes']['candidate']['selectedWasmSHA256']='baseline'
   with self.assertRaises(AssertionError):m.validate(c,roots)
   c['runtimes']['candidate']['selectedWasmSHA256']='candidate';(root/'ruffle.js').write_bytes(b'mutated')
   with self.assertRaises(AssertionError):m.validate(c,roots)
 def test_call_classification_not_decode_counter(self):
  self.assertEqual(m.uploads16({'calls':[{'name':'texImage2D','width':16,'height':16},{'name':'drawElements','width':None,'height':None},{'name':'texSubImage3D','width':16,'height':16},{'name':'texImage2D','width':256,'height':256}]}),2)
 def test_three_cases_only(self):self.assertEqual(len(m.FIXTURES),3)
if __name__=='__main__':unittest.main()

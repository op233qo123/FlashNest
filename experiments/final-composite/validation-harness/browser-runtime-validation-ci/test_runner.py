import copy,importlib.util,json,pathlib,tempfile,unittest
ROOT=pathlib.Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('browser_ci',ROOT/'run.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
H=ROOT.parent/'browser-runtime-validation'
class Tests(unittest.TestCase):
 def engine(self):return {'sha256':'a'*64,'wasmSHA256':['b'*64,'c'*64],'wasmFlavorBySHA256':{'b'*64:'extensions','c'*64:'mvp'}}
 def result(self,chosen='b'*64):return {'passed':True,'selection':'unmodified-shipping-default','runtimeBindingSHA256':'d'*64,'rows':[{'arm':'candidate','fetchedWasm':[{'sha256':chosen}]} for _ in range(232)],'browserVersion':'156.0.8078.47','preflightSHA256':'e'*64}
 def verified(self):return {'rows':290,'phases':870,'trustedClicks':4350}
 def test_actual_extensions_receipt(self):
  r=m.receipt_from_result(self.result(),self.verified(),self.engine(),'d'*64)
  self.assertEqual(r['realLoaderPaths'],['extensions']);self.assertEqual(r['mvpSelectionStatus'],'not-executed-no-supported-route');self.assertEqual(r['selectedWasmSHA256'],'b'*64);self.assertEqual(r['skipped'],0)
 def test_actual_mvp_receipt_not_forced(self):
  r=m.receipt_from_result(self.result('c'*64),self.verified(),self.engine(),'d'*64)
  self.assertEqual(r['realLoaderPaths'],['mvp']);self.assertEqual(r['mvpSelectionStatus'],'executed-shipping-default')
 def test_no_flavor_guess(self):
  e=self.engine();e.pop('wasmFlavorBySHA256')
  with self.assertRaises(ValueError):m.receipt_from_result(self.result(),self.verified(),e,'d'*64)
 def test_incomplete_or_duplicate_map_rejected(self):
  for mapping in [{'b'*64:'extensions'},{'b'*64:'extensions','c'*64:'extensions'}]:
   e=self.engine();e['wasmFlavorBySHA256']=mapping
   with self.assertRaises(ValueError):m.receipt_from_result(self.result(),self.verified(),e,'d'*64)
 def test_incomplete_rows_rejected(self):
  r=self.result();r['rows'].pop()
  with self.assertRaises(ValueError):m.receipt_from_result(r,self.verified(),self.engine(),'d'*64)
 def test_mixed_path_one_matrix_rejected(self):
  r=self.result();r['rows'][0]['fetchedWasm'][0]['sha256']='c'*64
  with self.assertRaises(ValueError):m.receipt_from_result(r,self.verified(),self.engine(),'d'*64)
 def test_unrecognized_wasm_rejected(self):
  with self.assertRaises(ValueError):m.receipt_from_result(self.result('f'*64),self.verified(),self.engine(),'d'*64)
 def test_incomplete_verifier_rejected(self):
  v=self.verified();v['trustedClicks']=1
  with self.assertRaises(ValueError):m.receipt_from_result(self.result(),v,self.engine(),'d'*64)
 def test_wrong_binding_rejected(self):
  with self.assertRaises(ValueError):m.receipt_from_result(self.result(),self.verified(),self.engine(),'f'*64)
 def test_frozen_harness(self):
  self.assertEqual(len(m.verify_harness(H,'c688a37a6b1938f05ca6a5308e26852e4d5271a5098931f90c4be136362bd1f6')),51)
 def test_wrong_harness_pin_rejected(self):
  with self.assertRaises(ValueError):m.verify_harness(H,'0'*64)
 def test_fresh_outputs_only(self):
  with tempfile.TemporaryDirectory() as d:
   p=pathlib.Path(d);(p/'validation-lock.json').write_text(json.dumps({'lanes':{'browser':{}}}));(p/'evidence/browser').mkdir(parents=True)
   with self.assertRaises(ValueError):m.Runner(p,H)
 def test_stale_acceptance_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p=pathlib.Path(d);(p/'validation-lock.json').write_text(json.dumps({'lanes':{'browser':{}}}));(p/'evidence').mkdir();(p/'evidence/browser-acceptance.json').write_text('{}')
   with self.assertRaises(ValueError):m.Runner(p,H)
 def test_no_installs_or_dispatch_or_shell(self):
  s=(ROOT/'run.py').read_text()
  self.assertNotIn('shell=True',s);self.assertNotIn('--no-sandbox',s);self.assertNotIn('requests.post',s);self.assertNotIn('pip install',s)
if __name__=='__main__':unittest.main()

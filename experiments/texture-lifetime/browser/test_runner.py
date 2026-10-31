import copy,importlib.util,pathlib,unittest
spec=importlib.util.spec_from_file_location('runner',pathlib.Path(__file__).with_name('run.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Identity(unittest.TestCase):
 def setUp(self):
  self.w=[{'name':'x.wasm','path':'/runtime/x.wasm','status':200,'origin':'http://127.0.0.1:1','requestId':'one'}];self.q=[{'path':'/runtime/x.wasm','status':200,'sha256':'h','bytes':42,'requestId':'one'}];self.l={'selectedWasmSHA256':'h','runtimeFiles':{'x.wasm':{'sha256':'h'}}}
 def test_exact(self):m.verify_wasm_identity(self.w,self.q,self.l,'http://127.0.0.1:1');self.assertEqual(self.w[0]['servedSHA256'],'h')
 def test_missing(self):
  for w,q in [([],self.q),(self.w,[])]:
   with self.assertRaises(AssertionError):m.verify_wasm_identity(copy.deepcopy(w),q,self.l,'http://127.0.0.1:1')
 def test_changed(self):
  for key,value in [('sha256','wrong'),('path','/other/x.wasm'),('status',404),('requestId','other')]:
   q=copy.deepcopy(self.q);q[0][key]=value
   with self.assertRaises(AssertionError):m.verify_wasm_identity(copy.deepcopy(self.w),q,self.l,'http://127.0.0.1:1')
 def test_wrong_response(self):
  for key,value in [('path','/other/x.wasm'),('status',404),('requestId','other')]:
   w=copy.deepcopy(self.w);w[0][key]=value
   with self.assertRaises(AssertionError):m.verify_wasm_identity(w,self.q,self.l,'http://127.0.0.1:1')
class FixtureRoute(unittest.TestCase):
 def test_named_child_alias(self):
  runtime=pathlib.Path('/tmp/runtime');fixtures=pathlib.Path('/tmp/fixtures')
  self.assertEqual(m.resolve_path('/texture-child.swf?cycle=1',runtime,fixtures),fixtures/'texture-child.swf')
  self.assertEqual(m.resolve_path('/fixtures/texture-child.swf?cycle=2',runtime,fixtures),fixtures/'texture-child.swf')
  for path in ['/other.swf','/fixtures/../../escape','/runtime/../escape']:
   with self.assertRaises((AssertionError,KeyError,ValueError)):m.resolve_path(path,runtime,fixtures)
if __name__=='__main__':unittest.main()

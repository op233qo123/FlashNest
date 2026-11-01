import hashlib,json,pathlib,tempfile,unittest,zipfile,sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
from stage_candidate import stage
h=lambda b:hashlib.sha256(b).hexdigest()
j=lambda v:(json.dumps(v)+'\n').encode()
class StageTests(unittest.TestCase):
 def fixture(self,d):
  delta=b'{}\n';(d/'delta.json').write_bytes(delta)
  runtime={('e.wasm' if i==0 else 'm.wasm' if i==1 else f'f{i}.js'):str(i).encode() for i in range(12)}
  prov=j({'run':{'GITHUB_SHA':'head','GITHUB_RUN_ID':'123'},'acceptedSourceLockSHA256':'7200650c24fe505844ea676c02c44a42dd2ee7bc484344e775e4458d84566494'})
  lock={'sourceCommit':'head','runID':'123','provenanceSHA256':h(prov),'flavorMapSHA256':h(b'{}'),'candidateDeltaSHA256':h(delta),'acceptedRecipeCommit':'6d3e4322293972a28ab2cdf129ee6398f40f0f37','runtimeFiles':{n:h(b) for n,b in runtime.items()},'selectedWasm':'e.wasm','selectedWasmSHA256':h(runtime['e.wasm']),'runtimeAccepted':False,'ipaBuilt':False}
  tests=[{'name':['bitmap-cache','loader-events','loader-loadbytes-events'][i],'passed':1,'failed':0,'ignored':0,'logSHA256':h(b'pass')} for i in range(3)]
  files={'runtime-lock.json':j(lock),'provenance.json':prov,'flavor-map.json':b'{}','source-correspondence/candidate-delta/source-lock.json':delta,'source-correspondence/staging/candidate-source.json':b'{}','full-source-before.json':b'{}','full-source-after.json':b'{}','core-tests/results.json':j({'candidateSourceManifestSHA256':h(b'{}'),'passed':True,'tests':tests,'run':{'GITHUB_SHA':'head','GITHUB_RUN_ID':'123'}})}
  files.update({'runtime/'+n:b for n,b in runtime.items()});files.update({'core-tests/'+['bitmap-cache','loader-events','loader-loadbytes-events'][i]+'.log':b'pass' for i in range(3)})
  return files
 def run_case(self,change=None,fail=False):
  with tempfile.TemporaryDirectory() as tmp:
   d=pathlib.Path(tmp);files=self.fixture(d)
   if change:change(files)
   manifest={n:{'sha256':h(b),'bytes':len(b)} for n,b in files.items()}
   files['artifact-files.json']=j(manifest)
   with zipfile.ZipFile(d/'a.zip','w') as z:
    for n,b in files.items():z.writestr(n,b)
   call=lambda:stage(d/'a.zip',d/'runtime',d/'lock.json',d/'receipt.json',d/'delta.json','head','123')
   if fail:
    with self.assertRaises((ValueError,KeyError)):call()
    self.assertFalse((d/'runtime').exists())
   else:
    result=call();self.assertEqual(len(result['runtimeFiles']),12)
 def test_valid(self):self.run_case()
 def test_traversal(self):self.run_case(lambda f:f.update({'../evil':b'x'}),True)
 def test_absolute(self):self.run_case(lambda f:f.update({'/evil':b'x'}),True)
 def test_wrong_delta(self):self.run_case(lambda f:f.update({'source-correspondence/candidate-delta/source-lock.json':b'x'}),True)
 def test_wrong_wasm(self):self.run_case(lambda f:f.update({'runtime/e.wasm':b'x'}),True)
 def test_extra_runtime(self):self.run_case(lambda f:f.update({'runtime/extra':b'x'}),True)
 def test_core_wrong_log(self):self.run_case(lambda f:f.update({'core-tests/bitmap-cache.log':b'x'}),True)
 def test_wrong_run(self):
  def change(f):
   x=json.loads(f['runtime-lock.json']);x['runID']='other';f['runtime-lock.json']=j(x)
  self.run_case(change,True)
if __name__=='__main__':unittest.main()

"""Synthetic archive tests, not a built runtime or native observation."""
import hashlib,json,pathlib,tempfile,unittest,zipfile
from verify_engine import verify,UPSTREAM
class EngineTests(unittest.TestCase):
 def fixture(self,t):
  content=b'FAKE-NOT-WASM';runtime={'fixture.wasm':{'sha256':hashlib.sha256(content).hexdigest(),'bytes':len(content)}}
  files={'runtime/fixture.wasm':content,'runtime-manifest.json':json.dumps(runtime).encode()}
  provenance={'schema':1,'kind':'sigill-phase-diagnostic-not-shipping','status':'diagnostic-only-unpromoted','upstreamCommit':UPSTREAM,'experiment':{'GITHUB_SHA':'c'*40,'GITHUB_RUN_ID':'12'},'files':{k:{'sha256':hashlib.sha256(v).hexdigest(),'bytes':len(v)}for k,v in files.items()}}
  files['provenance.json']=json.dumps(provenance).encode()
  with zipfile.ZipFile(t/'runtime.zip','w')as z:
   for key,value in files.items():z.writestr(key,value)
  a=dict(repository='op233qo123/FlashNest',kind=provenance['kind'],authorizedObservationCount=1,runID=12,artifactID=13,buildCommit='c'*40,archiveBytes=(t/'runtime.zip').stat().st_size,archiveSHA256=hashlib.sha256((t/'runtime.zip').read_bytes()).hexdigest(),provenanceSHA256=hashlib.sha256(files['provenance.json']).hexdigest(),runtimes={'diagnostic':{'directory':'runtime','files':{'fixture.wasm':runtime['fixture.wasm']['sha256']}}})
  (t/'run.json').write_text(json.dumps({'id':12,'head_sha':'c'*40,'status':'completed','conclusion':'success'}));(t/'artifact.json').write_text(json.dumps({'id':13,'workflow_run':{'id':12},'name':'FlashNest-sigill-phase-diagnostic-engine','expired':False,'size_in_bytes':a['archiveBytes']}))
  p=t/'approval.json';p.write_text(json.dumps(a));return p,a
 def test_exact_synthetic_inventory(self):
  with tempfile.TemporaryDirectory()as t:
   t=pathlib.Path(t);p,a=self.fixture(t);self.assertEqual(verify(t,p),t/'extracted')
   with self.assertRaises(ValueError):verify(t,p)
 def test_wrong_approval_fields_fail_closed(self):
  for key,value in [('kind','shipping'),('authorizedObservationCount',3),('artifactID',99),('archiveSHA256','0'*64),('provenanceSHA256','0'*64),('buildCommit','0'*40)]:
   with self.subTest(key=key),tempfile.TemporaryDirectory()as t:
    t=pathlib.Path(t);p,a=self.fixture(t);a[key]=value;p.write_text(json.dumps(a))
    with self.assertRaises(ValueError):verify(t,p)
if __name__=='__main__':unittest.main()

import copy,hashlib,json,pathlib,struct,sys,tempfile,unittest,zlib
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import generate_fixtures as g
from verify_as import verify_as
class Retention(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory();cls.out=pathlib.Path(cls.tmp.name);cls.manifest=g.generate(cls.out)
 @classmethod
 def tearDownClass(cls):cls.tmp.cleanup()
 def test_budgets_and_prior_bitmap_exact(self):
  files=self.manifest['files'];baseline=json.loads((ROOT/'bitmap-fixture-manifest.json').read_text())
  for name in ('old','new'):self.assertEqual(files['retention/'+name+'.swf'],baseline['files']['sized-bitmap/'+name+'.swf'])
  for name,size in [('prefix-a',48),('prefix-b',44)]:self.assertEqual(files['retention/'+name+'.swf']['actualDecodedBytes'],size*g.MIB)
  self.assertLessEqual(self.manifest['totals']['compressedBytes'],144*g.MIB)
  self.assertLessEqual(self.manifest['totals']['actualDecodedBytes'],154*g.MIB)
  self.assertEqual(files['retention/main-retain.swf'],files['retention/main-drop.swf'])
 def test_prefix_shape_and_no_instantiated_binary(self):
  for name in ('prefix-a','prefix-b'):
   tags=self.manifest['files']['retention/'+name+'.swf']['tags']
   self.assertEqual([t['code'] for t in tags],[69,87,82,76,1,0])
   self.assertEqual(tags[-3]['symbols'],[[0,'PrefixChild']])
  sources='\n'.join(p.read_text() for p in (ROOT/'as').glob('*.as'))
  self.assertNotIn('ByteArray',sources);self.assertNotIn('System.gc',sources)
 def test_corrupt_prefix_rejected(self):
  data=bytearray((self.out/'retention/prefix-a.swf').read_bytes());data[4]^=1
  with self.assertRaises(AssertionError):g.inspect(data)
  data=bytearray((self.out/'retention/prefix-b.swf').read_bytes());data[-1]^=1
  with self.assertRaises(zlib.error):g.inspect(data)
 def records(self,case):
  phases=['parent.ready','prefix-b.first-frame','prefix-a.init','prefix-b.init','prefix-a.first-frame','prefix-a.complete','prefix-b.complete','prefixes.ready','old.open','old.first-frame','old.init','old.complete','old.awaiting-space','transition.key',('prefixes.retained' if case=='retain' else 'prefixes.references-dropped'),'before-unload','old.unload-event','returned-unload','new.open','new.first-frame','new.init','new.complete','parent.done']
  rows=[dict(sequence=i+1,phase=p,timeMs=i,bytesLoaded=-1,bytesTotal=-1) for i,p in enumerate(phases)]
  for r in rows:
   if r['phase'].startswith('prefixes.'):
    drop=r['phase']=='prefixes.references-dropped'
    r.update(liveLoaderRefs=0 if drop else 2,liveContentRefs=0 if drop else 2,attachedPrefixLoaders=0 if drop else 2,unloadCalls=2 if drop else 0,removeCalls=2 if drop else 0,unsubscribeCalls=8 if drop else 0,nullAssignments=4 if drop else 0)
  return rows
 def test_two_cases_and_interleaved_prefix_order(self):
  for case in ('retain','drop'):verify_as(self.records(case),case)
 def test_actual_null_core_two_branches_and_single_initialization(self):
  proof=json.loads((ROOT/'local-core-evidence.json').read_text())
  self.assertTrue(proof['semanticVerificationPassed']);self.assertTrue(proof['secondAddedToStageControl'])
  self.assertEqual(proof['logSHA256'],hashlib.sha256((ROOT/'core-smoke.log').read_bytes()).hexdigest())
  for case in ('retain','drop'):verify_as(proof['cases'][case]['phases'],case)
 def test_oracle_mutations_rejected(self):
  for case in ('retain','drop'):
   for phase,key,value in [('prefixes.ready','liveLoaderRefs',0),('prefixes.ready','attachedPrefixLoaders',0),('prefixes.retained' if case=='retain' else 'prefixes.references-dropped','liveContentRefs',1)]:
    rows=self.records(case);next(r for r in rows if r['phase']==phase)[key]=value
    with self.assertRaises(AssertionError):verify_as(rows,case)
   rows=self.records(case);next(r for r in rows if r['phase']=='prefix-a.complete')['phase']='unexpected'
   with self.assertRaises(AssertionError):verify_as(rows,case)
   with self.assertRaises(AssertionError):verify_as(self.records(case),'drop' if case=='retain' else 'retain')
if __name__=='__main__':unittest.main()

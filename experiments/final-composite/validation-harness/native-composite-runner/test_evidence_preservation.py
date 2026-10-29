"""Mocked command/error preservation only; no native test pass implied."""
import importlib.util,json,tempfile,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('runner',Path(__file__).with_name('run.py'));r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
class Verifier:
 def verify(self,summary,log,cfg):return {'lane':cfg['name'],'tests':cfg['expectedCount']}
class Fake(r.Runner):
 def __init__(self,root,primary=False,summary=False,export=False,result=True):
  self.out=root/'out';self.stage=root/'stage';self.out.mkdir();self.stage.mkdir();self.results=[];self.verifier=Verifier();self.calls=[];self.argv=[]
  self.primary=primary;self.summary_error=summary;self.export_error=export;self.has_result=result
  self.lanes={'sampling-candidate':r.lane('sampling-candidate','Scheme',['Module/Class/testOne'],900)}
 def budget(self):pass
 def command(self,argv,name,cwd=None,timeout=1200,allowed=(0,)):
  self.argv.append(list(map(str,argv)));self.calls.append((name,timeout));log=self.out/(name+'.log');log.write_text('raw command output')
  if name=='lane':
   if self.has_result:(self.stage/'lane.xcresult').mkdir()
   if self.primary:raise ValueError('Bounded command timed out: lane')
  elif name=='lane-summary':
   if self.primary:
    assert json.loads((self.out/'lane-primary-error.json').read_text())['error']=='Bounded command timed out: lane'
   if self.summary_error:raise ValueError('summary exit=64')
   log.write_text(json.dumps({'passedTests':1}))
  elif name=='lane-export':
   p=self.stage/'lane-attachments';p.mkdir();(p/'raw.json').write_text('{"observed":"before failure"}')
   if self.export_error:raise ValueError('export exit=64')
  return log
class EvidenceContracts(unittest.TestCase):
 def test_primary_timeout_survives_summary_error_and_exports(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);f=Fake(p,primary=True,summary=True)
   with self.assertRaisesRegex(ValueError,'Bounded command timed out: lane'):f.test_once(p,'P','D','sampling-candidate','lane')
   report=json.loads((f.out/'lane-execution-evidence.json').read_text())
   self.assertEqual(report['primaryError'],'Bounded command timed out: lane');self.assertEqual(report['extractionErrors'],[{'phase':'summary','error':'summary exit=64'}])
   self.assertTrue((f.out/'attachments/lane/raw.json').exists());self.assertEqual(f.results,[])
   self.assertEqual(dict(f.calls)['lane'],1200)
 def test_both_extraction_errors_and_partial_files_preserved(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);f=Fake(p,primary=True,summary=True,export=True)
   with self.assertRaisesRegex(ValueError,'Bounded command timed out'):f.test_once(p,'P','D','sampling-candidate','lane')
   report=json.loads((f.out/'lane-execution-evidence.json').read_text());self.assertEqual([e['phase'] for e in report['extractionErrors']],['summary','export'])
   self.assertTrue((f.out/'attachments/lane/raw.json').exists());self.assertFalse(report['accepted'])
 def test_extraction_failure_without_primary_cannot_pass(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);f=Fake(p,summary=True)
   with self.assertRaisesRegex(ValueError,'Evidence extraction failed'):f.test_once(p,'P','D','sampling-candidate','lane')
   self.assertIn('lane-export',dict(f.calls));self.assertEqual(f.results,[])
 def test_no_result_preserves_primary(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);f=Fake(p,primary=True,result=False)
   with self.assertRaisesRegex(ValueError,'Bounded command timed out'):f.test_once(p,'P','D','sampling-candidate','lane')
   self.assertEqual(json.loads((f.out/'lane-execution-evidence.json').read_text())['extractionErrors'][0]['phase'],'result')
 def test_success_still_requires_semantic_verifier(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);f=Fake(p);f.test_once(p,'P','D','sampling-candidate','lane');self.assertEqual(len(f.results),1)
   self.assertTrue((f.out/'lane-verification.json').exists())
 def test_semantic_verifier_failure_cannot_append_acceptance(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);f=Fake(p)
   class Reject:
    def verify(self,*args):raise ValueError('wrong selectors')
   f.verifier=Reject()
   with self.assertRaisesRegex(ValueError,'wrong selectors'):f.test_once(p,'P','D','sampling-candidate','lane')
   self.assertEqual(f.results,[]);self.assertTrue((f.out/'attachments/lane/raw.json').exists())
 def test_prebuilt_child_command_keeps_exact_selector_and_bounds(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);f=Fake(p);report=f.test_once(p,'P','D','sampling-candidate','lane',xctestrun='/fixed/Tests.xctestrun',append_result=False,attachment_group='parent')
   argv=f.argv[0];self.assertEqual(argv[:4],['xcodebuild','test-without-building','-xctestrun','/fixed/Tests.xctestrun'])
   self.assertEqual([x for x in argv if x.startswith('-only-testing:')],['-only-testing:Module/Class/testOne'])
   self.assertEqual(argv[argv.index('-maximum-test-execution-time-allowance')+1],'900');self.assertEqual(dict(f.calls)['lane'],1200)
   self.assertEqual(f.results,[]);self.assertEqual(report['tests'],1);self.assertTrue((f.out/'attachments/parent/lane/raw.json').exists())
if __name__=='__main__':unittest.main(verbosity=2)

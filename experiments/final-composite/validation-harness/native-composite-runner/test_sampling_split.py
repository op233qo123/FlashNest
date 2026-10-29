"""Source/product-bound execution models only; no native execution."""
import importlib.util,json,plistlib,tempfile,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('split',Path(__file__).with_name('run.py'));r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
class Fake(r.Runner):
 def __init__(self,p,fail=None):
  self.out=p/'out';self.stage=p/'stage';self.out.mkdir();self.stage.mkdir();self.results=[];self.commands=[];self.children=[];self.fail=fail;self.devices={'2':'dpr2','3':'dpr3'};self.config_mutation=None
  for name in ('xcode-version.log','available-devices.log','tool-receipt.json','binding.json'):(self.out/name).write_text('verified preflight evidence')
  for arm in ('baseline','candidate'):r.dump(self.out/('sampling-'+arm+'-generated-app-files.json'),{'files':{'App/Info.plist':'fixture-only-generated-hash'},'artifact':'fixture-only.plist','projectSpecificationSHA256':'fixture-only','toolReceiptSHA256':'fixture-only'})
  self.lanes={'sampling-candidate':r.lane('sampling-candidate','FlashNestSamplingUI',['M/C/testB','M/C/testA'],900),'sampling-enhanced-boundary':r.lane('sampling-enhanced-boundary','FlashNestSamplingUI',['M/C/testEnhanced'],300),'sampling-baseline':r.lane('sampling-baseline','FlashNestSamplingUI',['M/C/testA'],900)}
 def command(self,argv,name,cwd=None,timeout=1200,allowed=(0,)):
  self.commands.append((list(map(str,argv)),name,timeout));products=Path(cwd)/'build/Build/Products';products.mkdir(parents=True)
  for n in ('Runner.app','Runner.app/PlugIns/Tests.xctest','App.app'):(products/n).mkdir(parents=True,exist_ok=True)
  (products/'Runner.app/runner').write_bytes(b'executable');(products/'Runner.app/PlugIns/Tests.xctest/test').write_bytes(b'test');(products/'App.app/app').write_bytes(b'app')
  (products/'Sampling.xctestrun').write_bytes(plistlib.dumps({'TestConfigurations':[{'TestTargets':[{'TestHostPath':'__TESTROOT__/Runner.app','TestBundlePath':'__TESTHOST__/PlugIns/Tests.xctest','UITargetAppPath':'__TESTROOT__/App.app'}]}]}))
  if self.config_mutation:
   config=products/'Sampling.xctestrun';data=plistlib.loads(config.read_bytes());target=data['TestConfigurations'][0]['TestTargets'][0]
   if self.config_mutation=='escape':target['UITargetAppPath']='/tmp/foreign.app'
   if self.config_mutation=='unknown':target['TestBundlePath']='__OTHER__/Tests.xctest'
   if self.config_mutation=='missing':target.pop('TestHostPath')
   if self.config_mutation=='multiple':(products/'Other.xctestrun').write_bytes(config.read_bytes())
   config.write_bytes(plistlib.dumps(data))
  log=self.out/(name+'.log');log.write_text('build');return log
 def test_once(self,app,project,device,key,name=None,**kw):
  cfg=kw.get('cfg_override',self.lanes[key]);selector=cfg['selectors'][0];self.children.append((name,selector,device,kw))
  assert cfg['expectedCount']==1 and cfg['maximumTestExecutionSeconds']==(300 if key=='sampling-enhanced-boundary' else 900) and not kw['append_result']
  if selector==self.fail:raise ValueError('real modeled child failed')
  report={'lane':key,'runName':name,'tests':1,'osVersion':'18.2','semanticResultValid':True};r.dump(self.out/(name+'-verification.json'),report);return report
class SplitContracts(unittest.TestCase):
 def app(self,p,name='app'):
  a=p/name;a.mkdir();(a/'source.swift').write_text('exact');return a
 def test_build_once_same_arm_both_dpr_and_exact_aggregate(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);f=Fake(p);a=self.app(p)
   f.test(a,'P','dpr2','sampling-candidate','candidate2');f.test(a,'P','dpr3','sampling-candidate','candidate3')
   self.assertEqual(len(f.commands),1);self.assertEqual([x[1] for x in f.children],['M/C/testA','M/C/testB']*2)
   self.assertEqual([x['tests'] for x in f.results],[2,2]);self.assertEqual(f.commands[0][2],600)
   proof=json.loads(next(f.out.glob('*-proof.json')).read_text());self.assertEqual(proof['sourceExcludedPaths'],['build/']);self.assertIn('source.swift',proof['sourceFiles'])
 def test_failure_keeps_children_and_never_aggregates_or_retries(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);f=Fake(p,fail='M/C/testB');a=self.app(p)
   with self.assertRaisesRegex(ValueError,'child failed'):f.test(a,'P','dpr2','sampling-candidate','candidate2')
   self.assertEqual(len(f.children),2);self.assertEqual(f.results,[]);self.assertTrue((f.out/'candidate2-selector-01-verification.json').exists())
   progress=json.loads((f.out/'candidate2-selector-progress.json').read_text());self.assertEqual(progress['failedSelector'],'M/C/testB');self.assertEqual(len(progress['completedChildren']),1)
 def test_drift_or_wrong_project_rejected_before_reuse(self):
  for mutation in ('source','product','xctestrun','project','symlink'):
   with self.subTest(mutation=mutation),tempfile.TemporaryDirectory() as d:
    p=Path(d);f=Fake(p);a=self.app(p);f.test(a,'P','dpr2','sampling-candidate','candidate2');before=len(f.children);project='P'
    if mutation=='source':(a/'source.swift').write_text('drift')
    if mutation=='product':(a/'build/Build/Products/App.app/app').write_text('drift')
    if mutation=='xctestrun':next((a/'build/Build/Products').glob('*.xctestrun')).write_bytes(b'bad')
    if mutation=='project':project='OTHER'
    if mutation=='symlink':(a/'linked').symlink_to(a/'source.swift')
    with self.assertRaises(ValueError):f.test(a,project,'dpr3','sampling-candidate','candidate3')
    self.assertEqual(len(f.children),before)
 def test_arm_products_never_shared(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);f=Fake(p);a=self.app(p,'candidate');b=self.app(p,'baseline');f.test(a,'P','dpr2','sampling-candidate','c');f.test(b,'P','dpr2','sampling-baseline','b')
   self.assertEqual(len(f.commands),2);self.assertNotEqual(f.children[0][3]['xctestrun'],f.children[-1][3]['xctestrun'])
 def test_existing_derived_data_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);f=Fake(p);a=self.app(p);(a/'build').mkdir()
   with self.assertRaisesRegex(ValueError,'fresh'):f.test(a,'P','dpr2','sampling-candidate','c')
   self.assertEqual(f.commands,[])
 def test_unsafe_missing_or_ambiguous_xctestrun_rejected_before_launch(self):
  for mutation in ('escape','unknown','missing','multiple'):
   with self.subTest(mutation=mutation),tempfile.TemporaryDirectory() as d:
    p=Path(d);f=Fake(p);f.config_mutation=mutation;a=self.app(p)
    with self.assertRaises(ValueError):f.test(a,'P','dpr2','sampling-candidate','c')
    self.assertEqual(f.children,[])
 def test_duplicate_selector_rejected_no_aggregate(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);f=Fake(p);a=self.app(p);f.lanes['sampling-candidate']['selectors']=['M/C/testA']*2
   with self.assertRaises(ValueError):f.test(a,'P','dpr2','sampling-candidate','c')
   self.assertEqual(f.children,[]);self.assertEqual(f.results,[])
 def test_enhanced_reuses_candidate_proof_without_rebuild_and_dpr_reuses(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);f=Fake(p);a=self.app(p)
   with self.assertRaisesRegex(ValueError,'already pinned'):f.test(a,'P','dpr2','sampling-enhanced-boundary','e0')
   f.test(a,'P','dpr2','sampling-candidate','c2');f.test(a,'P','dpr2','sampling-enhanced-boundary','e2');f.test(a,'P','dpr3','sampling-candidate','c3')
   self.assertEqual(len(f.commands),1);self.assertEqual([x['tests'] for x in f.results],[2,1,2]);self.assertEqual(f.results[1]['lane'],'sampling-enhanced-boundary')
 def test_verified_absolute_root_may_contain_double_underscore(self):
  with tempfile.TemporaryDirectory(prefix='runner__normal__') as d:
   p=Path(d);f=Fake(p);a=self.app(p);f.test(a,'P','dpr2','sampling-candidate','c')
   self.assertEqual(f.results[0]['tests'],2)
if __name__=='__main__':unittest.main(verbosity=2)

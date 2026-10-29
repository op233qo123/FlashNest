"""Source/contract models only; no native execution."""
import copy,hashlib,itertools,json,re,tempfile,unittest
from pathlib import Path
import verify_results as v
ROOT=Path(__file__).resolve().parents[1]
class TierPartition(unittest.TestCase):
 def setUp(self):self.contract=v.load_method_map();self.source=(ROOT/'UITests/NativeSamplingUITests.swift').read_text()
 def test_exact_method_map_and_single_tier_calls(self):
  entries=self.contract['methods'];methods=re.findall(r'func (test\w+)\(\)',self.source)
  self.assertEqual(set(methods),set(entries));self.assertEqual(len(methods),len(entries))
  calls=re.findall(r'func (test\w+)\(\) throws \{ try matrix\(renderer: "([^"]+)", mode: "([^"]+)", tiers: \["([^"]+)"\], method: "([^"]+)"(?:, quality: "([^"]+)")?\) \}',self.source)
  self.assertEqual(len(calls),24)
  for name,renderer,mode,tier,provenance,quality in calls:
   e=entries[name];self.assertEqual(name,provenance);self.assertEqual((renderer,mode,tier),(e['rendererPolicy'],e['scaleMode'],e['tier']))
   self.assertEqual(e['lane'],'diagnostic-launch-'+quality if quality else 'shipping-default-quality')
 def test_all_rows_phases_inputs_and_same_player_lifecycle_preserved(self):
  rows=set();lifecycle=[]
  for method,e in self.contract['methods'].items():
   if e['kind']!='matrix':continue
   for dpr in (2,3):
    rows.add((e['arm'],dpr,e['rendererPolicy'],e['scaleMode'],e['tier'],e['lane']))
    if e['lifecycle']:lifecycle.append((dpr,e['rendererPolicy'],e['tier'],e['scaleMode'],e['lane']))
  self.assertEqual(len(rows),48);self.assertEqual(sum(r[0]=='candidate' for r in rows),44)
  self.assertEqual(len(rows)*3,144);self.assertEqual(len(rows)*3*5,720);self.assertEqual(len(rows)*3*6,864)
  self.assertEqual(set(lifecycle),set(itertools.product((2,3),('automatic','webgl'),('quarter',),('showAll',),('shipping-default-quality',))))
  self.assertIn('try lifecycle(app, row: rowID)',self.source)
 def test_original_v3_row_cartesian_set_exactly_preserved(self):
  actual={(e['arm'],dpr,e['rendererPolicy'],e['scaleMode'],e['tier'],e['lane']) for e in self.contract['methods'].values() if e['kind']=='matrix' for dpr in (2,3)}
  expected={('baseline',dpr,'webgl',mode,'original','shipping-default-quality') for dpr,mode in itertools.product((2,3),('showAll','noScale'))}
  expected|={('candidate',dpr,policy,mode,tier,'shipping-default-quality') for dpr,policy,mode,tier in itertools.product((2,3),('automatic','webgl'),('showAll','noScale'),('original','threeQuarter','half','quarter'))}
  for quality,tiers in [('low',('original','quarter')),('high',('original','threeQuarter','half','quarter'))]:
   expected|={('candidate',dpr,'webgl','showAll',tier,'diagnostic-launch-'+quality) for dpr,tier in itertools.product((2,3),tiers)}
  self.assertEqual(actual,expected)
 def test_original_tier_body_and_reviewed_readonly_lifecycle_are_exact(self):
  body=self.source[self.source.index('        for tier in tiers {'):self.source.index('    private func lifecycle(')]
  body=body.replace('"flashnest-native-sampling-v4"','"flashnest-native-sampling-v3"').replace(', "method": method','')
  self.assertEqual(hashlib.sha256(body.encode()).hexdigest(),'d8174db5675852616d4d39f7a7921c631829d59621a024be34eb6f564ae958b4')
  life=self.source[self.source.index('    private func lifecycle('):self.source.index('    private func verifyStatusUI(')]
  self.assertEqual(hashlib.sha256(life.encode()).hexdigest(),'e46fe5e19b926111bdb7228f4b2ba45937bf3ecdf7ab827b210ff9a7c1a5739a')
  self.assertIn('executionTimeAllowance = 900',self.source)
 def test_selection_counts_and_roles_explicitly_v4(self):
  c=json.loads((ROOT.parent/'native-composite-runner/selection-contract-v4.json').read_text());self.assertEqual(c['contract'],'flashnest-native-composite-v4');self.assertEqual(c['schema'],4)
  self.assertEqual(c['samplingMethodMapSHA256'],v.METHOD_MAP_SHA256);self.assertEqual(sum(x['expectedCount'] for x in c['runs']),198)
  self.assertEqual((c['totalMethodExecutions'],c['regressionMethodExecutions'],c['enhancedBoundaryDiagnosticExecutions']),(198,196,2))
  for run in c['runs']:
   if run['lane'] not in ('sampling-baseline','sampling-candidate'):continue
   arm=run['lane'].removeprefix('sampling-');want={'FlashNestSamplingUITests/NativeSamplingUITests/'+n for n,e in self.contract['methods'].items() if e['arm']==arm and e['kind'] in ('matrix','navigation')}
   self.assertEqual(set(run['selectors']),want);self.assertEqual(len(run['selectors']),len(want));self.assertEqual(run['expectedCount'],2 if arm=='baseline' else 23)
 def test_wrong_or_missing_method_row_cannot_pass(self):
  name=next(n for n,e in self.contract['methods'].items() if e['kind']=='matrix');e=self.contract['methods'][name]
  row={**{k:e[k] for k in ('arm','rendererPolicy','scaleMode','tier','lane')},'phase':'portrait','method':name};v.check_method_row(row,self.contract)
  for field in ('arm','rendererPolicy','scaleMode','tier','lane','phase','method'):
   bad=copy.deepcopy(row);bad[field]='wrong'
   with self.subTest(field=field),self.assertRaises(AssertionError):v.check_method_row(bad,self.contract)
  row.pop('method')
  with self.assertRaises(AssertionError):v.check_method_row(row,self.contract)
 def test_method_map_tamper_rejected(self):
  original=v.__file__
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);(root/'scripts').mkdir();v.__file__=str(root/'scripts/verify_results.py')
   try:
    missing=copy.deepcopy(self.contract);missing['methods'].pop(next(iter(missing['methods'])))
    wrong=copy.deepcopy(self.contract);next(e for e in wrong['methods'].values() if e['kind']=='matrix')['arm']='wrong'
    for mutation in ({},missing,wrong):
     (root/'method-map-v4.json').write_text(json.dumps(mutation))
     with self.assertRaises(AssertionError):v.load_method_map()
   finally:v.__file__=original
if __name__=='__main__':unittest.main(verbosity=2)

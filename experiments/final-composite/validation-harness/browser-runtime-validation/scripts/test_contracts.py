import ast,copy,json,pathlib,tempfile,unittest
from contracts import ROOT,matrix,key,verify_measure,expected_scale,resolved_quality,bind,inventory,near,delivered_baseline,verify_baseline_entry
from pixel_checks import compare
from PIL import Image,ImageDraw
class Tests(unittest.TestCase):
 def test_matrix_exact_groups(self):
  rows=matrix();self.assertEqual(len(rows),290);self.assertEqual({r['loader'] for r in rows},{'shipping-default'})
  self.assertEqual(len({key(r) for r in rows}),58)
  self.assertEqual(sum(r['arm']=='baseline' for r in rows),58)
 def test_baseline_before_candidates(self):
  seen=set()
  for r in matrix():
   if r['arm']=='baseline':seen.add(key(r))
   else:self.assertIn(key(r),seen)
 def test_fixture_bindings(self):
  files=json.loads((ROOT/'fixtures/manifest.json').read_text())['files']
  for r in matrix():self.assertIn(f"{r['mode']}-{r['align'] or 'center'}.swf",files)
 def example(self,renderer='webgl',quality='low',samples=1):
  row={'group':'production-controls','renderer':renderer,'quality':quality,'arm':'candidate','scale':.25,'dpr':1}
  m={'actualRenderer':renderer,'backend':'2d' if renderer=='canvas' else 'webgl2','storage':[[samples,443,287]],'mobileQualityBranch':False,'allocationOverflow':False,'launchConfig':{'preferredRenderer':renderer}}
  if quality is not None:m['launchConfig']['quality']=quality
  return row,m
 def test_default_omission_and_mobile_branch(self):
  r,m=self.example(quality=None,samples=4);self.assertEqual(resolved_quality(r,m),'high');self.assertEqual(expected_scale(r,m)[0],1)
  m['mobileQualityBranch']=True;m['storage']=[[1,443,287]];self.assertEqual(resolved_quality(r,m),'low');self.assertEqual(expected_scale(r,m)[0],.25)
  m['launchConfig']['quality']='low'
  with self.assertRaises(AssertionError):expected_scale(r,m)
 def test_real_custom_msaa_required(self):
  r,m=self.example(quality='high');
  with self.assertRaises(AssertionError):expected_scale(r,m)
  m['storage']=[[4,443,287]];self.assertEqual(expected_scale(r,m),(1,4))
  m['glSamples']=4;m['storage']=[]
  with self.assertRaises(AssertionError):expected_scale(r,m)
 def test_canvas_fallback(self):
  r,m=self.example(renderer='canvas',quality=None);self.assertEqual(expected_scale(r,m)[0],1)
 def test_wgpu_high_reduced(self):
  r,m=self.example(renderer='wgpu-webgl',quality='high',samples=4);self.assertEqual(expected_scale(r,m)[0],.25)
  m['storage']=[]
  with self.assertRaises(AssertionError):expected_scale(r,m)
 def test_no_renderer_substitution(self):
  r,m=self.example();m['actualRenderer']='canvas'
  with self.assertRaises(AssertionError):expected_scale(r,m)
 def test_bounded_allocator(self):
  r,m=self.example();m['allocationOverflow']=True
  with self.assertRaises(AssertionError):expected_scale(r,m)
 def test_physical_mapping_and_stale_status(self):
  r,m=self.example();m.update(width=111,height=72,css=[0,0,443,287],client=[443,287],dpr=1,gl=[111,72],attributes={'data-flashnest-render-scale':'.25','data-flashnest-render-request':'.25','data-flashnest-viewport-width':'443','data-flashnest-viewport-height':'287','data-flashnest-renderer':'webgl'})
  self.assertEqual(verify_measure(r,m,443,287)['appliedScale'],.25)
  for change in [('width',443),('gl',[443,287]),('client',[111,72])]:
   bad=copy.deepcopy(m);bad[change[0]]=change[1]
   with self.assertRaises(AssertionError):verify_measure(r,bad,443,287)
  m['attributes']['data-flashnest-render-scale']='1'
  with self.assertRaises(AssertionError):verify_measure(r,m,443,287)
 def test_delivered_primary_receipt(self):
  entry=delivered_baseline(ROOT/'provenance/delivered-155-runtime.json')
  verify_baseline_entry(entry);self.assertEqual(len(entry['files']),12)
  self.assertIn('4b85d6e32912d24cca47.wasm',entry['files'])
 def test_historical_audio_substitution_rejected(self):
  entry=delivered_baseline(ROOT/'provenance/delivered-155-runtime.json')
  old=entry['files'].pop('4b85d6e32912d24cca47.wasm')
  entry['files']['1bab053d8911d6c21b75.wasm']={'bytes':14301916,'sha256':'c7e7f3f2b92909971a65cd6bd4169d0b07ac360fff7d68753b651f3d36209671'}
  with self.assertRaises(AssertionError):verify_baseline_entry(entry)
 def test_partial_smoke_inventory_rejected(self):
  entry=delivered_baseline(ROOT/'provenance/delivered-155-runtime.json')
  entry['files'].pop('ruffle.js.map')
  with self.assertRaises(AssertionError):verify_baseline_entry(entry)
 def test_unreviewed_primary_receipt_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p=pathlib.Path(d)/'receipt.json';p.write_text((ROOT/'provenance/delivered-155-runtime.json').read_text()+' ')
   with self.assertRaises(AssertionError):delivered_baseline(p)
 def test_full_runtime_inventory(self):
  with tempfile.TemporaryDirectory() as d:
   p=pathlib.Path(d)
   for n in ['a.wasm','b.wasm','ruffle.js','a.js.map','b.js.map','c.js.map','LICENSE_MIT','LICENSE_APACHE']:(p/n).write_text(n)
   pin={'files':inventory(p),'sourceIdentity':'a'*40};bind(p,pin)
   (p/'extra').write_text('unknown')
   with self.assertRaises(AssertionError):bind(p,pin)
 def test_noncenter_clipped_geometry(self):
  for x,y in [(0,10),(70,0),(50,50)]:
   a=Image.new('RGB',(120,100),(29,39,58));ImageDraw.Draw(a).rectangle((x,y,x+30,y+30),fill=(25,171,117));compare(a,a,120)
   b=Image.new('RGB',a.size,(29,39,58));ImageDraw.Draw(b).rectangle((x+8,y,x+38,y+30),fill=(25,171,117))
   with self.assertRaises(AssertionError):compare(b,a,120)
 def test_input_trace_mutation(self):
  near([['12','13']],[['12','13']])
  with self.assertRaises(AssertionError):near([['120','13']],[['12','13']])
 def test_no_faked_events_or_loader(self):
  s=(ROOT/'scripts/browser_matrix.py').read_text();page=(ROOT/'page.html').read_text()
  for bad in ['dispatch_event','--no-sandbox','WebAssembly.validate','quality:quality||']:self.assertNotIn(bad,s+page)
  self.assertIn('chromium_sandbox=True',s);self.assertIn("if(quality!==null)config.quality=quality",page)
  self.assertIn('renderbufferStorageMultisample',page);self.assertNotIn('getParameter(context.SAMPLES)',page)
 def test_syntax(self):
  for f in (ROOT/'scripts').glob('*.py'):ast.parse(f.read_text())
if __name__=='__main__':unittest.main()

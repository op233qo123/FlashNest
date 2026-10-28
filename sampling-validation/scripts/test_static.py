"""Static/unit checks only: never imports/launches Playwright."""
import ast,pathlib,sys,unittest,tempfile,shutil
from PIL import Image,ImageDraw
from pixel_checks import compare,validate_warning
from verify_payload import verify,ROOT
class Checks(unittest.TestCase):
 def test_syntax(self):ast.parse((ROOT/'scripts/browser_geometry.py').read_text())
 def test_geometry_positive_and_shift_rejection(self):
  a=Image.new('RGB',(120,100),(29,39,58));ImageDraw.Draw(a).rectangle((20,20,60,60),fill=(25,171,117))
  self.assertEqual(compare(a,a,120)['edgeTolerancePixels'],4)
  b=Image.new('RGB',a.size,(29,39,58));ImageDraw.Draw(b).rectangle((30,20,70,60),fill=(25,171,117))
  with self.assertRaises(AssertionError):compare(b,a,120)
 def test_unknown_warning_rejected(self):
  with self.assertRaises(AssertionError):validate_warning({'visible':True,'id':'unexpected'})
 def test_payload(self):verify()
 def test_tamper_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   r=pathlib.Path(d)/'copy';shutil.copytree(ROOT,r)
   (r/'requirements.txt').write_text('tampered')
   with self.assertRaises(AssertionError):verify(r)
 def test_harness_contracts(self):
  s=(ROOT/'scripts/browser_geometry.py').read_text()
  for required in ["[1,.75,.5,.25]","('initial',w,h),('resized',h,w),('restored',w,h)","event['trusted'] is True","m['gl']==physical","compare(img,shots[key],pw_)","len(result['rows'])==80","chromium_sandbox=True"]:self.assertIn(required,s)
  self.assertNotIn('dispatch_event',s);self.assertNotIn('--no-sandbox',s)
 def test_evidence_budget_rejects_without_writing(self):
  import evidence_budget as b
  with tempfile.TemporaryDirectory() as d:
   p=pathlib.Path(d)/'result.json';old=b.MAX_JSON_FILE;b.MAX_JSON_FILE=3
   try:
    with self.assertRaises(AssertionError):b.write_json(p,'too long')
    self.assertFalse(p.exists())
   finally:b.MAX_JSON_FILE=old
 def test_supported_webgl_and_fallback_contract(self):
  src=ROOT/'source/patched'
  self.assertIn('StageQuality::Low => 1',(src/'render/src/quality.rs').read_text())
  self.assertIn('self.gl2.is_some() && self.msaa_sample_count > 1',(src/'render/webgl/src/lib.rs').read_text())
  front=(src/'web/src/lib.rs').read_text()
  self.assertIn('let mut applied_scale = 1.0',front)
  self.assertIn('if applied_scale == 1.0',front)
  self.assertIn("a.backend,'low'",(ROOT/'scripts/browser_geometry.py').read_text())
if __name__=='__main__':unittest.main()

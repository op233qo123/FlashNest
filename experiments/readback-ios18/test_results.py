import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from verify_results import verify,NAMES
import attest
class ResultsTests(unittest.TestCase):
 def sample(self):
  s={'result':'Passed','testFailures':[],'passedTests':3,'totalTestCount':3,'failedTests':0,'skippedTests':0,'expectedFailures':0,'devicesAndConfigurations':[{'device':{'osVersion':'18.2','platform':'iOS Simulator'},'passedTests':3,'failedTests':0,'skippedTests':0,'expectedFailures':0}]}
  l='\n'.join("Test Case '-[FlashNestTests.%s %s]' passed"%x for x in NAMES)+'\n** TEST SUCCEEDED **'
  return s,l
 def test_both_exact_arms(self):
  for arm in ['baseline','candidate']:
   s,l=self.sample();self.assertEqual(verify(arm,s,l)['passed'],NAMES)
 def test_summary_contradictions(self):
  s,l=self.sample()
  for key,val in [('result','Failed'),('testFailures',[{}]),('passedTests',2),('totalTestCount',4),('failedTests',1),('skippedTests',1),('expectedFailures',1)]:
   x=copy.deepcopy(s);x[key]=val
   with self.assertRaises(ValueError):verify('candidate',x,l)
 def test_wrong_os_platform_perdevice(self):
  s,l=self.sample()
  for key,val in [('osVersion','18.5'),('platform','iOS')]:
   x=copy.deepcopy(s);x['devicesAndConfigurations'][0]['device'][key]=val
   with self.assertRaises(ValueError):verify('candidate',x,l)
  for key,val in [('passedTests',2),('failedTests',1),('skippedTests',1),('expectedFailures',1)]:
   x=copy.deepcopy(s);x['devicesAndConfigurations'][0][key]=val
   with self.assertRaises(ValueError):verify('candidate',x,l)
 def test_names_duplicates_failures_deadlines(self):
  s,l=self.sample()
  for bad in [l.replace(NAMES[0][1],'wrong'),l+l,l.replace('** TEST SUCCEEDED **',''),l+"\nTest Case 'x' failed",l+"\nTest Case 'x' skipped",l+'\nExceeded test execution time allowance']:
   with self.assertRaises(ValueError):verify('baseline',s,bad)
  for arm in ['',None,'other']:
   with self.assertRaises(ValueError):verify(arm,s,l)
  for os in ['18.5','latest',None]:
   with self.assertRaises(ValueError):verify('baseline',s,l,os)
 def test_attestation_rejects_wrong_metadata_inventory_and_receipt(self):
  with tempfile.TemporaryDirectory() as td:
   r=Path(td);h=r/'h';h.mkdir();root=r/'root';root.mkdir()
   paths=['runtime.files.json','runtime.lock.json','App/Resources/Web/runtime-identity.json','Tests/FrameOrderRuntimeTests.swift']
   runtime=root/'App/Resources/Web/runtime';runtime.mkdir(parents=True);(runtime/'a.js').write_text('original')
   for name in paths:
    p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps({'a.js':attest.sha(runtime/'a.js')}) if name=='runtime.files.json' else '{}')
   overlay={'files':[{'path':n,'sha256':attest.sha(root/n),'originalSHA256':attest.sha(root/n)} for n in paths]}
   (h/'overlay.json').write_text(json.dumps(overlay))
   receipt={'sourceCommit':attest.SOURCE,'arm':'candidate','promotionManifestSHA256':attest.PROMOTION,'shippingCheckoutUnchanged':True}
   (root/'readback-stage-receipt.json').write_text(json.dumps(receipt))
   with patch.object(attest,'OVERLAY_SHA256',attest.sha(h/'overlay.json')):
    self.assertEqual(attest.attest(root,'candidate',h)['os'],'18.2')
    (runtime/'extra').write_text('bad')
    with self.assertRaises(ValueError):attest.attest(root,'candidate',h)
    (runtime/'extra').unlink();(root/'runtime.lock.json').write_text('wrong')
    with self.assertRaises(ValueError):attest.attest(root,'candidate',h)
    (root/'runtime.lock.json').write_text('{}');receipt['sourceCommit']='wrong';(root/'readback-stage-receipt.json').write_text(json.dumps(receipt))
    with self.assertRaises(ValueError):attest.attest(root,'candidate',h)

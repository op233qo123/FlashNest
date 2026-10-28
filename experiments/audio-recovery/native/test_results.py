import unittest
from verify_results import verify,NAMES
class ResultTests(unittest.TestCase):
 def sample(self,arm):
  names=NAMES[arm];return {'passedTests':len(names),'totalTestCount':len(names),'failedTests':0,'skippedTests':0,'expectedFailures':0,'result':'Passed','testFailures':[],'devicesAndConfigurations':[{'device':{'osVersion':'18.5','platform':'iOS Simulator'},'passedTests':len(names),'failedTests':0,'skippedTests':0,'expectedFailures':0}]},'\n'.join("Test Case '-[AudioRecoveryUITests.AudioRecoveryUITests "+n+"]' passed" for n in names)+'\n** TEST SUCCEEDED **'
 def test_exact_both_arms(self):
  for arm in NAMES:
   s,l=self.sample(arm);self.assertEqual(len(verify(arm,s,l)['passed']),len(NAMES[arm]))
 def test_skip_wrong_names_os_failure_rejected(self):
  s,l=self.sample('candidate')
  for key in ['failedTests','skippedTests','expectedFailures']:
   wrong=dict(s);wrong[key]=1
   with self.assertRaises(ValueError):verify('candidate',wrong,l)
  with self.assertRaises(ValueError):verify('candidate',s,l.replace(NAMES['candidate'][0],'wrong'))
  with self.assertRaises(ValueError):verify('candidate',s,l.replace('** TEST SUCCEEDED **',''))
  s['devicesAndConfigurations'][0]['device']['osVersion']='18.2'
  with self.assertRaises(ValueError):verify('candidate',s,l)

class ContradictionTests(unittest.TestCase):
 def test_contradictions_rejected(self):
  import copy
  s,l=ResultTests().sample('candidate')
  for key,value in [('result','Failed'),('testFailures',[{'failureText':'bad'}])]:
   x=copy.deepcopy(s);x[key]=value
   with self.assertRaises(ValueError):verify('candidate',x,l)
  for suffix in ["Test Case 'foo' failed", "Test Case 'foo' skipped", "Exceeded test execution time allowance", "** TEST FAILED **", l]:
   with self.assertRaises(ValueError):verify('candidate',s,l+'\n'+suffix)
  for key,value in [('platform','iOS'),('osVersion','18.2')]:
   x=copy.deepcopy(s);x['devicesAndConfigurations'][0]['device'][key]=value
   with self.assertRaises(ValueError):verify('candidate',x,l)
  x=copy.deepcopy(s);x['devicesAndConfigurations'][0]['expectedFailures']=1
  with self.assertRaises(ValueError):verify('candidate',x,l)

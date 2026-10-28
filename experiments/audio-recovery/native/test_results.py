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

class ExactOSChoiceTests(unittest.TestCase):
 def test_each_os_and_cross_os_rejected(self):
  for os in ['18.2','18.5']:
   for arm in NAMES:
    s,l=ResultTests().sample(arm)
    s['devicesAndConfigurations'][0]['device']['osVersion']=os
    self.assertEqual(verify(arm,s,l,os)['os'],os)
    with self.assertRaises(ValueError):verify(arm,s,l,'18.2' if os=='18.5' else '18.5')
 def test_malformed_os_choices_rejected(self):
  s,l=ResultTests().sample('candidate')
  for os in ['',None,18.2,'18','18.2.1','18.5 ', '18.2; true','latest']:
   with self.assertRaises(ValueError):verify('candidate',s,l,os)
 def test_workflow_closed_mapping_and_default(self):
  from pathlib import Path
  p=Path(__file__).resolve().parents[3]/'.github/workflows/test-audio-recovery-native.yml'
  s=p.read_text()
  for required in ["default: '18.5'", "options: ['18.5', '18.2']", "inputs.simulator_os == '18.2' && 'macos-14' || 'macos-15'", "18.2) expected_xcode=16.2", "18.5) expected_xcode=16.4", '*) echo "Unsupported exact simulator OS" >&2; exit 1', 'test "$(xcrun --sdk iphonesimulator --show-sdk-version)" = "$TEST_OS"', 'python3 scripts/select_simulator.py "$TEST_OS"', 'recovery-evidence/test.log "$TEST_OS"']:
   self.assertIn(required,s)
  self.assertNotIn('simctl runtime add',s)
  self.assertIn('-default-test-execution-time-allowance 180 -maximum-test-execution-time-allowance 360',s)

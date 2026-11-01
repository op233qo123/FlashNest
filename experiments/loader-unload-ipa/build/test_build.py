#!/usr/bin/env python3
"""Negative receipt tests; these are not native execution evidence."""
import copy,unittest
from run_ios_tests import verify_summary
class SummaryTests(unittest.TestCase):
 def setUp(self):
  self.expected=[('ExampleTests','testOne'),('ExampleTests','testTwo')];self.device='00000000-0000-0000-0000-000000000001'
  self.summary={'result':'Passed','totalTestCount':2,'passedTests':2,'failedTests':0,'skippedTests':0,'expectedFailures':0,'devicesAndConfigurations':[{'device':{'osVersion':'18.5','deviceId':self.device}}]}
  self.log="\n".join("Test Case '-[FlashNestTests.%s %s]' passed"%m for m in self.expected)
 def check(self,s=None,log=None,os='18.5'):
  return verify_summary(self.summary if s is None else s,self.log if log is None else log,self.expected,self.device,'FlashNestTests',os)
 def test_exact(self):self.assertEqual(self.check()['osVersion'],'18.5')
 def test_old_runtime(self):
  with self.assertRaises(ValueError):self.check(os='18.2')
 def test_skip(self):
  self.summary['skippedTests']=1
  with self.assertRaises(ValueError):self.check()
 def test_false_bool_count(self):
  self.summary['failedTests']=False
  with self.assertRaises(ValueError):self.check()
 def test_duplicate(self):
  with self.assertRaises(ValueError):self.check(log=self.log+'\n'+self.log)
 def test_missing(self):
  with self.assertRaises(ValueError):self.check(log=self.log.splitlines()[0])
 def test_wrong_bundle(self):
  with self.assertRaises(ValueError):self.check(log=self.log.replace('FlashNestTests','OtherTests'))
 def test_wrong_device(self):
  self.summary['devicesAndConfigurations'][0]['device']['deviceId']='wrong'
  with self.assertRaises(ValueError):self.check()
 def test_extra_device(self):
  self.summary['devicesAndConfigurations']*=2
  with self.assertRaises(ValueError):self.check()
 def test_expected_failure(self):
  self.summary['expectedFailures']=1
  with self.assertRaises(ValueError):self.check()
if __name__=='__main__':unittest.main()

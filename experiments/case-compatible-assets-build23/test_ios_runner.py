#!/usr/bin/env python3
"""Fail-closed receipt parser checks; not a substitute for actual simulator tests."""
import copy
import unittest
import run_ios_tests as runner

class IOSReceiptTests(unittest.TestCase):
    def setUp(self):
        self.summary = {'result': 'Passed', 'totalTestCount': 1, 'passedTests': 1,
            'failedTests': 0, 'skippedTests': 0, 'expectedFailures': 0,
            'devicesAndConfigurations': [{'device': {'osVersion': '18.2', 'deviceId': 'device'}}]}
        self.log = "Test Case '-[FlashNestTests.ExampleTests testExample]' passed"
    def check(self, summary=None, log=None):
        return runner.verify_summary(self.summary if summary is None else summary,
            self.log if log is None else log, [('ExampleTests', 'testExample')], 'device', 'FlashNestTests')
    def test_exact_receipt(self):
        self.assertEqual(self.check()['counts']['passedTests'], 1)
    def test_wrong_device(self):
        self.summary['devicesAndConfigurations'][0]['device']['deviceId'] = 'different'
        with self.assertRaises(ValueError): self.check()
    def test_wrong_os(self):
        self.summary['devicesAndConfigurations'][0]['device']['osVersion'] = '18.3'
        with self.assertRaises(ValueError): self.check()
    def test_no_skips(self):
        self.summary['skippedTests'] = 1
        with self.assertRaises(ValueError): self.check()
    def test_boolean_is_not_count(self):
        self.summary['passedTests'] = True
        with self.assertRaises(ValueError): self.check()
    def test_duplicate_pass(self):
        with self.assertRaises(ValueError): self.check(log=self.log + '\n' + self.log)
    def test_extra_method(self):
        with self.assertRaises(ValueError): self.check(log=self.log + "\nTest Case '-[FlashNestTests.ExampleTests testOther]' passed")
    def test_wrong_bundle(self):
        with self.assertRaises(ValueError): self.check(log=self.log.replace('FlashNestTests.', 'OtherTests.'))
    def test_missing_method(self):
        with self.assertRaises(ValueError): self.check(log='')
    def test_not_passed(self):
        self.summary['result'] = 'Failed'
        with self.assertRaises(ValueError): self.check()

if __name__ == '__main__': unittest.main()

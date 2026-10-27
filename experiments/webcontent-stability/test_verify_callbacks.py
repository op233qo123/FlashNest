import copy
import unittest
from verify_callbacks import verify, METHODS

class CallbackGateTests(unittest.TestCase):
    def fixture(self):
        counts = dict(passedTests=3, failedTests=0, skippedTests=0, expectedFailures=0)
        summary = dict(result='Passed', totalTestCount=3, testFailures=[], **counts)
        summary['devicesAndConfigurations'] = [dict(device=dict(osVersion='18.2', platform='iOS Simulator'), **counts)]
        log = '\n'.join(f"Test Case '-[FlashNestTests.PlayerCallbackIdentityTests {m}]' {state}" for m in METHODS for state in ['started.', 'passed (1.000 seconds).'])
        return summary, log
    def test_exact_pass(self):
        verify(*self.fixture())
    def test_zero_skips_wrong_platform_and_missing_counts_rejected(self):
        for key, value in [('totalTestCount', 0), ('skippedTests', 1), ('failedTests', 1), ('passedTests', True), ('testFailures', [{}])]:
            summary, log = self.fixture(); summary[key] = value
            with self.assertRaises(ValueError): verify(summary, log)
        summary, log = self.fixture(); summary['devicesAndConfigurations'][0]['device']['osVersion'] = '18.5'
        with self.assertRaises(ValueError): verify(summary, log)
    def test_missing_duplicate_wrong_test_rejected(self):
        summary, log = self.fixture()
        for bad in ['', log + '\n' + log, log.replace(METHODS[0], 'testWrongMethod')]:
            with self.assertRaises(ValueError): verify(summary, bad)

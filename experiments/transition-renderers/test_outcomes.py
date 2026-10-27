import unittest
from verify_outcomes import verify
class OutcomeTests(unittest.TestCase):
    def test_explicit_single_arm_is_not_ab_success(self):
        self.assertEqual(verify('webgl','skipped','success')['scope'],'webgl')
        self.assertEqual(verify('both','success','success')['scope'],'both')
    def test_failure_missing_or_unselected_arm_cannot_pass(self):
        for args in [('both','failure','success'),('both','success','failure'),('both','skipped','success'),('webgl','skipped','failure'),('webgl','success','success'),('webgl','failure','success'),('webgl','','success'),('','skipped','success'),('default','success','skipped')]:
            with self.assertRaises(ValueError): verify(*args)

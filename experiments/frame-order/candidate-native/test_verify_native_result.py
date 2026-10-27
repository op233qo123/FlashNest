import copy
import unittest

from verify_native_result import LIFECYCLE_CASES, METHODS, verify


def evidence(variant):
    methods = list(METHODS.values()) if variant == "both" else [METHODS[variant]]
    count = len(methods)
    counts = {"passedTests": count, "failedTests": 0, "skippedTests": 0, "expectedFailures": 0}
    summary = {**counts, "result": "Passed", "totalTestCount": count, "testFailures": [],
               "devicesAndConfigurations": [{**counts, "device": {
                   "osVersion": "18.2", "platform": "iOS Simulator"}}]}
    log = "\n".join(f"Test Case '-[FlashNestTests.FrameOrderCandidateRuntimeTests {method}]' {state}"
                    for method in methods for state in ("started.", "passed (1.234 seconds)."))
    return summary, log


class VerifyNativeResultTests(unittest.TestCase):
    def test_exact_selections(self):
        for variant in ("both", "control", "nested"):
            verify(*evidence(variant), variant)

    def test_false_green_summary(self):
        summary, log = evidence("both")
        for key, value in (("result", "Failed"), ("totalTestCount", 0), ("passedTests", 1),
                           ("failedTests", 1), ("skippedTests", 1), ("expectedFailures", 1),
                           ("testFailures", [{}]), ("devicesAndConfigurations", [])):
            wrong = copy.deepcopy(summary)
            wrong[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                verify(wrong, log, "both")

    def test_wrong_platform(self):
        summary, log = evidence("both")
        for key, value in (("osVersion", "18.5"), ("platform", "iOS")):
            wrong = copy.deepcopy(summary)
            wrong["devicesAndConfigurations"][0]["device"][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                verify(wrong, log, "both")

    def test_missing_duplicated_wrong_or_failed_named_cases(self):
        summary, log = evidence("both")
        wrong_logs = ("", log + "\n" + log, log.replace("Contract", "OtherContract"),
                      log.replace("passed", "failed", 1), log.replace("passed", "skipped", 1),
                      "\n".join(log.splitlines()[1:]))
        for wrong in wrong_logs:
            with self.subTest(log=wrong), self.assertRaises(ValueError):
                verify(summary, wrong, "both")

    def test_wrong_selection(self):
        with self.assertRaises(ValueError):
            verify(*evidence("control"), "nested")

    def test_noninteger_counts_are_not_accepted(self):
        for value in (True, 1.0, "1"):
            summary, log = evidence("control")
            summary["passedTests"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                verify(summary, log, "control")

    def test_lifecycle_scopes_require_exact_existing_test_cases(self):
        for scope, cases in LIFECYCLE_CASES.items():
            summary, _ = evidence("both" if len(cases) == 2 else "control")
            log = "\n".join(f"Test Case '-[{case}]' {state}" for case in cases
                            for state in ("started.", "passed (2.000 seconds)."))
            verify(summary, log, "both", scope)
            with self.assertRaises(ValueError):
                verify(summary, log, "both", "original")
            with self.assertRaises(ValueError):
                verify(summary, log, "control", scope)


if __name__ == "__main__":
    unittest.main()

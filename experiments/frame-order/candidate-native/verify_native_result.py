#!/usr/bin/env python3
"""Reject zero-test, skipped, wrong-selection and wrong-platform native greens."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re

METHODS = {
    "control": "testCandidateControlContract",
    "nested": "testCandidateNestedRepairContract",
}
LIFECYCLE_CASES = {
    "save-lifecycle": [
        "FlashNestTests.SharedObjectPersistenceTests testExplicitSaveAndRestartUsesNewPageAndPreservesSaveAndGameFiles",
        "FlashNestTests.SharedObjectPersistenceTests testDestroyFlushPersistsAndRestartReadsActualSharedObject",
    ],
    "ui-lifecycle": [
        "FlashNestUITests.LifecyclePlayerUITests testBackgroundDirectSaveCancelManagementAndRestartSameGame",
    ],
}


def verify(summary: dict, log: str, variant: str, scope: str = "original", expected_os: str = "18.2") -> None:
    if expected_os not in ("18.2", "18.5"):
        raise ValueError("Unsupported expected simulator OS")
    if variant not in ("both", "control", "nested"):
        raise ValueError("Unsupported candidate fixture selection")
    if scope == "original":
        methods = list(METHODS.values()) if variant == "both" else [METHODS[variant]]
        selected = [f"FlashNestTests.FrameOrderCandidateRuntimeTests {method}" for method in methods]
    elif scope in LIFECYCLE_CASES and variant == "both":
        selected = LIFECYCLE_CASES[scope]
    else:
        raise ValueError("Unsupported native result scope/selection")
    count = len(selected)
    for key, expected in {"result": "Passed", "totalTestCount": count,
                          "passedTests": count, "failedTests": 0,
                          "skippedTests": 0, "expectedFailures": 0}.items():
        if type(summary.get(key)) is not type(expected) or summary.get(key) != expected:
            raise ValueError(f"Native summary mismatch: {key}={summary.get(key)!r}, expected {expected!r}")
    if summary.get("testFailures") != []:
        raise ValueError("Native summary contains failures or lacks failure details")
    configurations = summary.get("devicesAndConfigurations")
    if not isinstance(configurations, list) or len(configurations) != 1:
        raise ValueError("Expected exactly one simulator configuration")
    configuration = configurations[0]
    device = configuration.get("device", {})
    if device.get("osVersion") != expected_os or device.get("platform") != "iOS Simulator":
        raise ValueError(f"The required iOS {expected_os} simulator was not measured")
    for key, expected in {"passedTests": count, "failedTests": 0,
                          "skippedTests": 0, "expectedFailures": 0}.items():
        if type(configuration.get(key)) is not int or configuration.get(key) != expected:
            raise ValueError(f"Simulator configuration mismatch: {key}")

    expected_cases = Counter({case: 1 for case in selected})
    started = Counter(re.findall(r"^Test Case '-\[([^\]\r\n]+)\]' started\.$", log, re.MULTILINE))
    passed = Counter(re.findall(r"^Test Case '-\[([^\]\r\n]+)\]' passed \([0-9.]+ seconds\)\.$",
                                log, re.MULTILINE))
    if started != expected_cases or passed != expected_cases:
        raise ValueError(f"Unexpected/missing/duplicate native test cases: started={started}, passed={passed}")
    if re.search(r"^Test Case .*\b(failed|skipped)\b", log, re.MULTILINE):
        raise ValueError("Native log includes a failed or skipped test case")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--variant", choices=("both", "control", "nested"), required=True)
    parser.add_argument("--scope", choices=("original", "save-lifecycle", "ui-lifecycle"), default="original")
    parser.add_argument("--os", choices=("18.2", "18.5"), default="18.2", dest="expected_os")
    args = parser.parse_args()
    verify(json.loads(args.summary.read_text()), args.log.read_text(), args.variant, args.scope, args.expected_os)
    print(f"Verified selected candidate tests passed without skips on iOS {args.expected_os}: {args.scope}/{args.variant}")


if __name__ == "__main__":
    main()

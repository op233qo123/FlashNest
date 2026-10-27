#!/usr/bin/env python3
"""Reject zero/skipped/foreign-selector/foreign-simulator native UI greens."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re

CASE = 'NativeAudioLifecycleUITests.NativeAudioLifecycleUITests testImmutableBaselineAndCandidateAudioLifecycleMatrix'

def verify(summary, log):
    for key, expected in {'result': 'Passed', 'totalTestCount': 1, 'passedTests': 1,
                          'failedTests': 0, 'skippedTests': 0, 'expectedFailures': 0}.items():
        if type(summary.get(key)) is not type(expected) or summary.get(key) != expected:
            raise ValueError('Native summary mismatch: ' + key)
    if summary.get('testFailures') != []:
        raise ValueError('Missing/nonempty failures')
    configs = summary.get('devicesAndConfigurations')
    if not isinstance(configs, list) or len(configs) != 1:
        raise ValueError('Exactly one simulator configuration required')
    device = configs[0].get('device', {})
    if device.get('osVersion') != '18.5' or device.get('platform') != 'iOS Simulator':
        raise ValueError('Exact iOS 18.5 simulator required')
    for key, expected in {'passedTests': 1, 'failedTests': 0, 'skippedTests': 0, 'expectedFailures': 0}.items():
        if type(configs[0].get(key)) is not int or configs[0].get(key) != expected:
            raise ValueError('Wrong per-device result: ' + key)
    started = Counter(re.findall(r"^Test Case '-\[([^\]\r\n]+)\]' started\.$", log, re.M))
    passed = Counter(re.findall(r"^Test Case '-\[([^\]\r\n]+)\]' passed \([0-9.]+ seconds\)\.$", log, re.M))
    if started != Counter({CASE: 1}) or passed != Counter({CASE: 1}):
        raise ValueError('Wrong/missing/duplicate native selectors')
    if re.search(r'^Test Case .*\b(failed|skipped)\b', log, re.M):
        raise ValueError('Failed/skipped native selector')

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--summary', type=Path, required=True)
    parser.add_argument('--log', type=Path, required=True)
    args = parser.parse_args()
    verify(json.loads(args.summary.read_text()), args.log.read_text())
    print('Verified exact one native audio UI matrix test on iOS Simulator 18.5; raw22 evidence replay is a separate required gate')

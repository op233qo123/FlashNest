#!/usr/bin/env python3
"""Exact XCTest/log and late record checks; not a substitute for source/run identity."""
import argparse
from collections import Counter
import importlib.util
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parents[1]
SELECTION = json.loads((HERE / 'test-selection.json').read_text())


def require(value, detail):
    if not value:
        raise ValueError(detail)


def verify(summary, log, lane):
    n = lane['expectedCount']
    expected = {'result': 'Passed', 'totalTestCount': n, 'passedTests': n,
                'failedTests': 0, 'skippedTests': 0, 'expectedFailures': 0,
                'title': 'Test - ' + lane['scheme']}
    for k, v in expected.items():
        require(type(summary.get(k)) is type(v) and summary[k] == v, 'summary mismatch: ' + k)
    require(summary.get('testFailures') == [], 'missing/nonempty test failures')
    configs = summary.get('devicesAndConfigurations')
    require(isinstance(configs, list) and len(configs) == 1, 'exactly one serial simulator required')
    config = configs[0]
    device = config.get('device', {})
    require(device.get('osVersion') == '18.2' and device.get('platform') == 'iOS Simulator', 'exact iOS18.2 simulator required')
    for k in ('passedTests', 'failedTests', 'skippedTests', 'expectedFailures'):
        require(type(config.get(k)) is int and config[k] == expected[k], 'device result mismatch: ' + k)
    # Retain the complete bounded XCTest log; do not feed truncated head/tail logs
    # to selector verification. Module names are required, not guessed from count.
    patterns = {
        'started': r"^Test Case '-\[([^\]\r\n]+)\]' started\.$",
        'passed': r"^Test Case '-\[([^\]\r\n]+)\]' passed \([0-9.]+ seconds\)\.$"}
    wanted = Counter()
    for selector in lane['selectors']:
        module, cls, method = selector.split('/')
        wanted[f'{module}.{cls} {method}'] += 1
    require(all(v == 1 for v in wanted.values()), 'duplicate selection contract')
    for state, pattern in patterns.items():
        require(Counter(re.findall(pattern, log, re.M)) == wanted, 'wrong/missing/duplicate ' + state + ' selectors')
    require(not re.search(r'^Test Case .*\b(failed|skipped)\b', log, re.M), 'failed/skipped selector')
    return {'lane': lane['name'], 'tests': n, 'osVersion': '18.2', 'semanticResultValid': True,
            'sourceRuntimeRunIdentityMustBeIndependentlyAuthenticated': True}


def verify_audio_records(log, lane):
    spec = importlib.util.spec_from_file_location('late_evidence', HERE / 'diagnostics/verify_late_evidence.py')
    verifier = importlib.util.module_from_spec(spec); spec.loader.exec_module(verifier)
    texts = re.findall(r'^AUDIO_LATE_FINAL (.+)$', log, re.M)
    require(len(texts) == lane['expectedCount'], 'exact terminal audio records required')
    records = [json.loads(t) for t in texts]
    expected = ['candidate-known', 'candidate-unknown'] if lane['name'] == 'audio-candidate' else ['baseline-known']
    require(Counter(r.get('mode') for r in records) == Counter(expected), 'wrong/duplicate audio case modes')
    for record in records:
        execution = record.get('execution', {})
        require(execution == {'kind': 'native-ios', 'osVersion': '18.2', 'platform': 'iOS Simulator'}, 'foreign/model audio execution declaration')
        verifier.validate(record)
    return {'cases': expected, 'recordsValid': True, 'audibleOutputProven': False, 'totalContextCount': None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lane', choices=[l['name'] for l in SELECTION['lanes']], required=True)
    parser.add_argument('--summary', type=Path, required=True)
    parser.add_argument('--log', type=Path, required=True)
    args = parser.parse_args()
    lane = next(x for x in SELECTION['lanes'] if x['name'] == args.lane)
    log = args.log.read_text()
    result = verify(json.loads(args.summary.read_text()), log, lane)
    if args.lane.startswith('audio-'):
        result['audio'] = verify_audio_records(log, lane)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()

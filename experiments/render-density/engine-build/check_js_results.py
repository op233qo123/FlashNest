#!/usr/bin/env python3
"""Reject missing, skipped, or failing original and added config test results."""
import argparse
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('log', type=Path)
parser.add_argument('summary', type=Path)
args = parser.parse_args()
args.summary.parent.mkdir(parents=True, exist_ok=True)
args.summary.write_text(json.dumps({'allPassed': False, 'status': 'incomplete'}, indent=2) + '\n')
config = json.loads(Path(__file__).with_name('build-inputs.json').read_text())
expected = config['expectedOriginalCoreJSTests'] + config['expectedNewConfigTests']
text = args.log.read_text(errors='replace')
objects = []
decoder = json.JSONDecoder()
for index, char in enumerate(text):
    if char == '{':
        try:
            data, _ = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and all(key in data for key in ('stats', 'tests', 'passes', 'failures', 'pending')):
            objects.append(data)
assert len(objects) == 1, f'Expected one Mocha JSON report, found {len(objects)}'
report = objects[0]
stats = report['stats']
assert stats['tests'] == stats['passes'] == len(report['tests']) == len(report['passes']) == expected, stats
assert stats['pending'] == stats['failures'] == len(report['pending']) == len(report['failures']) == 0, stats
prefix = config['newConfigTestTitlePrefix']
new = [test for test in report['passes'] if test['fullTitle'].startswith(prefix)]
assert len(new) == config['expectedNewConfigTests'], [test['fullTitle'] for test in new]
args.summary.write_text(json.dumps({'allPassed': True, 'expectedOriginalTests': config['expectedOriginalCoreJSTests'],
    'expectedNewConfigTests': config['expectedNewConfigTests'], 'stats': stats,
    'newConfigTestTitles': [test['fullTitle'] for test in new]}, indent=2) + '\n')
print(f'PASS: {expected} core JS tests, including {len(new)} original render-density config tests; none skipped')

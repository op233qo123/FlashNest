#!/usr/bin/env python3
"""Fail-closed staging, test-process opt-in and bounded XCTest evidence checks."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import plistlib
import re
import statistics
import subprocess

BASELINE = 'a09ccefc4513b617a88898a3d1e4dfb6eaea91f9'
SOURCE = 'App/Models/SaveStore.swift'
TEST = 'Tests/SaveStoreMemoryTests.swift'
SOURCE_SHA = '2c2ad1c2e3019e85fcf0b0af05d280f53eb77e18e840fb01e4862815dea86f4a'
TEST_SHA = '90ae65a10dc12b51dc0b025e6c4f4a9104402cf452d59bfeae4a413296e480e9'
METHODS = ['testMaximumDecodedPayloadRoundTripsWithIndependentChecksums', 'testMeasureMaximumCaptureMemory']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], text=True).strip()


def stage(repo, baseline, patched, output):
    if sha(repo / SOURCE) != SOURCE_SHA or sha(repo / TEST) != TEST_SHA:
        raise ValueError('Reviewed source/test fingerprint changed; require fresh review')
    for tree in (baseline, patched):
        if git(tree, 'rev-parse', 'HEAD') != BASELINE or git(tree, 'status', '--porcelain'):
            raise ValueError('Each input worktree must be clean at the pinned baseline')
        (tree / TEST).write_bytes((repo / TEST).read_bytes())
    (patched / SOURCE).write_bytes((repo / SOURCE).read_bytes())
    files = git(baseline, 'ls-files').splitlines() + [TEST]
    hashes = {name: {file: sha(root / file) for file in files}
              for name, root in [('baseline', baseline), ('patched', patched)]}
    differences = [file for file in files if hashes['baseline'][file] != hashes['patched'][file]]
    if differences != [SOURCE]:
        raise ValueError(f'Unexpected A/B source delta: {differences}')
    output.write_text(json.dumps({'baselineCommit': BASELINE, 'harnessCommit': git(repo, 'rev-parse', 'HEAD'),
                                 'onlyVariantFile': differences, 'sha256': hashes}, indent=2) + '\n')


def opt_in(document):
    """Patch the actual xctestrun test process; preserve all other launch settings."""
    if 'TestConfigurations' in document:
        configs = document['TestConfigurations']
        if len(configs) != 1 or configs[0].get('IsEnabled', True) is not True:
            raise ValueError('Require one enabled test configuration')
        targets = configs[0]['TestTargets']
    else:
        targets = [value for key, value in document.items() if not key.startswith('__')
                   and isinstance(value, dict) and 'TestBundlePath' in value]
    if len(targets) != 1:
        raise ValueError('Require exactly one native test target')
    target = targets[0]
    if target.get('BlueprintName', target.get('ProductModuleName')) != 'FlashNestTests':
        raise ValueError('Wrong test target')
    if target.get('IsUITestBundle', False):
        raise ValueError('UI tests are outside the benchmark scope')
    target.setdefault('EnvironmentVariables', {})['FLASHNEST_MEASURE_SAVE_MEMORY'] = '1'
    target['OnlyTestIdentifiers'] = ['SaveStoreMemoryTests/' + name for name in METHODS]
    target['SkipTestIdentifiers'] = []
    return document


def verify(summary, log):
    for key, expected in {'result': 'Passed', 'totalTestCount': 2, 'passedTests': 2,
                          'failedTests': 0, 'skippedTests': 0, 'expectedFailures': 0}.items():
        if type(summary.get(key)) is not type(expected) or summary.get(key) != expected:
            raise ValueError(f'Wrong test summary: {key}')
    if summary.get('testFailures') != []:
        raise ValueError('Missing or nonempty failures')
    configs = summary.get('devicesAndConfigurations', [])
    if len(configs) != 1:
        raise ValueError('Require exactly one measured configuration')
    device = configs[0].get('device', {})
    if device.get('platform') != 'iOS Simulator' or device.get('osVersion') != '18.2':
        raise ValueError('Require pinned iOS Simulator 18.2')
    for key, expected in {'passedTests': 2, 'failedTests': 0, 'skippedTests': 0, 'expectedFailures': 0}.items():
        if type(configs[0].get(key)) is not int or configs[0][key] != expected:
            raise ValueError(f'Wrong per-device counts: {key}')
    expected_cases = Counter({'FlashNestTests.SaveStoreMemoryTests ' + name: 1 for name in METHODS})
    for state, suffix in [('started', r'\.'), ('passed', r' \([0-9.]+ seconds\)\.')]:
        found = Counter(re.findall(r"^Test Case '-\[([^\]\r\n]+)\]' " + state + suffix + '$', log, re.MULTILINE))
        if found != expected_cases:
            raise ValueError(f'Wrong or duplicate {state} cases: {found}')
    if re.search(r'^Test Case .*\b(failed|skipped)\b', log, re.MULTILINE):
        raise ValueError('Failed/skipped case in log')
    metrics = {}
    for line in log.splitlines():
        if ' measured [' not in line:
            continue
        if 'testMeasureMaximumCaptureMemory' not in line:
            raise ValueError('Unexpected performance test')
        match = re.search(r'measured \[([^\]]+)\].*?values:\s*\[([^\]]+)\]', line)
        if not match:
            raise ValueError('Unrecognized raw metric format; retain evidence, do not infer success')
        label, numbers = match.groups()
        values = [float(value.strip()) for value in numbers.split(',')]
        if len(values) != 5 or not all(math.isfinite(value) for value in values) or label in metrics:
            raise ValueError('Metrics require exactly five finite measurements without duplicates')
        metrics[label] = {'values': values, 'median': statistics.median(values), 'mean': statistics.mean(values)}
    if not any('memory' in key.lower() for key in metrics) or not any('clock' in key.lower() for key in metrics):
        raise ValueError('Missing memory/clock measurements; an opt-in skip is not a benchmark')
    return {'device': device, 'testCount': 2, 'iterations': 5, 'metrics': metrics}


def compare(baseline, patched):
    if baseline['device'] != patched['device'] or baseline['metrics'].keys() != patched['metrics'].keys():
        raise ValueError('A/B device or metric mismatch')
    return {'baseline': baseline, 'patched': patched,
            'medianDeltaPatchedMinusBaseline': {key: patched['metrics'][key]['median'] - baseline['metrics'][key]['median']
                                                for key in baseline['metrics']},
            'interpretation': 'Single sequential simulator A/B; host/process/allocator noise and order bias remain. '
                              'Native save validation only, not WebContent/GPU/gameplay or proof about SIGBUS/OOM.'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['stage', 'opt-in', 'verify', 'compare'])
    parser.add_argument('paths', nargs='+', type=Path)
    args = parser.parse_args()
    if args.command == 'stage':
        stage(*args.paths)
    elif args.command == 'opt-in':
        path, evidence = args.paths
        document = opt_in(plistlib.loads(path.read_bytes()))
        path.write_bytes(plistlib.dumps(document))
        evidence.write_bytes(path.read_bytes())
    else:
        first, second, output = args.paths
        value = (verify(json.loads(first.read_text()), second.read_text()) if args.command == 'verify'
                 else compare(json.loads(first.read_text()), json.loads(second.read_text())))
        output.write_text(json.dumps(value, indent=2) + '\n')


if __name__ == '__main__':
    main()

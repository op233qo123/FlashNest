#!/usr/bin/env python3
"""Stage and attest an isolated full-payload versus metadata listing benchmark."""
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
from generate_fixtures import generate

BASELINE = '967a0a3f37ab842b8ebddffc0daa0d7237d8ad13'
APP_FILES = ['App/Models/SaveStore.swift', 'App/Views/SaveAreaView.swift']
BENCHMARK = 'Tests/SaveListingMemoryTests.swift'
SAFETY = 'Tests/SaveStoreSummaryTests.swift'
PINS = {
    APP_FILES[0]: '12f1c23ae4c3df73776d36b6e7d87d01b31239da3df2b3a35d2303ac3831790b',
    APP_FILES[1]: 'd472be913d5da40b46363450059ea2bb8e82cfc41b0f51d9cb11752f05243d37',
    SAFETY: '259101480e0689faaebdff9cb42050605fce629539a3db0b61a3ca7582ee5774',
    BENCHMARK: '8f5e5f4af50f0b2f1d04e8d66c88a9dd3c059ecbb680b602bc024262fc607248',
}
METHOD = 'testMeasurePopulatedSaveListingMemory'
SAFETY_METHODS = [
    'testSummariesMatchValidatedCurrentAndBackupMetadataAndOrdering',
    'testCorruptNeighborIsIsolatedAndStrictOldAPIUnchanged',
    'testExportRejectsCorruptMissingAndReplacedNamedArchiveAfterListing',
    'testExportRejectsWrongPackageAndChangedCurrentWithoutFallingBackToBackup',
    'testExportRejectsSymlinkReplacementAndWrongIdentityOnListing',
    'testEmptyAndCombiningCharacterNamesHaveBoundedDisplayMetadata',
    'testOversizedArchiveIsSkippedWithoutHidingValidMetadata',
    'testDirectoryEntryBudgetStillRejectsOversizedListing',
    'testNamedExportPreservesListedFilenameCaseAndRejectsForgedPath',
]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], text=True).strip()


def stage(repo, baseline, patched, output):
    for file, expected in PINS.items():
        if sha(repo / file) != expected:
            raise ValueError(f'Reviewed input fingerprint changed: {file}')
    for tree in (baseline, patched):
        if git(tree, 'rev-parse', 'HEAD') != BASELINE or git(tree, 'status', '--porcelain'):
            raise ValueError('Both worktrees must be clean at the pinned baseline')
        (tree / BENCHMARK).write_bytes((repo / BENCHMARK).read_bytes())
    for file in APP_FILES + [SAFETY]:
        (patched / file).write_bytes((repo / file).read_bytes())
    files = git(baseline, 'ls-files').splitlines() + [BENCHMARK]
    hashes = {name: {file: sha(tree / file) for file in files}
              for name, tree in [('baseline', baseline), ('patched', patched)]}
    differences = sorted(file for file in files if hashes['baseline'][file] != hashes['patched'][file])
    if differences != sorted(APP_FILES):
        raise ValueError(f'Unexpected production delta: {differences}')
    hashes['patched'][SAFETY] = sha(patched / SAFETY)
    fixtures = {}
    for name, tree in [('baseline', baseline), ('patched', patched)]:
        destination = tree / 'fixtures/save-listing-memory'
        manifest = generate(destination)
        for file, record in manifest['files'].items():
            actual = destination / 'save' / manifest['packageID'] / file
            if sha(actual) != record['sha256'] or actual.stat().st_size != record['bytes']:
                raise ValueError('Generated fixture hash/size mismatch')
        fixtures[name] = manifest
    if fixtures['baseline'] != fixtures['patched']:
        raise ValueError('A/B fixture mismatch')
    output.write_text(json.dumps({'baselineCommit': BASELINE, 'harnessCommit': git(repo, 'rev-parse', 'HEAD'),
                                 'productionDelta': differences, 'patchedOnlyTest': SAFETY,
                                 'benchmarkSelector': {'baseline': '', 'patched': '-DSAVE_METADATA_LISTING'},
                                 'sha256': hashes, 'fixtures': fixtures['baseline']}, indent=2) + '\n')


def selection(scope):
    if scope == 'safety':
        return 'SaveStoreSummaryTests', SAFETY_METHODS
    if scope in ('baseline', 'patched'):
        return 'SaveListingMemoryTests', [METHOD]
    raise ValueError('Unknown measurement scope')


def opt_in(document, scope):
    class_name, methods = selection(scope)
    if 'TestConfigurations' in document:
        configs = document['TestConfigurations']
        if len(configs) != 1 or configs[0].get('IsEnabled', True) is not True:
            raise ValueError('Require one enabled test configuration')
        targets = configs[0]['TestTargets']
    else:
        targets = [value for key, value in document.items() if not key.startswith('__')
                   and isinstance(value, dict) and 'TestBundlePath' in value]
    if len(targets) != 1:
        raise ValueError('Require one test target')
    target = targets[0]
    if target.get('BlueprintName', target.get('ProductModuleName')) != 'FlashNestTests' or target.get('IsUITestBundle', False):
        raise ValueError('Require native FlashNestTests target')
    environment = target.setdefault('EnvironmentVariables', {})
    environment.pop('FLASHNEST_MEASURE_SAVE_MEMORY', None)
    if scope == 'safety':
        environment.pop('FLASHNEST_MEASURE_SAVE_LISTING', None)
    else:
        environment['FLASHNEST_MEASURE_SAVE_LISTING'] = '1'
    target['OnlyTestIdentifiers'] = [class_name + '/' + method for method in methods]
    target['SkipTestIdentifiers'] = []
    return document


def verify(summary, log, scope):
    class_name, methods = selection(scope)
    count = len(methods)
    for key, expected in {'result': 'Passed', 'totalTestCount': count, 'passedTests': count,
                          'failedTests': 0, 'skippedTests': 0, 'expectedFailures': 0}.items():
        if type(summary.get(key)) is not type(expected) or summary.get(key) != expected:
            raise ValueError(f'Wrong summary field: {key}')
    if summary.get('testFailures') != []:
        raise ValueError('Missing/nonempty failures')
    configs = summary.get('devicesAndConfigurations', [])
    if len(configs) != 1:
        raise ValueError('Require one simulator configuration')
    device = configs[0].get('device', {})
    if device.get('platform') != 'iOS Simulator' or device.get('osVersion') != '18.2':
        raise ValueError('Require iOS Simulator 18.2')
    for key, expected in {'passedTests': count, 'failedTests': 0, 'skippedTests': 0, 'expectedFailures': 0}.items():
        if type(configs[0].get(key)) is not int or configs[0][key] != expected:
            raise ValueError(f'Wrong device count: {key}')
    expected_cases = Counter({'FlashNestTests.' + class_name + ' ' + method: 1 for method in methods})
    for state, suffix in [('started', r'\.'), ('passed', r' \([0-9.]+ seconds\)\.')]:
        found = Counter(re.findall(r"^Test Case '-\[([^\]\r\n]+)\]' " + state + suffix + '$', log, re.MULTILINE))
        if found != expected_cases:
            raise ValueError(f'Wrong/missing/duplicate {state} tests')
    if re.search(r'^Test Case .*\b(failed|skipped)\b', log, re.MULTILINE):
        raise ValueError('Failed/skipped test in log')
    result = {'device': device, 'testCount': count, 'scope': scope}
    if scope == 'safety':
        if 'FLASHNEST_SAVE_LISTING ' in log or ' measured [' in log:
            raise ValueError('Safety run unexpectedly contains performance measurements')
        return result
    expected_marker = ('FLASHNEST_SAVE_LISTING mode=full rows=5 current=1 invalid=1 retainedSOLUTF8Bytes=67108992'
                       if scope == 'baseline' else
                       'FLASHNEST_SAVE_LISTING mode=metadata rows=5 current=1 invalid=1 retainedSOLUTF8Bytes=0')
    markers = re.findall(r'^FLASHNEST_SAVE_LISTING .*$', log, re.MULTILINE)
    if markers != [expected_marker]:
        raise ValueError('Missing, duplicate, or incorrect retained-payload marker')
    metrics = {}
    for line in log.splitlines():
        if ' measured [' not in line:
            continue
        if METHOD not in line:
            raise ValueError('Unexpected measured test')
        match = re.search(r'measured \[([^\]]+)\].*?values:\s*\[([^\]]+)\]', line)
        if not match:
            raise ValueError('Unknown metric format')
        label, numbers = match.groups()
        values = [float(value.strip()) for value in numbers.split(',')]
        if label in metrics or len(values) != 5 or not all(math.isfinite(value) for value in values):
            raise ValueError('Expected five finite samples per unique metric')
        metrics[label] = {'values': values, 'median': statistics.median(values), 'mean': statistics.mean(values)}
    if not any('memory' in key.lower() for key in metrics) or not any('clock' in key.lower() for key in metrics):
        raise ValueError('Missing memory or clock metrics')
    result.update(iterations=5, metrics=metrics, retainedSOLUTF8Bytes=67_108_992 if scope == 'baseline' else 0)
    return result


def compare(baseline, patched, safety):
    if baseline.get('scope') != 'baseline' or patched.get('scope') != 'patched' or safety.get('scope') != 'safety':
        raise ValueError('Wrong evidence scopes')
    if baseline['device'] != patched['device'] or patched['device'] != safety['device']:
        raise ValueError('Mismatched A/B/safety device')
    if baseline['metrics'].keys() != patched['metrics'].keys():
        raise ValueError('Mismatched A/B metrics')
    return {'baseline': baseline, 'patched': patched, 'safety': safety,
            'medianDeltaPatchedMinusBaseline': {key: patched['metrics'][key]['median'] - baseline['metrics'][key]['median']
                                                for key in baseline['metrics']},
            'interpretation': 'One sequential hosted-simulator A/B; allocator/host/order noise remains. Retained SOL UTF8 bytes '
                              'are logical payload, not physical RAM. Native listing only, no WebContent/GPU/game or OOM/SIGBUS claim.'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['stage', 'opt-in', 'verify', 'compare'])
    parser.add_argument('--scope', choices=['baseline', 'patched', 'safety'])
    parser.add_argument('paths', nargs='+', type=Path)
    args = parser.parse_args()
    if args.command == 'stage': stage(*args.paths)
    elif args.command == 'opt-in':
        path, evidence = args.paths
        value = opt_in(plistlib.loads(path.read_bytes()), args.scope)
        path.write_bytes(plistlib.dumps(value)); evidence.write_bytes(path.read_bytes())
    else:
        *inputs, output = args.paths
        if args.command == 'verify': value = verify(json.loads(inputs[0].read_text()), inputs[1].read_text(), args.scope)
        else: value = compare(*(json.loads(path.read_text()) for path in inputs))
        output.write_text(json.dumps(value, indent=2) + '\n')


if __name__ == '__main__': main()

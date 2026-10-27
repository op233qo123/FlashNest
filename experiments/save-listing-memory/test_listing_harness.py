import base64
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import listing_harness as h
from generate_fixtures import generate


def summary(scope='baseline'):
    count = 9 if scope == 'safety' else 1
    counts = dict(passedTests=count, failedTests=0, skippedTests=0, expectedFailures=0)
    return dict(result='Passed', totalTestCount=count, testFailures=[], **counts,
                devicesAndConfigurations=[dict(device=dict(platform='iOS Simulator', osVersion='18.2', deviceId='same'), **counts)])


def log(scope='baseline'):
    class_name, methods = h.selection(scope)
    lines = []
    for method in methods:
        case = f"Test Case '-[FlashNestTests.{class_name} {method}]'"
        lines.extend([case + ' started.', case + ' passed (1.000 seconds).'])
    if scope != 'safety':
        for label in ['Memory Peak Physical, kB', 'Memory Physical, kB', 'Clock Monotonic Time, s']:
            lines.append(f"Tests.swift:41: Test Case '-[FlashNestTests.{class_name} {methods[0]}]' "
                         f'measured [{label}] average: 3, values: [1, 2, 3, 4, 5]')
        mode, retained = ('full', 67108992) if scope == 'baseline' else ('metadata', 0)
        lines.append(f'FLASHNEST_SAVE_LISTING mode={mode} rows=5 current=1 invalid=1 retainedSOLUTF8Bytes={retained}')
    return '\n'.join(lines)


class ListingHarnessTests(unittest.TestCase):
    def test_exact_benchmark_and_safety_counts(self):
        baseline = h.verify(summary(), log(), 'baseline')
        patched = h.verify(summary('patched'), log('patched'), 'patched')
        safety = h.verify(summary('safety'), log('safety'), 'safety')
        result = h.compare(baseline, patched, safety)
        self.assertEqual(baseline['retainedSOLUTF8Bytes'], 67_108_992)
        self.assertEqual(patched['retainedSOLUTF8Bytes'], 0)
        self.assertEqual(safety['testCount'], 9)
        self.assertEqual(result['medianDeltaPatchedMinusBaseline']['Memory Peak Physical, kB'], 0)

    def test_reject_zero_skip_failure_boolean_counts_or_wrong_platform(self):
        for key, value in [('totalTestCount', 0), ('skippedTests', 1), ('failedTests', 1), ('passedTests', True), ('result', 'Failed')]:
            broken = summary(); broken[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): h.verify(broken, log(), 'baseline')
        broken = summary(); broken['devicesAndConfigurations'][0]['device']['osVersion'] = '18.5'
        with self.assertRaises(ValueError): h.verify(broken, log(), 'baseline')
        broken = summary(); broken['devicesAndConfigurations'][0]['skippedTests'] = 1
        with self.assertRaises(ValueError): h.verify(broken, log(), 'baseline')
        broken = summary(); broken['devicesAndConfigurations'].append(copy.deepcopy(broken['devicesAndConfigurations'][0]))
        with self.assertRaises(ValueError): h.verify(broken, log(), 'baseline')

    def test_reject_wrong_or_duplicate_identity_missing_or_nonfinite_samples(self):
        for broken in [log().replace(h.METHOD, 'wrongMethod'), log() + '\n' + log(),
                       log().replace('[1, 2, 3, 4, 5]', '[1, 2, 3, 4]'),
                       log().replace('[1, 2, 3, 4, 5]', '[1, 2, nan, 4, 5]'),
                       log().replace('values:', 'unrecognized:'),
                       '\n'.join(line for line in log().splitlines() if 'Memory' not in line),
                       '\n'.join(line for line in log().splitlines() if 'Clock' not in line)]:
            with self.subTest(log=broken[-100:]), self.assertRaises(ValueError): h.verify(summary(), broken, 'baseline')

    def test_reject_wrong_missing_duplicate_or_cross_arm_marker(self):
        for broken in [log().replace('67108992', '0'), log().replace('rows=5', 'rows=6'),
                       log().replace('invalid=1', 'invalid=0'), log('patched'),
                       '\n'.join(line for line in log().splitlines() if 'FLASHNEST_' not in line),
                       log() + '\n' + log().splitlines()[-1]]:
            with self.assertRaises(ValueError): h.verify(summary(), broken, 'baseline')

    def test_safety_cannot_skip_case_or_substitute_benchmark(self):
        with self.assertRaises(ValueError): h.verify(summary('safety'), log(), 'safety')
        with self.assertRaises(ValueError): h.verify(summary('safety'), log('safety') + '\n' + log().splitlines()[-1], 'safety')
        broken = log('safety').replace(h.SAFETY_METHODS[0], 'notTheRequiredCase')
        with self.assertRaises(ValueError): h.verify(summary('safety'), broken, 'safety')

    def test_actual_test_process_opt_in_preserves_other_environment(self):
        target = dict(BlueprintName='FlashNestTests', TestBundlePath='x',
                      EnvironmentVariables={'KEEP': 'yes', 'FLASHNEST_MEASURE_SAVE_MEMORY': '1'}, SkipTestIdentifiers=['old'])
        for document in [{'FlashNestTests': copy.deepcopy(target)},
                         {'TestConfigurations': [{'TestTargets': [copy.deepcopy(target)]}]}]:
            for scope in ['baseline', 'patched', 'safety']:
                result = h.opt_in(copy.deepcopy(document), scope)
                got = (result['TestConfigurations'][0]['TestTargets'][0] if 'TestConfigurations' in result else result['FlashNestTests'])
                expected = {'KEEP': 'yes'} if scope == 'safety' else {'KEEP': 'yes', 'FLASHNEST_MEASURE_SAVE_LISTING': '1'}
                self.assertEqual(got['EnvironmentVariables'], expected)
                self.assertEqual(got['SkipTestIdentifiers'], [])
                self.assertEqual(len(got['OnlyTestIdentifiers']), 9 if scope == 'safety' else 1)

    def test_opt_in_rejects_wrong_target_or_disabled_multi_configuration(self):
        for document in [{}, {'TestConfigurations': []},
                         {'TestConfigurations': [{'IsEnabled': False, 'TestTargets': []}]},
                         {'Other': dict(BlueprintName='Other', TestBundlePath='x')},
                         {'TestConfigurations': [{'TestTargets': [dict(BlueprintName='FlashNestTests', IsUITestBundle=True)]}]}]:
            with self.assertRaises(ValueError): h.opt_in(document, 'baseline')
        with self.assertRaises(ValueError): h.selection('unknown')

    def test_comparison_requires_same_device_and_all_three_scopes(self):
        a = h.verify(summary(), log(), 'baseline')
        b = h.verify(summary('patched'), log('patched'), 'patched')
        c = h.verify(summary('safety'), log('safety'), 'safety')
        for which in ['device', 'metrics', 'scope']:
            bad = copy.deepcopy(b)
            if which == 'device': bad['device']['deviceId'] = 'other'
            elif which == 'metrics': del bad['metrics']['Clock Monotonic Time, s']
            else: bad['scope'] = 'baseline'
            with self.assertRaises(ValueError): h.compare(a, bad, c)

    def test_original_fixture_manifest_identity_integrity_and_64mib_boundary(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first, second = generate(root / 'one'), generate(root / 'two')
            self.assertEqual(first, second)
            self.assertEqual(first['base64BytesPerArchive'] * 6, 67_108_992)
            files = first['files']; self.assertEqual(len(files), 7)
            named = [value['bytes'] for name, value in files.items() if name != 'current.json']
            self.assertLessEqual(sum(sorted(named)[:5]), 64 * 1024 * 1024)
            self.assertGreater(sum(named), 64 * 1024 * 1024)
            for name, record in files.items():
                path = root / 'one/save' / first['packageID'] / name
                self.assertEqual(h.sha(path), record['sha256'])
                archive = json.loads(path.read_text())
                self.assertEqual(archive['decodedBytes'], 8_388_608)
                self.assertEqual(archive['packageID'], first['packageID'])
                if name != 'current.json': self.assertEqual(archive['id'] + '.json', name)
                for entry in archive['entries']:
                    data = base64.b64decode(entry['value'], validate=True)
                    self.assertEqual(hashlib.sha256(data).hexdigest(), entry['sha256'])
                    self.assertEqual(data[:2], b'\x00\xbf'); self.assertEqual(data[6:16], b'TCSO\x00\x04\x00\x00\x00\x00')
            with self.assertRaises(ValueError): generate(root / 'one')

    def test_stage_rejects_fingerprint_drift_before_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            for file in h.PINS:
                path = repo / file; path.parent.mkdir(parents=True, exist_ok=True); path.write_text('unreviewed')
            with self.assertRaises(ValueError): h.stage(repo, repo / 'old', repo / 'new', repo / 'out.json')
            self.assertFalse((repo / 'old').exists())

    def test_stage_attests_only_two_app_changes_and_identical_benchmark(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo, old, new = [root / name for name in ['repo', 'old', 'new']]
            for tree in (repo, old, new):
                for file in h.APP_FILES:
                    path = tree / file; path.parent.mkdir(parents=True, exist_ok=True); path.write_text('old')
                (tree / 'Tests').mkdir()
                (tree / 'runtime.lock.json').write_text('unchanged engine')
            for file in h.PINS: (repo / file).write_text('reviewed ' + file)
            def fake_git(tree, *args):
                if args[0] == 'rev-parse': return h.BASELINE
                if args[0] == 'status': return ''
                if args[0] == 'ls-files': return '\n'.join(h.APP_FILES + ['runtime.lock.json'])
                raise AssertionError(args)
            def tiny_generator(destination):
                path = destination / 'save/ID/a.json'; path.parent.mkdir(parents=True); path.write_text('fixture')
                return {'packageID': 'ID', 'files': {'a.json': {'bytes': 7, 'sha256': h.sha(path)}}}
            pins = {file: h.sha(repo / file) for file in h.PINS}
            with patch.object(h, 'git', side_effect=fake_git), patch.object(h, 'PINS', pins), patch.object(h, 'generate', side_effect=tiny_generator):
                h.stage(repo, old, new, root / 'evidence.json')
                evidence = json.loads((root / 'evidence.json').read_text())
                self.assertEqual(evidence['productionDelta'], sorted(h.APP_FILES))
                self.assertEqual(evidence['patchedOnlyTest'], h.SAFETY)
                self.assertEqual((old / h.BENCHMARK).read_bytes(), (new / h.BENCHMARK).read_bytes())
                self.assertFalse((old / h.SAFETY).exists())
                self.assertEqual((new / h.SAFETY).read_bytes(), (repo / h.SAFETY).read_bytes())
                (new / 'runtime.lock.json').write_text('unreviewed engine drift')
                with self.assertRaisesRegex(ValueError, 'Unexpected production delta'):
                    h.stage(repo, old, new, root / 'bad.json')


if __name__ == '__main__': unittest.main()

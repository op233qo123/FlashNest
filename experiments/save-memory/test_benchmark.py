import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import benchmark as b


def summary():
    counts = {'passedTests': 2, 'failedTests': 0, 'skippedTests': 0, 'expectedFailures': 0}
    return dict(result='Passed', totalTestCount=2, testFailures=[], **counts,
                devicesAndConfigurations=[dict(device={'platform': 'iOS Simulator', 'osVersion': '18.2',
                                                       'deviceId': 'same-device'}, **counts)])


def log():
    lines = []
    for method in b.METHODS:
        case = f"Test Case '-[FlashNestTests.SaveStoreMemoryTests {method}]'"
        lines.extend([case + ' started.', case + ' passed (0.123 seconds).'])
    for metric in ['Memory Peak Physical, kB', 'Memory Physical, kB', 'Clock Monotonic Time, s']:
        lines.append(f"Tests.swift:62: Test Case '-[FlashNestTests.SaveStoreMemoryTests {b.METHODS[1]}]' "
                     f'measured [{metric}] average: 3, relative standard deviation: 0%, values: [1, 2, 3, 4, 5]')
    return '\n'.join(lines)


class BenchmarkTests(unittest.TestCase):
    def test_exact_run_and_five_metrics(self):
        result = b.verify(summary(), log())
        self.assertEqual(result['testCount'], 2)
        self.assertEqual(result['metrics']['Memory Peak Physical, kB']['median'], 3)
        self.assertEqual(b.compare(result, result)['medianDeltaPatchedMinusBaseline']['Clock Monotonic Time, s'], 0)

    def test_reject_skip_zero_failure_wrong_device_or_config(self):
        for key, value in [('totalTestCount', 0), ('skippedTests', 1), ('failedTests', 1), ('passedTests', True), ('result', 'Failed')]:
            broken = summary(); broken[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): b.verify(broken, log())
        broken = summary(); broken['devicesAndConfigurations'][0]['device']['osVersion'] = '18.5'
        with self.assertRaises(ValueError): b.verify(broken, log())
        broken = summary(); broken['devicesAndConfigurations'].append(copy.deepcopy(broken['devicesAndConfigurations'][0]))
        with self.assertRaises(ValueError): b.verify(broken, log())

    def test_reject_missing_duplicate_wrong_tests_and_bad_metrics(self):
        for broken in [log().replace(b.METHODS[0], 'wrongTest'), log() + '\n' + log(),
                       log().replace('values: [1, 2, 3, 4, 5]', 'values: [1, 2, 3, 4]'),
                       log().replace('values: [1, 2, 3, 4, 5]', 'values: [1, 2, nan, 4, 5]'),
                       '\n'.join(line for line in log().splitlines() if 'Memory' not in line),
                       '\n'.join(line for line in log().splitlines() if 'Clock' not in line),
                       log().replace('values:', 'unknown:')]:
            with self.subTest(log=broken[:80]), self.assertRaises(ValueError): b.verify(summary(), broken)

    def test_opt_in_actual_legacy_and_v2_test_process_preserving_environment(self):
        target = {'BlueprintName': 'FlashNestTests', 'TestBundlePath': 'test.xctest',
                  'EnvironmentVariables': {'KEEP': 'unchanged'}, 'SkipTestIdentifiers': ['anything']}
        for document in [{'FlashNestTests': copy.deepcopy(target)},
                         {'TestConfigurations': [{'TestTargets': [copy.deepcopy(target)]}]}]:
            result = b.opt_in(document)
            got = (result['TestConfigurations'][0]['TestTargets'][0]
                   if 'TestConfigurations' in result else result['FlashNestTests'])
            self.assertEqual(got['EnvironmentVariables'], {'KEEP': 'unchanged', 'FLASHNEST_MEASURE_SAVE_MEMORY': '1'})
            self.assertEqual(got['SkipTestIdentifiers'], [])
            self.assertEqual(got['OnlyTestIdentifiers'], ['SaveStoreMemoryTests/' + name for name in b.METHODS])

    def test_opt_in_rejects_wrong_disabled_or_ambiguous_target(self):
        for document in [{}, {'TestConfigurations': []},
                         {'Other': {'BlueprintName': 'Other', 'TestBundlePath': 'x'}},
                         {'TestConfigurations': [{'IsEnabled': False, 'TestTargets': []}]},
                         {'TestConfigurations': [{'TestTargets': [{'BlueprintName': 'FlashNestTests', 'IsUITestBundle': True}]}]}]:
            with self.assertRaises(ValueError): b.opt_in(document)

    def test_comparison_rejects_changed_device_or_metrics(self):
        first = b.verify(summary(), log()); second = copy.deepcopy(first)
        second['device']['deviceId'] = 'other'
        with self.assertRaises(ValueError): b.compare(first, second)
        second = copy.deepcopy(first); del second['metrics']['Memory Physical, kB']
        with self.assertRaises(ValueError): b.compare(first, second)

    def test_stage_only_reviewed_savestore_delta_and_common_test(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo, old, new = [root / name for name in ['repo', 'old', 'new']]
            for tree in (repo, old, new):
                (tree / 'App/Models').mkdir(parents=True)
                (tree / 'Tests').mkdir()
                (tree / b.SOURCE).write_text('baseline')
                (tree / 'runtime.lock.json').write_text('unchanged engine')
            (repo / b.SOURCE).write_text('reviewed patch')
            (repo / b.TEST).write_text('same synthetic tests')
            def fake_git(tree, *args):
                if args[0] == 'rev-parse': return b.BASELINE
                if args[0] == 'status': return ''
                if args[0] == 'ls-files': return b.SOURCE + '\nruntime.lock.json'
                raise AssertionError(args)
            with patch.object(b, 'git', side_effect=fake_git), patch.object(b, 'SOURCE_SHA', b.sha(repo / b.SOURCE)), patch.object(b, 'TEST_SHA', b.sha(repo / b.TEST)):
                b.stage(repo, old, new, root / 'evidence.json')
                evidence = json.loads((root / 'evidence.json').read_text())
                self.assertEqual(evidence['onlyVariantFile'], [b.SOURCE])
                self.assertEqual((old / b.TEST).read_bytes(), (new / b.TEST).read_bytes())
                (repo / b.SOURCE).write_text('unreviewed drift')
                with self.assertRaises(ValueError): b.stage(repo, old, new, root / 'bad.json')


if __name__ == '__main__': unittest.main()

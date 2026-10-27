import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('native_collector', HERE / 'collect_native_evidence.py')
c = importlib.util.module_from_spec(spec); spec.loader.exec_module(c)
DEVICE = '11111111-2222-4333-8444-555555555555'
OTHER = '11111111-2222-4333-8444-666666666666'


def summary(device=DEVICE):
    return {'devicesAndConfigurations': [{'device': {'deviceId': device, 'osVersion': '18.5', 'platform': 'iOS Simulator'}}]}


class NativeCollectionTests(unittest.TestCase):
    def test_actual_device_not_requested_guess(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); output = root / 'output'; output.mkdir()
            container = root / 'container'
            evidence = container / 'Documents/audio-native-evidence' / DEVICE.lower() / 'baseline-normal'
            evidence.mkdir(parents=True); (evidence / 'page-terminal.json').write_text('{"passed":false}')
            commands = []
            def run(command, **kwargs):
                commands.append(command)
                return subprocess.CompletedProcess(command, 0, str(container) + '\n', 'retained diagnostic stderr')
            result = c.collect(summary(OTHER), DEVICE, output, run)
            self.assertTrue(result['verified']); self.assertEqual(commands[0][3], OTHER)
            self.assertEqual(result['lookupStderr'], 'retained diagnostic stderr')
            self.assertEqual(len(result['files']), 1)
            self.assertEqual(json.loads((output / 'raw' / DEVICE.lower() / 'baseline-normal/page-terminal.json').read_text()), {'passed': False})

    def test_lookup_error_retains_exit_stderr_and_fails(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            with self.assertRaises(ValueError):
                c.collect(summary(), DEVICE, root, lambda *a, **k: subprocess.CompletedProcess(a[0], 42, '', 'Not installed'))
            result = json.loads((root / 'raw-collection.json').read_text())
            self.assertFalse(result['verified']); self.assertEqual(result['lookupExitCode'], 42)
            self.assertEqual(result['lookupStderr'], 'Not installed'); self.assertFalse((root / 'raw').exists())

    def test_invalid_device_platform_and_ambiguity(self):
        for value in [{}, summary('not UUID'), {'devicesAndConfigurations': []},
                      {'devicesAndConfigurations': summary()['devicesAndConfigurations'] + summary(OTHER)['devicesAndConfigurations']}]:
            with self.subTest(value=value), self.assertRaises((ValueError, KeyError)):
                c.actual_device(value)
        wrong = summary(); wrong['devicesAndConfigurations'][0]['device']['osVersion'] = '18.2'
        with self.assertRaises(ValueError): c.actual_device(wrong)

    def test_missing_linked_unexpected_oversized_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); source = root / 'source'; mode = source / DEVICE.lower() / 'baseline-normal'
            mode.mkdir(parents=True); output = root / 'out'
            with self.assertRaises(ValueError): c.copy_evidence(source, output)
            file = mode / 'unexpected.json'; file.write_text('{}')
            with self.assertRaises(ValueError): c.copy_evidence(source, output)
            file.unlink(); file = mode / 'case-0.json'; file.symlink_to(HERE / 'browser-approval.json')
            with self.assertRaises(ValueError): c.copy_evidence(source, output)
            file.unlink(); file.write_bytes(b' ' * (2 * 1024 * 1024 + 1))
            with self.assertRaises(ValueError): c.copy_evidence(source, output)
            file.write_text('{}'); c.copy_evidence(source, output)
            with self.assertRaises(ValueError): c.copy_evidence(source, output)

    def test_failure_mirror_bounds_and_build_test_separation(self):
        host = (HERE / 'Host/NativeAudioHost.swift').read_text()
        ui = (HERE / 'UITests/NativeAudioLifecycleUITests.swift').read_text()
        workflow = (HERE / 'workflow-draft.yml').read_text()
        self.assertIn('bytes.count <= 131_072', host); self.assertIn('result["error"]', host)
        self.assertIn('redactDiagnosticURL', host); self.assertIn('.withoutEscapingSlashes', host)
        self.assertIn('status.value as? String', ui); self.assertIn('uniformTypeIdentifier: "public.json"', ui)
        self.assertIn('xcodebuild build-for-testing', workflow); self.assertIn('xcodebuild test-without-building', workflow)
        self.assertIn('timeout-minutes: 12', workflow); self.assertIn('timeout-minutes: 30', workflow)
        self.assertNotIn("container=''", workflow)


if __name__ == '__main__': unittest.main()

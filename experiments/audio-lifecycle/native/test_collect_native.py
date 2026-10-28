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

    def test_same_shutdown_device_boots_once_after_crash_capture(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); output = root / 'out'; output.mkdir()
            (output / 'crashes').mkdir(); (output / 'crashes/collection.json').write_text('{"reports":[],"skipped":0}')
            container = root / 'container'
            mode = container / 'Documents/audio-native-evidence' / DEVICE.lower() / 'baseline-normal'
            mode.mkdir(parents=True); (mode / 'page-terminal.json').write_text('{"passed":false}')
            commands, lookups = [], 0
            def run(command, **kwargs):
                nonlocal lookups
                commands.append((command, kwargs['timeout']))
                if command[2] == 'get_app_container':
                    lookups += 1
                    return subprocess.CompletedProcess(command, 149 if lookups == 1 else 0,
                        '' if lookups == 1 else str(container), 'Shutdown' if lookups == 1 else '')
                if command[2] == 'list':
                    return subprocess.CompletedProcess(command, 0, json.dumps({'devices': {'iOS-18-5': [
                        {'udid': OTHER, 'state': 'Shutdown', 'isAvailable': True}]}}), '')
                return subprocess.CompletedProcess(command, 0, '', '')
            result = c.collect(summary(OTHER), DEVICE, output, run)
            self.assertTrue(result['verified']); self.assertEqual(result['priorDeviceState'], 'Shutdown')
            self.assertEqual(result['lookupExitCode'], 149); self.assertEqual(result['recoveryLookupExitCode'], 0)
            self.assertEqual([x[0][2] for x in commands], ['get_app_container','list','boot','bootstatus','get_app_container'])
            for command, bound in commands:
                if command[2] != 'list': self.assertEqual(command[3], OTHER)
                self.assertLessEqual(bound, 90)
            self.assertIn('priorCrashCollectionSHA256', result)
            self.assertIn('no app launch', result['recovery']['scope'])

    def test_no_recovery_before_crash_capture_or_for_nonshutdown(self):
        for state, available in [('Booted', True), ('Creating', True), ('Shutdown', False), (None, True)]:
            with self.subTest(state=state, available=available), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary); (root / 'crashes').mkdir()
                (root / 'crashes/collection.json').write_text('{"reports":[]}')
                commands = []
                def run(command, **kwargs):
                    commands.append(command)
                    if command[2] == 'get_app_container': return subprocess.CompletedProcess(command, 149, '', 'lookup failed')
                    return subprocess.CompletedProcess(command, 0, json.dumps({'devices': {'iOS-18-5': [
                        {'udid': DEVICE, 'state': state, 'isAvailable': available}]}}), '')
                with self.assertRaises(ValueError): c.collect(summary(), DEVICE, root, run)
                self.assertEqual([x[2] for x in commands], ['get_app_container','list'])
                self.assertFalse(json.loads((root / 'raw-collection.json').read_text())['verified'])
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary); commands=[]
            def run(command, **kwargs):
                commands.append(command); return subprocess.CompletedProcess(command,149,'','Shutdown')
            with self.assertRaisesRegex(ValueError, 'Crash collection'): c.collect(summary(), DEVICE, root, run)
            self.assertEqual(len(commands),1)

    def test_recovery_boot_failure_and_timeout_are_retained(self):
        for failure in ['boot', 'bootstatus']:
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary); (root / 'crashes').mkdir(); (root / 'crashes/collection.json').write_text('{"reports":[]}')
                def run(command, **kwargs):
                    if command[2] == 'get_app_container': return subprocess.CompletedProcess(command,149,'','Shutdown')
                    if command[2] == 'list': return subprocess.CompletedProcess(command,0,json.dumps({'devices': {'iOS': [
                        {'udid':DEVICE,'state':'Shutdown','isAvailable':True}]}}),'')
                    if command[2] == failure:
                        if failure == 'bootstatus': raise subprocess.TimeoutExpired(command,kwargs['timeout'])
                        return subprocess.CompletedProcess(command,42,'','Boot rejected')
                    return subprocess.CompletedProcess(command,0,'','')
                with self.assertRaises(ValueError): c.collect(summary(),DEVICE,root,run)
                result=json.loads((root / 'raw-collection.json').read_text()); self.assertFalse(result['verified'])
                record=result['recovery'][failure]
                if failure == 'bootstatus': self.assertTrue(record['timedOut'])
                else: self.assertEqual(record['stderr'],'Boot rejected')
                self.assertIn('endedAt',record)

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
        self.assertIn('diagnosticOnly', host); self.assertIn('fullBodySHA256', host)
        self.assertIn('attachTerminal("audio-native-teardown"', ui)
        self.assertIn('continueAfterFailure = true', ui)
        self.assertLess(workflow.index('python3 scripts/collect_test_webkit_crashes.py'), workflow.index('python3 experiments/audio-lifecycle/native/collect_native_evidence.py'))
        self.assertIn('redactDiagnosticURL', host); self.assertIn('.withoutEscapingSlashes', host)
        self.assertIn('status.value as? String', ui); self.assertIn('uniformTypeIdentifier: "public.json"', ui)
        self.assertIn('xcodebuild build-for-testing', workflow); self.assertIn('xcodebuild test-without-building', workflow)
        self.assertIn('timeout-minutes: 12', workflow); self.assertIn('timeout-minutes: 30', workflow)
        self.assertNotIn("container=''", workflow)


if __name__ == '__main__': unittest.main()

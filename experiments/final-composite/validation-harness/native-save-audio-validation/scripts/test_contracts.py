"""Small source/model checks only; no Swift, WebKit, native audio or UI execution."""
from collections import Counter
import copy
import importlib.util
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

import stage_audio_target as stage
import verify_results as result

SOURCE = stage.HERE.parent / 'next-ipa-156-prep/app-integration/source'


class OverlayContracts(unittest.TestCase):
    def test_exact_source_plan_and_no_execution_claim(self):
        inputs, diagnostics, changes, manifest = stage.overlay(SOURCE)
        self.assertEqual(set(changes), {stage.SHELL, stage.SESSION})
        self.assertEqual(manifest['state'], 'authored-not-executed')
        self.assertFalse(manifest['runtimeBound']); self.assertFalse(manifest['audibleOutputProven'])
        self.assertIsNone(manifest['totalContextCount'])
        self.assertEqual(stage.source_bytes(SOURCE), inputs)

    def test_rebound_transforms_identical_to_reviewed_original_operations(self):
        prior = stage.HERE.parent / 'audio-recovery-acceptance/late-native-integration/stage_overlay.py'
        spec = importlib.util.spec_from_file_location('prior_stage', prior)
        original = importlib.util.module_from_spec(spec); spec.loader.exec_module(original)
        inputs, diagnostics, changes, _ = stage.overlay(SOURCE)
        # Only this in-memory reference accepts the new source digest; no old
        # reviewed file is changed and the transform implementation is identical.
        original.PINS[stage.SHELL] = stage.digest(inputs[stage.SHELL])
        original.PINS[stage.SESSION] = stage.digest(inputs[stage.SESSION])
        self.assertEqual(changes[stage.SHELL], original.transform_shell(inputs[stage.SHELL]))
        self.assertEqual(changes[stage.SESSION], original.transform_session(inputs[stage.SESSION]))

    def test_one_scoped_injection_no_production_paused_override(self):
        _, _, changes, _ = stage.overlay(SOURCE)
        text = changes[stage.SESSION].decode()
        added = text.split('func diagnosticLateInject')[1].split('func setPaused')[0]
        self.assertEqual(added.count('FlashNestLateHost.inject'), 1)
        self.assertNotIn('setPaused(false)', added)
        self.assertNotIn('addUserScript', added)
        self.assertIn('paused = false', added)

    def test_shell_only_observes_exact_production_intent(self):
        _, diagnostics, changes, _ = stage.overlay(SOURCE)
        bridge = diagnostics['evidence-bridge.inc.js'].decode()
        self.assertIn('!!player && started && !paused && !backgrounded && !document.hidden && !closing && !fatal', bridge)
        self.assertNotIn('dispatchEvent', bridge)
        self.assertNotIn('prototype', bridge)
        self.assertIn('saveBridge.capture()', bridge)
        self.assertNotIn('localStorage.setItem', bridge)
        self.assertEqual(changes[stage.SHELL].decode().count('lateObserveTrace(message);'), 1)

    def test_late_readiness_precedes_loading_and_no_synthetic_retry(self):
        diagnostics = stage.diagnostic_bytes()
        host = diagnostics['Host/LateAudioHost.swift'].decode()
        body = host.split('func begin()')[1].split('func inject()')[0]
        self.assertLess(body.index('FlashNestLateEvidence.snapshot()'), body.index('for name in ["late-audio-probe"'))
        self.assertNotIn('addUserScript', host)
        tests = diagnostics['UITests/LateAudioUITests.swift'].decode()
        self.assertIn('retry.tap()', tests)
        self.assertNotIn('.click()', host + tests)
        self.assertIn('probe["totalContextCount"] is NSNull', tests)

    def test_metadata_cannot_authorize_code_drift(self):
        with self.assertRaises(ValueError):
            stage.source_bytes(SOURCE, {stage.SESSION: {'sha256': '0' * 64, 'bytes': 0}})

    def test_anchor_drift_rejected(self):
        with self.assertRaises(ValueError): stage.transform_shell(b'no anchors', stage.diagnostic_bytes())
        with self.assertRaises(ValueError): stage.transform_session(b'no anchor')

    def test_existing_injector_rejected(self):
        text = stage.read(SOURCE, stage.SESSION) + b'\n// FlashNestAudioProbe'
        with self.assertRaises(ValueError): stage.transform_session(text)

    def test_unsafe_paths_rejected(self):
        for p in ('../x', 'a/../b', '/tmp/x', 'a//b', 'a\\b', '', './a', None):
            with self.subTest(path=p), self.assertRaises(ValueError): stage.path_key(p)

    def test_symlink_and_ancestor_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); (root/'real').mkdir(); (root/'real/data').write_text('synthetic')
            (root/'alias').symlink_to(root/'real', target_is_directory=True)
            with self.assertRaises(ValueError): stage.read(root/'alias', 'data')
            with self.assertRaises(ValueError): stage.inventory(root)
            with self.assertRaises(ValueError): stage.no_symlink_ancestors(root/'alias/future')

    def test_native_save_fixture_is_nonempty_readonly_exact_bytes(self):
        text = (stage.HERE/'Tests/NativeSaveSettingsPreservationTests.swift').read_text()
        for token in ('explicit-flush.swf', 'read-only.swf', 'baseline.entries.count, 1',
                      'RenderSamplingSettings.Mode.allCases', 'RendererSettings(mode: .webgl)',
                      'current), nativeBytes', 'reopened.entries, baseline.entries',
                      'session.suspendAndSave()', 'session.resumeAfterSuspension()',
                      'RenderSamplingSettings.runtimeValidated', 'fixtureFiles(content), originalFiles'):
            self.assertIn(token, text)
        capture = text.split('private func capture')[1].split('private func evaluate')[0]
        self.assertNotIn('shutdownAndCapture()', capture)
        self.assertNotIn('setItem', capture)

    def test_project_is_diagnostic_only_and_locked_package(self):
        project = stage.project()
        self.assertNotIn('FlashNest', project['targets'])
        host = project['targets']['LateAudioDiagnostic']
        self.assertEqual(host['settings']['base']['PRODUCT_BUNDLE_IDENTIFIER'], 'com.flashnest.late-audio.diagnostic')
        self.assertEqual(project['packages']['ZIPFoundation']['exactVersion'], '0.9.20')
        self.assertIn('FlashNestApp.swift', host['sources'][1]['excludes'])
        self.assertNotIn('archive', json.dumps(project))


class SelectionContracts(unittest.TestCase):
    def test_exact_counts_no_duplicate_or_picker_sampling_overlap(self):
        lanes = result.SELECTION['lanes']
        self.assertEqual([l['expectedCount'] for l in lanes], [48,19,1,2,1])
        all_ids = [s for lane in lanes for s in lane['selectors']]
        self.assertEqual(len(all_ids), len(set(all_ids)))
        excluded = set(result.SELECTION['forbiddenOverlapClasses'])
        self.assertFalse(excluded.intersection(s.split('/')[1] for s in all_ids))
        self.assertTrue(all(l['expectedSkipped'] == 0 and not l['parallelTesting'] for l in lanes))

    def test_exact_selected_source_methods_and_hashes(self):
        for name, row in result.SELECTION['sourceTests'].items():
            path = stage.HERE.parent / row['path']
            self.assertEqual(stage.digest(path.read_bytes()), row['sha256'])
            body = re.split(r'\bclass\s+' + name + r'\b', path.read_text(), maxsplit=1)[1]
            body = re.split(r'\bclass\s+\w+', body, maxsplit=1)[0]
            self.assertEqual(re.findall(r'\bfunc\s+(test\w+)\s*\(', body), row['tests'])


class RuntimeInventoryContracts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.runtime = self.root/'runtime'; self.runtime.mkdir()
        # Deliberately tiny model inputs: inventory semantics only, never an
        # executable release engine or evidence that WASM successfully loaded.
        for name in ('ruffle.js', 'one.wasm', 'two.wasm'):
            (self.runtime/name).write_bytes(('model-only-'+name).encode())
        self.map = stage.inventory(self.runtime)
        self.file = self.root/'runtime-files.json'
        self.file.write_text(json.dumps(self.map))
        self.sha = stage.digest(self.file.read_bytes())

    def tearDown(self):
        self.tmp.cleanup()

    def test_accepts_exact_inventory_semantics_not_runtime_eligibility(self):
        got, _ = stage.validate_runtime(self.runtime, self.file, self.sha, 'candidate-composite')
        self.assertEqual(got, self.map)

    def test_rejects_wrong_explicit_inventory_hash(self):
        with self.assertRaises(ValueError): stage.validate_runtime(self.runtime, self.file, '0'*64, 'candidate-composite')

    def test_rejects_changed_runtime_bytes(self):
        (self.runtime/'ruffle.js').write_text('changed')
        with self.assertRaises(ValueError): stage.validate_runtime(self.runtime, self.file, self.sha, 'candidate-composite')

    def test_rejects_missing_or_extra_runtime_file(self):
        (self.runtime/'extra').write_text('not declared')
        with self.assertRaises(ValueError): stage.validate_runtime(self.runtime, self.file, self.sha, 'candidate-composite')

    def test_rejects_subset_browser_manifest(self):
        self.file.write_text(json.dumps({k:v['sha256'] for k,v in self.map.items()}))
        with self.assertRaises(ValueError): stage.validate_runtime(self.runtime, self.file, stage.digest(self.file.read_bytes()), 'candidate-composite')

    def test_rejects_wrong_runtime_for_historical_baseline(self):
        with self.assertRaises(ValueError): stage.validate_runtime(self.runtime, self.file, self.sha, 'baseline-historical')

    def test_rejects_undeclared_role(self):
        with self.assertRaises(ValueError): stage.validate_runtime(self.runtime, self.file, self.sha, 'auto')


class ResultContracts(unittest.TestCase):
    def setUp(self):
        self.lane = result.SELECTION['lanes'][0]
        n = self.lane['expectedCount']
        counts = {'passedTests': n, 'failedTests': 0, 'skippedTests': 0, 'expectedFailures': 0}
        self.summary = {**counts, 'result': 'Passed', 'title': 'Test - FlashNest', 'totalTestCount': n,
                        'testFailures': [], 'devicesAndConfigurations': [{**counts, 'device': {'osVersion': '18.2', 'platform': 'iOS Simulator'}}]}
        self.log = ''
        for selector in self.lane['selectors']:
            module, cls, method = selector.split('/')
            name = f'{module}.{cls} {method}'
            self.log += f"Test Case '-[{name}]' started.\nTest Case '-[{name}]' passed (0.001 seconds).\n"

    def test_accepts_exact_synthetic_record_semantics_only(self):
        self.assertTrue(result.verify(self.summary, self.log, self.lane)['semanticResultValid'])

    def test_rejects_skip(self):
        self.summary['skippedTests'] = 1
        with self.assertRaises(ValueError): result.verify(self.summary, self.log, self.lane)

    def test_rejects_wrong_os(self):
        self.summary['devicesAndConfigurations'][0]['device']['osVersion'] = '18.5'
        with self.assertRaises(ValueError): result.verify(self.summary, self.log, self.lane)

    def test_rejects_expected_failure(self):
        self.summary['expectedFailures'] = 1
        with self.assertRaises(ValueError): result.verify(self.summary, self.log, self.lane)

    def test_rejects_missing_case(self):
        with self.assertRaises(ValueError): result.verify(self.summary, '\n'.join(self.log.splitlines()[2:]), self.lane)

    def test_rejects_duplicate_execution(self):
        with self.assertRaises(ValueError): result.verify(self.summary, self.log + self.log, self.lane)

    def test_rejects_same_count_foreign_selector(self):
        with self.assertRaises(ValueError): result.verify(self.summary, self.log.replace('SaveStoreTests', 'OtherTests'), self.lane)

    def test_rejects_zero_case_summary(self):
        self.summary['passedTests'] = self.summary['totalTestCount'] = 0
        with self.assertRaises(ValueError): result.verify(self.summary, '', self.lane)

    def test_rejects_no_audio_terminal_records(self):
        with self.assertRaises(ValueError): result.verify_audio_records('', result.SELECTION['lanes'][3])

    def test_rejects_foreign_model_audio_record(self):
        log = '\n'.join('AUDIO_LATE_FINAL ' + json.dumps({'mode': m, 'execution': {'kind': 'model'}})
                        for m in ('candidate-known', 'candidate-unknown'))
        with self.assertRaises(ValueError): result.verify_audio_records(log, result.SELECTION['lanes'][3])


if __name__ == '__main__':
    unittest.main()

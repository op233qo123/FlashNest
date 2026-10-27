import copy
from pathlib import Path
import unittest
from harness import verify, METHOD

ROOT = Path(__file__).resolve().parents[2]

class TransitionGateTests(unittest.TestCase):
    def fixture(self):
        counts = dict(passedTests=1, failedTests=0, skippedTests=0, expectedFailures=0)
        summary = dict(result='Passed', totalTestCount=1, testFailures=[], **counts)
        summary['devicesAndConfigurations'] = [dict(device=dict(osVersion='18.2', platform='iOS Simulator'), **counts)]
        log = f"Test Case '-[{METHOD}]' started.\n"
        states = [('initial-input', 0)]
        for cycle in range(1,4):
            states += [(phase, cycle) for phase in ['scene-ready', 'after-landscape', 'after-background', 'after-portrait']]
            if cycle == 2: states.append(('after-paused-background', 2))
        log += '\n'.join(f'FLASHNEST_TRANSITION_STATE phase={phase} boot=original generation={g} heartbeat={i+1} pointers={g} keys={i+1} ready=1 childGeneration={g} childHeartbeat={i+1} errors=0 unloadCalls={g} unloadEvents={g}' for i,(phase,g) in enumerate(states))
        log += '\n' + '\n'.join(f'FLASHNEST_TRANSITION_HOME cycle={g} phase={phase} visibleHomeIcon=true reportedAppState=4' for g,phase in [(1,'running-child'),(2,'running-child'),(2,'paused-menu'),(3,'running-child')])
        log += f"\nFLASHNEST_TRANSITION_COMPLETE cycles=3 keys=14 pointers=3 unloadCalls=3 unloadEvents=3 errors=0\nTest Case '-[{METHOD}]' passed (10.000 seconds).\n"
        return summary, log
    def test_exact_pass(self):
        self.assertEqual(verify(*self.fixture(), ROOT)['cycles'], 3)
    def test_explicit_18_5_pass_requires_actual_18_5_and_preserves_summary(self):
        summary, log = self.fixture()
        with self.assertRaises(ValueError): verify(summary, log, ROOT, expected_os='18.5')
        summary['devicesAndConfigurations'][0]['device']['osVersion'] = '18.5'
        before = copy.deepcopy(summary)
        result = verify(summary, log, ROOT, expected_os='18.5')
        self.assertEqual(result, dict(result='Passed', cycles=3, states=14, bootCount=1, actualHomeTransitions=4))
        self.assertEqual(summary, before)
        with self.assertRaises(ValueError): verify(summary, log, ROOT)
        for expected_os in ('18', '18.5.0', '26.0', '', None):
            with self.assertRaises(ValueError): verify(summary, log, ROOT, expected_os=expected_os)
    def test_alternate_os_does_not_relax_state_home_or_result_gate(self):
        summary, log = self.fixture()
        summary['devicesAndConfigurations'][0]['device']['osVersion'] = '18.5'
        for bad in [log.replace('visibleHomeIcon=true', 'visibleHomeIcon=false'),
                    log.replace('childHeartbeat=3', 'childHeartbeat=2'),
                    log.replace('keys=14', 'keys=13'),
                    log.replace('unloadEvents=3', 'unloadEvents=2'),
                    log.replace('boot=original generation=3', 'boot=restarted generation=3')]:
            with self.assertRaises(ValueError): verify(summary, bad, ROOT, expected_os='18.5')
        summary['skippedTests'] = 1
        with self.assertRaises(ValueError): verify(summary, log, ROOT, expected_os='18.5')
    def test_zero_skips_failures_and_wrong_os_reject(self):
        for key, value in [('totalTestCount', 0), ('skippedTests', 1), ('failedTests', 1), ('passedTests', True)]:
            summary, log = self.fixture(); summary[key] = value
            with self.assertRaises(ValueError): verify(summary, log, ROOT)
        summary, log = self.fixture(); summary['devicesAndConfigurations'][0]['device']['osVersion'] = '18.5'
        with self.assertRaises(ValueError): verify(summary, log, ROOT)
    def test_missing_duplicate_wrong_completion_reject(self):
        summary, log = self.fixture()
        for bad in [log.replace('FLASHNEST_TRANSITION_COMPLETE cycles=3', ''), log+'FLASHNEST_TRANSITION_COMPLETE cycles=3\n', log.replace('cycles=3', 'cycles=2')]:
            with self.assertRaises(ValueError): verify(summary, bad, ROOT)
    def test_root_reload_missing_generation_and_wrong_test_reject(self):
        summary, log = self.fixture()
        for bad in [log.replace('boot=original generation=3', 'boot=restarted generation=3'), log.replace('generation=3', 'generation=2'), log.replace(METHOD, 'FlashNestUITests.Wrong testWrong')]:
            with self.assertRaises(ValueError): verify(summary, bad, ROOT)
    def test_duplicate_and_failed_case_reject(self):
        summary, log = self.fixture()
        for bad in [log+f"Test Case '-[{METHOD}]' passed (10.000 seconds).\n", log.replace("passed (10.000 seconds).", "failed (10.000 seconds).")]:
            with self.assertRaises(ValueError): verify(summary, bad, ROOT)
    def test_framework_interleaved_xctest_pass(self):
        summary, log = self.fixture()
        verify(summary, log.replace("Test Case '-[", "framework-message:Test Case '-["), ROOT)

    def test_missing_home_frozen_child_and_bad_unload_counter_reject(self):
        summary, log = self.fixture()
        for bad in [log.replace('visibleHomeIcon=true', 'visibleHomeIcon=false'), log.replace('childHeartbeat=3', 'childHeartbeat=2'), log.replace('unloadEvents=3', 'unloadEvents=2')]:
            with self.assertRaises(ValueError): verify(summary, bad, ROOT)

class StagingContractTests(unittest.TestCase):
    def test_alternate_os_requires_corrected_exact_thirteen_file_lock(self):
        import json
        import tempfile
        from harness import fixture_contract, sha, CORRECTED_FIXTURE_LOCK_SHA256
        fixture = ROOT/'experiments/transition-stress/fixture'
        lock_path = ROOT/'experiments/transition-stress/fixture.lock.json'
        lock = fixture_contract(fixture, lock_path, '18.5')
        self.assertEqual(len(lock['files']), 13)
        self.assertEqual(sha(lock_path.read_bytes()), CORRECTED_FIXTURE_LOCK_SHA256)
        self.assertEqual(lock['files']['main.swf'], '9e6f0768d08018c2ae324dbc61d33eb1d62378f8c7de7b30bc054e1a74a63878')
        with tempfile.TemporaryDirectory() as temporary:
            changed_lock = Path(temporary)/'lock.json'
            changed_lock.write_text(json.dumps(lock, separators=(',', ':')))
            # Existing18.2 generic lock contract remains unchanged; alternate
            # lane additionally requires the exact reviewed corrected lock bytes.
            fixture_contract(fixture, changed_lock)
            with self.assertRaises(ValueError): fixture_contract(fixture, changed_lock, '18.5')

    def test_alternate_workflow_is_separate_and_retains_timeout_and_outcome_gates(self):
        import yaml
        from harness import sha
        old_path = ROOT/'.github/workflows/compare-transition-stress.yml'
        self.assertEqual(sha(old_path.read_bytes()), '723fe6ebb1ef4e14f1370d53182f8a81cc223151b93fa3ac74fbbb27be7d417e')
        old = yaml.safe_load(old_path.read_text())['jobs']['transitions']
        new = yaml.safe_load((ROOT/'.github/workflows/compare-transition-stress-ios18_5.yml').read_text())['jobs']['transitions']
        self.assertEqual(new['runs-on'], 'macos-15')
        self.assertEqual(new['env']['DEVELOPER_DIR'], '/Applications/Xcode_16.4.app/Contents/Developer')
        self.assertEqual(new['env']['TRANSITION_EXPECTED_OS'], '18.5')
        self.assertEqual(new['timeout-minutes'], old['timeout-minutes'])
        self.assertEqual(new['timeout-minutes'], 40)
        old_steps = {step['id']: step for step in old['steps'] if 'id' in step}
        new_steps = {step['id']: step for step in new['steps'] if 'id' in step}
        for arm in ('baseline', 'guarded'):
            self.assertEqual(new_steps[arm]['timeout-minutes'], old_steps[arm]['timeout-minutes'])
            self.assertEqual(new_steps[arm]['timeout-minutes'], 15)
            self.assertTrue(new_steps[arm]['continue-on-error'])
        self.assertIn('--os 18.5', new_steps['prepare']['run'])
        self.assertIn('select_simulator.py 18.5', new_steps['prepare']['run'])
        gate = next(step for step in new['steps'] if step.get('env', {}).get('BASELINE'))
        self.assertIn('steps.baseline.outcome', gate['env']['BASELINE'])
        self.assertIn('steps.guarded.outcome', gate['env']['GUARDED'])
        self.assertIn('test "$BASELINE" = success', gate['run'])
        self.assertIn('test "$GUARDED" = success', gate['run'])
        runner = (ROOT/'experiments/transition-stress/run_arm.sh').read_text()
        self.assertIn('${TRANSITION_EXPECTED_OS:-18.2}', runner)
        self.assertIn('--os "$expected_os"', runner)
        self.assertIn('-maximum-test-execution-time-allowance 480', runner)

    def test_actual_local_worktrees_have_only_pinned_session_delta(self):
        import tempfile
        import subprocess
        import json
        from unittest.mock import patch
        import harness
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); driver = root / 'driver'; driver.mkdir()
            def write(name, text):
                path = driver / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_text(text)
            def git(*args):
                return subprocess.check_output(['git', '-C', str(driver), *args], stderr=subprocess.DEVNULL).decode().strip()
            git('init'); git('config', 'user.email', 'synthetic@example.invalid'); git('config', 'user.name', 'Original Fixture')
            write('App/Player/PlayerSession.swift', 'original control\n')
            write('Tests/PlayerCallbackIdentityTests.swift', 'callback-only test placeholder\n')
            write('UITests/Existing.swift', 'unchanged test\n')
            write('UITestSupport/FixtureSource/App.swift', 'try CrossAppFixtureSeed.prepare()\n')
            write('fixtures/existing.txt', 'original fixture\n')
            write('project.yml', 'targets:\n  FlashNestFixtureSource:\n    sources: []\n')
            for name in ['runtime.lock.json', 'runtime.files.json', 'Package.resolved']: write(name, '{}\n')
            write('experiments/transition-stress/fixture/main.swf', 'inert synthetic bytes, not executed\n')
            write('experiments/transition-stress/fixture.lock.json', json.dumps({'variant':'unload','files':{'main.swf':harness.sha((driver/'experiments/transition-stress/fixture/main.swf').read_bytes())}}))
            write('experiments/transition-stress/TransitionStressUITests.swift', 'original UI placeholder\n')
            write('experiments/transition-stress/TransitionFixtureSeed.swift', 'original seed placeholder\n')
            git('add', '.'); git('commit', '-m', 'original control'); baseline = git('rev-parse', 'HEAD')
            control_hash = harness.sha((driver/harness.SESSION).read_bytes())
            write(harness.SESSION, 'original guarded\n'); git('add', '.'); git('commit', '-m', 'guard'); guarded=git('rev-parse', 'HEAD')
            guard_hash = harness.sha((driver/harness.SESSION).read_bytes())
            with patch.object(harness, 'BASE', baseline), patch.object(harness, 'GUARD', guarded), patch.object(harness, 'HASHES', {'baseline':control_hash,'guarded':guard_hash}):
                harness.prepare(driver, root/'trees', root/'evidence')
            a=json.loads((root/'evidence/baseline-source-sha256.json').read_text()); b=json.loads((root/'evidence/guarded-source-sha256.json').read_text())
            self.assertEqual([name for name in a if a[name]!=b[name]], [harness.SESSION])
            for arm in ['baseline','guarded']:
                tree=root/'trees'/arm
                self.assertFalse((tree/'Tests/PlayerCallbackIdentityTests.swift').exists())
                self.assertTrue((tree/'UITests/TransitionStressUITests.swift').exists())
                self.assertEqual((tree/'UITestSupport/FixtureSource/App.swift').read_text().count('try TransitionFixtureSeed.prepare()'),1)
            write('experiments/transition-stress/fixture/main.swf', 'tampered\n')
            with self.assertRaises(ValueError): harness.prepare(driver, root/'rejected', root/'rejected-evidence')

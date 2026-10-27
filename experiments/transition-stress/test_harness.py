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

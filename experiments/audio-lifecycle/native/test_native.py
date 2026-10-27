#!/usr/bin/env python3
"""Pure native-adapter/source checks; not Swift compilation or WebKit execution."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import shutil
import tempfile
import zipfile
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]

def module(name, file):
    spec = importlib.util.spec_from_file_location(name, file)
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value); return value

stage = module('native_stage_contracts', HERE / 'stage_native.py')
xctest = module('native_result_contracts', HERE / 'verify_xctest.py')

class NativeSourceTests(unittest.TestCase):
    def test_generated_project_paths_are_self_contained_and_checked(self):
        paths = module('project_path_checks', HERE / 'verify_project_paths.py')
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary) / 'repo'; output = repo / 'audio-native-stage'
            output.mkdir(parents=True); (output / 'Web').mkdir()
            for name in ['NativeAudioIdentity.swift', 'Info.plist', 'Web/native-manifest.json']:
                (output / name).write_text('synthetic')
            for name in ['Host/NativeAudioHost.swift', 'UITests/NativeAudioLifecycleUITests.swift']:
                target = repo / 'experiments/audio-lifecycle/native' / name
                target.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(HERE / name, target)
            for name in ['LoopbackServer.swift', 'HTTPProtocol.swift']:
                target = repo / 'App/Server' / name
                target.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(ROOT / 'App/Server' / name, target)
            record = stage.stage_project(output, repo)
            self.assertFalse(record['relocatedProject'])
            config = [{'target': 'NativeAudioLifecycle', 'buildSettings': {
                'PROJECT_DIR': str(output), 'SRCROOT': str(output), 'INFOPLIST_FILE': 'Info.plist'}}]
            self.assertTrue(paths.verify(output, repo, config)['verified'])
            legacy = copy.deepcopy(config); legacy[0]['buildSettings']['INFOPLIST_FILE'] = '../../../audio-native-stage/Info.plist'
            with self.assertRaises(ValueError): paths.verify(output, repo, legacy)
            foreign = copy.deepcopy(config); foreign[0]['buildSettings']['PROJECT_DIR'] = str(repo.parent)
            with self.assertRaises(ValueError): paths.verify(output, repo, foreign)
            (output / 'Web/native-manifest.json').unlink()
            with self.assertRaises(ValueError): paths.verify(output, repo, config)
            with self.assertRaises(ValueError): stage.stage_project(output, repo)
        workflow = (HERE / 'workflow-draft.yml').read_text()
        self.assertIn('(cd audio-native-stage && ', workflow)
        self.assertIn('generate --spec project.yml)', workflow)
        self.assertNotIn('--project audio-native-stage', workflow)
        self.assertIn('verify_project_paths.py', workflow)
        self.assertIn('NativeAudioLifecycle.xcodeproj/project.pbxproj', workflow)

    def test_native_policy_trusted_events_and_bounded_teardown(self):
        host = (HERE / 'Host/NativeAudioHost.swift').read_text()
        ui = (HERE / 'UITests/NativeAudioLifecycleUITests.swift').read_text()
        driver = (HERE / 'Web/native-runner.mjs').read_text()
        self.assertIn('mediaTypesRequiringUserActionForPlayback = [.audio, .video]', host)
        self.assertIn('button.tap()', ui)
        self.assertEqual(ui.count('button.tap()'), 1)
        self.assertIn("action.trusted,true", driver)
        for text in ('.click()', 'api.resume(', 'api.suspend(', 'new AudioContext', 'setTimeout(resume'):
            self.assertNotIn(text, driver)
        self.assertEqual(host.count('evaluateJavaScript('), 1)
        self.assertIn('3_000_000_000', host)
        self.assertIn('try await server.stopAndWait()', host)
        self.assertIn('guard !completed else { return }; completed = true', host)
        self.assertLess(host.index('try verifyBundle(web)'), host.index('WKWebView(frame:'))
        self.assertIn('observed == Set(files.keys)', host)
        self.assertIn('requestAbortAndDrain', ui)
        self.assertIn('lastTappedAction', ui)
        self.assertIn('addingTimeInterval(600)', ui)
        self.assertIn('executionTimeAllowance = 660', ui)
        self.assertIn('host.deadlineMS', driver)
        self.assertNotIn('App/Player', (HERE / 'project.yml').read_text())
        self.assertIn('../../../App/Server/LoopbackServer.swift', (HERE / 'project.yml').read_text())

    def test_locked_browser_helpers_untouched_and_fresh_action_same(self):
        lock = json.loads((ROOT / 'experiments/audio-lifecycle/browser-reuse/build-lock.json').read_text())
        for name in ('observer.mjs', 'page.mjs', 'contracts.mjs', 'console-observer.mjs'):
            relative = 'experiments/audio-lifecycle/browser-tests/' + name
            self.assertEqual(hashlib.sha256((ROOT / relative).read_bytes()).hexdigest(), lock['correctedHarnessSHA256'][relative])
        original = (ROOT / 'experiments/audio-lifecycle/browser-tests/runner-guards.mjs').read_text()
        native = (HERE / 'Web/fresh-action.mjs').read_text()
        body = re.search(r'export function freshAction\([^\n]+', original).group()
        self.assertIn(body, native)

    def test_native_contract_adapter_runs_all_shared_negatives(self):
        browser = ROOT / 'experiments/audio-lifecycle/browser-tests'
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            contract, record = stage.transform((browser / 'contracts.mjs').read_bytes(), stage.CONTRACT_TRANSFORMS, 'contracts.mjs', 'contracts.mjs')
            self.assertIn('expectedDPR', contract.decode())
            self.assertIn("row.renderer,'canvas'", contract.decode())
            (dest / 'contracts.mjs').write_bytes(contract)
            for name in ('assert.mjs', 'fresh-action.mjs'):
                (dest / name).write_bytes((HERE / 'Web' / name).read_bytes())
            test = (browser / 'test_contracts.mjs').read_text()
            test = test.replace("renderer:'wgpu-webgl'", "renderer:'canvas'")
            test = test.replace("kind:'webgl2',lost:false,dpr:1,drawingBufferWidth:320,drawingBufferHeight:240", "kind:'2d',dpr:3,backingWidth:960,backingHeight:720")
            test = test.replace('cycle:0,actions:', 'cycle:0,expectedDPR:3,actions:')
            test += "\n{const{e,config}=fixture();e.rows[0].context.dpr=2;assert.throws(()=>verifyCycle(e,config));e.rows[0].context.dpr=3;e.rows[0].renderer='wgpu-webgl';assert.throws(()=>verifyCycle(e,config));}\n"
            (dest / 'test.mjs').write_text(test)
            subprocess.run(['node', str(dest / 'test.mjs')], check=True)

    def test_native_wait_is_bounded_and_fail_fast_even_for_falsy_throws(self):
        source = (HERE / 'Web/native-runner.mjs').read_text()
        function = source[source.index('async function waitFor('):source.index('\nfunction healthy()')]
        program = """
const assert=require('node:assert/strict');
const host={deadlineMS:1000};let now=0;const Date={now:()=>now++};
const setTimeout=fn=>fn();
FUNCTION
(async()=>{
for(const value of [null,undefined,false,0,'',new Error('fatal')]){
 let calls=0,threw=false;try{await waitFor(()=>{calls++;throw value},'mock')}catch(error){threw=true;assert.equal(error,value)}assert(threw);assert.equal(calls,1);
}
let calls=0;await waitFor(()=>++calls===3,'mock');assert.equal(calls,3);
now=1001;await assert.rejects(waitFor(()=>true,'expired'));
console.log('PASS native bounded/fail-fast polling mocks; no browser');
})().catch(e=>{console.error(e);process.exitCode=1});
""".replace('FUNCTION', function)
        subprocess.run(['node', '-'], input=program, text=True, check=True)

    def test_archive_hash_before_extraction_and_unsafe_paths(self):
        import prepare_browser_archive
        import test_stage_native as fixtures
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); metadata = root / 'metadata'; metadata.mkdir()
            archive = root / 'browser.zip'
            with zipfile.ZipFile(archive, 'w') as z: z.writestr('audio-browser-reuse-evidence/test.txt', 'synthetic only')
            approval = fixtures.approval()
            approval.update(buildLockSHA256=stage.sha(stage.REUSE / 'build-lock.json'),
                            artifactSHA256=stage.sha(archive), artifactBytes=archive.stat().st_size)
            run, artifact, jobs = fixtures.metadata(approval)
            for name, value in [('run', run), ('artifact', artifact), ('jobs', jobs)]:
                fixtures.write(metadata / (name + '.json'), value)
            approval_file = root / 'approval.json'; fixtures.write(approval_file, approval)
            prepare_browser_archive.prepare(archive, metadata, approval_file, root / 'valid')
            archive.write_bytes(archive.read_bytes() + b'tampered')
            with self.assertRaises(ValueError): prepare_browser_archive.prepare(archive, metadata, approval_file, root / 'refused')
            self.assertFalse((root / 'refused').exists())
            with zipfile.ZipFile(archive, 'w') as z: z.writestr('../outside', 'bad')
            approval.update(artifactSHA256=stage.sha(archive), artifactBytes=archive.stat().st_size)
            run, artifact, jobs = fixtures.metadata(approval)
            for name, value in [('run', run), ('artifact', artifact), ('jobs', jobs)]: fixtures.write(metadata / (name + '.json'), value)
            fixtures.write(approval_file, approval)
            with self.assertRaises(ValueError): prepare_browser_archive.prepare(archive, metadata, approval_file, root / 'unsafe')
            self.assertFalse((root / 'outside').exists())

    def test_exact_native_summary_and_negative_selections(self):
        summary = {'result': 'Passed', 'totalTestCount': 1, 'passedTests': 1,
                   'failedTests': 0, 'skippedTests': 0, 'expectedFailures': 0, 'testFailures': [],
                   'devicesAndConfigurations': [{'device': {'osVersion': '18.5', 'platform': 'iOS Simulator'},
                    'passedTests': 1, 'failedTests': 0, 'skippedTests': 0, 'expectedFailures': 0}]}
        log = f"Test Case '-[{xctest.CASE}]' started.\nTest Case '-[{xctest.CASE}]' passed (1.0 seconds).\n"
        xctest.verify(summary, log)
        for key, value in [('totalTestCount', 0), ('passedTests', 0), ('failedTests', 1), ('skippedTests', 1), ('expectedFailures', 1), ('result', 'Failed')]:
            changed = {**summary, key: value}
            with self.subTest(key=key), self.assertRaises(ValueError): xctest.verify(changed, log)
        changed = copy.deepcopy(summary); changed['devicesAndConfigurations'][0]['device']['osVersion'] = '18.2'
        with self.assertRaises(ValueError): xctest.verify(changed, log)
        for wrong in ('', log + log, log.replace(xctest.CASE, 'AnotherSuite anotherTest')):
            with self.assertRaises(ValueError): xctest.verify(summary, wrong)

if __name__ == '__main__': unittest.main(verbosity=2)

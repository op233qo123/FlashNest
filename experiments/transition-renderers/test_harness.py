import copy
import importlib.util
import json
from pathlib import Path
import unittest
from harness import instrument, verify, FIELDS
ROOT=Path(__file__).resolve().parents[2]

class RendererGateTests(unittest.TestCase):
    def fixture(self, backend='wgpu-webgl'):
        counts=dict(passedTests=1,failedTests=0,skippedTests=0,expectedFailures=0)
        summary=dict(result='Passed',totalTestCount=1,testFailures=[],**counts)
        summary['devicesAndConfigurations']=[dict(device=dict(osVersion='18.5',platform='iOS Simulator'),**counts)]
        method='FlashNestUITests.TransitionStressUITests testThreeSceneLoadsWithRotationAndBackgroundPreserveLiveState'
        rows=[('initial-input',0)]
        for g in range(1,4):
            rows += [(p,g) for p in ['scene-ready','after-landscape','after-background','after-portrait']]
            if g==2: rows.append(('after-paused-background',2))
        log=f"Test Case '-[{method}]' started.\n"
        for i,(phase,g) in enumerate(rows):
            log+=f'FLASHNEST_TRANSITION_STATE phase={phase} boot=original generation={g} heartbeat={i+1} pointers={g} keys={i+1} ready=1 childGeneration={g} childHeartbeat={i+1} errors=0 unloadCalls={g} unloadEvents={g}\n'
        for g,p in [(1,'running-child'),(2,'running-child'),(2,'paused-menu'),(3,'running-child')]: log+=f'FLASHNEST_TRANSITION_HOME cycle={g} phase={p} visibleHomeIcon=true reportedAppState=4\n'
        for p in ['startup']+[p for p,_ in rows]:
            d=dict(backend=backend,context='webgl2',lost=False,width=640,height=480,nativeDPR=3,lossEvents=0,bannerCount=1)
            log+='FLASHNEST_RENDERER_STATE phase='+p+' '+json.dumps(d,separators=(',',':'))+'\n'
        log+=f"FLASHNEST_TRANSITION_COMPLETE cycles=3 keys=14 pointers=3 unloadCalls=3 unloadEvents=3 errors=0\nTest Case '-[{method}]' passed (10.000 seconds).\n"
        return summary,log
    def test_exact_observed_backend(self):
        for arm,backend in [('default','wgpu-webgl'),('webgl','webgl')]:
            self.assertEqual(verify(*self.fixture(backend),ROOT,arm)['rendererObservations'],15)
    def test_actual_webgl1_alias_is_not_mistaken_for_unknown(self):
        s,l=self.fixture('webgl'); verify(s,l.replace('"context":"webgl2"','"context":"experimental-webgl"'),ROOT,'webgl')
    def test_fallback_or_unknown_backend_rejected(self):
        for backend in ['webgl','canvas','unknown']:
            with self.assertRaises(ValueError): verify(*self.fixture(backend),ROOT,'default')
    def test_context_lost_missing_zero_or_multiple_instance_rejected(self):
        s,l=self.fixture()
        for a,b in [('"lost":false','"lost":true'),('"context":"webgl2"','"context":"unknown"'),('"width":640','"width":0'),('"height":480','"height":null'),('"lossEvents":0','"lossEvents":1'),('"bannerCount":1','"bannerCount":2'),('"nativeDPR":3','"nativeDPR":true')]:
            with self.assertRaises(ValueError): verify(s,l.replace(a,b),ROOT,'default')
    def test_duplicate_renderer_json_field_rejected(self):
        s,l=self.fixture()
        with self.assertRaises(ValueError): verify(s,l.replace('"lost":false','"lost":true,"lost":false'),ROOT,'default')
    def test_missing_duplicate_renderer_sample_rejected(self):
        s,l=self.fixture(); row=next(x for x in l.splitlines() if x.startswith('FLASHNEST_RENDERER_STATE'))
        for bad in [l.replace(row+'\n',''), l+row+'\n']:
            with self.assertRaises(ValueError): verify(s,bad,ROOT,'default')
    def test_xctest_state_and_raw_os_gate_remain(self):
        s,l=self.fixture()
        for bad in [l.replace('visibleHomeIcon=true','visibleHomeIcon=false'),l.replace('unloadEvents=3','unloadEvents=2')]:
            with self.assertRaises(ValueError): verify(s,bad,ROOT,'default')
        for key,value in [('skippedTests',1),('result','Failed')]:
            changed=copy.deepcopy(s);changed[key]=value
            with self.assertRaises(ValueError): verify(changed,l,ROOT,'default')
        s['devicesAndConfigurations'][0]['device']['osVersion']='18.2'
        with self.assertRaises(ValueError): verify(s,l,ROOT,'default')
    def test_overlay_only_one_arm_preference(self):
        shell="function reportTrace(message) { return message; }\nfunction watchRenderer() { }\nmovieLoaded = true; const config={logLevel:'warn'};"
        a=instrument(shell,'// common observer','default');b=instrument(shell,'// common observer','webgl')
        self.assertEqual(b,a.replace("logLevel:'info'","logLevel:'info', preferredRenderer:'webgl'",1))
        self.assertEqual(a.count('window.FlashNestRendererDiagnostic.sample(player);'),3)
    def test_overlay_drift_density_and_duplicate_anchor_reject(self):
        shell="function reportTrace(message) { }\nfunction watchRenderer() { }\nmovieLoaded = true; const config={logLevel:'warn'};"
        for bad in [shell.replace("logLevel:'warn'","logLevel:'info'"),shell+"preferredRenderer",shell+"FlashNestRendering",shell+"function watchRenderer() { }"]:
            with self.assertRaises(ValueError): instrument(bad,'//observer','default')

class StagingTests(unittest.TestCase):
    def test_actual_worktrees_share_guard_and_only_preference_diff(self):
        import tempfile, subprocess, shutil
        from unittest.mock import patch
        import harness
        base=harness.load_base(ROOT)
        with tempfile.TemporaryDirectory() as temporary:
            parent=Path(temporary);driver=parent/'driver';driver.mkdir()
            def write(name,text):
                p=driver/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text)
            def git(*args): return subprocess.check_output(['git','-C',str(driver),*args],stderr=subprocess.DEVNULL).decode().strip()
            git('init');git('config','user.email','synthetic@example.invalid');git('config','user.name','Original Fixture')
            write(base.SESSION,'original control\n')
            write('Tests/PlayerCallbackIdentityTests.swift','test placeholder\n')
            write('UITests/Existing.swift','unchanged\n')
            write('UITestSupport/FixtureSource/App.swift','try CrossAppFixtureSeed.prepare()\n')
            write('fixtures/existing.txt','original\n')
            write('project.yml','targets:\n  FlashNestFixtureSource:\n    sources: []\n')
            for name in ['runtime.lock.json','runtime.files.json','Package.resolved']:write(name,'{}\n')
            write(harness.SHELL,"function reportTrace(message) { }\nfunction watchRenderer() { }\nmovieLoaded = true; const config={logLevel:'warn'};\n")
            (driver/'experiments/transition-stress').mkdir(parents=True)
            shutil.copytree(ROOT/'experiments/transition-stress/fixture',driver/'experiments/transition-stress/fixture')
            shutil.copyfile(ROOT/'experiments/transition-stress/fixture.lock.json',driver/'experiments/transition-stress/fixture.lock.json')
            write('experiments/transition-stress/TransitionStressUITests.swift','original UI\n')
            write('experiments/transition-stress/TransitionFixtureSeed.swift','original seed\n')
            write('experiments/transition-renderers/renderer-observer.js','// same passive observer\n')
            write('experiments/transition-renderers/TransitionStressUITests.swift','same backend UI\n')
            git('add','.');git('commit','-m','control');control=git('rev-parse','HEAD');ch=base.sha((driver/base.SESSION).read_bytes())
            write(base.SESSION,'original guard\n');git('add','.');git('commit','-m','guard');guard=git('rev-parse','HEAD');gh=base.sha((driver/base.SESSION).read_bytes())
            with patch.object(base,'BASE',control),patch.object(base,'GUARD',guard),patch.object(base,'HASHES',{'baseline':ch,'guarded':gh}),patch.object(harness,'load_base',return_value=base):
                harness.prepare(driver,parent/'trees',parent/'evidence')
            a=json.loads((parent/'evidence/default-source-sha256.json').read_text());b=json.loads((parent/'evidence/webgl-source-sha256.json').read_text())
            self.assertEqual([k for k in a if a[k]!=b[k]],[harness.SHELL])
            self.assertEqual(a[base.SESSION],gh);self.assertEqual(b[base.SESSION],gh)
            for arm in ['default','webgl']:
                subprocess.run(['git','-C',str(parent/'trees'/arm),'status','--porcelain'],check=True,stdout=subprocess.DEVNULL)
                self.assertEqual((parent/'trees'/arm/'UITests/TransitionStressUITests.swift').read_text(),'same backend UI\n')
    def test_workflow_bounds_and_raw_outcome_gate(self):
        import yaml
        job=yaml.safe_load((ROOT/'.github/workflows/compare-transition-renderers-ios18_5.yml').read_text())['jobs']['transitions']
        self.assertEqual(job['runs-on'],'macos-15');self.assertEqual(job['timeout-minutes'],40)
        steps={x['id']:x for x in job['steps'] if 'id' in x}
        for arm in ['default','webgl']:
            self.assertEqual(steps[arm]['timeout-minutes'],15);self.assertTrue(steps[arm]['continue-on-error'])
        gate=next(x for x in job['steps'] if 'DEFAULT' in x.get('env',{}))
        self.assertIn('steps.default.outcome',gate['env']['DEFAULT']);self.assertIn('steps.webgl.outcome',gate['env']['WEBGL'])
        self.assertIn('test "$DEFAULT" = success',gate['run']);self.assertIn('test "$WEBGL" = success',gate['run'])
        self.assertIn('-maximum-test-execution-time-allowance 480',(ROOT/'experiments/transition-renderers/run_arm.sh').read_text())

if __name__=='__main__':unittest.main()

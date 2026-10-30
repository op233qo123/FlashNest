import importlib.util,os,re,tempfile,unittest
from pathlib import Path
s=importlib.util.spec_from_file_location('overlay',Path(__file__).with_name('ruffle_test_cleanup.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
APP=Path(os.environ.get('PHASE_APP',str(Path(__file__).resolve().parent.parent/'native-release-ipa-156-build22/local-stage/app')))
class Tests(unittest.TestCase):
    def fixture(self,root):
        app=root/'app';(app/'Tests').mkdir(parents=True);(app/m.TARGET).write_bytes((APP/m.TARGET).read_bytes());return app,root/'state.json'
    def test_exact_inverse(self):
        with tempfile.TemporaryDirectory() as temp:
            app,state=self.fixture(Path(temp));before=(app/m.TARGET).read_bytes();mapping={m.TARGET:m.sha(before)}
            m.apply(app,state,mapping);self.assertNotEqual((app/m.TARGET).read_bytes(),before)
            m.restore(app,state);self.assertEqual((app/m.TARGET).read_bytes(),before);self.assertFalse(state.exists())
    def test_original_assertion_lines_and_timeout_preserved(self):
        before=(APP/m.TARGET).read_text();after=m.transform(before)
        for line in before.splitlines():
            if 'XCTAssert' in line or 'XCTFail(' in line or 'executionTimeAllowance' in line:self.assertIn(line,after)
        self.assertEqual(after.count('executionTimeAllowance = 120'),1)
        self.assertNotIn('session.stop()',after)
        self.assertIn('let cleanupError = await cleanup.finish(root: root)',after)
        self.assertIn('if let primaryError { throw primaryError }\n        if let cleanupError { throw cleanupError }',after)
        self.assertLess(after.index('try await session?.closeWithoutSaving()'),after.index('window?.rootViewController = nil'))
        self.assertLess(after.index('window?.rootViewController = nil'),after.index('try FileManager.default.removeItem'))
        self.assertIn('if drained && FileManager.default.fileExists',after)
    def test_reject_changed_overlay(self):
        with tempfile.TemporaryDirectory() as temp:
            app,state=self.fixture(Path(temp));m.apply(app,state,{m.TARGET:m.sha((app/m.TARGET).read_bytes())})
            (app/m.TARGET).write_text('changed')
            with self.assertRaises(AssertionError):m.restore(app,state)
            self.assertTrue(state.exists())
    def test_reject_wrong_baseline_without_write(self):
        with tempfile.TemporaryDirectory() as temp:
            app,state=self.fixture(Path(temp));before=(app/m.TARGET).read_bytes()
            with self.assertRaises(AssertionError):m.apply(app,state,{m.TARGET:'0'*64})
            self.assertEqual(before,(app/m.TARGET).read_bytes());self.assertFalse(state.exists())
    def test_missing_target_map_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            app,state=self.fixture(Path(temp))
            with self.assertRaises(AssertionError):m.apply(app,state,{})
            self.assertFalse(state.exists())
if __name__=='__main__':unittest.main()

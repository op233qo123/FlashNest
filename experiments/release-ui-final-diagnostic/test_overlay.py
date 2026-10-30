import importlib.util,os,re,tempfile,unittest
from pathlib import Path
s=importlib.util.spec_from_file_location('overlay',Path(__file__).with_name('overlay.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
APP=Path(os.environ.get('PHASE_APP',str(Path(__file__).resolve().parent.parent/'native-release-ipa-156-build22/local-stage/app')))
class Tests(unittest.TestCase):
    def fixture(self,root):
        app=root/'app';(app/'UITests').mkdir(parents=True);(app/m.TARGET).write_bytes((APP/m.TARGET).read_bytes());return app,root/'state.json'
    def test_original_lines_and_fail_location_map_exact(self):
        before=(APP/m.TARGET).read_text();after=m.transform(before);lines=after.splitlines()
        mapping={int(k):int(v) for k,v in re.findall(r'(\d+): (\d+)',next(x for x in lines if 'diagnosticOriginalLines:' in x))}
        self.assertEqual(len(mapping),len(before.splitlines())-1)
        for actual,original in mapping.items():self.assertEqual(lines[actual-1],before.splitlines()[original-1])
        for i,line in enumerate(before.splitlines(),1):
            if 'XCTAssert' in line or 'waitForExistence(timeout:' in line:self.assertIn(i,mapping.values())
        markers=re.findall(r'diagnosticMark\("([A-Za-z]+)"\)',after)
        self.assertEqual(tuple(markers),m.STEPS)
        helper=after[after.index('    override func record'):]
        self.assertIn('["import", "backgroundRunning", "backgroundPaused"]',helper)
        self.assertNotIn('debugDescription',helper);self.assertNotIn('issue.compactDescription',helper)
        self.assertLess(helper.index('super.record(issue)\n            // Fixed'),helper.index('let app = XCUIApplication()'))
    def test_inverse(self):
        with tempfile.TemporaryDirectory() as temp:
            app,state=self.fixture(Path(temp));raw=(app/m.TARGET).read_bytes();m.apply(app,state,{m.TARGET:m.sha(raw)});m.restore(app,state)
            self.assertEqual(raw,(app/m.TARGET).read_bytes());self.assertFalse(state.exists())
    def test_changed_overlay_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            app,state=self.fixture(Path(temp));m.apply(app,state,{m.TARGET:m.sha((app/m.TARGET).read_bytes())});(app/m.TARGET).write_text('changed')
            with self.assertRaises(AssertionError):m.restore(app,state)
    def test_wrong_source_rejected_before_write(self):
        with tempfile.TemporaryDirectory() as temp:
            app,state=self.fixture(Path(temp));raw=(app/m.TARGET).read_bytes()
            with self.assertRaises(AssertionError):m.apply(app,state,{m.TARGET:'0'*64})
            self.assertEqual(raw,(app/m.TARGET).read_bytes());self.assertFalse(state.exists())
if __name__=='__main__':unittest.main()

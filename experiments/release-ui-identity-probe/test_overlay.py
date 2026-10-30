import importlib.util, tempfile, unittest, os
from pathlib import Path
spec=importlib.util.spec_from_file_location('overlay',Path(__file__).with_name('overlay.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
SOURCE=Path(os.environ.get('PHASE_APP',str(Path(__file__).resolve().parent.parent/'native-release-ipa-156-build22/local-stage/app')))
class Tests(unittest.TestCase):
    def fixture(self,root):
        app=root/'app';app.mkdir()
        for p in m.PATHS:
            target=app/p;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((SOURCE/p).read_bytes())
        return app,root/'state.json'
    def test_inverse_exact_and_opt_in(self):
        with tempfile.TemporaryDirectory() as temp:
            app,state=self.fixture(Path(temp)); before=m.inventory(app)
            m.apply(app,state)
            ui=(app/m.PATHS[2]).read_text()
            self.assertIn('play.waitForExistence(timeout: 60)',ui)
            self.assertIn('XCTAssertTrue(appeared)',ui)
            self.assertIn('--flashnest-identity-probe',ui)
            self.assertNotIn('.id(', (app/m.PATHS[0]).read_text())
            self.assertIn('weak var represented', (app/m.NEW).read_text())
            m.restore(app,state);self.assertEqual(before,m.inventory(app));self.assertFalse(state.exists())
    def test_changed_overlay_is_rejected_before_inverse(self):
        with tempfile.TemporaryDirectory() as temp:
            app,state=self.fixture(Path(temp));m.apply(app,state)
            (app/m.NEW).write_text('changed')
            with self.assertRaises(AssertionError):m.restore(app,state)
            self.assertTrue(state.exists());self.assertTrue((app/m.NEW).exists())
    def test_wrong_source_is_rejected_before_write(self):
        with tempfile.TemporaryDirectory() as temp:
            app,state=self.fixture(Path(temp));(app/m.PATHS[0]).write_text('wrong')
            before=m.inventory(app)
            with self.assertRaises(AssertionError):m.apply(app,state)
            self.assertEqual(before,m.inventory(app));self.assertFalse(state.exists())
    def test_selected_inventory_inverse_with_generated_project(self):
        with tempfile.TemporaryDirectory() as temp:
            app,state=self.fixture(Path(temp));before=m.inventory(app)
            project=app/'FlashNest.xcodeproj';project.mkdir();(project/'project.pbxproj').write_text('generated baseline')
            m.apply(app,state,source_map=before);(project/'project.pbxproj').write_text('generated diagnostic')
            m.restore(app,state)
            self.assertEqual({p:m.inventory(app)[p] for p in before},before)
            self.assertFalse((app/m.NEW).exists())
    def test_bounded_evidence_never_exports_state_or_container(self):
        import collect_evidence,json
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'ui.log').write_bytes(b'x'*(3*1024*1024));(root/'overlay-state.json').write_text('source backup');(root/'unrelated.sol').write_text('not evidence')
            collect_evidence.collect(root);out=root/'evidence';manifest=json.loads((out/'inventory.json').read_text())
            self.assertFalse((out/'overlay-state.json').exists());self.assertFalse((out/'unrelated.sol').exists());self.assertLessEqual(manifest['retainedPayloadBytes'],collect_evidence.TOTAL);self.assertLessEqual((out/'ui.log').stat().st_size,2*1024*1024)
    def test_diagnostic_workflow_has_no_release_path(self):
        text=Path(__file__).with_name('workflow.yml').read_text()
        for forbidden in ('-configuration Release','package_unsigned.sh','package.py verify','release-provenance.json'):
            self.assertNotIn(forbidden,text)
        self.assertIn('if: always()',text);self.assertIn('collect_evidence.py',text)
    def test_only_ui_execution_never_claims_unit_pass(self):
        text=Path(__file__).with_name('run_probe.py').read_text()
        self.assertNotIn("unit=lane(",text)
        self.assertEqual(text.count("ui=lane('ui'"),1)
        self.assertIn("'unitNotRun':True",text)
        self.assertIn("'priorSelectedUnitStatus':'failed'",text)
        self.assertIn("'selectedReleaseGatePassed':False",text)
if __name__=='__main__':unittest.main()

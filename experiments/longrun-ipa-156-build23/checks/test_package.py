#!/usr/bin/env python3
"""Recipe validation negative controls; never stages, dispatches, or publishes."""
import copy,importlib.util,json,shutil,tempfile,unittest,sys
from pathlib import Path
SOURCE=Path(__file__).resolve().parents[1]
class RecipeControls(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)/'recipe';shutil.copytree(SOURCE,self.root)
  self.x=json.loads((self.root/'inputs.json').read_text());self.x['dispatchAllowed']=True
  spec=importlib.util.spec_from_file_location('test_recipe',self.root/'package.py');self.module=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.module)
 def tearDown(self):self.tmp.cleanup()
 def save(self):(self.root/'inputs.json').write_text(json.dumps(self.x))
 def rejected(self):
  self.save()
  with self.assertRaises(ValueError):self.module.config()
 def test_reviewed_input(self):self.save();self.assertEqual(self.module.config()['build'],'23')
 def test_pending_permission_rejected(self):self.x['dispatchAllowed']=False;self.rejected()
 def test_version_and_baseline_changes_rejected(self):
  self.x['build']='22';self.rejected()
  self.x['build']='23';self.x['baselineSourceCommit']='0'*40;self.rejected()
 def test_default_on_and_acceptance_claim_rejected(self):
  for k in ('diagnosticOptInDefault','automaticUpload','cacheEvictionEnabled','engineProductChanges','originalCrashResolved','fullGatePassed','physicalDeviceCertified'):
   old=copy.deepcopy(self.x);self.x[k]=True;self.rejected();self.x=old
 def test_import_gate_omission_rejected(self):
  self.x['testClasses'].remove('ImportSizeWarningTests');self.rejected()
 def test_ui_gate_omission_rejected(self):
  self.x['expectedUITests']=[];self.rejected()
 def test_revision_mismatch_rejected(self):
  self.x['packageRevision']='old-longrun';self.rejected()
 def test_observer_revision_mismatch_rejected(self):
  self.x['observerRevision']=1;self.rejected()
 def test_schema_mismatch_rejected(self):
  self.x['diagnosticSchema']=True;self.rejected()
 def test_recipe_omission_rejected(self):self.x['recipeFiles'].pop('README.md');self.rejected()
 def test_recipe_tamper_rejected(self):
  f=self.root/'README.md';f.write_text(f.read_text()+'\nchanged');self.rejected()
 def test_overlay_tamper_rejected(self):
  f=self.root/'overlay/App/Player/LongRunDiagnostics.swift';f.write_text(f.read_text()+'\nchanged');self.rejected()
 def test_runtime_overlay_rejected(self):
  import hashlib
  rel='App/Resources/Web/runtime/injected.js';f=self.root/'overlay'/rel;f.parent.mkdir(parents=True,exist_ok=True);f.write_text('bad')
  self.x['overlay'][rel]={'before':None,'after':hashlib.sha256(b'bad').hexdigest()};self.rejected()
 def test_extra_overlay_rejected(self):
  (self.root/'overlay/App/extra.txt').write_text('unexpected');self.rejected()
 def test_linked_overlay_rejected(self):
  f=self.root/'overlay/App/Player/LongRunDiagnostics.swift';raw=f.read_bytes();f.unlink();target=self.root/'saved.swift';target.write_bytes(raw);f.symlink_to(target);self.rejected()
class SwiftInventoryControls(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  sys.path.insert(0,str(SOURCE))
  spec=importlib.util.spec_from_file_location('runner_under_test',SOURCE/'run_focused_tests.py');cls.runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.runner)
 def test_two_classes_same_file(self):
  code='final class OneTests: XCTestCase { func testA() {} } @MainActor final class TwoTests: XCTestCase { func testB() {} }'
  self.assertEqual(self.runner.swift_test_classes(code),{'OneTests':['testA'],'TwoTests':['testB']})
 def test_nested_helper_not_xctest(self):
  code='class OneTests: XCTestCase { func testA() { func testNested() {} }; struct Helper { func testFake() {} }; func testB() {} }'
  self.assertEqual(self.runner.swift_test_classes(code),{'OneTests':['testA','testB']})
 def test_comments_and_strings_do_not_add_methods(self):
  code='class OneTests: XCTestCase { /* nested /* func testFake() {} */ comment */ func testReal() { let x = "} func testString() {}" } // func testComment() {}\n }'
  self.assertEqual(self.runner.swift_test_classes(code),{'OneTests':['testReal']})
 def test_raw_multiline_string(self):
  code='class OneTests: XCTestCase { let text = #""" } func testFake() {} """#; func testReal() {} }'
  self.assertEqual(self.runner.swift_test_classes(code),{'OneTests':['testReal']})
 def test_duplicate_or_unclosed_rejected(self):
  for code in ['class OneTests: XCTestCase { func testA() {} func testA() {} }','class OneTests: XCTestCase {','/* unfinished']:
   with self.assertRaises(ValueError):self.runner.swift_test_classes(code)
 def test_mapping_is_explicit(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);(root/'Tests').mkdir();(root/'Tests/Shared.swift').write_text('class OneTests: XCTestCase { func testA() {} } class TwoTests: XCTestCase { func testB() {} }')
   x={'testClasses':['TwoTests','OneTests'],'testSourceFiles':{'OneTests':'Tests/Shared.swift','TwoTests':'Tests/Shared.swift'}}
   self.assertEqual(self.runner.expected_test_methods(root,x),[('TwoTests','testB'),('OneTests','testA')])
   x['testSourceFiles']['OneTests']='../escape.swift'
   with self.assertRaises(ValueError):self.runner.expected_test_methods(root,x)
if __name__=='__main__':unittest.main()

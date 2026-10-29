#!/usr/bin/env python3
"""Local mocked/source contracts, not native execution."""
import importlib.util,json,tempfile,unittest,shutil
from pathlib import Path
import os
spec=importlib.util.spec_from_file_location('runner',Path(__file__).with_name('run.py'));r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
APP=Path(os.environ.get('FLASHNEST_REVIEWED_TEMPLATE', str(r.WORK / 'next-ipa-156-prep/app-integration/source')))
class Contracts(unittest.TestCase):
 def test_pinned_xcodegen_archive_hash_matches_approved_route(self):
  expected='a760b4bf97460341316a2c00d8c87b2946c6c2729eb57e9a72abb3ef7bc0ef82'
  self.assertEqual(len(expected),64)
  self.assertEqual(json.loads((Path(r.__file__).parent/'binding-template.json').read_text())['xcodegenArchiveSHA256'],expected)
  self.assertIn(expected,Path(r.__file__).read_text())
  self.assertIn(expected,Path(os.environ.get('FLASHNEST_REVIEWED_WORKFLOW',str(r.WORK/'zip-native-validation/payload/.github/workflows/validate-zip-selection-ios18.yml'))).read_text())

 def test_exact_selection_counts_and_no_picker_save_overlap(self):
  lanes=r.selections(APP)
  self.assertEqual({k:v['expectedCount'] for k,v in lanes.items()},{'sampling-gate-off':18,'sampling-gate-on':18,'picker-models':31,'picker-ui':1,'sampling-baseline':4,'sampling-candidate':7,'save-models':48,'save-webkit':19,'save-ui':1,'audio-candidate':2,'audio-baseline':1})
  base=set(lanes['sampling-baseline']['selectors']);self.assertTrue(base < set(lanes['sampling-candidate']['selectors']))
  allsets=[set(lanes[k]['selectors']) for k in ('sampling-gate-off','picker-models','save-models','save-webkit')]
  for i,a in enumerate(allsets):
   for b in allsets[i+1:]:self.assertFalse(a&b)
  method=lanes['picker-ui']['selectors'][0].split('/')[-1];self.assertIn('func '+method+'(', (r.ZIP/'overlay/ZIPSelectionUITests.swift').read_text())
 def test_gate_on_changes_exact_two_lines_and_rejects_repeat(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t)
   for rel in ('App/Player/RenderSamplingSettings.swift','Tests/RenderSamplingSettingsTests.swift'):
    (root/rel).parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(APP/rel,root/rel)
   before={p:r.sha(root/p) for p in ('App/Player/RenderSamplingSettings.swift','Tests/RenderSamplingSettingsTests.swift')}
   report=r.gate_on_overlay(root);self.assertEqual(set(report),set(before))
   for rel in before:self.assertEqual(report[rel]['before'],before[rel]);self.assertNotEqual(report[rel]['before'],report[rel]['after'])
   self.assertIn('XCTAssertTrue(RenderSamplingSettings.runtimeValidated', (root/'Tests/RenderSamplingSettingsTests.swift').read_text())
   with self.assertRaises(ValueError):r.gate_on_overlay(root)
 def test_symlink_input_rejected(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);(p/'file').write_text('x');(p/'link').symlink_to(p/'file')
   with self.assertRaises(ValueError):r.inventory(p)
 def test_duplicate_or_missing_class_fails(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);(p/'x.swift').write_text('final class Sample: XCTestCase {\nfunc testX() {}\nfunc testX() {}\n}')
   with self.assertRaises(ValueError):r.methods(p,['Sample'])
   with self.assertRaises(ValueError):r.methods(p,['Missing'])
 def test_same_line_actor_class_boundaries(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);(p/'x.swift').write_text('final class A: XCTestCase {\nfunc testA() {}\n}\n@MainActor final class B: XCTestCase {\nfunc testB() {}\n}')
   self.assertEqual(r.methods(p,['A']),['FlashNestTests/A/testA'])
 def test_source_has_separate_baselines_and_prelaunch_identity_freeze(self):
  text=Path(r.__file__).read_text()
  self.assertIn("self.args.baseline/'sampling/runtime'",text);self.assertIn("self.args.baseline/'historical'",text)
  self.assertLess(text.index("dump(self.out/'sampling-expected-identities.json'"),text.index('for dpr,device in self.devices.items()'))
  self.assertLess(text.index("geometry['matrixPassed']"),text.index("main=self.copy_app('main-gate-on')"))
 def test_default_receipt_not_inferred_from_explicit_webgl(self):
  text=Path(r.__file__).read_text()
  self.assertIn("'shippingDefaultAppliesAllTiers':'automatic' in geometry['actualShippingReductionPolicies']",text)
  self.assertIn("'shippingPoliciesWithAllReductions':geometry['actualShippingReductionPolicies']",text)
 def test_expected_method_count_total(self):
  l=r.selections(APP);total=sum(l[k]['expectedCount'] for k in ('sampling-gate-off','sampling-gate-on','picker-models','picker-ui','save-models','save-webkit','save-ui','audio-candidate','audio-baseline'))+2*(4+7)
  self.assertEqual(total,161)
if __name__=='__main__':unittest.main(verbosity=2)

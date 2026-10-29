"""Exact source inverse/selection controls only; not native execution."""
import importlib.util,json,shutil,tempfile,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('runner',Path(__file__).with_name('run.py'));r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
ROOT=Path(__file__).resolve().parents[4];APP=ROOT/'renderer-policy-repair/full-v3-app';OLD=ROOT/'renderer-policy-repair/accepted-before-app'
class PolicyRunner(unittest.TestCase):
    def test_all_nine_inverse_restores_entire_old_tree(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'app';shutil.copytree(APP,p);proof=r.restore_legacy_source(p)
            self.assertEqual(len(proof['files']),9);self.assertTrue(proof['exactLegacySourceRestored'])
            self.assertEqual(r.inventory(p),r.inventory(OLD))
            with self.assertRaises(ValueError):r.restore_legacy_source(p)
    def test_drift_rejected_before_any_partial_inverse(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'app';shutil.copytree(APP,p);(p/'scripts/test_shell.js').write_text('drift')
            before=r.inventory(p)
            with self.assertRaises(ValueError):r.restore_legacy_source(p)
            self.assertEqual(r.inventory(p),before)
    def test_exact_count_and_roles(self):
        lanes=r.selections(APP)
        total=sum(v['expectedCount']*(2 if k in ('sampling-baseline','sampling-candidate','sampling-enhanced-boundary') else 1) for k,v in lanes.items())
        self.assertEqual(total,198);self.assertEqual(total-2*lanes['sampling-enhanced-boundary']['expectedCount'],196)
        self.assertTrue(all('Automatic' not in s for s in lanes['sampling-baseline']['selectors']))
        self.assertEqual(lanes['sampling-candidate']['expectedCount'],23)
        self.assertEqual(lanes['renderer-models']['expectedCount'],6);self.assertEqual(lanes['renderer-ui']['expectedCount'],1)
if __name__=='__main__':unittest.main(verbosity=2)

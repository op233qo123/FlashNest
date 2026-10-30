#!/usr/bin/env python3
"""Focused retry transport/safety controls; not browser execution."""
import json,unittest
from pathlib import Path
from unittest.mock import patch
import stage_reused_candidate as stage
ROOT=Path(__file__).resolve().parents[1]
class FocusedReuseTests(unittest.TestCase):
 def test_original_build_identity_and_pins(self):
  e=json.loads((ROOT/'candidate-reuse.json').read_text())['engine']
  self.assertEqual(e['runID'],40998892881);self.assertEqual(e['artifactID'],12953027984)
  self.assertEqual(e['sourceCommit'],'6d3e4322293972a28ab2cdf129ee6398f40f0f37')
  self.assertEqual(e['sha256'],'2cb4022b1859156f2e28dcb5d499ebf01cbf13b386acb8467d34c147ed22d28d');self.assertEqual(e['bytes'],13344196)
 def test_focused_workflow_does_not_build_or_change_sandbox(self):
  s=(ROOT/'focused-workflow.yml').read_text();run=(ROOT/'browser/run.py').read_text()
  self.assertNotIn('build_engine.sh',s);self.assertNotIn('cargo ',s);self.assertNotIn('playwright install',s)
  self.assertNotIn('--no-sandbox',s+run);self.assertNotIn('sysctl',s)
  self.assertIn("channel='chrome'",run);self.assertIn('chromium_sandbox=True',run);self.assertNotIn('--use-angle=swiftshader',run)
  self.assertIn('browser_preflight.py',s);self.assertIn('--reuse-candidate',s)
 def test_reused_receipt_matches_old_not_new_run(self):
  s=(ROOT/'scripts/prepare_browser_contract.py').read_text();self.assertIn("str(reuse['runID'])",s);self.assertIn("reuse['sourceCommit']",s);self.assertIn("reuse['provenanceSHA256']",s)
 def test_stage_requires_fresh_destination_before_fetch(self):
  import tempfile
  with tempfile.TemporaryDirectory() as t,patch.object(stage,'check'),patch.object(stage,'fetch',side_effect=AssertionError('must not fetch existing output')),self.assertRaises(ValueError):stage.main(Path(t))
if __name__=='__main__':unittest.main()

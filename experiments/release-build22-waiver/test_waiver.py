import copy,json,os,unittest
from pathlib import Path
from unittest.mock import patch
import waiver as w
class WaiverTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  directory=os.environ.get('WAIVER_EVIDENCE_DIR')
  cls.first=(Path(directory)/'prior-selected.zip' if directory else w.BASE/'actual-41018490270/tests.zip').read_bytes()
  cls.last=(Path(directory)/'last-ui.zip' if directory else w.ROOT.parent/'native-release-ui-final-diagnostic/actual-41021548758/evidence.zip').read_bytes()
 def test_actual_history_keeps_failure(self):
  x=w.config();r=w.validate_history(self.first,self.last,x,w.old.inputs());self.assertEqual(r['prior15App'],'passed');self.assertEqual(r['UIstatus'],'failed');self.assertFalse(r['selectedReleaseGatePassed'])
 def test_archive_modification_rejected(self):
  with self.assertRaises(ValueError):w.archive(self.first+b'x',w.config()['history']['priorSelected'])
 def test_no_gate_or_new_test_promotion(self):
  original=w.config()
  for key,value in [('selectedReleaseGatePassed',True),('testsRunThisPackagingJob',16),('acceptedByUser',False),('build','23')]:
   changed=copy.deepcopy(original);changed[key]=value
   with patch.object(w.c,'load',return_value=changed),self.assertRaises(ValueError):w.config()
 def test_disabled_dispatch_rejected(self):
  changed=copy.deepcopy(w.config());changed['dispatchAllowed']=False
  with patch.object(w.c,'load',return_value=changed),self.assertRaises(ValueError):w.config(True)
 def test_false_historical_pass_or_source_change_rejected(self):
  x=w.config();a=w.archive(self.first,x['history']['priorSelected']);b=w.archive(self.last,x['history']['lastUI'])
  for change in ('ui','source','lastUI'):
   first=copy.deepcopy(a);last=copy.deepcopy(b)
   if change=='ui':first['ui-result.json']['passed']=first['ui-result.json']['selected']
   if change=='source':first['test-source-receipt.json']['restoredOriginal207']=False
   if change=='lastUI':last['safe-ui-observation.json']['failures'][0]['line']=122
   with patch.object(w,'archive',side_effect=[first,last]),self.assertRaises(ValueError):w.validate_history(self.first,self.last,x,w.old.inputs())
 def test_workflow_build_only_and_verifier_not_old_gate_patch(self):
  flow=(w.ROOT/'workflow.yml').read_text();source=(w.ROOT/'waiver.py').read_text()
  for bad in ('run_selected_tests.py','run_ui.py','xcodebuild test','test_cleanup.py','--selected-evidence'):
   self.assertNotIn(bad,flow)
  self.assertNotIn('old.selected_gate',source);self.assertNotIn('old.verify(',source)
  for preserved in ('c.verify_sources','c.verify_outer_payload','c.device_macho','module.verify_web','Full bundled Web differs','Generated main Info.plist differs','Test probe in shipping Web'):
   self.assertIn(preserved,source)
if __name__=='__main__':unittest.main()

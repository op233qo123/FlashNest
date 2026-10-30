#!/usr/bin/env python3
import copy,hashlib,json,shutil,tempfile,unittest
from pathlib import Path
from check_contract import ROOT,check
class ContractTests(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup);self.root=Path(self.t.name)
  for rel in ('patches','reviews'):shutil.copytree(ROOT/rel,self.root/rel)
  for rel in ('source-lock.json','base-source-lock.json'):shutil.copyfile(ROOT/rel,self.root/rel)
  self.lock=json.loads((self.root/'source-lock.json').read_text())
 def write(self):(self.root/'source-lock.json').write_text(json.dumps(self.lock))
 def test_exact_source_scope(self):self.assertEqual(len(check(self.root)['modifiedSourceFiles']),58)
 def test_disabled_gate_blocks(self):
  self.lock['workflowDispatchAllowed']=False;self.write()
  with self.assertRaises(ValueError):check(self.root,'engine')
 def test_additional_product_or_hook_reject(self):
  for path in ('core/src/player.rs','core/src/lazy_count_backend.rs'):
   old=copy.deepcopy(self.lock);self.lock['modifiedSourceFiles'][path]={'sha256':'0'*64,'bytes':1};self.write()
   with self.subTest(path=path),self.assertRaises(ValueError):check(self.root)
   self.lock=old
 def test_toolchain_or_base_lock_drift_reject(self):
  self.lock['toolchain']['rust']='other';self.write()
  with self.assertRaises(ValueError):check(self.root)
 def test_source_review_is_not_production_acceptance(self):
  rel=self.lock['productionGcReview']['path'];f=self.root/rel;review=json.loads(f.read_text());review['candidateDiagnosticBuildReviewed']=True;review['productionAccepted']=False
  self.lock['workflowDispatchAllowed']=True;self.lock['engineBuildEligible']=True
  def save():
   f.write_text(json.dumps(review));self.lock['productionGcReview']['sha256']=hashlib.sha256(f.read_bytes()).hexdigest();self.write()
  save();check(self.root,'engine')
  review['productionAccepted']=True;save()
  with self.assertRaises(ValueError):check(self.root,'engine')
 def test_acceptance_overclaim_reject(self):
  self.lock['nativeAcceptance']=True;self.write()
  with self.assertRaises(ValueError):check(self.root)
class PipelineTests(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup);self.root=Path(self.t.name)/'recipe';shutil.copytree(ROOT,self.root)
  self.lock=json.loads((self.root/'pipeline-lock.json').read_text());self.lock['dispatchAllowed']=True;(self.root/'pipeline-lock.json').write_text(json.dumps(self.lock))
 def test_complete_source_closure(self):
  from check_pipeline import check as verify
  verify(self.root)
 def test_extra_script_rejected(self):
  from check_pipeline import check as verify
  (self.root/'scripts/extra.py').write_text('no')
  with self.assertRaises(ValueError):verify(self.root)
 def test_changed_script_rejected(self):
  from check_pipeline import check as verify
  (self.root/'scripts/build_engine.sh').write_text('no')
  with self.assertRaises(ValueError):verify(self.root)
if __name__=='__main__':unittest.main()

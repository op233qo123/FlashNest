#!/usr/bin/env python3
"""Recipe validation negative controls; never stages, dispatches, or publishes."""
import copy,importlib.util,json,shutil,tempfile,unittest
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
if __name__=='__main__':unittest.main()

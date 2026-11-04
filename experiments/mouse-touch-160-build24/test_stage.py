#!/usr/bin/env python3
"""Negative/closure tests for new overlay verifier; no mocked native pass claims."""
import importlib.util, pathlib, tempfile, unittest
spec=importlib.util.spec_from_file_location('mouse_stage',pathlib.Path(__file__).with_name('stage.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Tests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.temp.name)
  for p in ['App/A.swift','Tests/A.swift','UITests/A.swift']:
   f=self.root/p;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(p)
  self.expected=m.inventory(self.root)
 def tearDown(self):self.temp.cleanup()
 def test_exact(self):m.verify(self.root,self.expected)
 def test_changed_source(self):
  (self.root/'App/A.swift').write_text('changed')
  with self.assertRaises(ValueError):m.verify(self.root,self.expected)
 def test_extra_app_source(self):
  (self.root/'App/B.swift').write_text('extra')
  with self.assertRaises(ValueError):m.verify(self.root,self.expected)
 def test_extra_test_source(self):
  (self.root/'Tests/B.swift').write_text('extra')
  with self.assertRaises(ValueError):m.verify(self.root,self.expected)
 def test_symlink(self):
  p=self.root/'App/A.swift';p.unlink();p.symlink_to(self.root/'Tests/A.swift')
  with self.assertRaises(ValueError):m.verify(self.root,self.expected)
 def test_unreviewed_generated_info(self):
  (self.root/'App/Info.plist').write_text('not expected')
  with self.assertRaises(ValueError):m.verify(self.root,self.expected)

class RecoveryIdentityTests(unittest.TestCase):
 """Synthetic receipt negatives, not evidence that historical/native tests ran."""
 def setUp(self):
  from unittest.mock import patch
  self.temp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.temp.name)
  self.recipe=self.root/'recipe';self.app=self.root/'app';self.out=self.root/'out';self.base=self.root/'baseline'
  self.removed={'vendor/ruffle-audio-recovery-40614335019.zip':'3befcb048669c074a017e2bfb6d3ccc283028ef90d7960695bbf0964a2634e9a'}
  self.effective={};self.runtime={}
  for i in range(229):
   name=('App/Resources/Web/runtime/'+str(i)+'.bin') if i<12 else ('App/Source'+str(i)+'.swift')
   f=self.app/name;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(name)
   self.effective[name]=m.sha(f.read_bytes())
   if i<12:self.runtime[str(i)+'.bin']=self.effective[name]
  self.manifest={'effectiveSourceFiles':dict(self.effective),'originalEffectiveSourceFiles':{**self.effective,**self.removed},'removedFiles':dict(self.removed),'materials':{name:{'kind':'fixture','sha256':digest} for name,digest in self.effective.items()}}
  self.config={'overlay':{'App/Source12.swift':{'after':self.effective['App/Source12.swift']}},'recipeFiles':{'stage.py':'fixture'}}
  for k in ['additionalNativeTests','additionalTestSourceFiles','additionalUITests','additionalUITestSourceFiles']:self.config[k]=[]
  self.r={**self.manifest,'kind':'EXPLICIT-RECOVERED-SOURCE-BASELINE','legacyStageExecuted':False,'materialSources':self.manifest['materials'],'head':'current-head','runID':'current-run','runtimeFiles':dict(self.runtime)}
  self.s={**self.r,**self.config,'kind':'EXPERIMENTAL-MOUSE-TOUCH-160-26-RECOVERED'}
  self.reuse={'consumerHead':'current-head','consumerRunID':'current-run','engineBuildExecutedThisRun':False,'runtimeFiles':dict(self.runtime)}
  self.cadence={'head':'current-head','runID':'current-run','runtimeFiles':dict(self.runtime)}
  m.write(self.base/m.RECIPE/'inputs.json',{'fixture':True})
  self.patches=[patch.object(m,'ROOT',self.recipe),patch.object(m,'config',return_value=self.config),patch.object(m,'git_head',return_value=m.BASE),patch.dict(m.os.environ,{'GITHUB_SHA':'current-head','GITHUB_RUN_ID':'current-run'})]
  for p in self.patches:p.start()
 def tearDown(self):
  for p in reversed(self.patches):p.stop()
  self.temp.cleanup()
 def flush(self):
  m.write(self.recipe/'recovery-manifest.json',self.manifest)
  self.recipe.mkdir(parents=True,exist_ok=True)
  script=pathlib.Path(__file__).with_name('recovery_stage.py').read_bytes()
  (self.recipe/'recovery_stage.py').write_bytes(script)
  self.r.setdefault('recoveryScriptSHA256',m.sha(script))
  self.r['recoveryManifestSHA256']=m.sha((self.recipe/'recovery-manifest.json').read_bytes())
  for name,key,data in [('engine-reuse.json','engineReuseSHA256',self.reuse),('cadence-inputs.json','cadenceInputsSHA256',self.cadence)]:
   m.write(self.out/name,data);self.r[key]=self.s[key]=m.sha((self.out/name).read_bytes())
  m.write(self.out/'recovery-staging.json',self.r)
  self.s['recoveryReceiptSHA256']=m.sha((self.out/'recovery-staging.json').read_bytes())
  m.write(self.out/'mouse-staging.json',self.s)
 def validate(self):return m.validate_stage(self.app,self.out/'mouse-staging.json',self.base)
 def reject(self,message):
  self.flush()
  with self.assertRaisesRegex(ValueError,message):self.validate()
 def test_fixture_uses_actual_producer_manifest_key(self):
  import ast
  producer=pathlib.Path(__file__).with_name('recovery_stage.py')
  tree=ast.parse(producer.read_text())
  receipts=[n.value for n in ast.walk(tree) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='receipt' for t in n.targets) and isinstance(n.value,ast.Dict)]
  self.assertEqual(len(receipts),1)
  keys={k.value for k in receipts[0].keys if isinstance(k,ast.Constant)}
  self.assertIn('recoveryManifestSHA256',keys)
  self.assertNotIn('manifestSHA256',keys)
 def test_recovery_cannot_claim_legacy_execution(self):
  self.r['legacyStageExecuted']=True;self.reject('Recovery cannot claim legacy staging')
 def test_recovery_kind_cannot_claim_other_baseline(self):
  self.r['kind']='LEGACY-PASS';self.reject('Recovery cannot claim legacy staging')
 def test_recovery_script_identity_cannot_change(self):
  self.r['recoveryScriptSHA256']='0'*64;self.reject('Recovery producer changed')
 def test_recovery_material_sources_cannot_change(self):
  self.r['materialSources']={};self.reject('Recovery material sources differ')
 def test_exact_explicit_229_identity(self):
  self.flush();_,effective,_=self.validate();self.assertEqual(len(effective),229)
 def test_other_removal_forbidden_even_with_rehashed_receipts(self):
  self.manifest['removedFiles']={'App/Source12.swift':self.effective['App/Source12.swift']};self.reject('Unexpected recovery removal')
 def test_removed_zip_hash_cannot_change(self):
  self.manifest['removedFiles'][next(iter(self.removed))]='0'*64;self.reject('Unexpected recovery removal')
 def test_original_zip_hash_cannot_change(self):
  self.manifest['originalEffectiveSourceFiles'][next(iter(self.removed))]='0'*64;self.reject('differs beyond')
 def test_unrelated_source_hash_cannot_change(self):
  self.manifest['effectiveSourceFiles']['App/Source12.swift']='0'*64;self.reject('differs beyond')
 def test_unrelated_source_cannot_be_omitted(self):
  del self.manifest['effectiveSourceFiles']['App/Source12.swift'];self.reject('differs beyond')
 def test_same_count_source_substitution_rejected(self):
  value=self.manifest['effectiveSourceFiles'].pop('App/Source12.swift');self.manifest['effectiveSourceFiles']['App/Substitute.swift']=value;self.reject('differs beyond')
 def test_recovery_source_declaration_must_match(self):
  self.r['effectiveSourceFiles']={};self.reject('Recovery source declaration mismatch')
 def test_mouse_source_declaration_must_match(self):
  self.s['effectiveSourceFiles']={};self.reject('Mouse recovery identity mismatch')
 def test_each_receipt_must_name_current_head_and_run(self):
  for receipt in [self.s,self.r]:
   for field in ['head','runID']:
    with self.subTest(receipt='mouse' if receipt is self.s else 'recovery',field=field):
     old=receipt[field];receipt[field]='stale';self.reject('Wrong recovery current run');receipt[field]=old
 def test_reuse_and_cadence_cannot_claim_stale_identity(self):
  for receipt,fields,message in [(self.reuse,['consumerHead','consumerRunID'],'Engine reuse current-run identity'),(self.cadence,['head','runID'],'Cadence/runtime identity')]:
   for field in fields:
    with self.subTest(field=field):
     old=receipt[field];receipt[field]='stale';self.reject(message);receipt[field]=old
 def test_engine_reuse_cannot_claim_new_build(self):
  self.reuse['engineBuildExecutedThisRun']=True;self.reject('Engine reuse current-run identity')
 def test_cadence_runtime_cannot_differ(self):
  self.cadence['runtimeFiles']={};self.reject('Cadence/runtime identity')
 def test_unhashed_receipt_tampering_rejected(self):
  self.flush();self.r['runID']='tampered';m.write(self.out/'recovery-staging.json',self.r)
  with self.assertRaisesRegex(ValueError,'Recovery receipt changed'):self.validate()
 def test_runtime_bytes_cannot_change(self):
  (self.app/'App/Resources/Web/runtime/0.bin').write_text('different');self.reject('Exact engine closure differs')
 def test_unrelated_source_bytes_cannot_change(self):
  (self.app/'App/Source12.swift').write_text('different');self.reject('Source changed')
 def test_unrelated_source_bytes_cannot_disappear(self):
  (self.app/'App/Source12.swift').unlink();self.reject('Source changed')
 def test_removed_archive_cannot_reappear(self):
  f=self.app/next(iter(self.removed));f.parent.mkdir(parents=True);f.write_bytes(b'expired');self.reject('Removed historical archive unexpectedly present')
 def test_native_inventory_cannot_be_replaced(self):
  self.s['additionalNativeTests']=['fake-pass'];self.reject('Test inventory differs')

if __name__=='__main__':unittest.main()

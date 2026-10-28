import json,pathlib,tempfile,unittest,shutil,hashlib,subprocess
from unittest.mock import patch
import stage
HERE=pathlib.Path(__file__).parent
ARCHIVE=pathlib.Path('/workspace/scratch/bbe5ec6ec106/audio-native-recovery/records/run40614335019/artifact.zip')
class StageTests(unittest.TestCase):
 def test_pinned_real_payload_inventory(self):
  a=json.loads((HERE/'overlay.json').read_text());self.assertEqual(a['baseRef'],stage.SOURCE);self.assertEqual(a['promotionManifestSHA256'],stage.PROMOTION);self.assertEqual(len(a['files']),18)
  for x in a['files']:
   if x['path'].endswith('.zip'):
    self.assertEqual(x['bytes'],22076102);self.assertEqual(x['sha256'],'3befcb048669c074a017e2bfb6d3ccc283028ef90d7960695bbf0964a2634e9a')
   else:
    p=HERE/'payload'/x['path'];self.assertEqual(p.stat().st_size,x['bytes']);self.assertEqual(stage.sha(p),x['sha256'])
 def test_unknown_arm_and_existing_output_rejected(self):
  with tempfile.TemporaryDirectory() as tmp:
   with self.assertRaises(ValueError):stage.stage(tmp,tmp,'candidate',ARCHIVE)
   with self.assertRaises(ValueError):stage.stage(tmp,str(pathlib.Path(tmp)/'new'),'wrong',ARCHIVE)
 def test_real_git_archive_baseline_and_candidate_are_separate(self):
  with tempfile.TemporaryDirectory() as tmp:
   t=pathlib.Path(tmp);repo=t/'repo';repo.mkdir();here=t/'input';here.mkdir();arc=t/'a.zip';arc.write_bytes(b'zip')
   paths=['App/Resources/Web/runtime-identity.json']+[f'file-{i}' for i in range(16)]+['vendor/a.zip']
   files=[]
   for name in paths:
    dest=repo/name;new=b'new';old=b'old';before=None if name.endswith('.zip') else hashlib.sha256(old).hexdigest()
    if before:dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(old)
    payload=here/'payload'/name;payload.parent.mkdir(parents=True,exist_ok=True);payload.write_bytes(new)
    content=b'zip' if name.endswith('.zip') else new
    files.append({'path':name,'bytes':len(content),'sha256':hashlib.sha256(content).hexdigest(),'originalSHA256':before})
   subprocess.run(['git','init','-q',str(repo)],check=True)
   subprocess.run(['git','-C',str(repo),'add','.'],check=True)
   subprocess.run(['git','-C',str(repo),'-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-qm','Original fixture'],check=True)
   commit=subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip()
   (here/'overlay.json').write_text(json.dumps({'schema':1,'baseRef':commit,'promotionManifestSHA256':stage.PROMOTION,'files':files}))
   with patch.object(stage,'SOURCE',commit), patch.object(stage,'OVERLAY_SHA256',stage.sha(here/'overlay.json')):
    for arm in ['baseline','candidate']:
     out=stage.stage(repo,t/arm,arm,arc,here);self.assertEqual((out/paths[0]).read_bytes(),b'old' if arm=='baseline' else b'new')
    (here/'payload'/paths[0]).write_bytes(b'tampered')
    with self.assertRaises(ValueError):stage.stage(repo,t/'bad','candidate',arc,here)
   self.assertEqual((repo/paths[0]).read_bytes(),b'old')

 def test_rewritten_manifest_rejected(self):
  with tempfile.TemporaryDirectory() as tmp:
   here=pathlib.Path(tmp);a=json.loads((HERE/'overlay.json').read_text());a['files'][0]['path']='other';(here/'overlay.json').write_text(json.dumps(a))
   with self.assertRaisesRegex(ValueError,'Unreviewed'):stage.validated_inputs(here,ARCHIVE)
 def test_archive_symlink_rejected_before_resolve(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=pathlib.Path(tmp);(p/'real').write_bytes(b'zip');(p/'link').symlink_to(p/'real')
   with self.assertRaisesRegex(ValueError,'Symlink archive'):stage.stage(p,p/'out','candidate',p/'link')
 def test_payload_ancestor_symlink_rejected(self):
  with tempfile.TemporaryDirectory() as tmp:
   here=pathlib.Path(tmp);shutil.copyfile(HERE/'overlay.json',here/'overlay.json');(here/'payload').mkdir()
   (here/'payload/Tests').symlink_to(HERE/'payload/Tests',target_is_directory=True)
   with self.assertRaisesRegex(ValueError,'Symlink payload'):stage.validated_inputs(here,ARCHIVE)
 def test_invalid_size_fields_rejected(self):
  with tempfile.TemporaryDirectory() as tmp:
   here=pathlib.Path(tmp);a=json.loads((HERE/'overlay.json').read_text())
   for size in [-1,True,129*1024*1024,'23379']:
    a['files'][0]['bytes']=size;(here/'overlay.json').write_text(json.dumps(a))
    with patch.object(stage,'OVERLAY_SHA256',stage.sha(here/'overlay.json')):
     with self.assertRaisesRegex(ValueError,'Invalid file fields'):stage.validated_inputs(here,ARCHIVE)

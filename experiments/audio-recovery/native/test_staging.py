import hashlib,json,subprocess,tempfile,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
import stage_host,apply_injection,apply_startup,verify_download
class StagingTests(unittest.TestCase):
 def test_actual_local_archive_staging_preserves_shipping(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);repo=root/'repo';repo.mkdir();runtime=root/'runtime';runtime.mkdir();(runtime/'ruffle.js').write_text('// reviewed synthetic runtime')
   original=apply_injection.ANCHOR.encode();p=repo/apply_injection.SESSION;p.parent.mkdir(parents=True);p.write_bytes(original)
   for name,data in [('App/Resources/Web/runtime/ruffle.js','old'),('fixtures/lifecycle/main.swf','original synthetic placeholder'),('Package.resolved','{}')]:
    p=repo/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(data)
   shell=''.join(apply_startup.ANCHORS).encode();(repo/'App/Resources/Web/shell.js').write_bytes(shell)
   def git(*args):return subprocess.check_output(['git','-C',str(repo),*args],stderr=subprocess.DEVNULL).decode().strip()
   git('init');git('add','.');git('-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-m','synthetic test')
   commit=git('rev-parse','HEAD');here=Path(stage_host.__file__).parent
   inventory={str(p.relative_to(here)):stage_host.digest(p) for p in here.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name!='approval.json'}
   a={'sourceCommit':commit,'diagnosticFiles':inventory,'runtimes':{'candidate':{'files':{'ruffle.js':stage_host.digest(runtime/'ruffle.js')}}}}
   approval=root/'approval.json';approval.write_text(json.dumps(a))
   with patch.object(stage_host,'SOURCE',commit),patch.object(apply_injection,'EXPECTED',hashlib.sha256(original).hexdigest()),patch.object(apply_startup,'EXPECTED',hashlib.sha256(shell).hexdigest()):
    stage_host.prepare(repo,root/'output','candidate',runtime,approval)
   self.assertEqual(git('status','--porcelain'),'');self.assertEqual((repo/apply_injection.SESSION).read_bytes(),original)
   self.assertTrue((root/'output/source-manifest.json').exists())
   self.assertTrue((root/'output/startup-shell.diff').exists())
   self.assertEqual((repo/'App/Resources/Web/shell.js').read_bytes(),shell)
   self.assertIn('shell-load-call',(root/'output/staged/App/Resources/Web/shell.js').read_text())
 def test_download_metadata_digest_and_traversal(self):
  with tempfile.TemporaryDirectory() as t:
   r=Path(t);a={'repository':'op233qo123/FlashNest','runID':1,'artifactID':2,'buildCommit':'abc'}
   (r/'run.json').write_text(json.dumps({'id':1,'head_sha':'abc','conclusion':'success','status':'completed'}))
   (r/'artifact.json').write_text(json.dumps({'id':2,'workflow_run':{'id':1},'expired':False}))
   with zipfile.ZipFile(r/'runtime.zip','w') as z:z.writestr('../bad','no')
   b=(r/'runtime.zip').read_bytes();a.update(archiveSHA256=hashlib.sha256(b).hexdigest(),archiveBytes=len(b));p=r/'approval.json';p.write_text(json.dumps(a))
   with self.assertRaises(ValueError):verify_download.verify(r,p)
   self.assertFalse((r/'extracted').exists())
   a['archiveSHA256']='0'*64;p.write_text(json.dumps(a))
   with self.assertRaises(ValueError):verify_download.verify(r,p)
 def test_verified_archive_helper_source_and_runtime_path(self):
  with tempfile.TemporaryDirectory() as t:
   r=Path(t);helper=b'// exact source helper'
   a={'repository':'op233qo123/FlashNest','runID':1,'artifactID':2,'buildCommit':'abc',
      'audioOperationSource':{'path':'source/audio-operation.ts','sha256':hashlib.sha256(helper).hexdigest()},
      'runtimes':{'candidate':{'directory':'candidate/runtime'}}}
   (r/'run.json').write_text(json.dumps({'id':1,'head_sha':'abc','conclusion':'success','status':'completed'}))
   (r/'artifact.json').write_text(json.dumps({'id':2,'workflow_run':{'id':1},'expired':False}))
   with zipfile.ZipFile(r/'runtime.zip','w') as z:z.writestr('source/audio-operation.ts',helper)
   b=(r/'runtime.zip').read_bytes();a.update(archiveSHA256=hashlib.sha256(b).hexdigest(),archiveBytes=len(b));p=r/'approval.json';p.write_text(json.dumps(a))
   self.assertTrue((verify_download.verify(r,p)/'source/audio-operation.ts').is_file())

class StartupOverlayTests(unittest.TestCase):
 def test_fail_closed_pin_and_duplicate_anchor(self):
  with self.assertRaises(ValueError):apply_startup.transform(b'wrong production source')
  source=''.join(apply_startup.ANCHORS).encode()
  with patch.object(apply_startup,'EXPECTED',hashlib.sha256(source).hexdigest()):
   output,diff=apply_startup.transform(source)
   self.assertEqual(output.count(b'FlashNestStartupJournal'),3)
   self.assertIn('diagnostic/shell.js',diff)
  duplicate=source+next(iter(apply_startup.ANCHORS)).encode()
  with patch.object(apply_startup,'EXPECTED',hashlib.sha256(duplicate).hexdigest()):
   with self.assertRaises(ValueError):apply_startup.transform(duplicate)

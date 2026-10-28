import hashlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import profile as staging
class ProfileTests(unittest.TestCase):
 def fixture(self,root):
  original='prefix\n'+staging.ANCHOR+'suffix\n';session=root/'staged'/staging.SESSION;session.parent.mkdir(parents=True)
  session.write_text(original.replace(staging.ANCHOR,staging.ANCHOR+staging.INSERT))
  project='head\n'+staging.RESOURCE+'tail\n';(root/'project.yml').write_text(project)
  for name,data in [('startup-journal.js','// passive journal'),('startup-resources.json','{}'),('audio-recovery-injection.js','// fault injector')]: (root/'staged'/name).write_text(data)
  (root/'overlay-manifest.json').write_text(json.dumps({'shippingSessionSHA256':staging.sha(original.encode()),'overlaySessionSHA256':staging.sha(session.read_bytes()),'injectionSHA256':staging.sha(b'// fault injector'),'shippingUnchanged':True}))
  files={str(p.relative_to(root)):staging.sha(p.read_bytes()) for p in root.rglob('*') if p.is_file()}
  (root/'source-manifest.json').write_text(json.dumps({'files':files}))
  approval=root.parent/'approval.json';approval.write_text(json.dumps({'diagnosticFiles':{'project.yml':staging.sha(project.encode())}}))
  return original,approval
 def test_passive_omits_entire_injector_not_disarms(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t)/'stage';root.mkdir();original,approval=self.fixture(root)
   with patch.object(staging,'EXPECTED',staging.sha(original.encode())):source=staging.apply(root,'passive-only',approval)
   text=(root/'staged'/staging.SESSION).read_text();self.assertNotIn('injectionURL',text);self.assertNotIn('source: injection',text);self.assertNotIn('audio-recovery-injection',(root/'project.yml').read_text());self.assertFalse((root/'staged/audio-recovery-injection.js').exists())
   self.assertEqual(text.count('controller.addUserScript'),1);self.assertIn('registeredScript(source: startupSource)',text)
   self.assertEqual(source['registeredStartupScriptSHA256'],staging.sha(b'window.__FlashNestStartupResources={};' + b'// passive journal'))
   self.assertEqual(source['audioStateCoverage'],'unavailable-without-fault-injector');self.assertFalse(source['faultInjectorBundled'])
   self.assertNotIn('staged/audio-recovery-injection.js',source['files']);self.assertIsNone(json.loads((root/'overlay-manifest.json').read_text())['injectionSHA256'])
 def test_instrumented_profile_preserves_session_and_resource(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t)/'stage';root.mkdir();original,approval=self.fixture(root);before=(root/'staged'/staging.SESSION).read_bytes()
   with patch.object(staging,'EXPECTED',staging.sha(original.encode())):source=staging.apply(root,'instrumented',approval)
   self.assertEqual(before,(root/'staged'/staging.SESSION).read_bytes());self.assertTrue((root/'staged/audio-recovery-injection.js').exists());self.assertTrue(source['faultInjectorBundled'])
 def test_unknown_repeated_or_drifted_profiles_fail(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t)/'stage';root.mkdir();original,approval=self.fixture(root)
   with self.assertRaises(ValueError):staging.apply(root,'other',approval)
   with patch.object(staging,'EXPECTED',staging.sha(original.encode())):
    staging.apply(root,'instrumented',approval)
    with self.assertRaises(ValueError):staging.apply(root,'passive-only',approval)
  with tempfile.TemporaryDirectory() as t:
   root=Path(t)/'stage';root.mkdir();original,approval=self.fixture(root);(root/'staged'/staging.SESSION).write_text('drift')
   with self.assertRaises(ValueError):staging.apply(root,'passive-only',approval)
if __name__=='__main__':unittest.main()

import json,plistlib,shutil,tempfile,unittest,uuid
from pathlib import Path
from unittest.mock import patch
import installed_bundle as bundle
from run_control import BUNDLE
class InstalledBundleTests(unittest.TestCase):
 def app(self,root):
  root.mkdir(parents=True);(root/'Info.plist').write_bytes(plistlib.dumps({'CFBundleIdentifier':BUNDLE,'CFBundleExecutable':'Host'}));(root/'Host').write_bytes(b'original executable');(root/'Web/runtime').mkdir(parents=True);(root/'Web/runtime/core.wasm').write_bytes(b'original wasm');return root
 def test_exact_full_bundle_and_changed_code_resource_identity(self):
  with tempfile.TemporaryDirectory() as t:
   t=Path(t);built=self.app(t/'built.app');installed=t/'installed.app';shutil.copytree(built,installed)
   self.assertTrue(bundle.verify(built,installed,BUNDLE,True)['verified'])
   for relative in ['Host','Web/runtime/core.wasm']:
    p=installed/relative;old=p.read_bytes();p.write_bytes(b'changed');self.assertFalse(bundle.verify(built,installed,BUNDLE,True)['verified']);p.write_bytes(old)
   (installed/'extra.txt').write_text('unexpected');self.assertFalse(bundle.verify(built,installed,BUNDLE,True)['verified'])
 def test_wrong_identity_missing_file_and_injector_fail(self):
  with tempfile.TemporaryDirectory() as t:
   t=Path(t);built=self.app(t/'built.app');installed=t/'installed.app';shutil.copytree(built,installed)
   (installed/'Info.plist').write_bytes(plistlib.dumps({'CFBundleIdentifier':'other','CFBundleExecutable':'Host'}))
   with self.assertRaises(ValueError):bundle.verify(built,installed,BUNDLE,True)
   shutil.copyfile(built/'Info.plist',installed/'Info.plist');(installed/'Host').unlink()
   with self.assertRaises(ValueError):bundle.verify(built,installed,BUNDLE,True)
   shutil.copyfile(built/'Host',installed/'Host')
   for root in [built,installed]:(root/'audio-recovery-injection.js').write_text('fault')
   with self.assertRaises(ValueError):bundle.verify(built,installed,BUNDLE,True)
 def test_paths_bind_exact_simulator_and_reject_links(self):
  with tempfile.TemporaryDirectory() as t:
   t=Path(t);data=t/'Devices/device-a/data';path=data/'Containers/Bundle/Application'/str(uuid.uuid4())/'Host.app';path.mkdir(parents=True)
   self.assertEqual(bundle.installed_path(str(path),str(data),'device-a','Host.app'),path)
   for udid,name in [('device-b','Host.app'),('device-a','Other.app')]:
    with self.assertRaises(ValueError):bundle.installed_path(str(path),str(data),udid,name)
   path.rmdir();path.symlink_to(t)
   with self.assertRaises(ValueError):bundle.installed_path(str(path),str(data),'device-a','Host.app')
 def test_bounded_regular_inventory(self):
  with tempfile.TemporaryDirectory() as t:
   app=self.app(Path(t)/'app')
   with patch.object(bundle,'MAX_FILES',1):
    with self.assertRaises(ValueError):bundle.inventory(app,BUNDLE)
   with patch.object(bundle,'MAX_BYTES',1):
    with self.assertRaises(ValueError):bundle.inventory(app,BUNDLE)
   (app/'Case').mkdir()
   with patch('installed_bundle.os.walk',return_value=[(str(app),['Case','case'],[])]):
    with self.assertRaises(ValueError):bundle.inventory(app,BUNDLE)
   (app/'Case').rmdir()
   (app/'symlink').symlink_to(app/'Host')
   with self.assertRaises(ValueError):bundle.inventory(app,BUNDLE)
if __name__=='__main__':unittest.main()

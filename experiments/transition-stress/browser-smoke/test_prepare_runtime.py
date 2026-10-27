import tempfile,unittest,zipfile,stat
from pathlib import Path
from prepare_runtime import prepare,validate_names
class Prepare(unittest.TestCase):
 def test_names(self):
  self.assertEqual(validate_names([zipfile.ZipInfo('runtime/x.js')]),{'runtime/x.js'})
  for name in ('/tmp/x','../x','runtime/../../x','runtime\\x'):
   with self.assertRaises(AssertionError):validate_names([zipfile.ZipInfo(name)])
 def test_duplicate_links_limits(self):
  a=zipfile.ZipInfo('x')
  with self.assertRaises(AssertionError):validate_names([a,a])
  a.external_attr=(stat.S_IFLNK|0o777)<<16
  with self.assertRaises(AssertionError):validate_names([a])
  a=zipfile.ZipInfo('big');a.file_size=65*1024*1024
  with self.assertRaises(AssertionError):validate_names([a])
 def test_wrong_archive_never_creates_output(self):
  with tempfile.TemporaryDirectory() as d:
   d=Path(d);f=d/'bad.zip';f.write_bytes(b'not the pinned archive');o=d/'out'
   with self.assertRaises(AssertionError):prepare(f,o)
   self.assertFalse(o.exists())
if __name__=='__main__':unittest.main()

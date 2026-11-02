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
if __name__=='__main__':unittest.main()

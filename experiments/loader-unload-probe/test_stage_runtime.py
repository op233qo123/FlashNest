#!/usr/bin/env python3
import io,stat,unittest,warnings,zipfile
import stage_runtime as s
class ZipSafetyTests(unittest.TestCase):
    def make(self, rows):
        out=io.BytesIO()
        with warnings.catch_warnings():
            warnings.simplefilter('ignore',UserWarning)
            with zipfile.ZipFile(out,'w') as z:
                for name,body in rows:z.writestr(name,body)
        return out.getvalue()
    def test_regular(self):
        with s.checked_zip(self.make([('safe.txt',b'ok')]),100,False) as z:self.assertEqual(z.namelist(),['safe.txt'])
    def test_duplicate(self):
        with self.assertRaises(ValueError):s.checked_zip(self.make([('a',b''),('a',b'')]),100,False)
    def test_traversal(self):
        for name in ['../a','/a','a/../b','a//b','a\\b','a:b']:
            with self.subTest(name=name),self.assertRaises(ValueError):s.checked_zip(self.make([(name,b'')]),100,False)
    def test_symlink(self):
        i=zipfile.ZipInfo('a');i.create_system=3;i.external_attr=(stat.S_IFLNK|0o777)<<16
        with self.assertRaises(ValueError):s.checked_zip(self.make([(i,b'outside')]),100,False)
    def test_payload_bound(self):
        with self.assertRaises(ValueError):s.checked_zip(self.make([('a',b'123')]),2,False)
    def test_outer_directory_rejected(self):
        with self.assertRaises(ValueError):s.checked_zip(self.make([('dir/',b'')]),100,False)
    def test_inner_directory_allowed(self):
        with s.checked_zip(self.make([('dir/',b''),('dir/a',b'')]),100,True) as z:self.assertEqual(len(z.namelist()),2)
if __name__=='__main__':unittest.main()

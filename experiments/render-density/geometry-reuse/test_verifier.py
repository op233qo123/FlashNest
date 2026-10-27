#!/usr/bin/env python3
"""Archive safety tests; no renderer execution."""
import importlib.util,stat,tempfile,unittest,zipfile
from pathlib import Path
spec=importlib.util.spec_from_file_location('verifier',Path(__file__).with_name('verify_artifact.py'));v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)
class ExtractTests(unittest.TestCase):
    def test_valid_bounded_archive_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);z=p/'a.zip'
            with zipfile.ZipFile(z,'w') as f:f.writestr('nested/file.txt','original')
            v.safe_extract(z,p/'out');self.assertEqual((p/'out/nested/file.txt').read_text(),'original')
            with self.assertRaises(ValueError):v.safe_extract(z,p/'out')
    def test_reject_paths_symlinks_and_duplicates_before_extract(self):
        for mode in ['../escape','/absolute','nested\\escape','symlink','duplicate']:
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
                p=Path(tmp);z=p/'a.zip'
                with zipfile.ZipFile(z,'w') as f:
                    if mode=='symlink':
                        i=zipfile.ZipInfo('link');i.create_system=3;i.external_attr=(stat.S_IFLNK|0o777)<<16;f.writestr(i,'../escape')
                    elif mode=='duplicate':f.writestr('a','one');f.writestr('a','two')
                    else:f.writestr(mode,'bad')
                with self.assertRaises(ValueError):v.safe_extract(z,p/'out')
                self.assertFalse((p/'out').exists())
    def test_reject_wrong_zip_identity_before_extract(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'a.zip').write_bytes(b'not the locked artifact')
            with self.assertRaises(AssertionError):v.validate(p/'a.zip',p/'out')
            self.assertFalse((p/'out').exists())
if __name__=='__main__':unittest.main()

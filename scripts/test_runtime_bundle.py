#!/usr/bin/env python3
"""Offline fail-closed installer tests for the exact vendored candidate."""
import copy
import hashlib
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import fetch_runtime as runtime

ROOT = Path(__file__).resolve().parents[1]


class RuntimeBundleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lock = json.loads((ROOT / 'runtime.lock.json').read_text())
        cls.manifest = json.loads((ROOT / 'runtime.files.json').read_text())
        cls.identity = (ROOT / 'App/Resources/Web/runtime-identity.json').read_bytes()
        cls.archive = (ROOT / cls.lock['archivePath']).read_bytes()

    def verify(self, archive=None, lock=None, manifest=None, identity=None):
        return runtime.verified_runtime(self.archive if archive is None else archive,
            self.lock if lock is None else lock, self.manifest if manifest is None else manifest,
            self.identity if identity is None else identity)

    def test_exact_candidate_is_offline_and_complete(self):
        files = self.verify()
        self.assertEqual(set(files), set(self.manifest))
        self.assertEqual(len(files), 12)
        self.assertEqual(sum(name.endswith('.wasm') for name in files), 2)
        self.assertNotIn('urllib', (ROOT / 'scripts/fetch_runtime.py').read_text())

    def test_hash_identity_size_and_manifest_drift_rejected(self):
        for values in ({'archive': self.archive[:-1]}, {'identity': self.identity + b' '},
                       {'manifest': {**self.manifest, 'ruffle.js': '0' * 64}}):
            with self.subTest(values=list(values)), self.assertRaises(ValueError):
                self.verify(**values)
        wrong = {**self.lock, 'sha256': '0' * 64}
        with self.assertRaises(ValueError): self.verify(lock=wrong)

    def test_unsafe_member_rejected_even_after_outer_hash_matches(self):
        for name in ('../outside', '/outside', 'C:/outside', 'x\\outside', 'a/./b'):
            out = io.BytesIO()
            with zipfile.ZipFile(out, 'w') as z: z.writestr(name, b'x')
            data = out.getvalue(); lock = {**self.lock, 'archiveBytes': len(data), 'sha256': runtime.digest(data)}
            identity = json.loads(self.identity); identity['artifactArchiveSHA256'] = lock['sha256']
            raw = json.dumps(identity).encode(); lock['identitySHA256'] = runtime.digest(raw)
            with self.subTest(name=name), self.assertRaises(ValueError): self.verify(data, lock, identity=raw)

    def test_duplicate_json_rejected(self):
        with self.assertRaises(ValueError): runtime.parse_json('{"x":1,"x":2}')

    def test_archive_prefix_cannot_change_destination(self):
        with self.assertRaises(ValueError): self.verify(lock={**self.lock, 'runtimePrefix': '../'})

    def stage_root(self, parent):
        root = Path(parent) / 'repo'; web = root / 'App/Resources/Web'; web.mkdir(parents=True)
        (root / 'vendor').mkdir()
        shutil.copyfile(ROOT / self.lock['archivePath'], root / self.lock['archivePath'])
        (root / 'runtime.lock.json').write_text(json.dumps(self.lock))
        (root / 'runtime.files.json').write_text(json.dumps(self.manifest))
        (web / 'runtime-identity.json').write_bytes(self.identity)
        (web / 'licenses-not-touched.txt').write_bytes(b'outside-runtime')
        return root, web

    def test_replacement_removes_legacy_chunks_and_preserves_outside_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, web = self.stage_root(temporary); target = web / 'runtime'; target.mkdir()
            (target / '172de42e6619eac8f371.wasm').write_bytes(b'old')
            runtime.install_runtime(root)
            self.assertEqual({p.name for p in target.iterdir()}, set(self.manifest))
            self.assertEqual((web / 'licenses-not-touched.txt').read_bytes(), b'outside-runtime')
            runtime.install_runtime(root)
            self.assertEqual({p.name for p in target.iterdir()}, set(self.manifest))

    def test_unknown_content_and_symlink_are_not_removed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, web = self.stage_root(temporary); target = web / 'runtime'; target.mkdir()
            unknown = target / 'user-content.txt'; unknown.write_bytes(b'preserve')
            with self.assertRaises(ValueError): runtime.install_runtime(root)
            self.assertEqual(unknown.read_bytes(), b'preserve')
            unknown.unlink(); target.rmdir(); target.symlink_to(web)
            with self.assertRaises(ValueError): runtime.install_runtime(root)
            self.assertEqual((web / 'licenses-not-touched.txt').read_bytes(), b'outside-runtime')

    def test_packaged_bundle_verifier_rejects_asset_notice_and_identity_drift(self):
        from verify_bundled_runtime import verify_web
        with tempfile.TemporaryDirectory() as temporary:
            web = Path(temporary) / 'Web'
            shutil.copytree(ROOT / 'App/Resources/Web', web)
            verify_web(web)
            for relative in ('runtime/ruffle.js', 'runtime-identity.json', 'Ruffle-MODIFICATIONS.md'):
                path = web / relative; original = path.read_bytes(); path.write_bytes(original + b' ')
                with self.subTest(relative=relative), self.assertRaises(ValueError): verify_web(web)
                path.write_bytes(original)
            (web / 'runtime/stale.wasm').write_bytes(b'old')
            with self.assertRaises(ValueError): verify_web(web)

    def test_packaged_bundle_rejects_linked_root_and_license_directory(self):
        from verify_bundled_runtime import verify_web
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); web = root / 'Web'
            web.symlink_to(ROOT / 'App/Resources/Web')
            with self.assertRaises(ValueError): verify_web(web)
            web.unlink(); shutil.copytree(ROOT / 'App/Resources/Web', web)
            alias = root / 'outer-alias'; alias.symlink_to(root)
            # An outer workspace alias is not a link stored inside the .app.
            nested = root / 'app'; nested.mkdir(); (nested / 'Web').mkdir()
            shutil.rmtree(nested / 'Web'); shutil.copytree(web, nested / 'Web')
            verify_web(alias / 'app/Web')
            licenses = web / 'licenses'; outside = root / 'license-data'
            licenses.rename(outside); licenses.symlink_to(outside)
            with self.assertRaises(ValueError): verify_web(web)

    def test_failed_atomic_install_restores_previous_runtime(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, web = self.stage_root(temporary); target = web / 'runtime'; target.mkdir()
            (target / 'ruffle.js').write_bytes(b'original')
            real_replace = runtime.os.replace
            def failing_once(source, destination):
                if Path(source).name == 'new-runtime': raise OSError('injected staging failure')
                return real_replace(source, destination)
            with patch.object(runtime.os, 'replace', failing_once), self.assertRaises(OSError): runtime.install_runtime(root)
            self.assertEqual((target / 'ruffle.js').read_bytes(), b'original')


    def test_failed_install_and_failed_restore_preserve_previous_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, web = self.stage_root(temporary); target = web / 'runtime'; target.mkdir()
            (target / 'ruffle.js').write_bytes(b'original-recovery')
            with patch.object(runtime.os, 'replace', side_effect=OSError('injected double failure')):
                with self.assertRaisesRegex(RuntimeError, 'previous bytes retained'):
                    runtime.install_runtime(root)
            recoveries = list(web.parent.glob('.runtime-stage-*/previous-runtime/ruffle.js'))
            self.assertEqual(len(recoveries), 1)
            self.assertEqual(recoveries[0].read_bytes(), b'original-recovery')
            with self.assertRaisesRegex(ValueError, 'requires inspection'):
                runtime.install_runtime(root)



if __name__ == '__main__':
    unittest.main()

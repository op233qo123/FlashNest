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

    def changed_metadata(self, change):
        lock = copy.deepcopy(self.lock); identity = json.loads(self.identity)
        change(lock, identity)
        raw = json.dumps(identity).encode(); lock['identitySHA256'] = runtime.digest(raw)
        return lock, raw

    def changed_archive(self, replacements=None, omit=(), extra=None, changed_provenance=None):
        replacements = dict(replacements or {})
        lock = copy.deepcopy(self.lock); identity = json.loads(self.identity)
        if changed_provenance is not None:
            raw = json.dumps(changed_provenance).encode()
            replacements[lock['provenancePath']] = raw
            lock['provenanceSHA256'] = runtime.digest(raw)
            identity['provenanceSHA256'] = lock['provenanceSHA256']
        out = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(self.archive)) as old, zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as new:
            for info in old.infolist():
                if info.filename not in omit:
                    new.writestr(info, replacements.get(info.filename, old.read(info.filename)))
            if extra:
                for name, data in extra.items(): new.writestr(name, data)
        data = out.getvalue(); lock['archiveBytes'] = len(data); lock['sha256'] = runtime.digest(data)
        identity['artifactArchiveSHA256'] = lock['sha256']
        raw = json.dumps(identity).encode(); lock['identitySHA256'] = runtime.digest(raw)
        return data, lock, raw

    def test_schema_migration_is_explicit_and_never_silently_accepts_legacy(self):
        self.assertEqual(self.lock['schemaVersion'], 3)
        self.assertEqual(json.loads(self.identity)['schemaVersion'], 2)
        for schema in (2, True, '3'):
            with self.subTest(schema=schema), self.assertRaises(ValueError):
                self.verify(lock={**self.lock, 'schemaVersion': schema})
        for schema in (1, True, '2'):
            lock, raw = self.changed_metadata(lambda _, identity: identity.update(schemaVersion=schema))
            with self.subTest(identity_schema=schema), self.assertRaises(ValueError):
                self.verify(lock=lock, identity=raw)

    def test_ordered_patch_set_and_exact_modified_sources_cannot_expand(self):
        def mutate(key, value):
            def change(lock, identity): lock[key] = value; identity[key] = value
            return self.changed_metadata(change)
        mutations = [
            ('patches', list(reversed(self.lock['patches']))),
            ('patches', self.lock['patches'][:2]),
            ('modifiedSources', self.lock['modifiedSources'][:4]),
            ('modifiedSources', self.lock['modifiedSources'] + [self.lock['modifiedSources'][0]]),
            ('patchSetSHA256', '0' * 64),
        ]
        density = copy.deepcopy(self.lock['patches']); density[2]['path'] = 'experiments/render-density/engine-patch/wgpu-density.patch'
        mutations.append(('patches', density))
        for key, value in mutations:
            lock, raw = mutate(key, value)
            with self.subTest(key=key, value=str(value)[:60]), self.assertRaises(ValueError):
                self.verify(lock=lock, identity=raw)

    def test_corresponding_source_and_patch_bytes_verified_even_with_new_outer_hash(self):
        prefix = 'audio-recovery-candidate/'
        for path in ('source-correspondence/upstream/web/src/audio.rs',
                     'source-correspondence/patches/audio-recovery.patch',
                     'source-correspondence/upstream/LICENSE.md'):
            archive, lock, raw = self.changed_archive({prefix + path: b'tampered'})
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.verify(archive, lock, identity=raw)

    def test_provenance_cannot_claim_another_build_or_patch(self):
        with zipfile.ZipFile(io.BytesIO(self.archive)) as z:
            original = json.loads(z.read(self.lock['provenancePath']))
        for key, value in (('phase', 'baseline'), ('status', 'accepted'), ('patches', original['patches'][:2])):
            changed = copy.deepcopy(original); changed[key] = value
            archive, lock, raw = self.changed_archive(changed_provenance=changed)
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.verify(archive, lock, identity=raw)
        changed = copy.deepcopy(original); changed['experiment']['GITHUB_SHA'] = '0' * 40
        archive, lock, raw = self.changed_archive(changed_provenance=changed)
        with self.assertRaises(ValueError): self.verify(archive, lock, identity=raw)

    def test_candidate_inventory_cannot_add_baseline_or_test_assets(self):
        for extra in ({'audio-recovery-candidate/runtime/injection.js': b'not production'},
                      {'audio-recovery-candidate/unlisted.txt': b'unlisted'}):
            archive, lock, raw = self.changed_archive(extra=extra)
            with self.subTest(extra=list(extra)), self.assertRaises(ValueError):
                self.verify(archive, lock, identity=raw)
        files = self.verify()
        self.assertFalse(any('/' in name or name.endswith(('.swf', '.sol', '.patch')) for name in files))

    def test_archive_resource_budgets_remain_bounded(self):
        for setting, value in (('MAX_ARCHIVE', len(self.archive) - 1), ('MAX_EXPANDED', 1024), ('MAX_FILE', 1024)):
            with self.subTest(setting=setting), patch.object(runtime, setting, value), self.assertRaises(ValueError):
                self.verify()

    def test_reviewable_source_index_and_patches_match_immutable_archive(self):
        source = ROOT / 'vendor/ruffle-audio-recovery-source'
        index = runtime.parse_json((source / 'source-correspondence.manifest.json').read_bytes())
        self.assertEqual(index['schemaVersion'], 1)
        self.assertEqual(index['archivePath'], self.lock['archivePath'])
        self.assertEqual(index['archiveSHA256'], self.lock['sha256'])
        self.assertEqual(index['provenancePath'], self.lock['provenancePath'])
        self.assertEqual(index['provenanceSHA256'], self.lock['provenanceSHA256'])
        self.assertEqual(index['prefix'], 'audio-recovery-candidate/')
        with zipfile.ZipFile(io.BytesIO(self.archive)) as z:
            provenance = runtime.parse_json(z.read(self.lock['provenancePath']))
            self.assertEqual(index['files'], provenance['files'])
            for entry in self.lock['patches']:
                name = Path(entry['path']).name
                raw = (source / name).read_bytes()
                self.assertEqual(runtime.digest(raw), entry['sha256'])
                self.assertEqual(raw, z.read('audio-recovery-candidate/source-correspondence/patches/' + name))

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

    def test_frame_order_managed_chunks_migrate_without_removing_unknown_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, web = self.stage_root(temporary); target = web / 'runtime'; target.mkdir()
            old = ('1bab053d8911d6c21b75.wasm', '8135809bc288856cefbf.wasm',
                   'core.ruffle.4bf43128d442d808d913.js', 'core.ruffle.4bf43128d442d808d913.js.map',
                   'core.ruffle.8ee07edaf47829ab3e6f.js', 'core.ruffle.8ee07edaf47829ab3e6f.js.map')
            for name in old: (target / name).write_bytes(b'previous managed runtime')
            unexpected = target / 'unreviewed.wasm'; unexpected.write_bytes(b'preserve unknown')
            with self.assertRaises(ValueError): runtime.install_runtime(root)
            self.assertTrue(all((target / name).exists() for name in old))
            self.assertEqual(unexpected.read_bytes(), b'preserve unknown')
            unexpected.unlink(); runtime.install_runtime(root)
            self.assertEqual({p.name for p in target.iterdir()}, set(self.manifest))
            self.assertFalse(any((target / name).exists() for name in old))
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

    def test_packaged_web_rejects_diagnostic_injection_and_game_save_fixtures(self):
        from verify_bundled_runtime import verify_web
        with tempfile.TemporaryDirectory() as temporary:
            web = Path(temporary) / 'Web'; shutil.copytree(ROOT / 'App/Resources/Web', web)
            for name in ('audio-recovery-injection.js', 'renderer-observer.js', 'sample.swf', 'sample.sol',
                         'sample.flashnestsave', 'experiments/a.txt', 'source-correspondence/a.txt'):
                file = web / name; file.parent.mkdir(parents=True, exist_ok=True); file.write_bytes(b'not app data')
                with self.subTest(name=name), self.assertRaises(ValueError): verify_web(web)
                file.unlink()
                if file.parent != web: file.parent.rmdir()

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

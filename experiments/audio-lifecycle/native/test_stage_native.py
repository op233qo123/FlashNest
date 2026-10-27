#!/usr/bin/env python3
"""Pure staging/receipt negatives. Synthetic receipts do not authorize real runs."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('native_stage_under_test', HERE / 'stage_native.py')
stage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stage)


def approval():
    return {'schemaVersion': 1, 'status': 'reviewed-corrected-browser-22-pass',
            'repository': 'op233qo123/FlashNest', 'runID': 123456789, 'runAttempt': 1,
            'headSHA': 'a' * 40, 'artifactID': 987654321, 'artifactSHA256': 'b' * 64,
            'artifactBytes': 1000, 'resultsSHA256': 'c' * 64,
            'provenanceSHA256': 'd' * 64, 'buildLockSHA256': 'e' * 64}


def metadata(a):
    run = {'id': a['runID'], 'run_attempt': 1, 'head_sha': a['headSHA'],
           'repository': {'full_name': a['repository'], 'id': 1434064894},
           'path': stage.WORKFLOW, 'event': 'workflow_dispatch', 'head_branch': 'main',
           'status': 'completed', 'conclusion': 'success'}
    artifact = {'id': a['artifactID'], 'name': 'FlashNest-audio-lifecycle-corrected-browser',
                'expired': False, 'size_in_bytes': a['artifactBytes'],
                'digest': 'sha256:' + a['artifactSHA256'],
                'workflow_run': {'id': a['runID'], 'head_sha': a['headSHA'],
                                 'repository_id': 1434064894, 'head_repository_id': 1434064894}}
    job = {'name': 'browser-only', 'run_id': a['runID'], 'run_attempt': 1,
           'head_sha': a['headSHA'], 'status': 'completed', 'conclusion': 'success',
           'labels': ['ubuntu-24.04'], 'steps': [
               {'name': name, 'status': 'completed', 'conclusion': 'success'}
               for name in stage.REQUIRED_STEPS]}
    return run, artifact, {'total_count': 1, 'jobs': [job]}


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(stage.json_bytes(value) if not isinstance(value, bytes) else value)


class NativeStageTests(unittest.TestCase):
    def test_reviewed_approval_required_and_bound(self):
        a = approval()
        stage.validate_approval(a, 'e' * 64)
        for field, value in [('status', 'pending'), ('schemaVersion', True),
                             ('runID', 40540513351), ('artifactID', 12752805773),
                             ('runAttempt', 0), ('repository', 'fork/FlashNest'),
                             ('headSHA', '0' * 39), ('artifactSHA256', 'X' * 64),
                             ('buildLockSHA256', 'f' * 64)]:
            changed = {**a, field: value}
            with self.subTest(field=field), self.assertRaises(ValueError):
                stage.validate_approval(changed, 'e' * 64)
        with self.assertRaises(ValueError):
            stage.validate_approval({**a, 'latest': True}, 'e' * 64)

    def test_metadata_success_and_foreign_partial_skipped_rejection(self):
        a = approval()
        args = metadata(a)
        stage.validate_browser_metadata(*args, a)
        mutations = [
            lambda r, f, j: r.update(conclusion='failure'),
            lambda r, f, j: r.update(status='in_progress'),
            lambda r, f, j: r.update(head_sha='9' * 40),
            lambda r, f, j: r.update(path='.github/workflows/experiment-audio-lifecycle.yml'),
            lambda r, f, j: f.update(expired=True),
            lambda r, f, j: f.update(digest='sha256:' + '0' * 64),
            lambda r, f, j: f['workflow_run'].update(head_repository_id=1),
            lambda r, f, j: j.update(total_count=2),
            lambda r, f, j: j['jobs'][0].update(conclusion='failure'),
            lambda r, f, j: j['jobs'][0]['steps'][2].update(conclusion='skipped'),
            lambda r, f, j: j['jobs'][0]['steps'].pop(),
            lambda r, f, j: j['jobs'][0]['steps'].append(j['jobs'][0]['steps'][0]),
        ]
        for mutation in mutations:
            changed = copy.deepcopy(args)
            mutation(*changed)
            with self.subTest(mutation=mutation), self.assertRaises((ValueError, KeyError)):
                stage.validate_browser_metadata(*changed, a)

    def test_duplicate_nonfinite_json_and_symlinks_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            file = root / 'input.json'
            for raw in (b'{"passed":false,"passed":true}', b'{"n":NaN}'):
                file.write_bytes(raw)
                with self.assertRaises(ValueError):
                    stage.strict_json(file)
            file.write_text('{}')
            (root / 'link.json').symlink_to(file)
            with self.assertRaises(ValueError):
                stage.inventory(root)
            with self.assertRaises(ValueError):
                stage.file_bytes(root / 'link.json')
            (root / 'link.json').unlink()
            (root / 'nested').mkdir()
            (root / 'alias').symlink_to(root / 'nested', target_is_directory=True)
            with self.assertRaises(ValueError):
                stage.inventory(root)

    def test_bounds_and_unsafe_names(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            (root / 'x').write_bytes(b'123')
            with self.assertRaises(ValueError):
                stage.file_bytes(root / 'x', 2)
            with self.assertRaises(ValueError):
                stage.inventory(root, max_files=0)
            with self.assertRaises(ValueError):
                stage.inventory(root, max_bytes=2)
            (root / 'bad:name').write_bytes(b'')
            with self.assertRaises(ValueError):
                stage.inventory(root)

    def test_exact_canvas_audio_only_transformations(self):
        repo = stage.ROOT
        for name, replacements, count in [('page.mjs', stage.PAGE_TRANSFORMS, 4),
                                           ('contracts.mjs', stage.CONTRACT_TRANSFORMS, 5)]:
            source = stage.file_bytes(repo / 'experiments/audio-lifecycle/browser-tests' / name)
            out, evidence = stage.transform(source, replacements, name, name)
            self.assertEqual(len(evidence['replacements']), count)
            self.assertEqual(evidence['originalSHA256'], stage.digest(source))
            self.assertEqual(evidence['stagedSHA256'], stage.digest(out))
            self.assertNotIn(b'webgl2', out)
            self.assertNotIn(b'wgpu-webgl', out)
            self.assertNotIn(b'drawingBufferWidth', out)
            self.assertNotIn(b'row.context.lost', out)
            self.assertIn(b'backingWidth', out)
            if name == 'page.mjs':
                self.assertIn(b"preferredRenderer:'canvas'", out)
                self.assertIn(b"canvas.getContext('2d')", out)
                self.assertNotIn(b"autoplay:'on'", out)
            else:
                self.assertIn(b"assert.equal(row.renderer,'canvas')", out)
                self.assertIn(b'row.context.dpr===expectedDPR', out)
            reversed_text = out.decode()
            for old, new in reversed(replacements):
                self.assertEqual(reversed_text.count(new), 1)
                reversed_text = reversed_text.replace(new, old)
            self.assertEqual(reversed_text.encode(), source)
            for damaged in (source.replace(replacements[0][0].encode(), b'changed'),
                            source + replacements[0][0].encode()):
                with self.assertRaises(ValueError):
                    stage.transform(damaged, replacements, name, name)

    def synthetic_tree(self, root):
        repo, extracted = root / 'repo', root / 'extracted'
        for arm in ('baseline', 'candidate'):
            write(extracted / ('audio-lifecycle-' + arm) / 'runtime/ruffle.js',
                  ('synthetic-' + arm).encode())
        helpers = repo / 'experiments/audio-lifecycle/browser-tests'
        for name in stage.EXACT_HELPERS + ('page.mjs', 'contracts.mjs'):
            write(helpers / name, (stage.ROOT / 'experiments/audio-lifecycle/browser-tests' / name).read_bytes())
        for name in stage.NATIVE_WEB:
            write(repo / 'experiments/audio-lifecycle/native/Web' / name, ('synthetic-' + name).encode())
        write(repo / 'experiments/audio-lifecycle/fixtures/silent.swf', b'synthetic-only-not-an-engine-input')
        return repo, extracted

    def stage_inputs(self, repo, extracted):
        runtimes = {arm: stage.inventory(extracted / ('audio-lifecycle-' + arm) / 'runtime')
                    for arm in ('baseline', 'candidate')}
        helpers = {name: stage.sha(repo / 'experiments/audio-lifecycle/browser-tests' / name)
                   for name in stage.EXACT_HELPERS + ('page.mjs', 'contracts.mjs')}
        fixture = stage.sha(repo / 'experiments/audio-lifecycle/fixtures/silent.swf')
        return runtimes, helpers, fixture

    def test_synthetic_stage_deterministic_and_manifest_not_self_authorizing(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            repo, extracted = self.synthetic_tree(root)
            inputs = self.stage_inputs(repo, extracted)
            original = stage.inventory(repo)
            results = []
            for name in ('stage1', 'stage2'):
                out = root / name
                manifest, pin = stage.stage_web(out, extracted, repo,
                                                {'scope': 'synthetic-unit-only'}, {'synthetic': True}, *inputs)
                results.append((manifest, pin))
                self.assertNotIn('native-manifest.json', manifest['files'])
                self.assertEqual(manifest['adapterScope'], 'canvas-audio-only')
                self.assertIn('baseline/ruffle.js', manifest['files'])
                self.assertIn('candidate/ruffle.js', manifest['files'])
                self.assertEqual(stage.sha(out / 'Web/native-manifest.json'), pin)
                self.assertIn(pin, (out / 'NativeAudioIdentity.swift').read_text())
                with self.assertRaises(ValueError):
                    stage.stage_web(out, extracted, repo, {}, {}, *inputs)
            self.assertEqual(results[0], results[1])
            self.assertEqual(stage.inventory(repo), original)

    def test_stage_missing_extra_web_or_partial_write_fail_closed(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            repo, extracted = self.synthetic_tree(root)
            inputs = self.stage_inputs(repo, extracted)
            web = repo / 'experiments/audio-lifecycle/native/Web'
            (web / 'unexpected.js').write_text('bad')
            with self.assertRaises(ValueError):
                stage.stage_web(root / 'out', extracted, repo, {}, {}, *inputs)
            self.assertFalse((root / 'out').exists())
            (web / 'unexpected.js').unlink()
            # Force failure after stage creation at an actual copy boundary.
            with patch.object(stage.shutil, 'copyfile', side_effect=OSError('synthetic copy fault')):
                with self.assertRaises(OSError):
                    stage.stage_web(root / 'out', extracted, repo, {}, {}, *inputs)
            self.assertFalse((root / 'out').exists())

    def test_copy_time_drift_cannot_be_blessed_by_new_manifest(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            repo, extracted = self.synthetic_tree(root)
            inputs = self.stage_inputs(repo, extracted)
            runtime = extracted / 'audio-lifecycle-candidate/runtime/ruffle.js'
            original = runtime.read_bytes()
            runtime.write_bytes(original + b'changed-after-inventory')
            with self.assertRaises(ValueError):
                stage.stage_web(root / 'out', extracted, repo, {}, {}, *inputs)
            self.assertFalse((root / 'out').exists())
            runtime.write_bytes(original)
            helper = repo / 'experiments/audio-lifecycle/browser-tests/observer.mjs'
            helper.write_bytes(helper.read_bytes() + b'changed-after-inventory')
            with self.assertRaises(ValueError):
                stage.stage_web(root / 'out', extracted, repo, {}, {}, *inputs)
            self.assertFalse((root / 'out').exists())

    def test_immutable_build_identity_rejected_when_changed(self):
        lock = stage.strict_json(stage.REUSE / 'build-lock.json')
        stage.validate_build_lock(lock)
        for key in ('runID', 'artifactID', 'buildCommit', 'artifactSHA256', 'patchSetSHA256'):
            changed = copy.deepcopy(lock)
            changed[key] = 'wrong'
            with self.subTest(key=key), self.assertRaises(ValueError):
                stage.validate_build_lock(changed)

    def browser_receipt(self, root):
        folder, extracted = root / 'browser', root / 'extracted'
        lock = stage.strict_json(stage.REUSE / 'build-lock.json')
        provenance = {'fixture': {
            'manifestSha256': '40687509557be41070b3a3eb19e550870e3ca8d902f2bfea2cedb03c8995ae0f',
            'sha256': 'e25f5dba4162a25b9a07832be4e6f8f62242734f6f39e92983c53467a28e7fd2'},
            'helpers': {name: lock['correctedHarnessSHA256']['experiments/audio-lifecycle/browser-tests/' + name]
                        for name in lock['browserRuntimeHelpers']}}
        for arm in ('baseline', 'candidate'):
            # Only manifest JSON is needed by this pure receipt test.
            path = extracted / ('audio-lifecycle-' + arm) / 'runtime.browser-manifest.json'
            # Explicitly synthetic receipt-only test; it does not validate an
            # immutable artifact or produce a usable native stage approval.
            data = stage.json_bytes({'synthetic-' + arm + '.js': '0' * 64})
            lock[arm + 'BrowserManifestSHA256'] = stage.digest(data)
            write(path, data)
            provenance[arm] = {'manifestSha256': stage.sha(path), 'files': stage.strict_json(path)}
        rows = []
        for arm in ('baseline', 'candidate'):
            for mode in ('normal', 'start-first', 'start-second', 'synthetic-ended'):
                for cycle in range(8 if mode == 'normal' else 1):
                    name = f'{arm}-{mode}-{cycle}-evidence.json'
                    data = stage.json_bytes({'synthetic': True, 'case': [arm, mode, cycle]})
                    write(folder / name, data)
                    rows.append({'arm': arm, 'mode': mode, 'cycle': cycle,
                                 'closeFulfilled': 1, 'explicitDetachBeforeClose': arm == 'candidate',
                                 'expectedBaselineFailure': arm == 'baseline', 'extensions': 'ON',
                                 'evidence': {'file': name, 'bytes': len(data), 'sha256': stage.digest(data)}})
        result = {'passed': True, 'suiteComplete': True, 'plannedCases': 22, 'completedCases': 22,
                  'backendRequired': 'wgpu-webgl', 'quality': 'low', 'failures': [],
                  'rows': rows, 'provenance': provenance}
        write(folder / 'results.json', result)
        write(folder / 'provenance.json', provenance)
        a = approval()
        a.update(resultsSHA256=stage.sha(folder / 'results.json'), provenanceSHA256=stage.sha(folder / 'provenance.json'))
        return folder, extracted, lock, result, a

    def test_browser_receipt_requires_complete_matching_matrix(self):
        with tempfile.TemporaryDirectory() as t:
            folder, extracted, lock, result, a = self.browser_receipt(Path(t))
            checked, attachments = stage.validate_browser_receipt(folder / 'results.json', folder / 'provenance.json', a, lock, extracted)
            self.assertTrue(checked['passed'])
            self.assertEqual(len(attachments), 22)
            variants = []
            bad = copy.deepcopy(result); bad['rows'].pop(); variants.append(bad)
            bad = copy.deepcopy(result); bad['passed'] = False; variants.append(bad)
            bad = copy.deepcopy(result); bad['rows'][-1]['explicitDetachBeforeClose'] = False; variants.append(bad)
            bad = copy.deepcopy(result); bad['rows'][-1]['extensions'] = 'OFF'; variants.append(bad)
            bad = copy.deepcopy(result); bad['rows'][0]['evidence']['file'] = '../outside.json'; variants.append(bad)
            for bad in variants:
                write(folder / 'results.json', bad)
                a['resultsSHA256'] = stage.sha(folder / 'results.json')
                with self.assertRaises((ValueError, AssertionError)):
                    stage.validate_browser_receipt(folder / 'results.json', folder / 'provenance.json', a, lock, extracted)

    def test_browser_receipt_hash_tamper_and_attachment_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            folder, extracted, lock, result, a = self.browser_receipt(Path(t))
            path = folder / result['rows'][0]['evidence']['file']
            path.write_text('{}')
            with self.assertRaises(ValueError):
                stage.validate_browser_receipt(folder / 'results.json', folder / 'provenance.json', a, lock, extracted)
            path.unlink()
            path.symlink_to(folder / 'provenance.json')
            with self.assertRaises(ValueError):
                stage.validate_browser_receipt(folder / 'results.json', folder / 'provenance.json', a, lock, extracted)


if __name__ == '__main__':
    unittest.main(verbosity=2)

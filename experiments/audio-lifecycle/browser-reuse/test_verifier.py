#!/usr/bin/env python3
"""Offline negatives for metadata, hashes, extraction and inherited evidence."""
import argparse
import copy
import importlib.util
import json
from pathlib import Path
import shutil
import stat
import tempfile
import unittest
import warnings
import zipfile

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('verifier', HERE / 'verify_artifact.py')
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)
LOCK = v.read(HERE / 'build-lock.json')
parser = argparse.ArgumentParser()
parser.add_argument('--verified-root', type=Path, required=True)
args, remaining = parser.parse_known_args()
VERIFIED = args.verified_root


class MetadataTests(unittest.TestCase):
    def metadata(self):
        return [v.read(HERE / 'test-data' / name) for name in ('run.json', 'artifact.json', 'jobs.json')]

    def test_exact_api_snapshot(self):
        v.validate_metadata(*self.metadata(), LOCK)

    def test_reject_wrong_metadata_or_lost_failure(self):
        changes = [
            lambda r, a, j: r.update(head_sha='0' * 40),
            lambda r, a, j: r['repository'].update(full_name='other/repository'),
            lambda r, a, j: r.update(conclusion='success'),
            lambda r, a, j: a.update(id=1),
            lambda r, a, j: a.update(digest='sha256:' + '0' * 64),
            lambda r, a, j: a.update(expired=True),
            lambda r, a, j: j['jobs'][0].update(id=1),
            lambda r, a, j: next(x for x in j['jobs'][0]['steps'] if x['name'] == LOCK['successfulBuildSteps'][-1]).update(conclusion='failure'),
            lambda r, a, j: next(x for x in j['jobs'][0]['steps'] if x['name'] == LOCK['failedBrowserStep']).update(conclusion='success'),
        ]
        for change in changes:
            with self.subTest(change=changes.index(change)):
                data = self.metadata()
                change(*data)
                with self.assertRaises(AssertionError):
                    v.validate_metadata(*data, LOCK)


class ExtractionTests(unittest.TestCase):
    def test_valid_archive_and_refuse_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with zipfile.ZipFile(root / 'a.zip', 'w') as z:
                z.writestr('nested/file', b'original')
            v.safe_extract(root / 'a.zip', root / 'out')
            self.assertEqual((root / 'out/nested/file').read_bytes(), b'original')
            with self.assertRaises(ValueError):
                v.safe_extract(root / 'a.zip', root / 'out')

    def test_reject_unsafe_paths_duplicates_and_special_files(self):
        for name in ('../escape', '/absolute', 'nested\\escape', 'a//b', './a', 'symlink', 'fifo', 'duplicate'):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                with zipfile.ZipFile(root / 'a.zip', 'w') as z, warnings.catch_warnings():
                    warnings.simplefilter('ignore', UserWarning)
                    if name in ('symlink', 'fifo'):
                        info = zipfile.ZipInfo('entry')
                        info.create_system = 3
                        info.external_attr = ((stat.S_IFLNK if name == 'symlink' else stat.S_IFIFO) | 0o777) << 16
                        z.writestr(info, '../escape')
                    elif name == 'duplicate':
                        z.writestr('entry', 'one')
                        z.writestr('entry', 'two')
                    else:
                        z.writestr(name, 'bad')
                with self.assertRaises(ValueError):
                    v.safe_extract(root / 'a.zip', root / 'out')
                self.assertFalse((root / 'out').exists())

    def test_count_bound_and_root_allowlist(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with zipfile.ZipFile(root / 'a.zip', 'w') as z:
                for n in range(1001):
                    z.writestr(str(n), b'')
            with self.assertRaises(ValueError):
                v.safe_extract(root / 'a.zip', root / 'out')
            with zipfile.ZipFile(root / 'b.zip', 'w') as z:
                z.writestr('unapproved/file', 'bad')
            with self.assertRaises(ValueError):
                v.safe_extract(root / 'b.zip', root / 'out', v.ROOTS)
            self.assertFalse((root / 'out').exists())

    def test_partial_extract_cleanup(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with zipfile.ZipFile(root / 'a.zip', 'w') as z:
                z.writestr('file', 'one')
                z.writestr('file/child', 'two')
            with self.assertRaises(OSError):
                v.safe_extract(root / 'a.zip', root / 'out')
            self.assertFalse((root / 'out').exists())

    def test_wrong_archive_identity_fails_before_extraction(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'a.zip').write_bytes(b'wrong archive')
            with self.assertRaises(AssertionError):
                v.validate(root / 'a.zip', root / 'out', HERE / 'test-data')
            self.assertFalse((root / 'out').exists())


class InventoryAndEvidenceTests(unittest.TestCase):
    def test_unchanged_verified_root_can_be_reverified(self):
        v.verify_extracted(VERIFIED, LOCK)
        self.assertFalse((VERIFIED / 'reuse-verification.json').exists())

    def test_full_inventory_hash_missing_and_extra_negatives(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / 'file'
            path.write_bytes(b'original')
            entries = {'file': {'sha256': v.sha(path), 'bytes': path.stat().st_size}}
            v.verify_inventory(root, entries)
            path.write_bytes(b'changed!')
            with self.assertRaises(AssertionError):
                v.verify_inventory(root, entries)
            path.write_bytes(b'original')
            (root / 'extra').write_bytes(b'')
            with self.assertRaises(AssertionError):
                v.verify_inventory(root, entries)
            (root / 'extra').unlink()
            path.unlink()
            with self.assertRaises(AssertionError):
                v.verify_inventory(root, entries)

    def test_actual_inherited_evidence_and_semantic_negatives(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in list(LOCK['evidenceSHA256']) + ['audio-lifecycle-candidate/core-js-summary.json']:
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(VERIFIED / name, target)
            v.verify_core_evidence(root, LOCK)
            cases = [
                ('audio-lifecycle-evidence/patched/upstream-goldens/summary.json', lambda d: d.update(completedCount=30)),
                ('audio-lifecycle-evidence/patched/upstream-goldens/summary.json', lambda d: d.update(knownFailurePreservationCount=0)),
                ('audio-lifecycle-evidence/browser/results.json', lambda d: d.update(passed=True)),
                ('audio-lifecycle-candidate/core-js-summary.json', lambda d: d['stats'].update(passes=58)),
            ]
            for name, change in cases:
                with self.subTest(name=name):
                    path = root / name
                    original = path.read_bytes()
                    data = json.loads(original)
                    change(data)
                    path.write_text(json.dumps(data))
                    # Deliberately update the test's digest so semantic checks,
                    # rather than the earlier integrity check, reject the lie.
                    altered_lock = copy.deepcopy(LOCK)
                    if name in altered_lock['evidenceSHA256']:
                        altered_lock['evidenceSHA256'][name] = v.sha(path)
                    with self.assertRaises(AssertionError):
                        v.verify_core_evidence(root, altered_lock)
                    path.write_bytes(original)
            path = root / 'audio-lifecycle-evidence/ownership-model.log'
            path.write_text('tampered evidence')
            with self.assertRaises(AssertionError):
                v.verify_core_evidence(root, LOCK)


class NewBrowserSummaryTests(unittest.TestCase):
    def test_complete_rows_and_negative_summary_or_attachment(self):
        spec = importlib.util.spec_from_file_location('summary', HERE / 'check_browser_results.py')
        summary = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(summary)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            helpers = {name: 'a' * 64 for name in LOCK['browserRuntimeHelpers']}
            lock = {'browserRuntimeHelpers': LOCK['browserRuntimeHelpers'],
                    'baselineBrowserManifestSHA256': 'b' * 64,
                    'candidateBrowserManifestSHA256': 'c' * 64,
                    'correctedHarnessSHA256': {'experiments/audio-lifecycle/browser-tests/' + name: digest for name, digest in helpers.items()}}
            result = {'passed': True, 'suiteComplete': True, 'plannedCases': 22,
                      'completedCases': 22, 'backendRequired': 'wgpu-webgl', 'quality': 'low',
                      'failures': [], 'provenance': {'baseline': {'manifestSha256': 'b' * 64},
                      'candidate': {'manifestSha256': 'c' * 64}, 'helpers': helpers}, 'rows': []}
            for arm in ('baseline', 'candidate'):
                for mode in ('normal', 'start-first', 'start-second', 'synthetic-ended'):
                    for cycle in range(8 if mode == 'normal' else 1):
                        name = f'{arm}-{mode}-{cycle}.json'
                        (root / name).write_text('{}')
                        result['rows'].append({'arm': arm, 'mode': mode, 'cycle': cycle,
                            'evidence': {'file': name, 'bytes': 2, 'sha256': v.sha(root / name)}})
            path = root / 'results.json'
            path.write_text(json.dumps(result))
            self.assertTrue(summary.check(root, lock)['passed'])
            for change in (lambda r: r.update(completedCases=21),
                           lambda r: r.update(passed=False),
                           lambda r: r['provenance']['helpers'].pop('wait-until.mjs'),
                           lambda r: r['rows'][0].update(cycle=1),
                           lambda r: r['rows'][0]['evidence'].update(sha256='0' * 64)):
                modified = copy.deepcopy(result)
                change(modified)
                path.write_text(json.dumps(modified))
                with self.assertRaises(AssertionError):
                    summary.check(root, lock)


if __name__ == '__main__':
    unittest.main(argv=['test_verifier.py'] + remaining)

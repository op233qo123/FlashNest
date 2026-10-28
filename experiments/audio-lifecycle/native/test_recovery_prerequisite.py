"""Pure attestation negatives; no network, runtime, WebKit or build execution."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import recovery_prerequisite as r

HERE = Path(__file__).resolve().parent


def metadata(approved):
    a = approved
    return {
        'run': {'id': a['runID'], 'run_attempt': 1, 'head_sha': a['headSHA'],
                'repository': {'full_name': a['repository'], 'id': a['repositoryID']},
                'workflow_id': a['workflowID'], 'path': a['workflowPath'], 'event': 'workflow_dispatch',
                'head_branch': 'main', 'status': 'completed', 'conclusion': 'success'},
        'artifact': {'id': a['artifactID'], 'name': a['artifactName'], 'size_in_bytes': a['artifactBytes'],
                     'expired': False, 'digest': 'sha256:' + a['artifactSHA256'],
                     'workflow_run': {'id': a['runID'], 'head_sha': a['headSHA'],
                                      'repository_id': a['repositoryID'], 'head_repository_id': a['repositoryID']}},
        'jobs': {'total_count': 1, 'jobs': [{'id': a['jobID'], 'name': a['jobName'], 'run_id': a['runID'],
                    'run_attempt': 1, 'head_sha': a['headSHA'], 'status': 'completed', 'conclusion': 'success',
                    'labels': ['ubuntu-24.04'], 'steps': [{'name': name, 'status': 'completed', 'conclusion': 'success'}
                                                        for name in a['requiredSteps']]}]},
    }


class RecoveryPrerequisite(unittest.TestCase):
    def setUp(self):
        self.approved = r.approval(HERE / 'recovery-approval.json')

    def check_metadata(self, values, valid):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name, value in values.items():
                (root / (name + '.json')).write_text(json.dumps(value))
            if valid:
                r.metadata(root, self.approved)
            else:
                with self.assertRaises((ValueError, KeyError, TypeError)):
                    r.metadata(root, self.approved)

    def test_exact_new_approval_and_complete_metadata(self):
        self.check_metadata(metadata(self.approved), True)
        self.assertEqual(self.approved['runID'], 40614335019)
        self.assertEqual(self.approved['patches'][2]['sha256'], r.PATCHES[2])
        self.assertEqual(len(self.approved['runtimes']['candidate']['files']), 12)

    def test_old_candidate_wrong_patch_and_bool_schema_rejected(self):
        for key, value in [('runID', 40540513351), ('headSHA', '0' * 40), ('artifactID', 12752805773),
                           ('schemaVersion', True), ('artifactSHA256', '0' * 64)]:
            a = copy.deepcopy(self.approved); a[key] = value
            with tempfile.TemporaryDirectory() as tmp:
                p = Path(tmp) / 'a.json'; p.write_text(json.dumps(a))
                with self.assertRaises(ValueError): r.approval(p)
        a = copy.deepcopy(self.approved); a['patches'].reverse()
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'a.json'; p.write_text(json.dumps(a))
            with self.assertRaises(ValueError): r.approval(p)

    def test_failed_foreign_or_wrong_trigger_run_rejected(self):
        for key, value in [('conclusion', 'failure'), ('status', 'in_progress'), ('head_sha', '0' * 40),
                           ('path', 'other.yml'), ('event', 'push'), ('head_branch', 'other')]:
            m = metadata(self.approved); m['run'][key] = value; self.check_metadata(m, False)

    def test_artifact_size_digest_expiry_and_origin_rejected(self):
        for key, value in [('size_in_bytes', 1), ('digest', 'sha256:' + '0' * 64), ('expired', True), ('id', 1)]:
            m = metadata(self.approved); m['artifact'][key] = value; self.check_metadata(m, False)
        m = metadata(self.approved); m['artifact']['workflow_run']['head_sha'] = '0' * 40; self.check_metadata(m, False)

    def test_job_skips_missing_steps_duplicates_runner_and_failure_rejected(self):
        for mutation in [lambda j: j.update(conclusion='failure'), lambda j: j.update(labels=['macos-15']),
                         lambda j: j['steps'].pop(), lambda j: j['steps'].append(j['steps'][0]),
                         lambda j: j['steps'][3].update(conclusion='skipped')]:
            m = metadata(self.approved); mutation(m['jobs']['jobs'][0]); self.check_metadata(m, False)

    def test_wrong_zip_refused_before_extraction(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); archive = root / 'wrong.zip'; archive.write_bytes(b'not the approved artifact')
            with patch.object(r, 'metadata'):
                with self.assertRaisesRegex(ValueError, 'ZIP bytes'):
                    r.prepare(archive, root, HERE / 'recovery-approval.json', root / 'extracted')
            self.assertFalse((root / 'extracted').exists())

    def test_shared_extractor_rejects_paths_roots_links_and_existing_output(self):
        verifier = r.base.load_module('recovery_test_extract', r.base.REUSE / 'verify_artifact.py')
        for name in ['../escape', '/absolute', 'unexpected/a', 'audio-recovery-candidate/../escape', 'audio-recovery-candidate\\x']:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp); archive = root / 'x.zip'
                with zipfile.ZipFile(archive, 'w') as z: z.writestr(name, 'x')
                with self.assertRaises(ValueError): verifier.safe_extract(archive, root / 'out', r.ROOTS)
                self.assertFalse((root / 'out').exists())
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); archive = root / 'x.zip'; entry = zipfile.ZipInfo('audio-recovery-candidate/link'); entry.external_attr = 0o120777 << 16
            with zipfile.ZipFile(archive, 'w') as z: z.writestr(entry, 'target')
            with self.assertRaises(ValueError): verifier.safe_extract(archive, root / 'out', r.ROOTS)
            (root / 'out').mkdir()
            with self.assertRaises(ValueError): verifier.safe_extract(archive, root / 'out', r.ROOTS)


if __name__ == '__main__': unittest.main()

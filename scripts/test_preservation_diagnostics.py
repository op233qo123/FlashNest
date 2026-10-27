import pathlib
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import collect_preservation_diagnostics as collector


class CollectorTests(unittest.TestCase):
    def exercise(self, failure=None, oversized=False):
        def run(command, **kwargs):
            self.assertEqual(command, ['xcrun', 'simctl', 'spawn', 'synthetic-id', 'log', 'show',
                                      '--last', '20m', '--style', 'compact', '--predicate',
                                      'eventMessage BEGINSWITH "SAVE-PRESERVE-" OR eventMessage BEGINSWITH "CACHE-CLEANUP-"'])
            self.assertEqual(kwargs['timeout'], 30)
            self.assertEqual(kwargs['stderr'], subprocess.DEVNULL)
            kwargs['stdout'].write(b'x' * (collector.MAX_BYTES + 20) if oversized else b'SAVE-PRESERVE-ready\n')
            if failure:
                raise failure
            return subprocess.CompletedProcess(command, 0)
        with tempfile.TemporaryDirectory() as directory, patch.object(collector.subprocess, 'run', run):
            path = pathlib.Path(directory) / 'evidence.log'
            collector.collect('synthetic-id', path)
            self.assertEqual(path.stat().st_size, collector.MAX_BYTES if oversized else 20)

    def test_prefix_predicate_excludes_quoted_ax_messages(self):
        # Predicate syntax is verified against the actual subprocess command in
        # exercise(); these cases state BEGINSWITH semantics, not an OS-log test.
        prefixes = ('SAVE-PRESERVE-', 'CACHE-CLEANUP-')
        self.assertTrue('CACHE-CLEANUP-DEADLINE elapsedMs=15000'.startswith(prefixes))
        self.assertTrue('SAVE-PRESERVE-handshake accepted=0'.startswith(prefixes))
        for message in ['Checking "CACHE-CLEANUP-DEADLINE" for AX attributes',
                        'Current tree:\nAlert Diagnostic code: SAVE-PRESERVE-handshake',
                        'log show --predicate eventMessage BEGINSWITH "CACHE-CLEANUP-"']:
            self.assertFalse(message.startswith(prefixes))
        self.exercise()

    def test_fixed_scope_and_output(self):
        self.exercise()

    def test_output_cap(self):
        self.exercise(oversized=True)

    def test_deadline_preserves_partial_evidence(self):
        self.exercise(failure=subprocess.TimeoutExpired('synthetic', 30))


if __name__ == '__main__':
    unittest.main()

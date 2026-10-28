#!/usr/bin/env python3
"""Local contract tests only; no device execution or acceptance implied."""
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
import stage
import verify_ipa

HERE = Path(__file__).resolve().parent

class PackagingTests(unittest.TestCase):
    def test_overlay_exact_inventory_and_hashes(self):
        expected = {entry['path'] for entry in stage.INPUTS['overlay']}
        self.assertEqual(expected, {p.relative_to(HERE / 'overlay').as_posix() for p in (HERE / 'overlay').rglob('*') if p.is_file()})
        for entry in stage.INPUTS['overlay']:
            data = (HERE / 'overlay' / entry['path']).read_bytes()
            self.assertEqual(len(data), entry['bytes'])
            self.assertEqual(hashlib.sha256(data).hexdigest(), entry['sha256'])
        self.assertNotIn('.github/workflows/build-unsigned.yml', expected)
        self.assertNotIn('README.md', expected)
        self.assertFalse(any('sigill' in name or 'injection' in name for name in expected))

    def test_staging_pinned_clean_checkout_and_exact_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            with patch.object(stage.subprocess, 'check_output', side_effect=[stage.INPUTS['baseCommit'] + '\n', '']):
                stage.stage(Path(temporary))
            actual = {p.relative_to(temporary).as_posix() for p in Path(temporary).rglob('*') if p.is_file()}
            self.assertEqual(actual, {entry['path'] for entry in stage.INPUTS['overlay']})
            for entry in stage.INPUTS['overlay']:
                self.assertEqual(hashlib.sha256((Path(temporary) / entry['path']).read_bytes()).hexdigest(), entry['sha256'])

    def test_staging_rejects_other_commit_and_dirty_checkout(self):
        for output in [['0' * 40 + '\n'], [stage.INPUTS['baseCommit'] + '\n', '?? unknown']]:
            with tempfile.TemporaryDirectory() as temporary:
                with patch.object(stage.subprocess, 'check_output', side_effect=output), self.assertRaises(AssertionError):
                    stage.stage(Path(temporary))
                self.assertEqual(list(Path(temporary).iterdir()), [])

    def macho(self, cpu=0x100000c, subtype=0, kind=2, platform=2, command=0x32):
        return struct.pack('<8I', 0xfeedfacf, cpu, subtype, kind, 1, 24, 0, 0) + struct.pack('<6I', command, 24, platform, 0x110000, 0x120400, 0)

    def test_device_macho_pass(self):
        self.assertEqual(verify_ipa.device_macho(self.macho())['platform'], 'iPhoneOS')

    def test_macho_rejects_simulator_other_cpu_signed_or_malformed(self):
        for data in [self.macho(platform=7), self.macho(cpu=0x1000007), self.macho(subtype=2), self.macho(kind=6), self.macho(command=0x1d), self.macho()[:-1], b'bad']:
            with self.subTest(data=data[:8]), self.assertRaises(AssertionError):
                verify_ipa.device_macho(data)

    def test_version_identity_and_original_runtime(self):
        import plistlib
        metadata = plistlib.loads((HERE / 'overlay/App/Info-Debug.plist').read_bytes())
        self.assertEqual(metadata['CFBundleShortVersionString'], '1.5.5')
        self.assertEqual(metadata['CFBundleVersion'], '18')
        lock = json.loads((HERE / 'overlay/runtime.lock.json').read_text())
        self.assertEqual(lock['sha256'], stage.INPUTS['engineArchiveSHA256'])
        self.assertEqual(lock['buildRunID'], 40614335019)
        self.assertEqual(lock['runtimeKind'], 'flashnest-audio-recovery-experimental')
        project = (HERE / 'overlay/project.yml').read_text()
        self.assertIn('PRODUCT_BUNDLE_IDENTIFIER: com.flashnest.app\n', project)

if __name__ == '__main__':
    unittest.main()

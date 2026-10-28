#!/usr/bin/env python3
"""Exercise the real packager's bounded metadata check with synthetic plists.

This does not execute macOS signing/Mach-O tools or claim a device IPA was built.
"""
from pathlib import Path
import plistlib
import re
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class PackageMetadataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = (ROOT / 'scripts/package_unsigned.sh').read_text()
        matches = re.findall(r"<<'PY_VERSION'\n(.*?)\nPY_VERSION", cls.script, re.S)
        assert len(matches) == 1 and len(matches[0]) < 4096
        cls.validator = matches[0]
        cls.expected = plistlib.loads((ROOT / 'App/Info-Debug.plist').read_bytes())

    def run_metadata(self, actual):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, data in [('actual.plist', actual), ('expected.plist', self.expected)]:
                encoded = plistlib.dumps(data)
                self.assertLess(len(encoded), 16 * 1024)
                (root / name).write_bytes(encoded)
            return subprocess.run([sys.executable, '-c', self.validator,
                                   str(root / 'actual.plist'), str(root / 'expected.plist')],
                                  capture_output=True, text=True, timeout=5)

    def actual(self):
        return {'CFBundleIdentifier': 'com.flashnest.app',
                'CFBundleShortVersionString': self.expected['CFBundleShortVersionString'],
                'CFBundleVersion': self.expected['CFBundleVersion']}

    def test_exact_identifier_and_versions_pass(self):
        result = self.run_metadata(self.actual())
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_wrong_missing_or_unexpanded_identifier_fails(self):
        for value in ('com.example.other', 'com.FlashNest.app', '$(PRODUCT_BUNDLE_IDENTIFIER)', None):
            actual = self.actual()
            if value is None: actual.pop('CFBundleIdentifier')
            else: actual['CFBundleIdentifier'] = value
            with self.subTest(identifier=value):
                result = self.run_metadata(actual)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('Packaged bundle identifier mismatch', result.stderr)

    def test_version_value_or_type_mismatch_fails(self):
        for key, value in [('CFBundleShortVersionString', '0.0.0'),
                           ('CFBundleVersion', '0'), ('CFBundleVersion', 18)]:
            actual = self.actual(); actual[key] = value
            with self.subTest(key=key, value=value):
                result = self.run_metadata(actual)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('Packaged version mismatch', result.stderr)

    def test_existing_device_and_unsigned_guards_remain(self):
        for guard in ("grep -q 'Mach-O'", 'lipo -archs', 'grep -qw arm64',
                      '[[ "$platform" == iphoneos ]]', 'embedded.mobileprovision',
                      'if codesign -dv "$app"', 'verify_bundled_runtime.py'):
            with self.subTest(guard=guard): self.assertIn(guard, self.script)


if __name__ == '__main__':
    unittest.main()

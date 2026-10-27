import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch
import hashlib

spec = importlib.util.spec_from_file_location('probe', Path(__file__).with_name('apply_probe.py'))
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)

class ProbeTests(unittest.TestCase):
    def test_unknown_source_fails_closed(self):
        with self.assertRaises(ValueError): probe.transform(b'unknown')

    def test_only_cache_scope_changes_and_shared_deadline(self):
        source = b'''prefix\n    static func clearPackageCaches(packageID: UUID) async throws {
        let started = Date()
        NSLog("CACHE-CLEANUP-BEGIN supportedMask=%d", supported)
        try? await Task.sleep(nanoseconds: 15_000_000_000)
    }
    static func preparePackageRemoval(package: GamePackage) async throws {}
suffix\n'''
        with patch.object(probe, 'BASE_SHA', hashlib.sha256(source).hexdigest()):
            result = probe.transform(source).decode()
        self.assertTrue(result.startswith('prefix\n'))
        self.assertTrue(result.endswith('suffix\n'))
        self.assertEqual(result.count('addingTimeInterval(15)'), 1)
        self.assertIn('defer { lease.close() }', result)
        self.assertIn('try await lease.prepare(before: deadline)', result)
        self.assertIn('deadline.timeIntervalSinceNow', result)
        self.assertNotIn('15_000_000_000', result)

if __name__ == '__main__': unittest.main()

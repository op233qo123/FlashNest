#!/usr/bin/env python3
"""Archive fail-closed tests; not native or product compatibility acceptance."""
import hashlib
import stat
import tempfile
import unittest
import warnings
import zipfile
from pathlib import Path
from unittest.mock import patch
import verify_native_reference as v

class NativeReferenceTests(unittest.TestCase):
    def archive(self, mutate=None):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        p = Path(temp.name) / 'fixture.zip'
        rows = [(name, b'fixture') for name in sorted(v.MEMBERS)]
        if mutate: rows = mutate(rows)
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', UserWarning)
            with zipfile.ZipFile(p, 'w', compression=zipfile.ZIP_DEFLATED) as z:
                for name, value in rows: z.writestr(name, value)
        raw = p.read_bytes()
        return p, dict(v.PIN, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
    def test_exact_members(self):
        p, pin = self.archive()
        with patch.dict(v.PIN, pin, clear=True): self.assertEqual(set(v.read_archive(p)), v.MEMBERS)
    def test_wrong_hash(self):
        p, pin = self.archive(); pin['sha256'] = '0' * 64
        with patch.dict(v.PIN, pin, clear=True), self.assertRaises(ValueError): v.read_archive(p)
    def test_wrong_size(self):
        p, pin = self.archive(); pin['bytes'] += 1
        with patch.dict(v.PIN, pin, clear=True), self.assertRaises(ValueError): v.read_archive(p)
    def test_extra_payload_rejected(self):
        p, pin = self.archive(lambda rows: rows + [('extra.json', b'{}')])
        with patch.dict(v.PIN, pin, clear=True), self.assertRaises(ValueError): v.read_archive(p)
    def test_duplicate_payload_rejected(self):
        p, pin = self.archive(lambda rows: rows + [rows[0]])
        with patch.dict(v.PIN, pin, clear=True), self.assertRaises(ValueError): v.read_archive(p)
    def test_missing_payload_rejected(self):
        p, pin = self.archive(lambda rows: rows[:-1])
        with patch.dict(v.PIN, pin, clear=True), self.assertRaises(ValueError): v.read_archive(p)
    def test_traversal_member_rejected(self):
        p, pin = self.archive(lambda rows: rows + [('../escape', b'no')])
        with patch.dict(v.PIN, pin, clear=True), self.assertRaises(ValueError): v.read_archive(p)
    def test_symlink_member_rejected(self):
        def mutate(rows):
            info = zipfile.ZipInfo(rows[0][0]); info.create_system = 3
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            return [(info, b'outside')] + rows[1:]
        p, pin = self.archive(mutate)
        with patch.dict(v.PIN, pin, clear=True), self.assertRaises(ValueError): v.read_archive(p)
    def test_oversized_member_rejected(self):
        p, pin = self.archive(lambda rows: [(rows[0][0], b'x' * (8 * 1024 * 1024 + 1))] + rows[1:])
        with patch.dict(v.PIN, pin, clear=True), self.assertRaises(ValueError): v.read_archive(p)

if __name__ == '__main__': unittest.main()

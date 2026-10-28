import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import apply_injection as overlay

class OverlayTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.source = self.root/'shipping'
        self.original = ('prefix\n'+overlay.ANCHOR+'suffix\n').encode()
        p=self.source/overlay.SESSION;p.parent.mkdir(parents=True);p.write_bytes(self.original)
        self.script=self.root/'test.js';self.script.write_text('// Synthetic test script; not runtime acceptance\n')
        self.sha=hashlib.sha256(self.script.read_bytes()).hexdigest()
        self.pin=patch.object(overlay,'EXPECTED',hashlib.sha256(self.original).hexdigest());self.pin.start();self.addCleanup(self.pin.stop)
    def test_overlay_only_and_manifest(self):
        out=self.root/'overlay';e=overlay.stage(self.source,out,self.script,self.sha)
        self.assertTrue(e['shippingUnchanged']);self.assertEqual((self.source/overlay.SESSION).read_bytes(),self.original)
        self.assertIn(overlay.INSERT,(out/overlay.SESSION).read_text())
        self.assertTrue((out/'session-injection.diff').exists())
    def test_rejects_source_or_existing_destination(self):
        for out in [self.source,self.source/'nested',self.root]:
            with self.assertRaises(ValueError):overlay.stage(self.source,out,self.script,self.sha)
    def test_rejects_session_and_script_drift_before_writing(self):
        out=self.root/'overlay'
        with self.assertRaises(ValueError):overlay.stage(self.source,out,self.script,'0'*64)
        (self.source/overlay.SESSION).write_text('drift')
        with self.assertRaises(ValueError):overlay.stage(self.source,out,self.script,self.sha)
        self.assertFalse(out.exists())
    def test_rejects_duplicate_anchor_even_with_matching_pin(self):
        p=self.source/overlay.SESSION;p.write_bytes(self.original+overlay.ANCHOR.encode())
        with patch.object(overlay,'EXPECTED',hashlib.sha256(p.read_bytes()).hexdigest()):
            with self.assertRaises(ValueError):overlay.stage(self.source,self.root/'overlay',self.script,self.sha)

if __name__=='__main__':unittest.main()

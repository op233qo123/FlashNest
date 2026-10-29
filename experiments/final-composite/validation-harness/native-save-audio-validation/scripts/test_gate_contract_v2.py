"""Local source/transform tests only; not native audio or audible evidence."""
import copy, importlib.util, json, shutil, tempfile, unittest
from pathlib import Path
import stage_audio_target as stage
BASE=Path(__file__).resolve().parents[5]/'flashnest-published-recovery/experiments/final-composite/validation-app-template'
# Allow explicit immutable recovery root, not an unpinned executable override.
import os
BASE=Path(os.environ.get('FLASHNEST_REVIEWED_TEMPLATE',BASE))

class GateContracts(unittest.TestCase):
    def test_exact_gate_transform_and_immutable_source(self):
        metadata={k:stage.record(stage.read(BASE,k)) for k in stage.FINAL_METADATA}
        original=stage.source_bytes(BASE,metadata)
        with tempfile.TemporaryDirectory() as t:
            source=Path(t)/'app';shutil.copytree(BASE,source)
            gate=source/stage.GATE;gate.write_bytes(gate.read_bytes().replace(stage.GATE_OFF,stage.GATE_ON))
            inputs=stage.source_bytes(source,metadata,True)
            self.assertEqual(inputs[stage.GATE].replace(stage.GATE_ON,stage.GATE_OFF),original[stage.GATE])
            self.assertEqual(stage.overlay(source,metadata,True)[3]['candidateGateOn'],True)
            with self.assertRaises(ValueError):stage.source_bytes(source,metadata,False)
            with self.assertRaises(ValueError):stage.source_bytes(BASE,metadata,True)
            # Exact gate allowance never permits any other byte, including a comment.
            gate.write_bytes(gate.read_bytes()+b'\n// unauthorized drift\n')
            with self.assertRaises(ValueError):stage.source_bytes(source,metadata,True)
        self.assertEqual(stage.source_bytes(BASE,metadata),original)
    def test_metadata_cannot_authorize_gate(self):
        with self.assertRaises(ValueError):stage.source_bytes(BASE,{stage.GATE:stage.record(b'changed')},True)
    def test_candidate_historical_role_guard_is_fail_closed(self):
        stage.validate_gate_role('candidate-composite',True)
        stage.validate_gate_role('baseline-historical',False)
        for role,enabled in [('candidate-composite',False),('baseline-historical',True),('unknown',False),('unknown',True)]:
            with self.subTest(role=role,enabled=enabled),self.assertRaises(ValueError):stage.validate_gate_role(role,enabled)
if __name__=='__main__':unittest.main(verbosity=2)

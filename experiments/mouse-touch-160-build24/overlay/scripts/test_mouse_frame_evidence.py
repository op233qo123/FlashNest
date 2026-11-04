"""Offline acceptance-logic tests. These never claim execution of Ruffle/WASM."""
import unittest
from mouse_clicks_runtime import frame_evidence

class FrameEvidenceTests(unittest.TestCase):
    released=['FRAME_PRESSED false','FRAME_RIGHT_PRESSED false']
    def test_synchronous_left_pair_is_not_sufficient(self):
        self.assertFalse(frame_evidence(self.released,['EVENT:mouseDown','EVENT:mouseUp'])['framePollingPassed'])
    def test_synchronous_right_pair_is_not_sufficient(self):
        self.assertFalse(frame_evidence(self.released,['EVENT:rightMouseDown','EVENT:rightMouseUp'])['framePollingPassed'])
    def test_left_press_is_observed_then_released(self):
        self.assertTrue(frame_evidence(['FRAME_PRESSED true']+self.released,['EVENT:mouseDown','EVENT:mouseUp'])['framePollingPassed'])
    def test_right_press_is_observed_then_released(self):
        self.assertTrue(frame_evidence(['FRAME_RIGHT_PRESSED true']+self.released,['EVENT:rightMouseDown','EVENT:rightMouseUp'])['framePollingPassed'])
    def test_stuck_button_rejected(self):
        self.assertFalse(frame_evidence(self.released+['FRAME_PRESSED true'],['EVENT:mouseDown','EVENT:mouseUp'])['framePollingPassed'])
    def test_hover_has_no_press(self):
        self.assertTrue(frame_evidence(self.released,[])['framePollingPassed'])
        self.assertFalse(frame_evidence(['FRAME_PRESSED true']+self.released,[])['framePollingPassed'])
    def test_drag_must_move_while_left_held(self):
        self.assertFalse(frame_evidence(['DRAG_MOVE false false 160 120'],[],True)['dragPollingPassed'])
        self.assertTrue(frame_evidence(['DRAG_MOVE true false 170 120'],[],True)['dragPollingPassed'])
    def test_missing_frames_rejected(self):
        self.assertFalse(frame_evidence([],[])['framePollingPassed'])

if __name__=='__main__': unittest.main()

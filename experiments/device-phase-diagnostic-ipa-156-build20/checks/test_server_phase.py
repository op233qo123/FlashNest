"""Source-contract checks only; these do not execute Network.framework."""
import os
import pathlib
import unittest
P = pathlib.Path(os.environ['PHASE_APP']) / 'App/Server/LoopbackServer.swift'
S = P.read_text()
class ServerPhaseSourceTests(unittest.TestCase):
    def test_default_off(self):
        self.assertIn('loadPhaseDiagnosticsEnabled: Bool = false', S)
        self.assertIn('guard loadPhaseDiagnosticsEnabled, loadPhaseRequestID < 9_999_999 else { return nil }', S)
    def test_anonymous_header(self):
        self.assertIn('X-FlashNest-Diagnostic-Request: \\(diagnosticRequest)', S)
        shape = S.split('struct LoadPhaseEvent {')[1].split('    }')[0]
        self.assertNotIn('String', shape)
        for field in ('requestID', 'phase', 'expectedBytes', 'acceptedBytes', 'status'):
            self.assertIn('let '+field+':', shape)
    def test_terminal_remove_before_callback(self):
        terminal = S.split('private func finishLoadPhase(')[1].split('private func failure(')[0]
        self.assertLess(terminal.index('removeValue'), terminal.index('onLoadPhase?'))
    def test_send_accounting_after_success(self):
        body = S.split('private func stream(')[1].split('// Active map')[0]
        self.assertLess(body.index('guard error == nil'), body.index('self.acceptLoadPhaseBytes'))
        self.assertLess(body.index('self.acceptLoadPhaseBytes'), body.index('self.stream(handle'))
    def test_head_zero_body(self):
        self.assertIn('expectedBytes: parsed.method == "HEAD" ? 0 : range.count', S)
        self.assertIn('if parsed.method == "HEAD" || range.isEmpty', S)
    def test_chunk_and_range_preserved(self):
        self.assertIn('min(remaining, 262_144)', S)
        self.assertIn('try handle.seek(toOffset: range.lowerBound)', S)
        self.assertIn('remaining: remaining - UInt64(data.count)', S)
    def test_terminal_causes(self):
        for cause in ('serverStopped', 'serverTimedOut', 'serverDisconnected', 'serverReadFailed', 'serverSendFailed', 'serverSendCompleted'):
            self.assertIn('phase: .'+cause, S)
        self.assertIn('phase: error == nil ? .serverSendCompleted : .serverSendFailed', S)
    def test_connection_bounded(self):
        self.assertIn('connections.count < 24', S)
        self.assertNotIn('loadPhases.values', S)
        self.assertIn('acceptedBytes: min(previous.expectedBytes, previous.acceptedBytes + count)', S)
if __name__ == '__main__': unittest.main()

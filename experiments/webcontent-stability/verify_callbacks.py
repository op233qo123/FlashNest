#!/usr/bin/env python3
"""Reuse the strict native xcresult gate; do not accept skips or zero tests."""
import argparse
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('native_gate', ROOT / 'experiments/frame-order/candidate-native/verify_native_result.py')
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)
METHODS = [
    'testPriorPageMessagesCannotMutateReplacementAtSameShellURL',
    'testNilForeignFrameAndStoppedPageMessagesAreRejected',
    'testStaleNavigationFailuresCannotOverwriteActiveOrTerminatedPageState',
]
GATE.LIFECYCLE_CASES['callbacks'] = ['FlashNestTests.PlayerCallbackIdentityTests ' + method for method in METHODS]

def verify(summary, log):
    GATE.verify(summary, log, 'both', 'callbacks')

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('summary', type=Path)
    parser.add_argument('log', type=Path)
    args = parser.parse_args()
    verify(json.loads(args.summary.read_text()), args.log.read_text())
    print('Verified exactly three callback identity tests, zero skips/failures, iOS 18.2')

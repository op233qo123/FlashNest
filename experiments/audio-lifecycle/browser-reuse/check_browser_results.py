#!/usr/bin/env python3
"""Require the complete corrected 22-row browser gate and retained row evidence."""
import argparse
import hashlib
import json
from pathlib import Path


def check(folder, lock):
    if not __debug__:
        raise RuntimeError('Run browser summary checker without Python optimization')
    result = json.loads((folder / 'results.json').read_text())
    assert result['passed'] is True and result['suiteComplete'] is True
    assert result['plannedCases'] == result['completedCases'] == len(result['rows']) == 22
    assert result['backendRequired'] == 'wgpu-webgl' and result['quality'] == 'low'
    assert result['failures'] == []
    expected = {(arm, mode, cycle) for arm in ('baseline', 'candidate')
                for mode in ('normal', 'start-first', 'start-second', 'synthetic-ended')
                for cycle in range(8 if mode == 'normal' else 1)}
    actual = [(row['arm'], row['mode'], row['cycle']) for row in result['rows']]
    assert len(set(actual)) == len(actual) and set(actual) == expected
    for arm in ('baseline', 'candidate'):
        assert result['provenance'][arm]['manifestSha256'] == lock[arm + 'BrowserManifestSHA256']
    for name, digest in result['provenance']['helpers'].items():
        assert digest == lock['correctedHarnessSHA256']['experiments/audio-lifecycle/browser-tests/' + name]
    assert set(result['provenance']['helpers']) == set(lock['browserRuntimeHelpers'])
    assert len(result['provenance']['helpers']) == 9
    for row in result['rows']:
        attachment = row['evidence']
        assert Path(attachment['file']).name == attachment['file'] and '\\' not in attachment['file']
        data = (folder / attachment['file']).read_bytes()
        assert len(data) == attachment['bytes'] and hashlib.sha256(data).hexdigest() == attachment['sha256']
    return {'passed': True, 'suiteComplete': True, 'cases': 22,
            'runtimeRebuilt': False, 'scope': 'Corrected browser observer gate only; no native or memory-release claim'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('folder', type=Path)
    args = parser.parse_args()
    lock = json.loads(Path(__file__).with_name('build-lock.json').read_text())
    print(json.dumps(check(args.folder, lock), indent=2))

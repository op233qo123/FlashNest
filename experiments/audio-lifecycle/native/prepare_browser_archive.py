#!/usr/bin/env python3
"""Hash/metadata validation before bounded corrected-artifact extraction. No network."""
import argparse
from pathlib import Path
import stage_native as stage

def prepare(archive, metadata, approval_path, output):
    lock_path = stage.REUSE / 'build-lock.json'
    approval = stage.strict_json(approval_path)
    stage.validate_approval(approval, stage.sha(lock_path))
    stage.validate_browser_metadata(*(stage.strict_json(metadata / (name + '.json'))
        for name in ('run', 'artifact', 'jobs')), approval)
    data = stage.file_bytes(archive, 300 * 1024 * 1024)
    stage.require(len(data) == approval['artifactBytes'] and stage.digest(data) == approval['artifactSHA256'],
                  'Wrong corrected browser artifact ZIP')
    verifier = stage.load_module('native_browser_safe_archive', stage.REUSE / 'verify_artifact.py')
    verifier.safe_extract(archive, output, {'audio-browser-reuse-evidence', 'audio-reused-build'})
    return {'verifiedArchive': True, 'nativeExecutionPerformed': False,
            'artifactSHA256': approval['artifactSHA256']}

if __name__ == '__main__':
    import json
    parser = argparse.ArgumentParser()
    for name in ('archive', 'metadata', 'approval', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.archive, args.metadata, args.approval, args.output)))

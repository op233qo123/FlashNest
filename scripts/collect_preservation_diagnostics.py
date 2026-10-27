#!/usr/bin/env python3
"""Collect only fixed-code preservation/cache events from a synthetic CI simulator."""
import pathlib
import subprocess
import sys
import tempfile

MAX_BYTES = 256 * 1024


def collect(device_id, destination):
    command = ['xcrun', 'simctl', 'spawn', device_id, 'log', 'show', '--last', '20m',
               '--style', 'compact', '--predicate', 'eventMessage BEGINSWITH "SAVE-PRESERVE-" OR eventMessage BEGINSWITH "CACHE-CLEANUP-"']
    # File-backed output avoids an unbounded in-memory subprocess buffer. Only a
    # bounded prefix is retained as evidence; temporary output is always removed.
    status = 'completed'
    with tempfile.TemporaryFile() as output:
        try:
            result = subprocess.run(command, stdout=output, stderr=subprocess.DEVNULL,
                                    timeout=30, check=False)
            if result.returncode:
                status = 'unavailable'
        except subprocess.TimeoutExpired:
            status = 'timed-out'
        except OSError:
            status = 'unavailable'
        output.seek(0)
        data = output.read(MAX_BYTES)
        truncated = bool(output.read(1))
    path = pathlib.Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    print(f'Preservation diagnostics: status={status}, bytes={len(data)}, truncated={truncated}')


if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit('usage: collect_preservation_diagnostics.py SIMULATOR_ID OUTPUT')
    collect(sys.argv[1], sys.argv[2])

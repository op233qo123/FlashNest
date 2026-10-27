#!/usr/bin/env python3
"""Generate original, inert SOL-header JSON outside the measured iOS process."""
import base64
import hashlib
import json
from pathlib import Path
import sys
import uuid

PACKAGE = 'a1111111-1111-4111-8111-111111111111'


def generate(destination):
    destination = Path(destination)
    if destination.exists():
        raise ValueError('Fixture destination must be absent')
    directory = destination / 'save' / PACKAGE.upper()
    directory.mkdir(parents=True)
    entries = []
    for index in range(8):
        data = bytearray([index]) * 1_048_576
        data[0:2] = b'\x00\xbf'; data[6:10] = b'TCSO'; data[10:16] = b'\x00\x04\x00\x00\x00\x00'
        entries.append({'scope': 'origin', 'key': f'object{index}',
                        'value': base64.b64encode(data).decode(), 'sha256': hashlib.sha256(data).hexdigest()})
    files = {}
    for index in range(7):
        identity = str(uuid.UUID(int=index + 1)).upper()
        snapshot = {'id': identity, 'schemaVersion': 1, 'runtimeVersion': '0.7.1', 'packageID': PACKAGE.upper(),
                    'packageTitle': 'Original listing fixture', 'movie': 'main.swf', 'name': f'Backup {index}',
                    'createdAt': f'2026-01-{index + 1:02d}T00:00:00Z', 'entries': entries, 'decodedBytes': 8_388_608}
        name = 'current.json' if index == 6 else identity + '.json'
        data = json.dumps(snapshot, sort_keys=True, separators=(',', ':')).encode()
        (directory / name).write_bytes(data)
        files[name] = {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
    manifest = {'packageID': PACKAGE.upper(), 'decodedBytesPerArchive': 8_388_608,
                'base64BytesPerArchive': sum(len(entry['value']) for entry in entries), 'files': files,
                'namedArchiveCount': 6, 'expectedVisibleBackups': 5, 'expectedInvalidCount': 1}
    lengths = [item['bytes'] for name, item in files.items() if name != 'current.json']
    assert sum(sorted(lengths)[:5]) <= 64 * 1024 * 1024 < sum(lengths)
    assert max(lengths) <= 16 * 1024 * 1024
    (destination / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest


if __name__ == '__main__': generate(sys.argv[1])

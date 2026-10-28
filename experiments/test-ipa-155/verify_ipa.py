#!/usr/bin/env python3
"""Inspect an unsigned device IPA and write code-only build provenance."""
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import plistlib
import stat
import struct
import sys
import tempfile
import zipfile

HERE = Path(__file__).resolve().parent
INPUTS = json.loads((HERE / 'inputs.json').read_text())

def digest(data):
    return hashlib.sha256(data).hexdigest()

def device_macho(data):
    assert len(data) >= 32, 'Short executable'
    magic, cpu, subtype, kind, count, command_bytes, flags, reserved = struct.unpack_from('<8I', data)
    assert magic == 0xfeedfacf and cpu == 0x100000c and subtype == 0 and kind == 2, 'Expected thin arm64 device executable'
    assert 0 < count <= 4096 and 8 * count <= command_bytes <= len(data) - 32
    position = 32
    platforms = []
    for _ in range(count):
        assert position + 8 <= 32 + command_bytes
        command, size = struct.unpack_from('<II', data, position)
        assert size >= 8 and size % 8 == 0 and position + size <= 32 + command_bytes
        if command == 0x32:
            assert size >= 24
            platform, minimum, sdk, tools = struct.unpack_from('<4I', data, position + 8)
            assert size == 24 + tools * 8
            platforms.append(platform)
        assert command != 0x1d, 'Unexpected code signature command'
        position += size
    assert position == 32 + command_bytes and platforms == [2], 'Not iPhoneOS platform'
    return {'architecture': 'arm64', 'platform': 'iPhoneOS', 'sha256': digest(data)}

def verify(ipa, root, output):
    root = root.resolve()
    sys.path.insert(0, str(root / 'scripts'))
    from verify_bundled_runtime import verify_web
    with tempfile.TemporaryDirectory() as temporary:
        destination = Path(temporary)
        with zipfile.ZipFile(ipa) as archive:
            items = archive.infolist()
            assert len(items) < 10000 and sum(item.file_size for item in items) < 300 * 1024 * 1024
            names = set()
            for item in items:
                name = item.filename
                path = PurePosixPath(name)
                assert not path.is_absolute() and '..' not in path.parts and '\\' not in name and ':' not in name
                assert name not in names and (path.parts[:2] == ('Payload', 'FlashNest.app') or (name == 'Payload/' and item.is_dir()))
                names.add(name)
                assert stat.S_IFMT(item.external_attr >> 16) in (0, stat.S_IFDIR, stat.S_IFREG)
                assert not any(part in {'experiments', 'fixtures', 'source-correspondence', '_CodeSignature'} or part.endswith(('.xctest', '.appex')) for part in path.parts)
                assert path.suffix.lower() not in {'.swf', '.sol', '.flashnestsave', '.mobileprovision', '.ips', '.tracev3'}
            archive.extractall(destination)
        app = destination / 'Payload/FlashNest.app'
        metadata = plistlib.loads((app / 'Info.plist').read_bytes())
        for key, expected in {'CFBundleIdentifier': INPUTS['bundleID'], 'CFBundleShortVersionString': INPUTS['version'], 'CFBundleVersion': INPUTS['build'], 'DTPlatformName': 'iphoneos'}.items():
            assert metadata.get(key) == expected, key
        executable = metadata['CFBundleExecutable']
        assert executable == 'FlashNest'
        architecture = device_macho((app / executable).read_bytes())
        verify_web(app / 'Web', root)
        source_web = root / 'App/Resources/Web'
        expected_web = {p.relative_to(source_web).as_posix(): digest(p.read_bytes()) for p in source_web.rglob('*') if p.is_file()}
        actual_web = {p.relative_to(app / 'Web').as_posix(): digest(p.read_bytes()) for p in (app / 'Web').rglob('*') if p.is_file()}
        assert actual_web == expected_web, 'Full Web inventory mismatch'
        for name in ('shell.js', 'index.html'):
            data = (app / 'Web' / name).read_bytes()
            assert not any(marker in data for marker in (b'__flashnestPhase', b'engine-second-start', b'audio-recovery-injection', b'late-audio-probe', b'startup-journal'))
        record = {'schemaVersion': 1, 'kind': INPUTS['kind'], 'sourceCommit': INPUTS['baseCommit'],
                  'packagingCommit': __import__('os').environ.get('GITHUB_SHA'),
                  'version': INPUTS['version'], 'build': INPUTS['build'], 'bundleID': INPUTS['bundleID'],
                  'engineSource': INPUTS['engineSource'], 'engineRun': INPUTS['engineRun'],
                  'engineArchiveSHA256': INPUTS['engineArchiveSHA256'],
                  'ipaSHA256': digest(Path(ipa).read_bytes()), 'executable': architecture,
                  'webFiles': actual_web, 'nativeAcceptancePerformed': False, 'originalSIGILLResolved': False}
        Path(output).write_text(json.dumps(record, indent=2, sort_keys=True) + '\n')
    print('Experimental IPA device/version/full resource/unsigned gates passed; not native acceptance')

if __name__ == '__main__':
    verify(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))

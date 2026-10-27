#!/usr/bin/env python3
"""Verify and stage the exact checked-in experimental runtime, entirely offline.

The historical official baseline workflow checks out its historical source and
fetcher explicitly; this script never silently falls back to an official build.
"""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
MAX_ARCHIVE = 50 * 1024 * 1024
MAX_EXPANDED = 100 * 1024 * 1024
MAX_FILE = 32 * 1024 * 1024
# Previous official managed filenames, retained only to reject unknown content
# before replacing the generated runtime directory. License files live outside
# that directory too and are never removed by this installer.
LEGACY_NAMES = {
    '172de42e6619eac8f371.wasm', '878d548199cddef07035.wasm',
    'LICENSE_APACHE', 'LICENSE_MIT', 'README.md', 'package.json',
    'core.ruffle.16d61072ac7fdc4d5013.js', 'core.ruffle.16d61072ac7fdc4d5013.js.map',
    'core.ruffle.994eeef0a471a88cd0e3.js', 'core.ruffle.994eeef0a471a88cd0e3.js.map',
    'ruffle.js', 'ruffle.js.map',
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def pairs(values):
    out = {}
    for key, value in values:
        require(key not in out, 'Duplicate JSON key: ' + key)
        out[key] = value
    return out


def parse_json(data):
    return json.loads(data, object_pairs_hook=pairs)


def safe_path(name):
    require(isinstance(name, str) and name and not any(ord(c) < 32 for c in name), 'Unsafe empty/control path')
    require('\\' not in name and ':' not in name, 'Unsafe archive path: ' + name)
    path = PurePosixPath(name)
    require(path.parts and not path.is_absolute() and '..' not in path.parts and '.' not in path.parts and path.as_posix() == name,
            'Noncanonical/escaping path: ' + name)
    return path


def verified_runtime(archive, lock, manifest, identity_bytes):
    require(lock.get('schemaVersion') == 2, 'Unsupported runtime lock schema')
    require(lock.get('runtimeKind') == 'flashnest-frame-order-experimental', 'Not the reviewed derivative kind')
    require(lock.get('runtimePrefix') == 'frame-order-engine-candidate/runtime/', 'Unexpected runtime archive prefix')
    require(lock.get('provenancePath') == 'frame-order-engine-candidate/provenance.json', 'Unexpected provenance path')
    require(len(archive) <= MAX_ARCHIVE and len(archive) == lock['archiveBytes'], 'Runtime archive size mismatch')
    require(digest(archive) == lock['sha256'], 'Runtime archive hash mismatch')
    require(digest(identity_bytes) == lock['identitySHA256'], 'Bundled runtime identity hash mismatch')
    identity = parse_json(identity_bytes)
    require(identity.get('schemaVersion') == 1, 'Unsupported bundled identity schema')
    for key in ('runtimeKind', 'experimentalVersionName', 'upstreamSourceCommit', 'patchSHA256',
                'originalSourceSHA256', 'patchedSourceSHA256', 'provenanceSHA256'):
        require(identity.get(key) == lock[key], 'Runtime identity drift: ' + key)
    require(identity.get('artifactArchiveSHA256') == lock['sha256'], 'Identity refers to another archive')
    expected = identity['runtimeFiles']
    require(len(expected) == 12 and set(expected) == set(manifest), 'Runtime file set mismatch')
    for name, entry in expected.items():
        require(len(safe_path(name).parts) == 1, 'Runtime files must be flat')
        require(re.fullmatch('[0-9a-f]{64}', entry['sha256']) is not None and entry['sha256'] == manifest[name], 'Runtime manifest drift')
        require(type(entry['bytes']) is int and 0 < entry['bytes'] <= MAX_FILE, 'Invalid runtime file size')
    import io
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        infos = z.infolist()
        require(len(infos) <= 1000 and sum(i.file_size for i in infos) <= MAX_EXPANDED, 'Oversized expanded runtime archive')
        names = set()
        for info in infos:
            name = info.filename
            safe_path(name)
            require(name not in names, 'Duplicate archive member: ' + name)
            names.add(name)
            require(0 <= info.file_size <= MAX_FILE, 'Oversized archive member')
            kind = stat.S_IFMT(info.external_attr >> 16)
            require(kind in (0, stat.S_IFREG), 'Non-regular archive member: ' + name)
        provenance_bytes = z.read(lock['provenancePath'])
        require(digest(provenance_bytes) == lock['provenanceSHA256'], 'Source provenance hash mismatch')
        provenance = parse_json(provenance_bytes)
        for field, key in [('upstreamCommit', 'upstreamSourceCommit'), ('patchSHA256', 'patchSHA256'),
                           ('originalFileSHA256', 'originalSourceSHA256'), ('modifiedFileSHA256', 'patchedSourceSHA256')]:
            require(provenance.get(field) == lock[key], 'Source correspondence drift: ' + field)
        prefix = lock['runtimePrefix']
        require({name[len(prefix):] for name in names if name.startswith(prefix)} == set(expected), 'Archive runtime inventory mismatch')
        output = {}
        for name, entry in expected.items():
            data = z.read(prefix + name)
            require(len(data) == entry['bytes'] and digest(data) == entry['sha256'], 'Runtime file hash/size mismatch: ' + name)
            require(provenance['files']['runtime/' + name] == entry, 'Provenance file manifest drift: ' + name)
            output[name] = data
    require(parse_json(output['package.json']).get('version') == lock['version'] == identity['upstreamBaseVersion'], 'Base package version mismatch')
    require(len([n for n in output if n.endswith('.wasm')]) == 2, 'Expected dual WASM')
    for name, data in output.items():
        if name.endswith('.wasm'):
            require(data[:4] == b'\0asm', 'Invalid WASM magic')
    for text in (lock['experimentalVersionName'], lock['runtimeKind'], lock['upstreamSourceCommit']):
        require(text.encode() in output['ruffle.js'], 'Runtime JS lacks modified-build identity')
    return output


def install_runtime(root=ROOT):
    root = Path(root).resolve()
    lock = parse_json((root / 'runtime.lock.json').read_bytes())
    manifest = parse_json((root / 'runtime.files.json').read_bytes())
    archive_relative = safe_path(lock['archivePath'])
    require(archive_relative.parts[0] == 'vendor', 'Runtime archive must be checked in under vendor')
    archive_path = root.joinpath(*archive_relative.parts)
    require(archive_path.is_file() and not archive_path.is_symlink() and archive_path.resolve().is_relative_to(root / 'vendor'), 'Unsafe local runtime archive')
    require(archive_path.stat().st_size <= MAX_ARCHIVE, 'Oversized archive before read')
    web = root / 'App/Resources/Web'
    require(web.is_dir() and not web.is_symlink() and web.resolve() == web, 'Unsafe Web resource directory')
    output = verified_runtime(archive_path.read_bytes(), lock, manifest, (web / 'runtime-identity.json').read_bytes())
    target = web / 'runtime'
    require(not target.is_symlink(), 'Refusing to replace a linked runtime directory')
    if target.exists():
        require(target.is_dir(), 'Runtime destination is not a directory')
        for path in target.iterdir():
            require(path.is_file() and not path.is_symlink() and path.name in set(output) | LEGACY_NAMES,
                    'Refusing to remove unknown runtime content: ' + path.name)
    require(not list(web.parent.glob('.runtime-stage-*')), 'An interrupted runtime stage requires inspection before retry')
    # Keep a failed recovery outside the bundled Web resource subtree.
    temporary = Path(tempfile.mkdtemp(prefix='.runtime-stage-', dir=web.parent))
    staging = temporary / 'new-runtime'
    backup = temporary / 'previous-runtime'
    preserve_recovery = False
    try:
        staging.mkdir()
        for name, data in output.items():
            (staging / name).write_bytes(data)
        # The move and install share one handler: an interrupt immediately
        # after rename must still discover and restore the previous directory.
        try:
            if target.exists():
                target.rename(backup)
            os.replace(staging, target)
        except BaseException:
            if backup.exists():
                try:
                    os.replace(backup, target)
                except BaseException as restoration_error:
                    # Never auto-delete the only prior bytes if restoration
                    # itself fails. The failed build keeps a discoverable
                    # recovery directory and a later install refuses to hide it.
                    preserve_recovery = True
                    raise RuntimeError('Runtime restoration failed; previous bytes retained at ' + str(backup)) from restoration_error
            raise
    finally:
        if not preserve_recovery:
            shutil.rmtree(temporary)
    print('Verified and bundled exact experimental Ruffle derivative offline: ' + lock['experimentalVersionName'])


if __name__ == '__main__':
    install_runtime()

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
# Previous official/frame-order managed filenames, retained only to reject unknown content
# before replacing the generated runtime directory. License files live outside
# that directory too and are never removed by this installer.
LEGACY_NAMES = {
    '172de42e6619eac8f371.wasm', '878d548199cddef07035.wasm',
    'LICENSE_APACHE', 'LICENSE_MIT', 'README.md', 'package.json',
    'core.ruffle.16d61072ac7fdc4d5013.js', 'core.ruffle.16d61072ac7fdc4d5013.js.map',
    'core.ruffle.994eeef0a471a88cd0e3.js', 'core.ruffle.994eeef0a471a88cd0e3.js.map',
    'ruffle.js', 'ruffle.js.map',
    '1bab053d8911d6c21b75.wasm', '8135809bc288856cefbf.wasm',
    'core.ruffle.4bf43128d442d808d913.js', 'core.ruffle.4bf43128d442d808d913.js.map',
    'core.ruffle.8ee07edaf47829ab3e6f.js', 'core.ruffle.8ee07edaf47829ab3e6f.js.map',
}
PATCH_PATHS = (
    'experiments/frame-order/engine-patch/queued-goto-guard.patch',
    'experiments/audio-lifecycle/engine-patch/audio-lifecycle.patch',
    'experiments/audio-recovery/audio-recovery.patch',
)
SOURCE_PATHS = (
    'core/src/display_object/movie_clip.rs',
    'web/packages/core/src/internal/audio-operation.ts',
    'web/packages/core/src/internal/player/inner.tsx',
    'web/packages/core/src/ruffle-imports.ts',
    'web/src/audio.rs',
)


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


def valid_hash(value):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None


def verified_identity(lock, manifest, identity_bytes):
    if lock.get('schemaVersion') == 4:
        from composite_runtime import verified_identity as verify_composite_identity
        return verify_composite_identity(lock, manifest, identity_bytes)
    require(type(lock.get('schemaVersion')) is int and lock['schemaVersion'] == 3, 'Unsupported runtime lock schema')
    require(lock.get('runtimeKind') == 'flashnest-audio-recovery-experimental', 'Not the reviewed derivative kind')
    require(lock.get('runtimePrefix') == 'audio-recovery-candidate/runtime/', 'Unexpected runtime archive prefix')
    require(lock.get('provenancePath') == 'audio-recovery-candidate/provenance.json', 'Unexpected provenance path')
    require(type(lock.get('archiveBytes')) is int and 0 < lock['archiveBytes'] <= MAX_ARCHIVE, 'Invalid archive size')
    for key in ('sha256', 'identitySHA256', 'provenanceSHA256', 'patchSetSHA256'):
        require(valid_hash(lock.get(key)), 'Invalid digest: ' + key)
    for key in ('upstreamSourceCommit', 'buildSourceCommit'):
        require(isinstance(lock.get(key), str) and re.fullmatch('[0-9a-f]{40}', lock[key]) is not None, 'Invalid source commit')
    require(type(lock.get('buildRunID')) is int and lock['buildRunID'] > 0, 'Invalid build run')
    require(lock.get('version') == '0.7.1', 'Unexpected upstream base version')
    require(lock.get('experimentalVersionName') == 'FlashNest experimental Ruffle 0.7.1 audio-recovery ' + lock['patchSetSHA256'][:12], 'Unexpected modified-build identity')
    patches = lock.get('patches')
    require(isinstance(patches, list) and len(patches) == 3, 'Expected all three ordered patches')
    for entry, path in zip(patches, PATCH_PATHS):
        require(isinstance(entry, dict) and set(entry) == {'path', 'sha256'} and entry['path'] == path and valid_hash(entry['sha256']), 'Unexpected patch correspondence')
    require(digest(json.dumps(patches, sort_keys=True, separators=(',', ':')).encode()) == lock['patchSetSHA256'], 'Ordered patch-set digest mismatch')
    sources = lock.get('modifiedSources')
    require(isinstance(sources, list) and len(sources) == 5, 'Expected all five modified sources')
    for entry, path in zip(sources, SOURCE_PATHS):
        require(isinstance(entry, dict) and set(entry) == {'path', 'originalSHA256', 'modifiedSHA256', 'bytes'} and entry['path'] == path, 'Unexpected modified-source correspondence')
        original = entry['originalSHA256']
        require(original is None if path == SOURCE_PATHS[1] else valid_hash(original), 'Invalid original-source digest')
        require(valid_hash(entry['modifiedSHA256']) and type(entry['bytes']) is int and 0 < entry['bytes'] <= MAX_FILE, 'Invalid modified-source hash/size')
    require(digest(identity_bytes) == lock['identitySHA256'], 'Bundled runtime identity hash mismatch')
    identity = parse_json(identity_bytes)
    require(type(identity.get('schemaVersion')) is int and identity['schemaVersion'] == 2, 'Unsupported bundled identity schema')
    for key in ('runtimeKind', 'experimentalVersionName', 'upstreamSourceCommit', 'patches',
                'patchSetSHA256', 'modifiedSources', 'provenanceSHA256', 'buildSourceCommit', 'buildRunID'):
        require(identity.get(key) == lock[key], 'Runtime identity drift: ' + key)
    require(identity.get('artifactArchiveSHA256') == lock['sha256'], 'Identity refers to another archive')
    require(identity.get('upstreamBaseVersion') == lock['version'], 'Identity base version mismatch')
    expected = identity['runtimeFiles']
    require(isinstance(expected, dict) and isinstance(manifest, dict) and len(expected) == 12 and set(expected) == set(manifest), 'Runtime file set mismatch')
    for name, entry in expected.items():
        require(len(safe_path(name).parts) == 1, 'Runtime files must be flat')
        require(isinstance(entry, dict) and set(entry) == {'sha256', 'bytes'}, 'Invalid runtime entry')
        require(valid_hash(entry['sha256']) and entry['sha256'] == manifest[name], 'Runtime manifest drift')
        require(type(entry['bytes']) is int and 0 < entry['bytes'] <= MAX_FILE, 'Invalid runtime file size')
    return identity


def verified_runtime(archive, lock, manifest, identity_bytes):
    if lock.get('schemaVersion') == 4:
        from composite_runtime import verified_runtime as verify_composite_runtime
        return verify_composite_runtime(archive, lock, manifest, identity_bytes)
    identity = verified_identity(lock, manifest, identity_bytes)
    expected = identity['runtimeFiles']
    require(len(archive) == lock['archiveBytes'], 'Runtime archive size mismatch')
    require(digest(archive) == lock['sha256'], 'Runtime archive hash mismatch')
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
        for field, key in [('upstreamCommit', 'upstreamSourceCommit'), ('patches', 'patches'),
                           ('patchSetSHA256', 'patchSetSHA256'), ('modifiedSources', 'modifiedSources')]:
            require(provenance.get(field) == lock[key], 'Source correspondence drift: ' + field)
        require(provenance.get('phase') == 'recovery' and provenance.get('status') == 'experimental-unpromoted', 'Unexpected original provenance phase/status')
        require(provenance.get('addedConfigTests') == [], 'Unexpected additional engine modification')
        experiment = provenance.get('experiment', {})
        require(experiment.get('GITHUB_REPOSITORY') == 'op233qo123/FlashNest' and
                experiment.get('GITHUB_SHA') == lock['buildSourceCommit'] and
                experiment.get('GITHUB_RUN_ID') == str(lock['buildRunID']), 'Build source/run mismatch')
        seal = provenance.get('versionSeal', {})
        require(seal.get('version_number') == lock['version'] and seal.get('version_name') == lock['experimentalVersionName'] and
                seal.get('version_channel') == lock['runtimeKind'] and seal.get('commitHash') == lock['upstreamSourceCommit'], 'Version seal mismatch')
        # Verify the complete candidate inventory, not baseline/evidence members,
        # before returning only the twelve runtime files for app installation.
        candidate = 'audio-recovery-candidate/'
        files = provenance.get('files')
        require(isinstance(files, dict) and len(files) == 145, 'Unexpected candidate correspondence inventory')
        require({n[len(candidate):] for n in names if n.startswith(candidate)} == set(files) | {'provenance.json'}, 'Candidate source/runtime inventory mismatch')
        for name, entry in files.items():
            safe_path(name)
            require(name.startswith(('runtime/', 'source-correspondence/')) or name in {
                'runtime.browser-manifest.json', 'build.log', 'core-js-summary.json',
                'core-js.log', 'core-types-preflight.log'}, 'Unexpected candidate member')
            require(isinstance(entry, dict) and set(entry) == {'sha256', 'bytes'} and valid_hash(entry['sha256']) and
                    type(entry['bytes']) is int and 0 < entry['bytes'] <= MAX_FILE, 'Invalid correspondence entry')
            data = z.read(candidate + name)
            require(len(data) == entry['bytes'] and digest(data) == entry['sha256'], 'Candidate correspondence hash/size mismatch: ' + name)
        for patch in lock['patches']:
            for path in ('source-correspondence/experiment/' + patch['path'], 'source-correspondence/patches/' + PurePosixPath(patch['path']).name):
                require(files.get(path, {}).get('sha256') == patch['sha256'], 'Archived patch correspondence mismatch')
        for source in lock['modifiedSources']:
            require(files.get('source-correspondence/upstream/' + source['path']) == {'sha256': source['modifiedSHA256'], 'bytes': source['bytes']}, 'Archived modified-source mismatch')
        for name in ('Cargo.lock', 'web/package-lock.json', 'LICENSE.md', 'web/packages/selfhosted/LICENSE_MIT', 'web/packages/selfhosted/LICENSE_APACHE'):
            require('source-correspondence/upstream/' + name in files, 'Missing corresponding lock/license: ' + name)
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
    limit = MAX_ARCHIVE
    if lock.get('schemaVersion') == 4:
        from composite_runtime import MAX_ARCHIVE as limit
    require(archive_path.stat().st_size <= limit, 'Oversized archive before read')
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

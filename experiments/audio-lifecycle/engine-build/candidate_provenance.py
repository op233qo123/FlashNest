#!/usr/bin/env python3
"""Verify exact additive patches and package an isolated WebAudio lifecycle candidate."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
PIN = '89a7049965f3090e706265670df309a5128233ac'
GUARD_SHA256 = 'de0acabdf957fccbc11966b67defd0a7f577cdc5a147db949e0a4f0e56c6331f'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def command(args, cwd=None):
    return subprocess.check_output(args, cwd=cwd, stderr=subprocess.STDOUT).decode().strip()


def inputs():
    if not __debug__:
        raise RuntimeError('Run provenance validation without Python optimization')
    data = json.loads((HERE / 'build-inputs.json').read_text())
    assert data['upstreamCommit'] == PIN
    assert len(data['patches']) == 2 and data['patches'][0]['sha256'] == GUARD_SHA256
    for row in data['patches']:
        assert sha((ROOT / row['path']).read_bytes()) == row['sha256'], row['path']
    return data


def patch_paths(patch):
    old = None
    for line in patch.read_text().splitlines():
        if line.startswith('--- '):
            old = line[4:]
        elif line.startswith('+++ '):
            new = line[4:]
            assert old is not None and new.startswith('b/')
            relative = new[2:]
            assert not Path(relative).is_absolute() and '..' not in Path(relative).parts
            assert old in ('a/' + relative, '/dev/null'), 'Renames/deletions are not allowed'
            yield relative, old == '/dev/null'
            old = None


def verify(source, phase='audio'):
    config = inputs()
    assert command(['git', 'rev-parse', 'HEAD'], source) == PIN, 'Wrong source commit'
    patches = config['patches'][:1] if phase == 'guard' else config['patches']
    expected_paths = {}
    for row in patches:
        for relative, new in patch_paths(ROOT / row['path']):
            assert relative not in expected_paths, 'Patch paths must not overlap'
            expected_paths[relative] = new
    existing = sorted(path for path, new in expected_paths.items() if not new)
    actual = command(['git', 'diff', '--name-only', 'HEAD'], source).splitlines()
    assert actual == existing, f'Unexpected tracked diff: {actual}'
    source_rows = []
    with tempfile.TemporaryDirectory(prefix='audio-source-verify-') as temporary:
        reconstructed = Path(temporary)
        original_hashes = {}
        for relative, new in expected_paths.items():
            if not new:
                original = subprocess.check_output(['git', 'show', f'{PIN}:{relative}'], cwd=source)
                target = reconstructed / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(original)
                original_hashes[relative] = sha(original)
        for row in patches:
            path = ROOT / row['path']
            subprocess.run(['git', 'apply', '--check', str(path)], cwd=reconstructed, check=True)
            subprocess.run(['git', 'apply', str(path)], cwd=reconstructed, check=True)
        files = sorted(str(p.relative_to(reconstructed)) for p in reconstructed.rglob('*') if p.is_file())
        assert files == sorted(expected_paths)
        for relative in files:
            expected = (reconstructed / relative).read_bytes()
            assert (source / relative).read_bytes() == expected, f'Patch byte mismatch: {relative}'
            source_rows.append({'path': relative, 'originalSHA256': original_hashes.get(relative),
                                'modifiedSHA256': sha(expected), 'bytes': len(expected)})
    test_rows = []
    assert config['expectedNewConfigTests'] == 0
    assert set(expected_paths) == ({'core/src/display_object/movie_clip.rs'} if phase == 'guard' else {'core/src/display_object/movie_clip.rs', 'web/src/audio.rs'})
    allowed = {'tests/tests/flashnest_frame_order.rs', 'web/version_seal.json'} | set(path for path, new in expected_paths.items() if new)
    allowed |= {row['path'] for row in test_rows}
    for relative in command(['git', 'ls-files', '--others', '--exclude-standard'], source).splitlines():
        assert relative in allowed or relative.startswith('tests/flashnest-frame-order-fixtures/'), f'Unexpected untracked source: {relative}'
    identity = sha(json.dumps(patches, sort_keys=True, separators=(',', ':')).encode())
    return {'upstreamCommit': PIN, 'upstreamURL': f'https://github.com/ruffle-rs/ruffle/tree/{PIN}',
            'phase': phase, 'patches': patches, 'patchSetSHA256': identity,
            'modifiedSources': source_rows, 'addedConfigTests': test_rows}


def runtime_manifest(directory):
    return {str(p.relative_to(directory)): sha(p.read_bytes()) for p in sorted(directory.rglob('*'))
            if p.is_file() and p.suffix in ('.js', '.wasm')}


def baseline(output):
    config = inputs()
    archive = ROOT / config['baselineArchive']
    assert sha(archive.read_bytes()) == config['baselineArchiveSHA256']
    assert not output.exists(), 'Refuse nonempty/reused baseline directory'
    output.mkdir(parents=True)
    with zipfile.ZipFile(archive) as z:
        prefix = 'frame-order-engine-candidate/'
        data = z.read(prefix + 'provenance.json')
        assert sha(data) == config['baselineProvenanceSHA256']
        provenance = json.loads(data)
        assert provenance['upstreamCommit'] == PIN and provenance['patchSHA256'] == GUARD_SHA256
        runtime_rows = {name: row for name, row in provenance['files'].items() if name.startswith('runtime/')}
        archive_rows = {name[len(prefix):] for name in z.namelist() if name.startswith(prefix + 'runtime/') and not name.endswith('/')}
        assert archive_rows == set(runtime_rows), 'Unexpected baseline runtime inventory'
        for name, row in runtime_rows.items():
            relative = Path(name)
            assert not relative.is_absolute() and '..' not in relative.parts
            data = z.read(prefix + name)
            assert len(data) == row['bytes'] and sha(data) == row['sha256']
            target = output / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        (output / 'provenance.json').write_bytes(z.read(prefix + 'provenance.json'))
    (output / 'runtime.browser-manifest.json').write_text(json.dumps(runtime_manifest(output / 'runtime'), indent=2) + '\n')
    (output / 'baseline-identity.json').write_text(json.dumps({
        'archivePath': config['baselineArchive'], 'archiveSHA256': config['baselineArchiveSHA256'],
        'provenanceSHA256': config['baselineProvenanceSHA256'], 'runtimeKind': 'unchanged-existing-queued-goto-candidate',
    }, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=('baseline', 'verify-guard', 'verify-audio', 'prepare', 'package'))
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    source, output = args.source.resolve(), args.output.resolve()
    if args.mode == 'baseline':
        baseline(output)
        return
    info = verify(source, 'guard' if args.mode == 'verify-guard' else 'audio')
    if args.mode.startswith('verify-'):
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(info, indent=2) + '\n')
        return
    if args.mode == 'prepare':
        assert not output.exists(), 'Refuse reused candidate output'
        output.mkdir(parents=True)
        epoch = int(command(['git', 'show', '-s', '--format=%ct', PIN], source))
        seal = {'version_number': '0.7.1',
                'version_name': f"FlashNest experimental Ruffle 0.7.1 audio-lifecycle {info['patchSetSHA256'][:12]}",
                'version_channel': 'flashnest-audio-lifecycle-experimental',
                'build_date': datetime.fromtimestamp(epoch, timezone.utc).isoformat().replace('+00:00', 'Z'),
                'commitHash': PIN, 'version4': '0.7.1.0', 'firefox_extension_id': 'flashnest-audio-lifecycle-experimental'}
        (source / 'web/version_seal.json').write_text(json.dumps(seal, sort_keys=True) + '\n')
        info.update(status='experimental-unpromoted', versionSeal=seal, sourceDateEpoch=epoch,
                    actualBuildStartedUTC=datetime.now(timezone.utc).isoformat(),
                    reproducibility='Pinned recipe and dependency locks; independent clean-build byte identity not verified',
                    experiment={key: os.environ.get(key) for key in ('GITHUB_REPOSITORY', 'GITHUB_SHA', 'GITHUB_RUN_ID', 'GITHUB_RUN_ATTEMPT')},
                    runnerImage={key: os.environ.get(key) for key in ('ImageOS', 'ImageVersion', 'RUNNER_ARCH', 'RUNNER_OS')})
        (output / 'provenance.json').write_text(json.dumps(info, indent=2) + '\n')
        print(epoch)
        return
    recorded = json.loads((output / 'provenance.json').read_text())
    for key, value in info.items():
        assert recorded.get(key) == value, f'Source changed during build: {key}'
    assert (source / 'web/version_seal.json').read_text() == json.dumps(recorded['versionSeal'], sort_keys=True) + '\n', 'Version seal changed during build'
    runtime = source / 'web/packages/selfhosted/dist'
    assert (runtime / 'ruffle.js').is_file() and len(list(runtime.glob('*.wasm'))) == 2
    shutil.copytree(runtime, output / 'runtime')
    (output / 'runtime.browser-manifest.json').write_text(json.dumps(runtime_manifest(output / 'runtime'), indent=2) + '\n')
    correspondence = output / 'source-correspondence'
    paths = {'Cargo.lock', 'Cargo.toml', 'web/package-lock.json', 'web/package.json', 'web/version_seal.json',
             'LICENSE.md', 'web/packages/selfhosted/LICENSE_MIT', 'web/packages/selfhosted/LICENSE_APACHE'}
    paths |= {row['path'] for row in info['modifiedSources'] + info['addedConfigTests']}
    for relative in sorted(paths):
        target = correspondence / 'upstream' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / relative, target)
    # Preserve the complete original-only experiment, its recipes and all patches,
    # not only the resulting WASM. No production application resources are changed.
    for relative in ('experiments/audio-lifecycle', 'experiments/frame-order/engine-build',
                     'experiments/frame-order/engine-patch', 'experiments/frame-order/fixtures',
                     'experiments/frame-order/source'):
        shutil.copytree(ROOT / relative, correspondence / 'experiment' / relative,
                        ignore=shutil.ignore_patterns('__pycache__'))
    for filename in ('make_fixtures.py', 'validate_fixtures.py'):
        target = correspondence / 'experiment/experiments/frame-order' / filename
        shutil.copyfile(ROOT / 'experiments/frame-order' / filename, target)
    for row in inputs()['patches']:
        target = correspondence / 'patches' / Path(row['path']).name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / row['path'], target)
    web = ROOT / 'App/Resources/Web'
    shutil.copytree(web / 'licenses', correspondence / 'licenses/javascript')
    shutil.copyfile(ROOT / 'LICENSE', correspondence / 'licenses/FlashNest-LICENSE.txt')
    shutil.copyfile(web / 'Ruffle-THIRD-PARTY-LICENSES.md', correspondence / 'licenses/Ruffle-THIRD-PARTY-LICENSES.md')
    (correspondence / 'MODIFICATIONS.md').write_text(
        '# Experimental WebAudio lifecycle derivative\n\n'
        f'Base: https://github.com/ruffle-rs/ruffle/tree/{PIN}\n\n'
        'This is not an official unmodified Ruffle binary. It retains the exact queued-goto guard '
        'and adds the supplied audio-lifecycle patches. Exact source, test and patch hashes are in provenance.json. '
        'Existing copyrights, license texts and JavaScript NOTICE materials are retained. '
        'Historical experiment documents describe their own source/build time. This candidate is not promoted '
        'and is not an upstream-approved compatibility fix or a legal-compliance certification.\n')
    recorded['toolVersions'] = {name: command(cmd) for name, cmd in {
        'rustc': ['rustc', '-vV'], 'cargo': ['cargo', '--version'], 'node': ['node', '--version'],
        'npm': ['npm', '--version'], 'java': ['java', '-version'], 'clang': ['clang-18', '--version'],
        'wasmBindgen': ['wasm-bindgen', '--version'], 'binaryen': ['wasm-opt', '--version'],
    }.items()}
    recorded['completedUTC'] = datetime.now(timezone.utc).isoformat()
    recorded['ascJarSHA256'] = sha((source / 'tools/asc/asc.jar').read_bytes())
    recorded['wasmFeatures'] = {'dualWasm': True, 'additionalCargoFeatures': 'jpegxr', 'binaryenOptimization': True}
    recorded['files'] = {str(p.relative_to(output)): {'sha256': sha(p.read_bytes()), 'bytes': p.stat().st_size}
                         for p in sorted(output.rglob('*')) if p.is_file() and p != output / 'provenance.json'}
    (output / 'provenance.json').write_text(json.dumps(recorded, indent=2) + '\n')


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Verify one failed-browser/successful-build artifact; never rebuild or promote."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
ROOTS = {'audio-lifecycle-candidate', 'audio-lifecycle-baseline', 'audio-lifecycle-evidence'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def safe_extract(archive, output, allowed_roots=None):
    if output.exists():
        raise ValueError('Refuse existing extraction directory')
    with zipfile.ZipFile(archive) as z:
        rows = z.infolist()
        names = set()
        if len(rows) > 1000 or sum(row.file_size for row in rows) > 300 * 1024 * 1024:
            raise ValueError('Archive size/count bound exceeded')
        for row in rows:
            path = PurePosixPath(row.filename)
            mode = row.external_attr >> 16
            canonical = path.as_posix() + ('/' if row.is_dir() else '')
            if (not row.filename or path.is_absolute() or '..' in path.parts or
                    '\\' in row.filename or canonical != row.filename or row.filename in names or
                    stat.S_ISLNK(mode) or row.flag_bits & 1):
                raise ValueError('Unsafe archive entry')
            if stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR) or row.file_size > 64 * 1024 * 1024:
                raise ValueError('Unsafe entry type/size')
            if allowed_roots is not None and (not path.parts or path.parts[0] not in allowed_roots):
                raise ValueError('Unexpected archive root')
            names.add(row.filename)
        output.mkdir(parents=True)
        try:
            for row in rows:
                target = output.joinpath(*PurePosixPath(row.filename).parts)
                if row.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with z.open(row) as source, target.open('xb') as dest:
                    shutil.copyfileobj(source, dest)
        except BaseException:
            shutil.rmtree(output)
            raise


def validate_metadata(run, artifact, jobs, lock):
    assert run['id'] == lock['runID'] and run['head_sha'] == lock['buildCommit']
    assert run['repository']['full_name'] == lock['repository'] and run['repository']['id'] == lock['repositoryID']
    assert run['status'] == 'completed' and run['conclusion'] == lock['priorRunConclusion'] == 'failure'
    assert run['run_attempt'] == lock['runAttempt'] == 1
    assert run['workflow_id'] == lock['workflowID'] and run['path'] == lock['workflowPath']
    assert run['event'] == 'workflow_dispatch' and run['head_branch'] == 'main'
    assert artifact['id'] == lock['artifactID'] and artifact['name'] == lock['artifactName']
    assert artifact['expired'] is False and artifact['size_in_bytes'] == lock['artifactBytes']
    assert artifact['digest'] == 'sha256:' + lock['artifactSHA256']
    arun = artifact['workflow_run']
    assert arun['id'] == lock['runID'] and arun['head_sha'] == lock['buildCommit']
    assert arun['repository_id'] == arun['head_repository_id'] == lock['repositoryID']
    assert jobs['total_count'] == len(jobs['jobs']) == 1
    job = jobs['jobs'][0]
    assert job['id'] == lock['jobID'] and job['run_id'] == lock['runID'] and job['name'] == lock['jobName']
    assert job['head_sha'] == lock['buildCommit'] and job['run_attempt'] == lock['runAttempt']
    assert job['status'] == 'completed' and job['conclusion'] == 'failure'
    assert job['labels'] == ['ubuntu-24.04']
    steps = {row['name']: row for row in job['steps']}
    assert len(steps) == len(job['steps']), 'Duplicate step names'
    for name in lock['successfulBuildSteps']:
        assert steps[name]['status'] == 'completed' and steps[name]['conclusion'] == 'success', name
    assert steps[lock['failedBrowserStep']]['conclusion'] == 'failure', 'Prior browser result must remain failed'
    for name in ('Preserve complete source and partial failures', 'Retain unpromoted candidate and ownership evidence'):
        assert steps[name]['conclusion'] == 'success', name


def verify_inventory(root, entries, exclude=()):
    actual = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()} - set(exclude)
    assert actual == set(entries), 'Complete inventory mismatch'
    for name, row in entries.items():
        assert not PurePosixPath(name).is_absolute() and '..' not in PurePosixPath(name).parts
        path = root / name
        assert path.stat().st_size == row['bytes'] and sha(path) == row['sha256'], name


def verify_browser_manifest(folder, digest):
    path = folder / 'runtime.browser-manifest.json'
    assert sha(path) == digest
    expected = read(path)
    actual = {p.relative_to(folder / 'runtime').as_posix(): sha(p)
              for p in (folder / 'runtime').rglob('*') if p.is_file() and p.suffix in ('.js', '.wasm')}
    assert actual == expected and len(actual) == 5
    assert len([name for name in actual if name.endswith('.wasm')]) == 2
    for name in actual:
        if name.endswith('.wasm'):
            assert (folder / 'runtime' / name).read_bytes()[:8] == b'\0asm\x01\0\0\0'


def verify_core_evidence(output, lock):
    evidence = output / 'audio-lifecycle-evidence'
    for name, digest in lock['evidenceSHA256'].items():
        assert sha(output / name) == digest, name
    suite_path = ROOT / 'experiments/frame-order/engine-build/adjacent-tests.json'
    assert sha(suite_path) == lock['adjacentSuiteSHA256']
    suite = read(suite_path)
    summary = read(evidence / 'patched/upstream-goldens/summary.json')
    assert summary['allPassed'] is True and summary['suiteComplete'] is True
    assert summary['completedCount'] == summary['expectedCount'] == 31
    assert summary['strictReferenceCount'] == 29 and summary['knownFailurePreservationCount'] == 2
    assert summary['sourceCommit'] == lock['upstreamCommit'] and summary['phase'] == 'patched'
    assert [row['name'] for row in summary['tests']] == suite['tests'] + suite['knownFailureTests']
    for row in summary['tests']:
        assert row['passed'] is True and row['returncode'] == 0
        expected_scope = 'preserve-upstream-known-failure-and-ruffle-output' if row['name'] in suite['knownFailureTests'] else 'match-upstream-Flash-reference-output'
        assert row['scope'] == expected_scope
        if row['name'] in suite['knownFailureTests']:
            assert 'output.ruffle.txt' in row['inputSHA256']
        log = (evidence / 'patched/upstream-goldens' / row['log']).read_text()
        assert re.search(r'test result: ok\. 1 passed; 0 failed; 0 ignored;', log)
    for name in ('ownership-model.log', 'patched-original.log'):
        assert re.search(r'test result: ok\. 2 passed; 0 failed; 0 ignored;', (evidence / name).read_text()), name
    for fixture, golden in [('nested-child-goto', 'nested-repair-target.txt'), ('control-no-child-goto', 'control.txt')]:
        expected = ROOT / 'experiments/frame-order/engine-patch/expectations' / golden
        assert sha(expected) == lock['frameExpectationsSHA256'][golden]
        assert (evidence / 'patched/original' / (fixture + '.trace.txt')).read_bytes() == expected.read_bytes()
    js = read(output / 'audio-lifecycle-candidate/core-js-summary.json')
    assert js['allPassed'] is True and js['stats']['tests'] == js['stats']['passes'] == 59
    assert js['stats']['pending'] == js['stats']['failures'] == 0
    assert js['expectedOriginalTests'] == 59 and js['expectedNewConfigTests'] == 0 and js['newConfigTestTitles'] == []
    prior = read(evidence / 'browser/results.json')
    assert prior['passed'] is False and prior['suiteComplete'] is False
    assert prior['plannedCases'] == 22 and prior['completedCases'] == len(prior['rows']) == 11
    assert all(row['arm'] == 'baseline' for row in prior['rows'])
    assert prior['activeCase'] == {'arm': 'candidate', 'mode': 'normal', 'cycle': 0}
    assert any('Native onended identity changed' in failure for failure in prior['failures'])
    return prior


def verify_current_harness(lock):
    assert lock['correctedHarnessReady'] is True and lock['correctedHarnessSHA256'], 'Corrected harness not frozen'
    for name, digest in lock['correctedHarnessSHA256'].items():
        assert sha(ROOT / name) == digest, 'Corrected helper/fixture changed: ' + name
    for directory in ('browser-tests', 'fixtures'):
        folder = ROOT / 'experiments/audio-lifecycle' / directory
        manifest = read(folder / 'bundle-manifest.json')
        for path in folder.iterdir():
            assert not path.is_symlink(), 'Helper/fixture symlink'
            assert path.is_file() or (path.is_dir() and path.name == '__pycache__'), 'Unexpected helper/fixture directory'
        expected = {'bundle-manifest.json'} | set(manifest['files'])
        actual = {p.name for p in folder.iterdir() if p.is_file()}
        assert actual == expected, 'Unexpected helper/fixture file'
        for name, row in manifest['files'].items():
            path = folder / name
            assert path.stat().st_size == row['bytes'] and sha(path) == row['sha256'], name
            assert 'experiments/audio-lifecycle/' + directory + '/' + name in lock['correctedHarnessSHA256']


def verify_extracted(output, lock):
    assert {p.name for p in output.iterdir()} == ROOTS
    candidate = output / 'audio-lifecycle-candidate'
    baseline = output / 'audio-lifecycle-baseline'
    assert sha(candidate / 'provenance.json') == lock['candidateProvenanceSHA256']
    build = read(candidate / 'provenance.json')
    assert build['upstreamCommit'] == lock['upstreamCommit'] and build['phase'] == 'audio'
    assert build['status'] == 'experimental-unpromoted' and build['addedConfigTests'] == []
    assert build['experiment'] == {'GITHUB_REPOSITORY': lock['repository'], 'GITHUB_SHA': lock['buildCommit'],
                                   'GITHUB_RUN_ID': str(lock['runID']), 'GITHUB_RUN_ATTEMPT': str(lock['runAttempt'])}
    assert build['patches'] == lock['patches'] and len(build['patches']) == 2
    assert build['patchSetSHA256'] == lock['patchSetSHA256']
    assert build['modifiedSources'] == lock['modifiedSources'] and len(build['modifiedSources']) == 2
    assert build['versionSeal'] == lock['versionSeal']
    assert build['wasmFeatures'] == {'dualWasm': True, 'additionalCargoFeatures': 'jpegxr', 'binaryenOptimization': True}
    assert len(build['files']) == 95
    verify_inventory(candidate, build['files'], exclude=('provenance.json',))
    for row in build['patches']:
        assert sha(ROOT / row['path']) == row['sha256'], row['path']
        assert sha(candidate / 'source-correspondence/patches' / Path(row['path']).name) == row['sha256']
    for row in build['modifiedSources']:
        path = candidate / 'source-correspondence/upstream' / row['path']
        assert sha(path) == row['modifiedSHA256'] and path.stat().st_size == row['bytes']
    assert sha(baseline / 'provenance.json') == lock['baselineProvenanceSHA256']
    assert sha(baseline / 'baseline-identity.json') == lock['baselineIdentitySHA256']
    bp = read(baseline / 'provenance.json')
    assert bp['upstreamCommit'] == lock['upstreamCommit'] and bp['patchSHA256'] == build['patches'][0]['sha256']
    # Only the original runtime subset is present. Do NOT claim that the old
    # provenance's absent source/build-log entries were reverified here.
    runtime_entries = {name: row for name, row in bp['files'].items() if name.startswith('runtime/')}
    assert len(runtime_entries) == 12
    verify_inventory(baseline, runtime_entries, exclude=('provenance.json', 'runtime.browser-manifest.json', 'baseline-identity.json'))
    identity = read(baseline / 'baseline-identity.json')
    assert identity == {'archivePath': 'vendor/ruffle-frame-order-40491098384.zip',
                        'archiveSHA256': '57d7eaed19edd006e2a33a9bfa816f22da8b1003becf3719dfca0c97cb38c4af',
                        'provenanceSHA256': lock['baselineProvenanceSHA256'],
                        'runtimeKind': 'unchanged-existing-queued-goto-candidate'}
    verify_browser_manifest(candidate, lock['candidateBrowserManifestSHA256'])
    verify_browser_manifest(baseline, lock['baselineBrowserManifestSHA256'])
    prior = verify_core_evidence(output, lock)
    return build, prior


def validate(archive, output, metadata):
    if not __debug__:
        raise RuntimeError('Run verifier without Python optimization')
    lock = read(HERE / 'build-lock.json')
    assert archive.stat().st_size == lock['artifactBytes'] and sha(archive) == lock['artifactSHA256'], 'Wrong locked artifact ZIP'
    assert metadata is not None, 'API metadata is required'
    validate_metadata(read(metadata / 'run.json'), read(metadata / 'artifact.json'), read(metadata / 'jobs.json'), lock)
    verify_current_harness(lock)
    safe_extract(archive, output, ROOTS)
    build, prior = verify_extracted(output, lock)
    result = {'verified': True, 'runtimeRebuilt': False, 'runtimeBuildCommit': lock['buildCommit'],
              'runtimeBuildRun': lock['runID'], 'artifactID': lock['artifactID'], 'artifactSHA256': lock['artifactSHA256'],
              'patchSetSHA256': build['patchSetSHA256'], 'currentHarnessCommit': os.environ.get('GITHUB_SHA'),
              'candidateVerifiedInventoryFiles': len(build['files']), 'baselineVerifiedRuntimeFiles': 12,
              'baselineScope': 'Included runtime subset and identity only; absent prior source/build files not reverified',
              'inheritedGates': {'ownershipModel': 2, 'originalFrameOrder': 2, 'adjacent': 31, 'strictReference': 29, 'knownFailurePreservation': 2, 'coreJS': 59},
              'previousBrowser': {'passed': False, 'suiteComplete': False, 'completedCases': prior['completedCases'],
                                  'plannedCases': prior['plannedCases'], 'activeCase': prior['activeCase'], 'failures': prior['failures']},
              'correctedHarnessSHA256': lock['correctedHarnessSHA256']}
    # Receipt is emitted to stdout and retained outside the unchanged extraction root.
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('archive', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--metadata', type=Path, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(validate(args.archive, args.output, args.metadata), indent=2))
    except (AssertionError, ValueError, KeyError, OSError, zipfile.BadZipFile) as error:
        print(json.dumps({'verified': False, 'error': str(error), 'errorType': type(error).__name__}, indent=2))
        raise SystemExit(1)

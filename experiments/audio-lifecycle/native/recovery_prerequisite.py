#!/usr/bin/env python3
"""Explicit replacement candidate attestation; old Weak-only approvals stay historical.

Only reads local original-fixture artifacts and project sources; no network or engine execution.
"""
import argparse
from pathlib import Path
import shutil
import stage_native as base

ROOTS = {'audio-recovery-baseline', 'audio-recovery-candidate', 'audio-recovery-evidence'}
EXPECTED = {
    'schemaVersion': 1, 'status': 'reviewed-recovery-build-and-browser-22-pass',
    'repository': 'op233qo123/FlashNest', 'repositoryID': 1434064894,
    'runID': 40614335019, 'runAttempt': 1,
    'headSHA': '5d2cdcc6757d65194bd55c4a0395b76b0176d224',
    'workflowPath': '.github/workflows/experiment-audio-recovery.yml',
    'jobID': 122573186188, 'jobName': 'validate-build-observe',
    'artifactID': 12783974867, 'artifactName': 'FlashNest-experimental-audio-recovery',
    'artifactSHA256': '3befcb048669c074a017e2bfb6d3ccc283028ef90d7960695bbf0964a2634e9a',
    'artifactBytes': 22076102, 'upstreamCommit': '89a7049965f3090e706265670df309a5128233ac',
    'patchSetSHA256': '3eea9c1603f46966d4de835325484d5433d8999998e6fb9baadf98c56b9fab2e',
    'audioOperationSourceSHA256': '32986bab21da5cc3417ce2b67dfd6a3f829fa2b5c5910805e4a833fb1843a2cb',
}
PATCHES = [
    'de0acabdf957fccbc11966b67defd0a7f577cdc5a147db949e0a4f0e56c6331f',
    '89dfadc1b9d113adb01f08582237559c71a5c0e04fe712cb0e31d80f077b07b9',
    '631027394ab35c7ff5b8bd1da1402a649c38e913dd2b788d1a9ef514fc6aee60',
]


def approval(path):
    value = base.strict_json(path)
    for key, expected in EXPECTED.items():
        base.require(type(value.get(key)) is type(expected) and value[key] == expected, 'Foreign recovery approval: ' + key)
    base.require([p['sha256'] for p in value['patches']] == PATCHES, 'Wrong ordered recovery patch set')
    base.require(set(value['runtimes']) == {'baseline', 'candidate'} and len(value['helpers']) == 9, 'Incomplete approved inputs')
    return value


def metadata(folder, approved):
    values = {name: base.strict_json(folder / (name + '.json')) for name in ('run', 'artifact', 'jobs')}
    run, artifact, jobs = (values[k] for k in ('run', 'artifact', 'jobs'))
    base.require(run['id'] == approved['runID'] and run['run_attempt'] == approved['runAttempt'] and
                 run['head_sha'] == approved['headSHA'] and run['repository']['full_name'] == approved['repository'] and
                 run['repository']['id'] == approved['repositoryID'], 'Wrong recovery run/source')
    base.require(run['workflow_id'] == approved['workflowID'] and run['path'] == approved['workflowPath'] and
                 run['event'] == 'workflow_dispatch' and run['head_branch'] == 'main', 'Wrong recovery workflow/trigger')
    base.require(run['status'] == 'completed' and run['conclusion'] == 'success', 'Recovery build/browser run not successful')
    base.require(artifact['id'] == approved['artifactID'] and artifact['name'] == approved['artifactName'] and
                 artifact['size_in_bytes'] == approved['artifactBytes'] and artifact['expired'] is False and
                 artifact['digest'] == 'sha256:' + approved['artifactSHA256'], 'Wrong recovery artifact')
    origin = artifact['workflow_run']
    base.require(origin['id'] == approved['runID'] and origin['head_sha'] == approved['headSHA'] and
                 origin['repository_id'] == origin['head_repository_id'] == approved['repositoryID'], 'Foreign recovery artifact source')
    base.require(jobs['total_count'] == len(jobs['jobs']) == 1, 'Incomplete recovery job metadata')
    job = jobs['jobs'][0]
    base.require(job['id'] == approved['jobID'] and job['name'] == approved['jobName'] and job['run_id'] == approved['runID'] and
                 job['run_attempt'] == approved['runAttempt'] and job['head_sha'] == approved['headSHA'] and
                 job['status'] == 'completed' and job['conclusion'] == 'success' and job['labels'] == ['ubuntu-24.04'],
                 'Wrong/failed recovery build job')
    steps = {s['name']: s for s in job['steps']}
    base.require(len(steps) == len(job['steps']) and set(steps) == set(approved['requiredSteps']), 'Changed/missing recovery steps')
    base.require(all(s['status'] == 'completed' and s['conclusion'] == 'success' for s in steps.values()), 'Skipped/failed recovery gate')
    return values


def extracted(root, approved, repo):
    all_files = base.inventory(root, max_files=1000, max_bytes=300 * 1024 * 1024)
    base.require({Path(p).parts[0] for p in all_files} == ROOTS, 'Unexpected artifact roots')
    candidate = root / 'audio-recovery-candidate'
    base.require(base.sha(candidate / 'provenance.json') == approved['candidateProvenanceSHA256'], 'Candidate provenance differs')
    build = base.strict_json(candidate / 'provenance.json')
    base.require(build['upstreamCommit'] == approved['upstreamCommit'] and build['patchSetSHA256'] == approved['patchSetSHA256'] and
                 build['patches'] == approved['patches'], 'Candidate source patches differ')
    base.require(build['experiment']['GITHUB_SHA'] == approved['headSHA'] and build['experiment']['GITHUB_RUN_ID'] == str(approved['runID']) and
                 build['experiment']['GITHUB_RUN_ATTEMPT'] == str(approved['runAttempt']), 'Candidate build provenance differs')
    actual = base.inventory(candidate)
    actual.pop('provenance.json')
    base.require(actual == build['files'] and len(actual) == 145, 'Complete candidate correspondence inventory differs')
    helper = candidate / 'source-correspondence/upstream/web/packages/core/src/internal/audio-operation.ts'
    base.require(base.sha(helper) == approved['audioOperationSourceSHA256'], 'Wrong source-bound recovery helper')
    baseline = root / 'audio-recovery-baseline'
    base.require(base.sha(baseline / 'provenance.json') == approved['baselineProvenanceSHA256'] and
                 base.sha(baseline / 'baseline-identity.json') == approved['baselineIdentitySHA256'], 'Baseline historical provenance differs')
    baseline_prov = base.strict_json(baseline / 'provenance.json')
    base.require(baseline_prov['patchSHA256'] == PATCHES[0] and baseline_prov['upstreamCommit'] == approved['upstreamCommit'], 'Wrong unchanged guard baseline')
    runtimes = {}
    for arm in ('baseline', 'candidate'):
        identity = approved['runtimes'][arm]
        base.require(identity['directory'] == 'audio-recovery-' + arm + '/runtime', 'Wrong runtime directory')
        runtime = root / identity['directory']
        rows = base.inventory(runtime, max_files=32, max_bytes=64 * 1024 * 1024)
        base.require(rows == identity['files'] and len(rows) == 12, 'Runtime inventory differs: ' + arm)
        p = build if arm == 'candidate' else baseline_prov
        base.require(rows == {name.removeprefix('runtime/'): row for name, row in p['files'].items() if name.startswith('runtime/')}, 'Runtime/provenance mismatch')
        manifest = runtime.parent / 'runtime.browser-manifest.json'
        base.require(base.sha(manifest) == identity['manifestSHA256'] and base.strict_json(manifest) ==
                     {name: row['sha256'] for name, row in rows.items() if name.endswith(('.js', '.wasm'))}, 'Actual loaded script/WASM manifest mismatch')
        runtimes[arm] = rows
    for name, expected in approved['helpers'].items():
        base.require(Path(name).name == name and '\\' not in name, 'Unsafe helper name')
        base.require(base.sha(repo / 'experiments/audio-lifecycle/browser-tests' / name) == expected, 'Original browser helper changed: ' + name)
    folder = root / 'audio-recovery-evidence/browser'
    # Reuse the existing complete22 checker, but bind its inputs explicitly to
    # this successful new artifact, not the old Weak-only build lock.
    checker_lock = {arm + 'BrowserManifestSHA256': approved['runtimes'][arm]['manifestSHA256'] for arm in runtimes}
    checker_lock['correctedHarnessSHA256'] = {'experiments/audio-lifecycle/browser-tests/' + name: value for name, value in approved['helpers'].items()}
    checker_lock['browserRuntimeHelpers'] = list(approved['helpers'])
    checked, attachments = base.validate_browser_receipt(folder / 'results.json', folder / 'provenance.json',
                                                         approved, checker_lock, root, runtime_prefix='audio-recovery-')
    base.require(base.strict_json(folder / 'provenance.json')['fixture'] == approved['fixture'], 'Fixture correspondence differs')
    return runtimes, checked, attachments


def prepare(archive, meta, approval_path, output):
    approved = approval(approval_path)
    metadata(meta, approved)
    data = base.file_bytes(archive, 128 * 1024 * 1024)
    base.require(len(data) == approved['artifactBytes'] and base.digest(data) == approved['artifactSHA256'], 'Wrong recovery ZIP bytes')
    verifier = base.load_module('native_recovery_safe_archive', base.REUSE / 'verify_artifact.py')
    verifier.safe_extract(archive, output, ROOTS)
    try:
        extracted(output, approved, base.ROOT)
    except BaseException:
        shutil.rmtree(output)
        raise
    return {'verifiedArchive': True, 'nativeExecutionPerformed': False, 'artifactSHA256': approved['artifactSHA256']}


if __name__ == '__main__':
    import json
    p = argparse.ArgumentParser()
    for name in ('archive', 'metadata', 'approval', 'output'):
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args()
    print(json.dumps(prepare(a.archive, a.metadata, a.approval, a.output)))

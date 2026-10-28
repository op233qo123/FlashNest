#!/usr/bin/env python3
"""Explicit new recovery candidate staging for the unchanged22 native matrix."""
import argparse
import json
from pathlib import Path
import shutil
import stage_native as base
import recovery_prerequisite as prerequisite


def stage(args):
    base.require(__debug__, 'Do not disable prerequisite assertions')
    repo, output, root = args.repo_root.resolve(), args.stage.absolute(), args.verified_root.resolve()
    base.require(repo == base.ROOT, 'Use this reviewed checkout root')
    for source in (root, base.HERE, args.metadata.resolve()):
        base.require(not output.resolve().is_relative_to(source) and not source.is_relative_to(output.resolve()), 'Stage overlaps source')
    approved = prerequisite.approval(args.approval)
    metadata = prerequisite.metadata(args.metadata, approved)
    runtime_files, checked, attachments = prerequisite.extracted(root, approved, repo)
    source_build = {key: approved[key] for key in ('repository', 'headSHA', 'runID', 'artifactID', 'artifactSHA256',
                    'upstreamCommit', 'patchSetSHA256', 'candidateProvenanceSHA256', 'baselineProvenanceSHA256', 'baselineIdentitySHA256')}
    source_build.update({'buildCommit': approved['headSHA'], 'runtimeRebuilt': False, 'candidateKind': 'guard-plus-Weak-plus-structured-audio-recovery'})
    receipt = {'approval': approved, 'approvalSHA256': base.sha(args.approval), 'gate': checked,
               'attachments': attachments, 'apiSHA256': {name: base.sha(args.metadata / (name + '.json')) for name in metadata}}
    manifest, digest = base.stage_web(output, root, repo, source_build, receipt, runtime_files, approved['helpers'],
                                      approved['fixture']['sha256'], runtime_prefix='audio-recovery-')
    try:
        project = base.stage_project(output, repo)
        evidence = output / 'prerequisite-evidence'; evidence.mkdir()
        shutil.copyfile(args.approval, evidence / 'recovery-approval.json')
        for name in metadata:
            shutil.copyfile(args.metadata / (name + '.json'), evidence / (name + '.json'))
        browser = root / 'audio-recovery-evidence/browser'
        for name in ('results.json', 'provenance.json', *attachments):
            shutil.copyfile(browser / name, evidence / name)
        for arm in ('baseline', 'candidate'):
            folder = root / ('audio-recovery-' + arm)
            shutil.copyfile(folder / 'provenance.json', evidence / (arm + '-provenance.json'))
            shutil.copyfile(folder / 'runtime.browser-manifest.json', evidence / (arm + '-browser-manifest.json'))
        result = {'verified': True, 'nativeExecutionPerformed': False, 'runtimeRebuilt': False,
                  'manifestSHA256': digest, 'stagedFiles': len(manifest['files']), 'project': project,
                  'browserPrerequisite': checked, 'scope': 'Offline new-candidate reattestation only; native execution remains required'}
        (output / 'verification.json').write_bytes(base.json_bytes(result))
        return result
    except BaseException:
        shutil.rmtree(output)
        raise


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    for name in ('verified-root', 'metadata', 'approval', 'stage', 'repo-root'):
        p.add_argument('--' + name, type=Path, required=True)
    print(json.dumps(stage(p.parse_args())))

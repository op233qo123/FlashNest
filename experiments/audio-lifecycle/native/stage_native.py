#!/usr/bin/env python3
"""Offline, fail-closed native-audio staging; never runs a browser or an engine.

An independently reviewed corrected-browser approval is deliberately required.
The previous failed build's partial browser evidence cannot authorize execution.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import stat

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
REUSE = ROOT / 'experiments/audio-lifecycle/browser-reuse'
WORKFLOW = '.github/workflows/experiment-audio-lifecycle-browser.yml'
NATIVE_WEB = {'index.html', 'native-runner.mjs', 'assert.mjs', 'fresh-action.mjs', 'observer-window.mjs'}
EXACT_HELPERS = ('console-observer.mjs',)
OBSERVER_TRANSFORMS = (
    ("// Diagnostic-only passthrough hooks.", "import {createNativeEventWindow} from './observer-window.mjs';\n// Diagnostic-only passthrough hooks."),
    ("  const record=(kind,data={})=>{if(events.length>=maxEvents){overflow=true;return}events.push({seq:events.length,kind,...data})};",
     "  if(maxEvents!==4096||maxNodes!==4096)throw Error('Native evidence caps must remain 4096');\n"
     "  const nativeWindow=createNativeEventWindow(events,maxEvents);\n"
     "  const record=(kind,data={})=>nativeWindow.record(kind,data);"),
    ("    snapshot(){return structuredClone({mode,overflow,injected,contexts:contextRows,nodes:nodeRows,events})},",
     "    nativeWindow,\n"
     "    snapshot(){const eventWindow=nativeWindow.status();return structuredClone({mode,overflow:overflow||eventWindow.overflow,observerOverflow:overflow,injected,contexts:contextRows,nodes:nodeRows,events,eventWindow,lastReceipt:nativeWindow.lastReceipt()})},"),
)
PAGE_TRANSFORMS = (
    ("script.src='/'+runtime+'/ruffle.js'", "script.src='./'+runtime+'/ruffle.js'"),
    ("url:'/fixtures/silent.swf'", "url:'./fixtures/silent.swf'"),
    ("preferredRenderer:'wgpu-webgl'", "preferredRenderer:'canvas'"),
    ("const observer=installAudioObserver(window,{mode});", "const observer=installAudioObserver(window,{mode});\nwindow.nativeAudioEvidenceWindow=observer.nativeWindow;"),
    ("window.dispose=()=>{if(disposed)return;try{if(player)player.remove()}finally{player=null;api=null;observer.releaseRetained();try{observer.restore()}finally{consoleObserver.restore();disposed=true}}};",
     "window.dispose=()=>{if(disposed)return;try{if(player)player.remove()}finally{player=null;api=null;observer.releaseRetained();disposed=true}};\n"
     "window.restoreNativeAudioObservation=()=>{try{observer.restore()}finally{consoleObserver.restore()}};"),
    (" const gl=canvas.getContext('webgl2');if(!gl)throw Error('Expected actual WebGL2 context for wgpu-webgl');\n"
     "  row.context={kind:'webgl2',lost:gl.isContextLost(),drawingBufferWidth:gl.drawingBufferWidth,drawingBufferHeight:gl.drawingBufferHeight,dpr:devicePixelRatio};\n"
     "  if(row.context.lost)throw Error('Renderer context already lost');\n"
     "  canvas.addEventListener('webglcontextlost',()=>report('webglcontextlost'));",
     " const context2d=canvas.getContext('2d');if(!context2d)throw Error('Expected actual Canvas2D context for native audio-only gate');\n"
     "  row.context={kind:'2d',backingWidth:canvas.width,backingHeight:canvas.height,dpr:devicePixelRatio};"),
)
CONTRACT_TRANSFORMS = (
    ("import assert from 'node:assert/strict';", "import assert from './assert.mjs';"),
    ("import {freshAction} from './runner-guards.mjs';", "import {freshAction} from './fresh-action.mjs';"),
    ('preRemove=null})', 'preRemove=null,expectedDPR=1})'),
    ("assert.equal(row.renderer,'wgpu-webgl');", "assert.equal(row.renderer,'canvas');"),
    ("assert(row.context?.kind==='webgl2'&&row.context.lost===false&&row.context.dpr===1&&row.context.drawingBufferWidth>0&&row.context.drawingBufferHeight>0,'Missing actual live WebGL2 context');",
     "assert(row.context?.kind==='2d'&&row.context.dpr===expectedDPR&&row.context.backingWidth>0&&row.context.backingHeight>0,'Missing actual Canvas2D backing surface in native audio-only gate');"),
)
REQUIRED_STEPS = (
    'Retrieve exact existing artifact and terminal build API records',
    'Validate corrected observer, verifier negatives and locked dependencies',
    'Corrected complete WebAudio ownership browser gate (22 rows)',
    'Preserve previous failure and corrected observer provenance separately',
    'Retain browser evidence and unchanged complete candidate correspondence',
)
APPROVAL_KEYS = {
    'schemaVersion', 'status', 'repository', 'runID', 'runAttempt', 'headSHA',
    'artifactID', 'artifactSHA256', 'artifactBytes', 'resultsSHA256',
    'provenanceSHA256', 'buildLockSHA256',
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def file_bytes(path, maximum=64 * 1024 * 1024):
    path = Path(path)
    mode = path.lstat().st_mode
    require(stat.S_ISREG(mode) and not stat.S_ISLNK(mode), 'Not a regular file: ' + str(path))
    require(path.stat().st_size <= maximum, 'File exceeds bound: ' + str(path))
    return path.read_bytes()


def sha(path):
    return digest(file_bytes(path))


def strict_json(path, maximum=2 * 1024 * 1024):
    def unique(pairs):
        out = {}
        for key, value in pairs:
            require(key not in out, 'Duplicate JSON key: ' + key)
            out[key] = value
        return out
    def invalid(value):
        raise ValueError('Non-finite JSON number: ' + value)
    return json.loads(file_bytes(path, maximum), object_pairs_hook=unique, parse_constant=invalid)


def json_bytes(value):
    return (json.dumps(value, indent=2, sort_keys=True) + '\n').encode()


def inventory(root, max_files=1000, max_bytes=300 * 1024 * 1024):
    """Reject links/special entries, including the root, before reading data."""
    root = Path(root)
    require(stat.S_ISDIR(root.lstat().st_mode) and not root.is_symlink(), 'Invalid inventory root')
    result = {}
    total = 0
    for path in sorted(root.rglob('*')):
        mode = path.lstat().st_mode
        require(not stat.S_ISLNK(mode), 'Symlink rejected: ' + str(path))
        if stat.S_ISDIR(mode):
            continue
        require(stat.S_ISREG(mode), 'Special entry rejected: ' + str(path))
        name = path.relative_to(root).as_posix()
        require('\\' not in name and ':' not in name and
                all(part not in ('', '.', '..') for part in PurePosixPath(name).parts), 'Unsafe path')
        data = file_bytes(path)
        total += len(data)
        require(len(result) < max_files and total <= max_bytes, 'Tree exceeds bounds')
        result[name] = {'bytes': len(data), 'sha256': digest(data)}
    return result


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_build_lock(lock):
    expected = {
        'schemaVersion': 1, 'repository': 'op233qo123/FlashNest',
        'runID': 40540513351, 'artifactID': 12752805773,
        'buildCommit': 'd3b402aec064f326a6b03c022253ccea559aa62f',
        'artifactSHA256': 'cd5c2f5eb9f907ffe165148d942e9fff58194511097a3fc75f0dafc4a5a91cb7',
        'upstreamCommit': '89a7049965f3090e706265670df309a5128233ac',
        'patchSetSHA256': '26aa9106bd1745f9c562d6b89bb2a734ce321bc619e8958d0f5603b476f03689',
    }
    for key, value in expected.items():
        require(lock.get(key) == value, 'Foreign immutable build: ' + key)
    require(lock['patches'][1]['sha256'] ==
            '89dfadc1b9d113adb01f08582237559c71a5c0e04fe712cb0e31d80f077b07b9', 'Wrong audio patch')


def validate_approval(approval, lock_hash):
    require(set(approval) == APPROVAL_KEYS, 'Unknown/missing browser approval keys')
    require(type(approval['schemaVersion']) is int and approval['schemaVersion'] == 1, 'Approval schema')
    require(approval['status'] == 'reviewed-corrected-browser-22-pass', 'Browser pass not reviewed')
    require(approval['repository'] == 'op233qo123/FlashNest', 'Foreign browser repository')
    for key in ('runID', 'runAttempt', 'artifactID', 'artifactBytes'):
        require(type(approval[key]) is int and approval[key] > 0, 'Invalid approval integer: ' + key)
    require(approval['runID'] != 40540513351 and approval['artifactID'] != 12752805773,
            'Old failed browser/build artifact cannot authorize native execution')
    require(approval['artifactBytes'] <= 300 * 1024 * 1024, 'Browser artifact exceeds bound')
    require(re.fullmatch(r'[0-9a-f]{40}', approval['headSHA']) is not None, 'Browser head SHA')
    for key in ('artifactSHA256', 'resultsSHA256', 'provenanceSHA256', 'buildLockSHA256'):
        require(re.fullmatch(r'[0-9a-f]{64}', approval[key]) is not None, 'Invalid approval digest: ' + key)
    require(approval['buildLockSHA256'] == lock_hash, 'Browser approval covers another build/helper lock')


def validate_browser_metadata(run, artifact, jobs, approval):
    require(run['id'] == approval['runID'] and run['run_attempt'] == approval['runAttempt'], 'Browser run identity')
    require(run['head_sha'] == approval['headSHA'] and run['repository']['full_name'] == approval['repository'],
            'Browser source identity')
    require(run['repository']['id'] == 1434064894 and run['path'] == WORKFLOW, 'Browser workflow/repository identity')
    require(run['event'] == 'workflow_dispatch' and run['head_branch'] == 'main', 'Unexpected browser trigger')
    require(run['status'] == 'completed' and run['conclusion'] == 'success', 'Corrected browser run not successful')
    require(artifact['id'] == approval['artifactID'] and
            artifact['name'] == 'FlashNest-audio-lifecycle-corrected-browser', 'Browser artifact identity')
    require(artifact['expired'] is False and artifact['size_in_bytes'] == approval['artifactBytes'], 'Browser artifact size/expiry')
    require(artifact['digest'] == 'sha256:' + approval['artifactSHA256'], 'Browser artifact digest')
    source = artifact['workflow_run']
    require(source['id'] == approval['runID'] and source['head_sha'] == approval['headSHA'] and
            source['repository_id'] == source['head_repository_id'] == 1434064894, 'Foreign artifact source')
    require(jobs['total_count'] == len(jobs['jobs']) == 1, 'Missing/duplicate browser jobs')
    job = jobs['jobs'][0]
    require(job['name'] == 'browser-only' and job['run_id'] == approval['runID'] and
            job['run_attempt'] == approval['runAttempt'] and job['head_sha'] == approval['headSHA'], 'Browser job identity')
    require(job['status'] == 'completed' and job['conclusion'] == 'success' and
            job['labels'] == ['ubuntu-24.04'], 'Browser job not successful on expected runner')
    steps = {row['name']: row for row in job['steps']}
    require(len(steps) == len(job['steps']), 'Duplicate browser step names')
    for name in REQUIRED_STEPS:
        step = steps.get(name, {})
        require(step.get('status') == 'completed' and step.get('conclusion') == 'success',
                'Browser prerequisite step incomplete/skipped: ' + name)


def validate_browser_receipt(results_path, provenance_path, approval, lock, extracted, runtime_prefix='audio-lifecycle-'):
    require(results_path.name == 'results.json' and provenance_path.name == 'provenance.json' and
            results_path.parent.resolve() == provenance_path.parent.resolve(), 'Use one complete browser evidence folder')
    require(sha(results_path) == approval['resultsSHA256'] and
            sha(provenance_path) == approval['provenanceSHA256'], 'Unreviewed browser result/provenance bytes')
    # Reject links and oversized files before the inherited checker reads any
    # attachment named by otherwise untrusted result metadata.
    inventory(results_path.parent, max_files=64, max_bytes=80 * 1024 * 1024)
    result, provenance = strict_json(results_path), strict_json(provenance_path)
    require(result['provenance'] == provenance, 'Browser result/provenance disagreement')
    for arm in ('baseline', 'candidate'):
        manifest = extracted / (runtime_prefix + arm) / 'runtime.browser-manifest.json'
        require(provenance[arm] == {'manifestSha256': sha(manifest), 'files': strict_json(manifest)},
                'Browser tested another runtime: ' + arm)
    require(provenance['fixture'] == {
        'manifestSha256': '40687509557be41070b3a3eb19e550870e3ca8d902f2bfea2cedb03c8995ae0f',
        'sha256': 'e25f5dba4162a25b9a07832be4e6f8f62242734f6f39e92983c53467a28e7fd2',
    }, 'Browser tested another original fixture')
    attachments = {}
    total = 0
    require(isinstance(result['rows'], list) and len(result['rows']) == 22, 'Browser matrix incomplete')
    for row in result['rows']:
        attachment = row['evidence']
        expected_name = f"{row['arm']}-{row['mode']}-{row['cycle']}-evidence.json"
        require(attachment['file'] == expected_name, 'Noncanonical browser evidence name')
        path = results_path.parent / expected_name
        data = file_bytes(path, 8 * 1024 * 1024)
        strict_json(path, 8 * 1024 * 1024)
        total += len(data)
        require(total <= 64 * 1024 * 1024, 'Browser evidence exceeds bound')
        attachments[expected_name] = {'bytes': len(data), 'sha256': digest(data)}
        require(attachments[expected_name] == {k: attachment[k] for k in ('bytes', 'sha256')}, 'Browser attachment mismatch')
        require(row['closeFulfilled'] == 1 and row['explicitDetachBeforeClose'] is (row['arm'] == 'candidate') and
                row['expectedBaselineFailure'] is (row['arm'] == 'baseline'), 'Wrong browser ownership contract')
    require({row['extensions'] for row in result['rows']} in ({'ON'}, {'OFF'}), 'Browser feature-path mismatch')
    checker = load_module('audio_native_browser_result_check', REUSE / 'check_browser_results.py')
    checked = checker.check(results_path.parent, lock)
    return checked, attachments


def transform(data, replacements, source_name, destination):
    text = data.decode('utf-8')
    rows = []
    for before, after in replacements:
        require(text.count(before) == 1, 'Audited source token changed: ' + before)
        text = text.replace(before, after)
        rows.append({'from': before, 'to': after, 'occurrences': 1})
    changed = text.encode()
    return changed, {'source': source_name, 'destination': destination,
                     'originalSHA256': digest(data), 'stagedSHA256': digest(changed), 'replacements': rows}


def stage_web(stage, extracted, repo, source_build, browser_prerequisite,
              runtime_files, helper_hashes, fixture_hash, runtime_prefix='audio-lifecycle-'):
    """Called only after prerequisite validation; also tested with synthetic files."""
    require(not stage.exists() and not stage.is_symlink(), 'Stage must not exist')
    web_source = repo / 'experiments/audio-lifecycle/native/Web'
    native_files = inventory(web_source, max_files=16, max_bytes=256 * 1024)
    require(set(native_files) == NATIVE_WEB, 'Unexpected/missing native Web helper')
    helpers = repo / 'experiments/audio-lifecycle/browser-tests'
    stage.mkdir(parents=True)
    try:
        web = stage / 'Web'
        web.mkdir()
        expected = {}
        for arm in ('baseline', 'candidate'):
            shutil.copytree(extracted / (runtime_prefix + arm) / 'runtime', web / arm)
            expected.update({arm + '/' + name: row for name, row in runtime_files[arm].items()})
        (web / 'fixtures').mkdir()
        fixture = file_bytes(repo / 'experiments/audio-lifecycle/fixtures/silent.swf')
        require(digest(fixture) == fixture_hash, 'Original fixture changed during staging')
        (web / 'fixtures/silent.swf').write_bytes(fixture)
        expected['fixtures/silent.swf'] = {'bytes': len(fixture), 'sha256': fixture_hash}
        for name in EXACT_HELPERS:
            data = file_bytes(helpers / name)
            require(digest(data) == helper_hashes[name], 'Corrected helper changed during staging: ' + name)
            (web / name).write_bytes(data)
            expected[name] = {'bytes': len(data), 'sha256': helper_hashes[name]}
        transformations = []
        for name, replacements in (('observer.mjs', OBSERVER_TRANSFORMS), ('page.mjs', PAGE_TRANSFORMS), ('contracts.mjs', CONTRACT_TRANSFORMS)):
            original = file_bytes(helpers / name)
            require(digest(original) == helper_hashes[name], 'Corrected helper changed during staging: ' + name)
            changed, record = transform(original, replacements,
                                        'experiments/audio-lifecycle/browser-tests/' + name, name)
            (web / name).write_bytes(changed)
            expected[name] = {'bytes': len(changed), 'sha256': digest(changed)}
            transformations.append(record)
        for name in sorted(NATIVE_WEB):
            shutil.copyfile(web_source / name, web / name)
            expected[name] = native_files[name]
        actual = inventory(web)
        # A fresh manifest must not bless input/copy-time drift after verification.
        require(actual == expected, 'Staged bytes differ from already verified input inventories')
        manifest = {'schemaVersion': 1, 'adapterScope': 'canvas-audio-only', 'eventWindowProtocol': 2, 'files': actual, 'sourceBuild': source_build,
                    'browserPrerequisite': browser_prerequisite, 'transformations': transformations}
        payload = json_bytes(manifest)
        (web / 'native-manifest.json').write_bytes(payload)
        swift = ('// Generated only by prerequisite-verified offline staging.\n'
                 'enum NativeAudioIdentity {\n'
                 f'    static let manifestSHA256 = "{digest(payload)}"\n'
                 '}\n')
        (stage / 'NativeAudioIdentity.swift').write_text(swift)
        return manifest, digest(payload)
    except BaseException:
        shutil.rmtree(stage)
        raise


def stage_native(args):
    require(__debug__, 'Do not use Python optimization; upstream verifier uses assertions')
    repo = args.repo_root.resolve()
    require(repo == ROOT, 'Repo root must contain this reviewed staging implementation')
    stage = args.stage.absolute()
    inputs = [args.verified_root, args.browser_results.parent, HERE]
    for source in inputs:
        require(not stage.resolve().is_relative_to(source.resolve()), 'Stage must not overwrite an input tree')
        require(not source.resolve().is_relative_to(stage.resolve()), 'Stage must not contain an input tree')
    lock_path = REUSE / 'build-lock.json'
    lock = strict_json(lock_path)
    validate_build_lock(lock)
    approval = strict_json(args.browser_approval)
    validate_approval(approval, sha(lock_path))
    metadata = {name: strict_json(args.browser_metadata / (name + '.json')) for name in ('run', 'jobs', 'artifact')}
    validate_browser_metadata(metadata['run'], metadata['artifact'], metadata['jobs'], approval)
    inventory(args.verified_root)
    verifier = load_module('audio_native_immutable_build_verify', REUSE / 'verify_artifact.py')
    verifier.verify_current_harness(lock)
    build, _ = verifier.verify_extracted(args.verified_root, lock)
    checked, attachments = validate_browser_receipt(args.browser_results, args.browser_provenance,
                                                    approval, lock, args.verified_root)
    source_build = {key: lock[key] for key in ('repository', 'buildCommit', 'runID', 'artifactID',
                    'artifactSHA256', 'upstreamCommit', 'patchSetSHA256', 'candidateProvenanceSHA256',
                    'baselineProvenanceSHA256', 'baselineIdentitySHA256')}
    source_build['buildLockSHA256'] = sha(lock_path)
    source_build['runtimeRebuilt'] = False
    prerequisite = {'approval': approval, 'approvalSHA256': sha(args.browser_approval),
                    'gate': checked, 'attachments': attachments,
                    'apiSHA256': {name: sha(args.browser_metadata / (name + '.json')) for name in metadata}}
    baseline_provenance = args.verified_root / 'audio-lifecycle-baseline/provenance.json'
    require(sha(baseline_provenance) == lock['baselineProvenanceSHA256'], 'Baseline provenance changed during staging')
    inventories = {'candidate': build['files'], 'baseline': strict_json(baseline_provenance)['files']}
    runtime_files = {arm: {name.removeprefix('runtime/'): row for name, row in rows.items()
                           if name.startswith('runtime/')} for arm, rows in inventories.items()}
    helper_hashes = {name: lock['correctedHarnessSHA256']['experiments/audio-lifecycle/browser-tests/' + name]
                     for name in EXACT_HELPERS + ('observer.mjs', 'page.mjs', 'contracts.mjs')}
    manifest, manifest_hash = stage_web(stage, args.verified_root, repo, source_build, prerequisite,
                                        runtime_files, helper_hashes,
                                        'e25f5dba4162a25b9a07832be4e6f8f62242734f6f39e92983c53467a28e7fd2')
    try:
        project = stage_project(stage, repo)
        evidence = stage / 'prerequisite-evidence'
        evidence.mkdir()
        shutil.copyfile(args.browser_approval, evidence / 'browser-approval.json')
        shutil.copyfile(lock_path, evidence / 'build-lock.json')
        for name in metadata:
            shutil.copyfile(args.browser_metadata / (name + '.json'), evidence / (name + '.json'))
        for path in [args.browser_results, args.browser_provenance] + [args.browser_results.parent / p for p in attachments]:
            shutil.copyfile(path, evidence / path.name)
        for arm in ('baseline', 'candidate'):
            folder = args.verified_root / ('audio-lifecycle-' + arm)
            shutil.copyfile(folder / 'provenance.json', evidence / (arm + '-provenance.json'))
            shutil.copyfile(folder / 'runtime.browser-manifest.json', evidence / (arm + '-browser-manifest.json'))
        result = {'verified': True, 'nativeExecutionPerformed': False, 'runtimeRebuilt': False,
                  'manifestSHA256': manifest_hash, 'stagedFiles': len(manifest['files']),
                  'project': project,
                  'browserPrerequisite': checked, 'scope': 'Offline staging only; native compilation and execution not performed'}
        (stage / 'verification.json').write_bytes(json_bytes(result))
        return result
    except BaseException:
        shutil.rmtree(stage)
        raise


def stage_project(stage, repo):
    """Resolve a JSON-compatible XcodeGen spec in the fresh staging directory.

    Source files use verified absolute paths inside this checkout. Generated
    identity, Web resources, plist and project remain together inside stage.
    There is no --project relocation and no dependency on the caller's cwd.
    """
    stage, repo = Path(stage).resolve(), Path(repo).resolve()
    require(stage.is_relative_to(repo), 'Native project stage must remain inside checkout')
    template = strict_json(HERE / 'project.yml')
    require(template['name'] == 'NativeAudioLifecycle', 'Unexpected project template')
    targets = template['targets']
    require(set(targets) == {'NativeAudioLifecycle', 'NativeAudioLifecycleUITests'}, 'Unexpected native targets')
    app, ui = targets['NativeAudioLifecycle'], targets['NativeAudioLifecycleUITests']
    require(app['sources'] == [
        {'path': 'Host', 'excludes': ['Info.plist']},
        '../../../App/Server/LoopbackServer.swift', '../../../App/Server/HTTPProtocol.swift',
        '../../../audio-native-stage/NativeAudioIdentity.swift',
        {'path': '../../../audio-native-stage/Web', 'type': 'folder', 'buildPhase': 'resources'},
    ], 'Unexpected source template')
    require(ui['sources'] == ['UITests'] and app['info']['path'] == '../../../audio-native-stage/Info.plist',
            'Unexpected UI/plist template')
    source_names = [
        'experiments/audio-lifecycle/native/Host/NativeAudioHost.swift',
        'experiments/audio-lifecycle/native/UITests/NativeAudioLifecycleUITests.swift',
        'App/Server/LoopbackServer.swift', 'App/Server/HTTPProtocol.swift',
    ]
    source_files = {}
    for relative in source_names:
        path = repo / relative
        require(path.resolve().is_relative_to(repo) and not path.is_symlink(), 'Source escaped checkout')
        data = file_bytes(path)
        source_files[relative] = {'bytes': len(data), 'sha256': digest(data)}
    require(set((repo / 'experiments/audio-lifecycle/native/Host').iterdir()) ==
            {repo / source_names[0]}, 'Unlisted host source')
    require(set((repo / 'experiments/audio-lifecycle/native/UITests').iterdir()) ==
            {repo / source_names[1]}, 'Unlisted UI source')
    require((stage / 'NativeAudioIdentity.swift').is_file() and (stage / 'Web').is_dir(), 'Missing verified staged resources')
    app['sources'] = [str(repo / source_names[0]), str(repo / source_names[2]), str(repo / source_names[3]),
                      'NativeAudioIdentity.swift', {'path': 'Web', 'type': 'folder', 'buildPhase': 'resources'}]
    ui['sources'] = [str(repo / source_names[1])]
    app['info']['path'] = 'Info.plist'
    payload = json_bytes(template)
    destination = stage / 'project.yml'
    require(not destination.exists(), 'Refusing generated project spec overwrite')
    destination.write_bytes(payload)
    return {'specSHA256': digest(payload), 'sourceFiles': source_files,
            'sourceRoot': 'verified-checkout-absolute', 'generatedRoot': 'native-stage',
            'relocatedProject': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('verified-root', 'browser-results', 'browser-provenance', 'browser-approval',
                 'browser-metadata', 'stage', 'repo-root'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(stage_native(args), indent=2))
    except (AssertionError, ValueError, KeyError, TypeError, OSError) as error:
        parser.exit(1, f'Native staging refused: {type(error).__name__}: {error}\n')


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Strict unsigned experimental IPA verifier; prior native evidence is never relabelled."""
import argparse
import importlib.util
import json
import os
import plistlib
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
import experiment as e
import verify_native_reference as reference

IPA_NAME = 'FlashNest-1.5.6-build23-case-compatible-diagnostic-v2-import-warning-unsigned.ipa'
INFO = {'CFBundleIdentifier': 'com.flashnest.app', 'CFBundleShortVersionString': '1.5.6',
        'CFBundleVersion': '23', 'DTPlatformName': 'iphoneos', 'CFBundleExecutable': 'FlashNest',
        'MinimumOSVersion': '17.0', 'DTSDKName': 'iphoneos18.2'}

def load_checks(baseline, x):
    root = baseline / 'experiments/release-ipa-156-build22'
    e.need(e.inventory(root) == x['releaseRecipeFiles'], 'Frozen release validators differ')
    path = root / 'package_checks.py'
    name = 'case_ipa_frozen_package_checks'
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

def verify_focused(path_evidence, fps_evidence, config, x):
    path_raw = path_evidence.read_bytes(); path = json.loads(path_raw)
    fixture_source = (e.ROOT / 'path-tests/CaseCompatibilityFixture.swift').read_text()
    names = re.findall(r'try check\("([^"\n]+)"', fixture_source)
    e.need(len(names) == len(set(names)) == 18, 'Reviewed path test inventory differs')
    e.need(path.get('schema') == 'flashnest-casecompat-native-v1'
           and path.get('passed') is True and path.get('caseSensitiveFilesystemVerified') is True,
           'Actual case-sensitive path tests not passed')
    e.need(type(path.get('count')) is int and path['count'] == 18 and path.get('tests') == names,
           'Actual path test names/counts differ')
    volume = plistlib.loads((path_evidence.parent / 'native-volume.plist').read_bytes())
    e.need(volume.get('FilesystemName') == 'Case-sensitive APFS'
           and volume.get('FilesystemType') == 'apfs', 'Case-sensitive filesystem evidence differs')
    raw = fps_evidence.read_bytes(); fps = json.loads(raw)
    e.need(fps.get('schema') == 'neutral-frame-cadence-v1' and fps.get('passed') is True,
           'Actual cadence tests not passed')
    e.need(fps.get('runtimeFiles') == x['runtimeFiles'] and fps.get('inputsSHA256') == config['baselineInputsSHA256'],
           'Cadence runtime/source inputs differ')
    for name in ('make_fixture.py', 'probe.html', 'run_fps.py'):
        digest = e.sha((e.ROOT / 'fps' / name).read_bytes())
        e.need(fps.get('sourceFiles', {}).get(name) == digest
               and config['recipeFiles'].get('fps/' + name) == digest, 'Cadence test source differs')
    spec = importlib.util.spec_from_file_location('case_ipa_neutral_fixture', e.ROOT / 'fps/make_fixture.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    generated = module.make_swf()
    e.need(fps.get('fixtureBytes') == len(generated) and fps.get('fixtureSHA256') == e.sha(generated),
           'Actual neutral fixture differs')
    sandbox = fps.get('sandbox', {})
    e.need(sandbox.get('requested') is True and sandbox.get('forbiddenFlagsAbsent') is True
           and sandbox.get('requestedChannel') == 'chrome', 'Sandbox/browser evidence differs')
    arguments = sandbox.get('effectiveCommandLine')
    forbidden = {'--no-sandbox', '--disable-setuid-sandbox', '--disable-gpu-sandbox', '--enable-unsafe-swiftshader'}
    e.need(isinstance(arguments, list) and arguments and all(isinstance(a, str) for a in arguments)
           and not any(a.split('=')[0] in forbidden for a in arguments), 'Forbidden browser flags')
    rows = fps.get('rows', [])
    e.need(len(rows) == 5, 'Incomplete cadence matrix')
    for index, row in enumerate(rows):
        e.need(row.get('passed') is True and row.get('actualRenderer') in ('webgl', 'webgl2', 'experimental-webgl')
               and row.get('physicalGPUCertified') is False, 'Invalid renderer/acceptance evidence')
        e.need(row.get('metadata', {}).get('frameRate') == 24, 'Wrong original SWF frame rate')
        fetched = row.get('wasmResponses', [])
        e.need(fetched and all(w.get('name', '').endswith('.wasm')
               and x['runtimeFiles'].get(w.get('name')) == w.get('sha256') for w in fetched), 'Actual WASM differs')
        if index < 3:
            target = (24, 24, 48)[index]
            e.need(row.get('scheduler') == 'real-browser-wallclock' and row.get('override') == (None, 24, 48)[index]
                   and row.get('expectedFPS') == target, 'Wrong cadence wall-clock arm')
            seconds = row.get('seconds'); frames = row.get('frames'); rate = row.get('observedFPS')
            e.need(type(seconds) in (float, int) and seconds >= 4 and type(frames) is int and frames > 0
                   and type(rate) in (float, int) and abs(rate - frames / seconds) < 1e-8
                   and abs(rate - target) < target * 0.18, 'Cadence measurement/threshold mismatch')
        else:
            seconds = row.get('virtualSeconds'); frames = row.get('frames')
            e.need(row.get('scheduler') == 'synthetic-RAF-timestamps' and row.get('syntheticHz') == (60, 120)[index - 3]
                   and row.get('physicalDisplayTest') is False and row.get('expectedFPS') == 24,
                   'Synthetic timing mislabeled')
            e.need(type(seconds) in (float, int) and abs(seconds - 10) < 1e-6 and type(frames) is int
                   and abs(frames - 24 * seconds) <= 2, 'Synthetic cadence count mismatch')
    e.need(1.65 < rows[2]['observedFPS'] / rows[0]['observedFPS'] < 2.35, 'Cadence control not sensitive')
    e.need(fps.get('productFrameRateChanged') is False and fps.get('privateGameInputs') is False,
           'Unexpected cadence source/product scope')
    return {'pathEvidenceSHA256': e.sha(path_raw), 'path': path,
            'volumeEvidenceSHA256': e.sha((path_evidence.parent / 'native-volume.plist').read_bytes()),
            'fpsEvidenceSHA256': e.sha(raw), 'fps': fps}

def verify(ipa, app, stage_receipt, native_reference, baseline, output, native_archive, path_evidence, fps_evidence):
    e.need(ipa.is_file() and not ipa.is_symlink(), 'Regular non-symlink IPA input required')
    ipa = ipa.resolve(); app = app.resolve(); baseline = baseline.resolve()
    stage_receipt = stage_receipt.resolve(); native_reference = native_reference.resolve()
    native_archive = native_archive.resolve()
    config = e.config()
    e.need(config.get('ipaBuildAllowed') is True and config.get('runtimeChanged') is False,
           'Experimental IPA build not authorized by this recipe')
    e.need(ipa.name == IPA_NAME and ipa.is_file() and not ipa.is_symlink(), 'Wrong experimental IPA name/type')
    head = os.environ.get('GITHUB_SHA'); run = os.environ.get('GITHUB_RUN_ID')
    e.need(isinstance(head, str) and re.fullmatch(r'[0-9a-f]{40}', head) is not None
           and isinstance(run, str) and run.isdigit(), 'Current CI identity missing')
    e.need(subprocess.check_output(['git', '-C', str(baseline), 'rev-parse', 'HEAD'], text=True).strip() == e.BASE,
           'Wrong immutable baseline checkout')
    xraw = (baseline / e.RECIPE / 'inputs.json').read_bytes()
    e.need(e.sha(xraw) == config['baselineInputsSHA256'], 'Baseline manifest differs')
    x = json.loads(xraw)
    checks = load_checks(baseline, x)
    focused = verify_focused(path_evidence, fps_evidence, config, x)
    stage_raw = stage_receipt.read_bytes(); stage = checks.parse(stage_raw)
    original = dict(x['baselineAppFiles']); original.update({p: row['after'] for p, row in x['overlay'].items()})
    expected = dict(original)
    for name, row in config['overlay'].items():
        e.need(expected[name] == row['before'], 'Unexpected prior source identity')
        expected[name] = row['after']
    e.need(stage.get('head') == head and stage.get('runID') == run, 'Current staging run differs')
    e.need(stage.get('baselineCommit') == e.BASE and stage.get('sourceCommit') == e.SOURCE,
           'Current staging lineage differs')
    e.need(stage.get('baselineSourceFiles') == original and stage.get('effectiveSourceFiles') == expected,
           'Candidate source inventory differs')
    e.need(stage.get('overlay') == config['overlay'] and stage.get('recipeFiles') == config['recipeFiles'],
           'Current staged recipe differs')
    e.need(stage.get('runtimeFiles') == x['runtimeFiles'] and len(x['runtimeFiles']) == 12,
           'Runtime inventory changed')
    for flag in ('diagnosticOptInDefault', 'runtimeChanged', 'ipaBuilt', 'fullGatePassed',
                 'physicalDeviceCertified', 'speedRootCauseEstablished'):
        e.need(stage.get(flag) is False, 'Incorrect pre-build staging claim: ' + flag)
    e.verify(app, expected)
    checks.verify_sources(app, expected)
    # Recompute the prior execution proof from the actual hash-pinned ZIP. A JSON
    # receipt alone must never authorize packaging or masquerade as new execution.
    native_raw = native_reference.read_bytes()
    with tempfile.TemporaryDirectory() as temp:
        recomputed_path = Path(temp) / 'recomputed-native-reference.json'
        reference.verify(native_archive, app, stage_receipt, baseline, recomputed_path)
        native = checks.parse(native_raw)
        e.need(native == checks.load(recomputed_path), 'Native reference receipt does not match actual archive')
    e.need(native.get('nativeExecutedThisRun') is False and native.get('nativeEvidenceVerified') is True,
           'Prior native execution incorrectly classified')
    e.need(native.get('reference') == reference.PIN and native.get('effectiveSourceFiles') == expected
           and native.get('runtimeFiles') == x['runtimeFiles'], 'Native source/runtime reference differs')
    e.need(native.get('head') == head and native.get('runID') == run, 'Native proof belongs to another packaging run')
    # The generated source Info.plist is allowed only by experiment.verify's exact
    # build23 normalized hash. Compiled outer payload fields are checked separately.
    e.need((app / 'App/Info.plist').is_file(), 'Generated Release Info source missing')
    ipa_raw = ipa.read_bytes()
    with tempfile.TemporaryDirectory() as temp:
        with zipfile.ZipFile(ipa) as z:
            checks.safe_ipa_members(z.infolist())
            e.need(z.testzip() is None, 'IPA CRC failure')
            z.extractall(temp)
        bundle = Path(temp) / 'Payload/FlashNest.app'
        outer = checks.verify_outer_payload(bundle)
        info = plistlib.loads((bundle / 'Info.plist').read_bytes())
        for key, value in INFO.items():
            e.need(info.get(key) == value, 'Actual packaged identity differs: ' + key)
        executable = (bundle / 'FlashNest').read_bytes()
        macho = checks.device_macho(executable)
        e.need(b'--flashnest-import-size-warning-ui-test' not in executable,
               'DEBUG import confirmation harness present in Release executable')
        web = checks.file_map(bundle / 'Web')
        e.need(web == checks.file_map(app / 'App/Resources/Web'), 'Complete packaged Web bytes differ')
        e.need(checks.file_map(bundle / 'Web/runtime') == x['runtimeFiles'], 'Packaged runtime differs')
        observer = (bundle / 'Web/long-run-diagnostics.js').read_text()
        e.need("type: 'longRunDiagnostics', schema: 2" in observer, 'Packaged observer schema differs')
        diagnostics = (app / 'App/Player/LongRunDiagnostics.swift').read_text()
        e.need('diagnosticSchema: 2, observerRevision: 2' in diagnostics
               and 'CFBundleShortVersionString' in diagnostics and 'CFBundleVersion' in diagnostics,
               'Native diagnostic identity/schema source differs')
        # safe_ipa_members rejects fixtures, SWFs, saves, test bundles, signatures,
        # provisioning profiles and unsafe roots; exact outer/Web allowlists close
        # the remaining packaged-resource namespace.
        payload = checks.file_map(bundle)
    e.verify(app, expected)
    e.need(stage_receipt.read_bytes() == stage_raw and native_reference.read_bytes() == native_raw,
           'Proof changed while packaging')
    e.need(ipa.read_bytes() == ipa_raw, 'IPA changed while verifying')
    result = {'schemaVersion': 1, 'kind': 'EXPERIMENTAL-CASE-COMPATIBLE-TEST-IPA',
        'packageRevision': 'case-compatible-diagnostic-v2-import-warning',
        'version': '1.5.6', 'build': '23', 'bundleID': 'com.flashnest.app',
        'unsigned': True, 'ipaBuilt': True, 'ipaFilename': ipa.name,
        'ipaSHA256': e.sha(ipa_raw), 'ipaBytes': len(ipa_raw),
        'packagingCommit': head, 'packagingRunID': run,
        'baselineCommit': e.BASE, 'frozenSourceCommit': e.SOURCE,
        'stageReceiptSHA256': e.sha(stage_raw), 'nativeReferenceReceiptSHA256': e.sha(native_raw),
        'nativeExecutedThisRun': False, 'nativeEvidenceReference': native, 'currentFocusedEvidence': focused,
        'appSourceFiles': expected, 'runtimeFiles': x['runtimeFiles'], 'webFiles': web,
        'packagedBundleFiles': payload, 'outerPayloadFiles': sorted(outer),
        'deviceExecutable': macho, 'observerRevision': 2, 'diagnosticSchema': 2,
        'diagnosticOptInDefault': False, 'automaticUpload': False, 'runtimeChanged': False,
        'productFrameRateChanged': False, 'originalCrashResolved': False,
        'gameLoadingIssueResolved': False, 'speedRootCauseEstablished': False,
        'fullGatePassed': False, 'physicalDeviceCertified': False, 'formalRelease': False}
    e.write(output, result)
    print('Verified unsigned arm64 build23 experimental IPA; prior native evidence reused, not re-executed')

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    for name in ('ipa', 'app', 'stage-receipt', 'native-reference', 'baseline-checkout', 'output', 'native-archive', 'path-evidence', 'fps-evidence'):
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args()
    verify(a.ipa, a.app, a.stage_receipt, a.native_reference, a.baseline_checkout, a.output, a.native_archive, a.path_evidence, a.fps_evidence)
